import logging
import time
from typing import Dict, Any, List, Literal, Annotated
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import Command, interrupt


from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.services.memory_service import get_memory_service

logger = logging.getLogger(__name__)

# === FUNCIONES AUXILIARES ===

def get_thread_id_from_state(state: PYMESState) -> str:
    """Extrae thread_id del estado."""
    # Intentar obtener de diferentes fuentes
    thread_id = state.get("thread_id")
    
    if not thread_id:
        messages = state.get("messages", [])
        for msg in messages:
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('thread_id'):
                return msg.additional_kwargs['thread_id']
    
    return thread_id or f"temp_{int(time.time())}"

def extract_business_info_from_conversation(messages: List, current_state: PYMESState) -> Dict[str, Any]:
    """Extrae información del negocio de la conversación actual."""
    try:
        # Obtener información existente
        existing_info = current_state.get("business_info", {})
        
        # Buscar información en los mensajes más recientes
        recent_content = ""
        for msg in messages[-3:]:  # Últimos 3 mensajes
            if isinstance(msg, HumanMessage):
                recent_content += f"Usuario: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                recent_content += f"Asistente: {msg.content}\n"
        
        # Lógica simple de extracción (en producción usarías un LLM con structured output)
        updated_info = existing_info.copy()
        
        # Extraer nombre de empresa
        if not updated_info.get("nombre_empresa"):
            if "empresa" in recent_content.lower() or "negocio" in recent_content.lower():
                lines = recent_content.split('\n')
                for line in lines:
                    if any(keyword in line.lower() for keyword in ["empresa", "negocio", "llamo", "llama"]):
                        # Lógica simple de extracción
                        words = line.split()
                        if len(words) > 2:
                            updated_info["nombre_empresa"] = ' '.join(words[2:5])  # Tomar algunas palabras
                        break
        
        # Extraer sector
        if not updated_info.get("sector"):
            sector_keywords = ["restaurante", "software", "retail", "construcción", "salud", "educación"]
            for keyword in sector_keywords:
                if keyword in recent_content.lower():
                    updated_info["sector"] = keyword.capitalize()
                    break
        
        # Solo retornar si hay información nueva
        if updated_info != existing_info:
            return updated_info
        
        return None
        
    except Exception as e:
        logger.error(f"Error extrayendo información del negocio: {str(e)}")
        return None

def extract_research_from_messages(messages: List) -> str:
    """Extrae contenido de investigación de los mensajes."""
    try:
        research_content = ""
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content
                # Buscar indicadores de investigación
                if any(keyword in content.lower() for keyword in ["investigación", "análisis", "oportunidades", "tendencias", "mercado"]):
                    research_content += content + "\n"
        
        return research_content.strip() if research_content else None
        
    except Exception as e:
        logger.error(f"Error extrayendo investigación: {str(e)}")
        return None

# === HERRAMIENTAS DE HANDOFF ENTRE AGENTES ===

def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """Crea una herramienta de handoff siguiendo el patrón LangGraph."""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transfer control to {agent_name} agent."

    @tool(name, description=description)
    def handoff_tool(
        task_description: Annotated[
            str,
            "Description of what the next agent should do, including all relevant context.",
        ],
        state: Annotated[PYMESState, InjectedState],
    ) -> Command:
        """Execute handoff to the specified agent."""
        # Create task message for the next agent
        task_message = AIMessage(content=f"Transferring to {agent_name}: {task_description}")
        
        return Command(
            goto=agent_name,
            update={
                "messages": [task_message],
                "current_agent": agent_name,
                "last_handoff": task_description
            }
        )
    
    return handoff_tool

# Crear herramientas de handoff específicas
transfer_to_info_extractor = create_handoff_tool(
    agent_name="info_extractor",
    description="Transfer to the business information extraction specialist when you need to collect or update basic company data."
)

transfer_to_researcher = create_handoff_tool(
    agent_name="researcher", 
    description="Transfer to the market research specialist when you need to analyze market opportunities, trends, or competitive research."
)

transfer_to_consultant = create_handoff_tool(
    agent_name="consultant",
    description="Transfer to the conversational consultant for general questions, specific doubts, or fluid business conversation."
)

