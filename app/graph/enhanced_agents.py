"""
Agentes especializados mejorados que usan handoffs y Command.
Implementa las mejores prácticas de LangGraph para comunicación entre agentes.
"""

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.services.business_info_manager import get_business_info_manager
from app.graph.handoff_system import get_handoff_tools_for_agent

logger = logging.getLogger(__name__)

# === AGENTES CON HANDOFFS ===

def create_enhanced_info_completion_agent():
    """Crea agente de recopilación de información con capacidades de handoff."""
    
    handoff_tools = get_handoff_tools_for_agent("info_completion_agent")
    
    # Importar herramientas existentes si están disponibles
    try:
        from app.graph.nodes import search, search_documents
        tools = [search, search_documents] + handoff_tools
    except ImportError:
        tools = handoff_tools
    
    prompt = """
Eres un asistente especializado en recopilar información empresarial de manera natural.

TU TRABAJO:
1. Extraer información empresarial de los mensajes del usuario
2. Identificar qué información crítica falta
3. Hacer preguntas naturales para completar información
4. Transferir control a otros agentes cuando sea apropiado

INFORMACIÓN CRÍTICA MÍNIMA:
- nombre_empresa: Nombre del negocio
- ubicacion: Dónde opera (ciudad, país, online)
- productos_servicios_principales: Qué vende o ofrece
- descripcion_negocio: Descripción general del negocio

HERRAMIENTAS DE HANDOFF DISPONIBLES:
- transfer_to_research_router: Cuando la información esté completa y el usuario pueda necesitar investigación
- transfer_to_conversational: Para consultas generales o conversación
- assign_research_task: Para asignar tareas específicas de investigación

INSTRUCCIONES:
- Sé conversacional y natural, no robótico
- Si la información está completa, sugiere investigación o transfiere control
- Si el usuario hace preguntas generales, transfiere al agente conversacional
- Reconoce y usa la información que ya tienes
- Extrae información automáticamente de mensajes completos

EJEMPLO DE CONVERSACIÓN NATURAL:
❌ MAL: "¿Cuál es el nombre de tu empresa? ¿Dónde está ubicada?"
✅ BIEN: "¡Hola! Me gustaría ayudarte con tu negocio. Cuéntame sobre tu empresa: ¿cómo se llama y qué tipo de productos o servicios ofreces?"
"""
    
    return create_react_agent(
        model=ChatOpenAI(model=LLM_MODEL, temperature=0.7),
        tools=tools,
        prompt=prompt,
        name="info_completion_agent"
    )

def create_enhanced_research_router():
    """Crea router de investigación con capacidades de handoff."""
    
    handoff_tools = get_handoff_tools_for_agent("research_router")
    
    prompt = """
Eres un router especializado en investigación de mercado y oportunidades empresariales.

TU TRABAJO:
1. Evaluar si la información disponible es suficiente para investigación
2. Consultar al usuario sobre qué tipo de investigación necesita
3. Transferir control al investigador o agentes apropiados
4. Mantener contexto empresarial en toda la conversación

HERRAMIENTAS DE HANDOFF DISPONIBLES:
- transfer_to_researcher: Para investigación inmediata
- transfer_to_conversational: Para consultas generales
- assign_research_task: Para asignar tareas específicas de investigación

TIPOS DE INVESTIGACIÓN QUE PUEDES OFRECER:
1. Análisis de competencia en su sector
2. Oportunidades de mercado en su ubicación
3. Tendencias de productos/servicios similares
4. Estrategias de crecimiento específicas
5. Análisis de precios del mercado

INSTRUCCIONES:
- Si la información es suficiente, pregunta qué tipo de investigación necesita
- Ofrece opciones específicas basadas en su negocio
- Mantén el contexto empresarial en tus respuestas
- Transfiere control cuando tengas claridad sobre la necesidad

EJEMPLO:
"Perfecto, {nombre_empresa}. Con la información de tu {descripcion_negocio} en {ubicacion}, puedo investigar:

🔍 ¿Te interesa que analice tu competencia local?
📊 ¿Quieres conocer tendencias del mercado de {productos}?
📈 ¿Te gustaría explorar nuevas oportunidades de crecimiento?

¿Qué tipo de investigación te sería más útil ahora?"
"""
    
    return create_react_agent(
        model=ChatOpenAI(model=LLM_MODEL, temperature=0.7),
        tools=handoff_tools,
        prompt=prompt,
        name="research_router"
    )

def create_enhanced_conversational_agent():
    """Crea agente conversacional con capacidades de handoff."""
    
    handoff_tools = get_handoff_tools_for_agent("conversational_agent")
    
    # Importar herramientas existentes si están disponibles
    try:
        from app.graph.nodes import search, search_documents
        tools = [search, search_documents] + handoff_tools
    except ImportError:
        tools = handoff_tools
    
    prompt = """
Eres un consultor empresarial conversacional que mantiene contexto de la información del negocio.

TU TRABAJO:
1. Responder preguntas generales sobre negocios
2. Dar consejos basados en la información empresarial disponible
3. Mantener una conversación natural y útil
4. Transferir control a agentes especializados cuando sea apropiado

HERRAMIENTAS DE HANDOFF DISPONIBLES:
- transfer_to_researcher: Para investigación de mercado
- transfer_to_info_completion: Para recopilar más información empresarial
- assign_research_task: Para asignar investigación específica

INSTRUCCIONES:
- Usa la información empresarial para personalizar tus respuestas
- Da consejos prácticos y específicos para su tipo de negocio
- Mantén un tono conversacional y profesional
- Si necesitas investigación específica, transfiere al investigador
- Si falta información empresarial, transfiere al agente de información
- Responde de manera útil y orientada a soluciones

EJEMPLO:
Usuario: "¿Cómo puedo mejorar las ventas?"
Respuesta: "Para {nombre_empresa} que se dedica a {productos} en {ubicacion}, hay varias estrategias específicas que podrían funcionar bien..."

Si necesitas investigación específica: "Para darte recomendaciones más precisas, voy a transferirte a nuestro investigador especializado."
"""
    
    return create_react_agent(
        model=ChatOpenAI(model=LLM_MODEL, temperature=0.7),
        tools=tools,
        prompt=prompt,
        name="conversational_agent"
    )

