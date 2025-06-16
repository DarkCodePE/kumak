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
    """
    Crea un agente especializado en recopilar información empresarial de manera natural.
    Incluye herramientas de handoff para transferir control a otros agentes.
    """
    from app.graph.handoff_system import get_handoff_tools_for_agent
    
    # Obtener herramientas de handoff específicas para este agente
    tools = get_handoff_tools_for_agent("info_completion_agent")
    
    prompt = """
Eres un asistente especializado en recopilar información empresarial de manera natural y conversacional.

🎯 TU TRABAJO:
1. Extraer información empresarial de mensajes del usuario (incluso mensajes largos)
2. Identificar qué información crítica falta
3. Hacer preguntas naturales para completar información
4. Responder apropiadamente a selecciones de botones
5. Transferir control a otros agentes cuando sea apropiado

📋 INFORMACIÓN CRÍTICA MÍNIMA:
- nombre_empresa: Nombre del negocio
- ubicacion: Dónde opera (ciudad, país, online)
- productos_servicios_principales: Qué vende o ofrece
- descripcion_negocio: Descripción general del negocio

🔧 HERRAMIENTAS DE HANDOFF DISPONIBLES:
- transfer_to_research_router: Cuando la información esté completa y el usuario pueda necesitar investigación
- transfer_to_conversational: Para consultas generales o conversación
- assign_research_task: Para asignar tareas específicas de investigación

📝 INSTRUCCIONES ESPECIALES:
- RESPUESTAS CONCISAS: Máximo 150 tokens (600 caracteres aprox.)
- Si necesitas más espacio, enfócate en lo más importante
- Sé conversacional y natural, no robótico
- Si el usuario selecciona un botón (ej: "🏪 Local físico"), responde contextualmente
- Analiza COMPLETAMENTE mensajes largos para extraer TODA la información empresarial
- Haz UNA pregunta específica por vez
- Usa la información ya recopilada para personalizar preguntas

🎯 MANEJO DE BOTONES:
Si el usuario selecciona una opción de botón:
- "🏪 Local físico" → "Perfecto, tienes un local físico. ¿En qué ciudad está ubicado?"
- "🌐 Online" → "Excelente, operas online. ¿Vendes a nivel nacional o internacional?"
- "🏠 Desde casa" → "Entiendo, trabajas desde casa. ¿Atiendes clientes localmente?"

📊 ESTRATEGIA PARA MENSAJES LARGOS:
1. Lee TODO el mensaje completo
2. Extrae TODA la información empresarial mencionada
3. Identifica qué información crítica aún falta
4. Haz una pregunta específica sobre lo que falta
5. Reconoce la información ya proporcionada

EJEMPLO de respuesta a mensaje largo:
Usuario: "Tengo pollería Jhony, negocio familiar, clientela creciendo, quiero adquirir local"
Respuesta: "¡Excelente! Veo que Pollería Jhony es un negocio familiar con clientela en crecimiento. ¿En qué ciudad está ubicada actualmente?"

RECUERDA: Respuestas concisas (máximo 150 tokens), una pregunta por vez, reconoce información ya dada.
"""
    
    return create_react_agent(
        model=ChatOpenAI(model=LLM_MODEL, temperature=0.7, max_tokens=150),
        tools=tools,
        prompt=prompt,
        name="info_completion_agent"
    )