@tool
def get_business_info_status():
    """Verificar el estado actual de la información del negocio recopilada."""
    # Esta herramienta checkeará el estado actual
    return "Información del negocio: En progreso/Completa/Faltante"

@tool
def get_research_status():
    """Verificar si ya se ha realizado investigación de mercado para este negocio."""
    return "Investigación: No iniciada/En progreso/Completada"

# === PROMPTS PARA CADA AGENTE ===

SUPERVISOR_PROMPT = """
Eres el SUPERVISOR de un equipo de consultores especializados en PYMES. Tu trabajo es coordinar y dirigir las conversaciones hacia el agente correcto.

AGENTES DISPONIBLES:
1. **info_extractor**: Especialista en recopilar información básica del negocio (nombre, sector, productos, desafíos, ubicación, etc.)
2. **researcher**: Especialista en investigación de mercado, análisis de oportunidades y tendencias del sector
3. **consultant**: Consultor conversacional para dudas específicas, preguntas generales y asesoramiento personalizado

ESTADO ACTUAL:
- Información del negocio: {business_info_status}
- Investigación realizada: {research_status}

REGLAS DE DECISIÓN:
1. Si NO hay información básica del negocio → **transfer_to_info_extractor**
2. Si hay información básica pero NO hay investigación → **transfer_to_researcher** 
3. Si el usuario hace preguntas específicas o quiere conversar → **transfer_to_consultant**
4. Si el usuario quiere actualizar/corregir información → **transfer_to_info_extractor**
5. Si el usuario quiere nueva investigación → **transfer_to_researcher**

Analiza el mensaje del usuario y el estado actual, luego transfiere al agente apropiado.
NO intentes responder directamente - siempre transfiere a un especialista.
"""

INFO_EXTRACTOR_PROMPT = """
Eres un ESPECIALISTA EN RECOPILACIÓN DE INFORMACIÓN EMPRESARIAL para PYMES.

Tu trabajo es recopilar de manera conversacional y amigable la siguiente información:

INFORMACIÓN REQUERIDA:
- 🏢 **Nombre de la empresa**
- 🏭 **Sector/Industria** (ej: "Restaurantes", "Software", "Retail")
- 💼 **Productos/Servicios principales** 
- ⚠️ **Desafíos principales** del negocio
- 📍 **Ubicación** de operación
- 📝 **Descripción** del negocio

INFORMACIÓN OPCIONAL:
- Años de operación
- Número de empleados

INSTRUCCIONES:
- Haz UNA pregunta específica a la vez
- Sé conversacional y empático
- Confirma información antes de continuar
- Usa ejemplos para ayudar al usuario
- Cuando tengas TODA la información requerida, usa **transfer_to_researcher**

HERRAMIENTAS DISPONIBLES:
- transfer_to_researcher: Cuando tengas información completa
- transfer_to_consultant: Si el usuario tiene dudas no relacionadas con datos básicos
"""

RESEARCHER_PROMPT = """
Eres un ESPECIALISTA EN INVESTIGACIÓN DE MERCADO Y OPORTUNIDADES para PYMES.

Tu trabajo es:
1. Analizar la información del negocio disponible
2. Realizar investigación web específica sobre:
   - Tendencias del sector
   - Oportunidades de mercado
   - Mejores prácticas
   - Análisis competitivo
   - Soluciones a desafíos identificados
3. Presentar análisis y recomendaciones estructuradas

HERRAMIENTAS DISPONIBLES:
- search: Búsqueda web para investigación de mercado
- transfer_to_consultant: Para conversación sobre los resultados
- transfer_to_info_extractor: Si necesitas más información del negocio

Cuando presentes resultados, sé específico y práctico. Pregunta al usuario si quiere profundizar en algún área específica.
"""

CONSULTANT_PROMPT = """
Eres un CONSULTOR CONVERSACIONAL especializado en PYMES.

Tu trabajo es:
- Responder preguntas específicas sobre el negocio
- Brindar asesoramiento personalizado
- Aclarar dudas sobre recomendaciones
- Mantener conversación fluida y útil
- Generar planes de acción detallados

HERRAMIENTAS DISPONIBLES:
- search: Búsqueda web para información específica
- search_documents: Búsqueda en documentos internos
- transfer_to_info_extractor: Si necesitas actualizar información básica
- transfer_to_researcher: Si necesitas nueva investigación

Eres empático, práctico y orientado a resultados. Siempre busca ser útil y accionable.
"""