# === NODOS DE AGENTES CON COMMAND ===

def enhanced_info_completion_node(state: PYMESState) -> Command[Literal["enhanced_human_feedback"]]:
    """
    Nodo de agente de información mejorado que usa Command para control de flujo.
    """
    try:
        logger.info("📝 enhanced_info_completion_node: Procesando información empresarial...")
        
        # Crear agente si no existe
        if not hasattr(enhanced_info_completion_node, 'agent'):
            enhanced_info_completion_node.agent = create_enhanced_info_completion_agent()
        
        # Ejecutar agente
        result = enhanced_info_completion_node.agent.invoke(state)
        
        # Extraer información empresarial del último mensaje del usuario
        messages = state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        # Intentar extraer información empresarial
        business_info = state.get("business_info", {})
        if user_message:
            try:
                business_manager = get_business_info_manager()
                thread_id = f"temp_{hash(user_message) % 10000}"
                updated_info = business_manager.extract_info(user_message, thread_id, business_info)
                if updated_info != business_info:
                    business_info = updated_info
                    logger.info("✅ Nueva información empresarial extraída en nodo")
            except Exception as e:
                logger.warning(f"Error extrayendo información en nodo: {str(e)}")
        
        # Usar Command para actualizar estado y continuar flujo
        return Command(
            update={
                **result,
                "business_info": business_info,
                "stage": "info_gathering"
            },
            goto="enhanced_human_feedback"
        )
        
    except Exception as e:
        logger.error(f"Error in enhanced_info_completion_node: {str(e)}")
        error_message = "Disculpa, hubo un error. ¿Podrías contarme sobre tu negocio?"
        return Command(
            update={
                "messages": [AIMessage(content=error_message)],
                "answer": error_message
            },
            goto="enhanced_human_feedback"
        )

def enhanced_research_router_node(state: PYMESState) -> Command[Literal["enhanced_human_feedback"]]:
    """
    Nodo de router de investigación mejorado que usa Command.
    """
    try:
        logger.info("🔬 enhanced_research_router_node: Evaluando necesidades de investigación...")
        
        # Crear agente si no existe
        if not hasattr(enhanced_research_router_node, 'agent'):
            enhanced_research_router_node.agent = create_enhanced_research_router()
        
        # Ejecutar agente
        result = enhanced_research_router_node.agent.invoke(state)
        
        return Command(
            update={
                **result,
                "stage": "research_routing"
            },
            goto="enhanced_human_feedback"
        )
        
    except Exception as e:
        logger.error(f"Error in enhanced_research_router_node: {str(e)}")
        fallback_message = "¿Te gustaría que investigue oportunidades para tu negocio?"
        return Command(
            update={
                "messages": [AIMessage(content=fallback_message)],
                "answer": fallback_message
            },
            goto="enhanced_human_feedback"
        )

def enhanced_conversational_node(state: PYMESState) -> Command[Literal["enhanced_human_feedback"]]:
    """
    Nodo conversacional mejorado que usa Command.
    """
    try:
        logger.info("💬 enhanced_conversational_node: Iniciando conversación contextual...")
        
        # Crear agente si no existe
        if not hasattr(enhanced_conversational_node, 'agent'):
            enhanced_conversational_node.agent = create_enhanced_conversational_agent()
        
        # Ejecutar agente
        result = enhanced_conversational_node.agent.invoke(state)
        
        return Command(
            update={
                **result,
                "stage": "conversational"
            },
            goto="enhanced_human_feedback"
        )
        
    except Exception as e:
        logger.error(f"Error in enhanced_conversational_node: {str(e)}")
        fallback_message = "¿En qué puedo ayudarte con tu negocio?"
        return Command(
            update={
                "messages": [AIMessage(content=fallback_message)],
                "answer": fallback_message
            },
            goto="enhanced_human_feedback"
        )

def enhanced_researcher_node(state: PYMESState) -> Command[Literal["enhanced_human_feedback"]]:
    """
    Nodo de investigador mejorado que usa Command.
    Reutiliza el agente investigador existente pero con handoffs.
    """
    try:
        logger.info("🔍 enhanced_researcher_node: Ejecutando investigación...")
        
        # Importar el agente investigador existente
        from app.graph.supervisor_architecture import researcher_agent_node
        
        # Ejecutar investigación
        result = researcher_agent_node(state)
        
        return Command(
            update={
                **result,
                "stage": "research_completed"
            },
            goto="enhanced_human_feedback"
        )
        
    except Exception as e:
        logger.error(f"Error in enhanced_researcher_node: {str(e)}")
        error_message = "Hubo un error en la investigación. ¿Puedes proporcionar más detalles sobre lo que necesitas?"
        return Command(
            update={
                "messages": [AIMessage(content=error_message)],
                "answer": error_message
            },
            goto="enhanced_human_feedback"
        ) 