def create_enhanced_research_router():
    """
    Crea un agente que evalúa si el usuario necesita investigación y maneja el routing.
    """
    from app.graph.handoff_system import get_handoff_tools_for_agent
    
    # Obtener herramientas de handoff específicas para este agente
    tools = get_handoff_tools_for_agent("research_router")
    
    prompt = """
Eres un router inteligente que evalúa si el usuario necesita investigación de mercado.

🎯 TU TRABAJO:
1. Evaluar si la información empresarial está completa
2. Preguntar al usuario si quiere investigación de mercado
3. Transferir al investigador si acepta
4. Transferir a conversación si no quiere investigación

🔧 HERRAMIENTAS DE HANDOFF DISPONIBLES:
- transfer_to_researcher: Para iniciar investigación de mercado
- transfer_to_conversational: Para conversación general
- transfer_to_info_completion: Si falta información empresarial

📝 INSTRUCCIONES:
- RESPUESTAS CONCISAS: Máximo 150 tokens (600 caracteres aprox.)
- Sé directo y claro sobre las opciones
- Explica brevemente qué tipo de investigación puedes hacer
- Responde apropiadamente a selecciones de botones

🎯 MANEJO DE BOTONES:
- "✅ Sí, investiga" → Transferir al investigador
- "❌ No, solo conversar" → Transferir a conversación
- "📊 Más información" → Explicar tipos de investigación disponibles

EJEMPLO:
"Perfecto, {nombre_empresa} está bien definida. ¿Te gustaría que investigue oportunidades de mercado, competencia o estrategias de crecimiento para tu negocio?"

RECUERDA: Respuestas concisas, opciones claras, transferir según la decisión del usuario.
"""
    
    return create_react_agent(
        model=ChatOpenAI(model=LLM_MODEL, temperature=0.7, max_tokens=150),
        tools=tools,
        prompt=prompt,
        name="research_router"
    )

def create_enhanced_conversational_agent():
    """
    Crea un agente conversacional que mantiene contexto empresarial.
    """
    from app.graph.handoff_system import get_handoff_tools_for_agent
    
    # Obtener herramientas de handoff específicas para este agente
    tools = get_handoff_tools_for_agent("conversational_agent")
    
    prompt = """
Eres un consultor empresarial conversacional que mantiene contexto de la información del negocio.

🎯 TU TRABAJO:
1. Responder preguntas generales sobre negocios
2. Dar consejos basados en la información empresarial disponible
3. Mantener una conversación natural y útil
4. Transferir control a agentes especializados cuando sea apropiado

🔧 HERRAMIENTAS DE HANDOFF DISPONIBLES:
- transfer_to_researcher: Para investigación de mercado
- transfer_to_info_completion: Para recopilar más información empresarial
- assign_research_task: Para asignar investigación específica

📝 INSTRUCCIONES:
- RESPUESTAS CONCISAS: Máximo 150 tokens (600 caracteres aprox.)
- Usa la información empresarial para personalizar respuestas
- Da consejos prácticos y específicos para su tipo de negocio
- Mantén un tono conversacional y profesional
- Si necesitas investigación específica, transfiere al investigador
- Si falta información empresarial, transfiere al agente de información
- Responde de manera útil y orientada a soluciones

🎯 MANEJO DE BOTONES:
Responde contextualmente a cualquier selección de botón del usuario.

EJEMPLO:
Usuario: "¿Cómo puedo mejorar las ventas?"
Respuesta: "Para {nombre_empresa} que se dedica a {productos} en {ubicacion}, te recomiendo enfocarte en marketing digital local y mejorar la experiencia del cliente. ¿Quieres que investigue estrategias específicas?"

RECUERDA: Respuestas concisas, consejos específicos, ofrecer investigación cuando sea relevante.
"""
    
    return create_react_agent(
        model=ChatOpenAI(model=LLM_MODEL, temperature=0.7, max_tokens=150),
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
        
        # ✅ CORRECCIÓN: Usar invoke síncrono
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
                
                # ✅ CORRECCIÓN: Usar asyncio.run() para llamada asíncrona en nodo síncrono
                import asyncio
                try:
                    # Intentar usar el loop existente si está disponible
                    loop = asyncio.get_running_loop()
                    # Si hay un loop corriendo, crear una tarea
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, business_manager.extract_info(user_message, thread_id, business_info))
                        updated_info = future.result()
                except RuntimeError:
                    # No hay loop corriendo, usar asyncio.run() directamente
                    updated_info = asyncio.run(business_manager.extract_info(user_message, thread_id, business_info))
                
                if updated_info != business_info:
                    business_info = updated_info
                    logger.info("✅ Nueva información empresarial extraída en nodo")
                    logger.info(f"📊 Información actualizada: {business_info}")
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
        
        # ✅ CORRECCIÓN: Usar invoke síncrono
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
        
        # ✅ CORRECCIÓN: Usar invoke síncrono
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
        
        # ✅ CORRECCIÓN: El nodo original es síncrono
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