# === FUNCIONES DE ESTADO ===

def get_business_info_status_from_state(state: PYMESState) -> str:
    """Obtiene el estado actual de la información del negocio."""
    business_info = state.get("business_info", {})
    required_fields = ["nombre_empresa", "sector", "productos_servicios_principales", "ubicacion"]
    
    if not business_info:
        return "No iniciada"
    
    missing_fields = [field for field in required_fields if not business_info.get(field)]
    
    if not missing_fields:
        return "Completa"
    elif len(missing_fields) < len(required_fields):
        return "Parcial"
    else:
        return "Faltante"

def get_research_status_from_state(state: PYMESState) -> str:
    """Obtiene el estado actual de la investigación."""
    context = state.get("context", "")
    web_search = state.get("web_search", "")
    stage = state.get("stage", "")
    
    if stage == "research_completed" or context or web_search:
        return "Completada"
    elif stage == "research_in_progress":
        return "En progreso"
    else:
        return "No iniciada"

# === NODOS DE AGENTES ===

def supervisor_node(state: PYMESState) -> Dict[str, Any]:
    """Nodo supervisor que decide qué agente usar usando handoffs."""
    try:
        logger.info("Supervisor analizando situación...")
        
        business_info_status = get_business_info_status_from_state(state)
        research_status = get_research_status_from_state(state)
        
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        user_message = last_message.content if isinstance(last_message, HumanMessage) else ""
        
        # Lógica de decisión del supervisor (sin LLM para simplicidad)
        logger.info(f"Estado info: {business_info_status}, investigación: {research_status}")
        
        # Decisiones basadas en reglas claras
        if business_info_status in ["No iniciada", "Faltante", "Parcial"]:
            agent_target = "info_extractor"
            task_desc = "Recopilar información básica del negocio que falta"
        elif business_info_status == "Completa" and research_status == "No iniciada":
            agent_target = "researcher"
            task_desc = "Realizar investigación de mercado basada en la información del negocio"
        else:
            agent_target = "consultant"
            task_desc = "Proporcionar asesoramiento conversacional"
        
        logger.info(f"Supervisor decidió: {agent_target} - {task_desc}")
        
        # Usar Command para handoff
        return {
            "current_agent": agent_target,
            "last_handoff": task_desc,
            "messages": [AIMessage(content=f"Transfiriendo a {agent_target}: {task_desc}")]
        }
        
    except Exception as e:
        logger.error(f"Error en supervisor_node: {str(e)}")
        # Fallback: ir al consultor si hay error
        return {
            "current_agent": "consultant",
            "messages": [AIMessage(content="Error en supervisor, transfiriendo al consultor...")]
        }

@tool
def save_business_info(info: str):
    """Guardar información del negocio extraída en memoria a largo plazo."""
    try:
        # Esta herramienta simula el guardado - en realidad se manejará en el nodo
        logger.info(f"Guardando información del negocio: {info}")
        return "Información guardada exitosamente en memoria a largo plazo"
    except Exception as e:
        logger.error(f"Error guardando información: {str(e)}")
        return "Error guardando información"

def info_extractor_agent_node(state: PYMESState) -> Dict[str, Any]:
    """Agente especializado en extracción de información del negocio."""
    try:
        logger.info("Agente extractor de información activado")
        
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        
        # Obtener información actual del negocio
        business_info = state.get("business_info", {})
        messages = state.get("messages", [])
        
        # Extraer nueva información de los mensajes recientes
        updated_info = extract_business_info_from_conversation(messages, state) or business_info
        
        # Determinar qué información falta
        required_fields = ["nombre_empresa", "sector", "productos_servicios_principales", "ubicacion"]
        missing_fields = [field for field in required_fields if not updated_info.get(field)]
        
        # Generar pregunta específica o completar si ya tenemos todo
        if missing_fields:
            # Generar pregunta para el primer campo faltante
            field = missing_fields[0]
            field_questions = {
                "nombre_empresa": "¿Cuál es el nombre de tu empresa o negocio?",
                "sector": "¿En qué sector o industria opera tu negocio? (por ejemplo: restaurantes, software, retail, etc.)",
                "productos_servicios_principales": "¿Cuáles son los principales productos o servicios que ofreces?",
                "ubicacion": "¿Dónde opera tu negocio? (ciudad, país, o si es online)"
            }
            
            question = field_questions.get(field, "¿Podrías proporcionar más información sobre tu negocio?")
            
            return {
                "messages": [AIMessage(content=question)],
                "current_agent": "info_extractor",  # Permanecer en este agente
                "business_info": updated_info,  # Guardar info actualizada
                "stage": "info_gathering"
            }
        else:
            # Información completa, transferir al investigador
            logger.info("Información del negocio completa, transfiriendo al investigador")
            
            # Guardar en memoria
            memory_service = get_memory_service()
            thread_id = get_thread_id_from_state(state)
            memory_service.save_business_info(thread_id, updated_info)
            
            return {
                "messages": [AIMessage(content="¡Perfecto! He recopilado toda la información de tu negocio. Ahora voy a investigar oportunidades específicas para tu empresa.")],
                "current_agent": "researcher",  # Handoff al investigador
                "last_handoff": "Información completa, iniciar investigación de mercado",
                "business_info": updated_info,
                "stage": "info_completed"
            }
        
    except Exception as e:
        logger.error(f"Error en info_extractor_agent_node: {str(e)}")
        return {"messages": [AIMessage(content="Hubo un error. ¿Podrías repetir tu información?")]}

@tool
def save_research_results(results: str):
    """Guardar resultados de investigación en memoria a largo plazo."""
    try:
        logger.info(f"Guardando resultados de investigación: {results[:100]}...")
        return "Resultados de investigación guardados exitosamente"
    except Exception as e:
        logger.error(f"Error guardando investigación: {str(e)}")
        return "Error guardando resultados"

def researcher_agent_node(state: PYMESState):
    """Agente especializado en investigación de mercado."""
    try:
        logger.info("Agente investigador activado")
        
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        
        # Herramientas para el investigador
        from app.graph.nodes import search  # Importar herramienta de búsqueda existente
        researcher_tools = [search, transfer_to_consultant, transfer_to_info_extractor, save_research_results]
        
        # Crear agente ReAct con información del negocio en el prompt
        business_info = state.get("business_info", {})
        enhanced_prompt = RESEARCHER_PROMPT
        
        if business_info:
            business_context = f"\n\nINFORMACIÓN DEL NEGOCIO DISPONIBLE:\n{business_info}\n\nUsa esta información para generar investigación específica y relevante."
            enhanced_prompt += business_context
        
        # Crear agente ReAct
        agent = create_react_agent(llm, researcher_tools, state_modifier=enhanced_prompt)
        
        # Ejecutar agente
        result = agent.invoke(state)
        
        # Guardar resultados de investigación si se generaron
        messages = result["messages"]
        research_content = extract_research_from_messages(messages)
        
        if research_content:
            memory_service = get_memory_service()
            thread_id = get_thread_id_from_state(state)
            memory_service.save_research_results(thread_id, {"content": research_content, "timestamp": time.time()})
            
            return {
                "messages": result["messages"],
                "context": research_content,
                "web_search": "Investigación completada",
                "stage": "research_completed"
            }
        
        return {"messages": result["messages"]}
        
    except Exception as e:
        logger.error(f"Error en researcher_agent_node: {str(e)}")
        return {"messages": [AIMessage(content="Hubo un error en la investigación. Intentemos de nuevo.")]}

def consultant_agent_node(state: PYMESState):
    """Agente consultor conversacional (el chatbot original)."""
    try:
        logger.info("Agente consultor conversacional activado")
        
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        
        # Herramientas para el consultor
        from app.graph.nodes import search, search_documents
        consultant_tools = [search, search_documents, transfer_to_info_extractor, transfer_to_researcher]
        
        # Crear agente ReAct
        agent = create_react_agent(llm, consultant_tools, state_modifier=CONSULTANT_PROMPT)
        
        # Ejecutar agente
        result = agent.invoke(state)
        
        return {"messages": result["messages"]}
        
    except Exception as e:
        logger.error(f"Error en consultant_agent_node: {str(e)}")
        return {"messages": [AIMessage(content="Hubo un error. ¿En qué puedo ayudarte?")]}

def human_feedback_node(state: PYMESState):
    """Nodo de feedback humano mejorado para la arquitectura supervisor."""
    try:
        logger.info("Esperando feedback del usuario...")
        
        # Interrupt para esperar input del usuario
        user_input = interrupt({
            "message": "Esperando tu respuesta...",
            "status": "waiting_for_input"
        })
        
        logger.info(f"Feedback recibido: {user_input}")
        
        # Actualizar estado con el nuevo mensaje del usuario
        return {
            "messages": [HumanMessage(content=user_input)],
            "input": user_input
        }
        
    except Exception as e:
        logger.error(f"Error en human_feedback_node: {str(e)}")
        return {"messages": [HumanMessage(content="Error procesando entrada")]}

# === FUNCIONES DE ENRUTAMIENTO ===

def route_after_supervisor(state: PYMESState) -> Literal["info_extractor", "researcher", "consultant", "human_feedback"]:
    """Enruta después del supervisor basado en la decisión de transferencia."""
    # Verificar si hay un agente especificado en el estado
    current_agent = state.get("current_agent")
    if current_agent in ["info_extractor", "researcher", "consultant"]:
        return current_agent
    
    # Fallback: analizar mensajes para tool calls
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        tool_name = tool_call["name"]
        
        if tool_name == "transfer_to_info_extractor":
            return "info_extractor"
        elif tool_name == "transfer_to_researcher":
            return "researcher"  
        elif tool_name == "transfer_to_consultant":
            return "consultant"
    
    # Por defecto, ir a feedback humano
    return "human_feedback"

def route_after_agents(state: PYMESState) -> Literal["supervisor", "human_feedback"]:
    """Enruta después de los agentes especializados."""
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    # Si hay una transferencia pendiente, volver al supervisor
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        if tool_call["name"].startswith("transfer_to_"):
            return "supervisor"
    
    # Si no hay transferencia, ir a feedback humano
    return "human_feedback"

def create_supervisor_pymes_graph():
    """
    Crea el grafo principal con arquitectura supervisor.
    """
    try:
        logger.info("Creando grafo supervisor PYMES...")
        
        # Crear el grafo
        workflow = StateGraph(PYMESState)
        
        # === AGREGAR NODOS ===
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("info_extractor", info_extractor_agent_node)
        workflow.add_node("researcher", researcher_agent_node)
        workflow.add_node("consultant", consultant_agent_node)
        workflow.add_node("human_feedback", human_feedback_node)
        
        # === DEFINIR FLUJO ===
        
        # Inicio -> Supervisor
        workflow.add_edge(START, "supervisor")
        
        # Supervisor -> Agentes especializados o feedback
        workflow.add_conditional_edges(
            "supervisor",
            route_after_supervisor,
            {
                "info_extractor": "info_extractor",
                "researcher": "researcher", 
                "consultant": "consultant",
                "human_feedback": "human_feedback"
            }
        )
        
        # Agentes -> Supervisor o feedback humano
        workflow.add_conditional_edges(
            "info_extractor",
            route_after_agents,
            {
                "supervisor": "supervisor",
                "human_feedback": "human_feedback"
            }
        )
        
        workflow.add_conditional_edges(
            "researcher", 
            route_after_agents,
            {
                "supervisor": "supervisor",
                "human_feedback": "human_feedback"
            }
        )
        
        workflow.add_conditional_edges(
            "consultant",
            route_after_agents, 
            {
                "supervisor": "supervisor", 
                "human_feedback": "human_feedback"
            }
        )
        
        # Feedback humano -> Supervisor (para nueva decisión)
        workflow.add_edge("human_feedback", "supervisor")
        
        # === COMPILAR ===
        from app.database.postgres import get_postgres_saver, get_postgres_store
        
        store = get_postgres_store()
        checkpointer = get_postgres_saver()
        
        compiled_graph = workflow.compile(
            checkpointer=checkpointer,
            store=store
        )
        
        logger.info("Grafo supervisor PYMES compilado exitosamente")
        return compiled_graph
        
    except Exception as e:
        logger.error(f"Error creando grafo supervisor: {str(e)}")
        raise

# Función de compatibilidad
def create_chat_graph():
    """Función de compatibilidad que devuelve el nuevo grafo supervisor."""
    return create_supervisor_pymes_graph() 