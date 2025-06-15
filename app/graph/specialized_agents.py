"""
Agentes especializados para el flujo de conversación inteligente.
Implementa agentes que manejan diferentes aspectos de la conversación empresarial.
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.services.business_info_manager import get_business_info_manager

logger = logging.getLogger(__name__)

# === PROMPTS PARA AGENTES ESPECIALIZADOS ===

INFO_COMPLETION_PROMPT = """
Eres un asistente especializado en recopilar información empresarial de manera natural y conversacional.

TU TRABAJO:
1. Analizar la información empresarial ya disponible
2. Identificar qué información crítica falta
3. Hacer preguntas específicas y naturales para completar la información
4. Extraer información de respuestas completas del usuario

INFORMACIÓN ACTUAL:
{business_info}

CAMPOS FALTANTES CRÍTICOS:
{missing_fields}

CONTEXTO DE ROUTING:
{routing_context}

INSTRUCCIONES:
- Si faltan campos críticos, haz UNA pregunta natural que pueda cubrir múltiples campos
- Si el usuario da información completa, extrae todo lo relevante
- Sé conversacional y no robótico (evita listas de preguntas)
- Reconoce y usa la información que ya tienes
- Si la información está completa, sugiere pasar a investigación

CAMPOS CRÍTICOS MÍNIMOS:
- nombre_empresa: Nombre del negocio
- ubicacion: Dónde opera (ciudad, país, online)
- productos_servicios_principales: Qué vende o ofrece
- descripcion_negocio: Descripción general del negocio

EJEMPLO DE CONVERSACIÓN NATURAL:
❌ MAL: "¿Cuál es el nombre de tu empresa? ¿Dónde está ubicada? ¿Qué productos vendes?"
✅ BIEN: "¡Hola! Me gustaría ayudarte con tu negocio. Cuéntame un poco sobre tu empresa: ¿cómo se llama y qué tipo de productos o servicios ofreces?"

Responde de manera natural y conversacional.
"""

RESEARCH_ROUTER_PROMPT = """
Eres un asistente especializado en investigación de mercado y oportunidades empresariales.

TU TRABAJO:
1. Evaluar si la información disponible es suficiente para investigación
2. Consultar al usuario sobre qué tipo de investigación necesita
3. Dirigir la conversación hacia investigación específica
4. Mantener el contexto empresarial en toda la conversación

INFORMACIÓN EMPRESARIAL:
{business_info}

CONTEXTO DE ROUTING:
{routing_context}

ESTADO DE PREPARACIÓN:
{research_readiness}

INSTRUCCIONES:
- Si la información es suficiente, pregunta qué tipo de investigación necesita
- Ofrece opciones específicas de investigación basadas en su negocio
- Si necesita preguntar sobre investigación, sé específico sobre qué puedes ofrecer
- Mantén el contexto empresarial en tus respuestas

TIPOS DE INVESTIGACIÓN QUE PUEDES OFRECER:
1. Análisis de competencia en su sector
2. Oportunidades de mercado en su ubicación
3. Tendencias de productos/servicios similares
4. Estrategias de crecimiento específicas
5. Análisis de precios del mercado

EJEMPLO:
"Perfecto, {nombre_empresa}. Con la información de tu {descripcion_negocio} en {ubicacion}, puedo investigar varias oportunidades:

🔍 ¿Te interesa que analice tu competencia local?
📊 ¿Quieres conocer tendencias del mercado de {productos}?
📈 ¿Te gustaría explorar nuevas oportunidades de crecimiento?

¿Qué tipo de investigación te sería más útil ahora?"

Sé específico y orientado a acción.
"""

CONVERSATIONAL_PROMPT = """
Eres un consultor empresarial conversacional que mantiene contexto de la información del negocio.

TU TRABAJO:
1. Responder preguntas generales sobre negocios
2. Dar consejos basados en la información empresarial disponible
3. Mantener una conversación natural y útil
4. Ofrecer orientación práctica y específica

INFORMACIÓN EMPRESARIAL:
{business_info}

CONTEXTO DE LA CONVERSACIÓN:
{conversation_context}

INSTRUCCIONES:
- Usa la información empresarial para personalizar tus respuestas
- Da consejos prácticos y específicos para su tipo de negocio
- Mantén un tono conversacional y profesional
- Si es relevante, sugiere investigación o más recopilación de información
- Responde de manera útil y orientada a soluciones

EJEMPLO:
Usuario: "¿Cómo puedo mejorar las ventas?"
Respuesta: "Para {nombre_empresa} que se dedica a {productos} en {ubicacion}, hay varias estrategias específicas que podrían funcionar bien..."

Sé útil, específico y conversacional.
"""

# === AGENTES ESPECIALIZADOS ===

def info_completion_agent_node(state: PYMESState) -> Dict[str, Any]:
    """
    Agente especializado en completar información empresarial faltante.
    Maneja la recopilación de información de manera natural y conversacional.
    """
    try:
        logger.info("📝 info_completion_agent_node: Analizando información faltante...")
        
        # Obtener información actual y contexto
        business_info = state.get("business_info", {})
        missing_fields = state.get("missing_fields", [])
        routing_context = state.get("routing_reason", "Recopilación de información")
        change_mode = state.get("change_mode", False)
        
        # Primero, intentar extraer información del último mensaje del usuario
        messages = state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        # Si hay un mensaje del usuario, extraer información primero
        if user_message and len(messages) > 2:  # No es el primer mensaje
            logger.info("🔍 Extrayendo información del mensaje del usuario...")
            business_manager = get_business_info_manager()
            thread_id = f"temp_{hash(user_message) % 10000}"
            
            try:
                updated_info = business_manager.extract_info(user_message, thread_id, business_info)
                if updated_info != business_info:
                    logger.info("✅ Nueva información extraída exitosamente")
                    business_info = updated_info
                    # Actualizar el estado con la nueva información
                    state["business_info"] = business_info
            except Exception as e:
                logger.warning(f"Error extrayendo información: {str(e)}")
        
        # Evaluar qué información sigue faltando
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        current_missing = [field for field in critical_fields if not business_info.get(field)]
        
        logger.info(f"📊 Información actual: {business_info}")
        logger.info(f"📋 Campos faltantes: {current_missing}")
        
        # Si ya no faltan campos críticos, sugerir investigación
        if not current_missing:
            logger.info("✅ Información completa, sugiriendo investigación")
            
            empresa = business_info.get("nombre_empresa", "tu empresa")
            productos = business_info.get("productos_servicios_principales", "tus productos/servicios")
            ubicacion = business_info.get("ubicacion", "tu ubicación")
            
            completion_message = f"""¡Excelente! 🎉 Ya tengo toda la información básica de {empresa}:

📊 **Resumen de tu negocio:**
🏢 **Empresa:** {empresa}
📍 **Ubicación:** {ubicacion}  
📦 **Productos/Servicios:** {productos}
📋 **Descripción:** {business_info.get("descripcion_negocio", "Información recopilada")}

Ahora que tengo el contexto completo de tu negocio, puedo ayudarte con:

🔍 **Investigar oportunidades** de mercado específicas para tu sector
📈 **Analizar la competencia** en tu zona
💡 **Sugerir estrategias** de crecimiento personalizadas

¿Te gustaría que comience con algún análisis específico, o tienes alguna pregunta particular sobre tu negocio?"""

            return {
                "messages": [AIMessage(content=completion_message)],
                "business_info": business_info,
                "answer": completion_message,
                "stage": "info_completed",
                "current_agent": "research_router"  # Sugerir cambio a research
            }
        
        # Si faltan campos, generar pregunta natural
        else:
            llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7)  # Más creatividad para naturalidad
            
            prompt = ChatPromptTemplate.from_template(INFO_COMPLETION_PROMPT)
            
            response = llm.invoke(
                prompt.format(
                    business_info=business_info,
                    missing_fields=current_missing,
                    routing_context=routing_context
                )
            )
            
            question = response.content
            
            logger.info(f"❓ Pregunta generada: {question[:100]}...")
            
            return {
                "messages": [AIMessage(content=question)],
                "business_info": business_info,
                "answer": question,
                "missing_fields": current_missing,
                "stage": "info_gathering"
            }
            
    except Exception as e:
        logger.error(f"Error in info_completion_agent_node: {str(e)}")
        error_message = "Disculpa, hubo un error. ¿Podrías contarme sobre tu negocio?"
        return {
            "messages": [AIMessage(content=error_message)],
            "answer": error_message
        }

def research_router_node(state: PYMESState) -> Dict[str, Any]:
    """
    Agente que maneja el routing hacia investigación y pregunta sobre intenciones de research.
    """
    try:
        logger.info("🔬 research_router_node: Evaluando necesidades de investigación...")
        
        business_info = state.get("business_info", {})
        routing_context = state.get("routing_reason", "Investigación de mercado")
        should_ask_intent = state.get("should_ask_research_intent", False)
        research_readiness = state.get("research_readiness", 0.5)
        
        # Obtener último mensaje del usuario para detectar intención
        messages = state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        # Detectar si el usuario menciona investigación específica
        research_keywords = ["investiga", "analiza", "oportunidades", "mercado", "competencia", "crecimiento", "estrategia"]
        wants_research = any(keyword in user_message.lower() for keyword in research_keywords)
        
        if wants_research:
            logger.info("🎯 Usuario quiere investigación específica")
            return {
                "current_agent": "researcher",
                "routing_reason": "Usuario solicitó investigación específica",
                "stage": "research_requested"
            }
        
        # Si debe preguntar sobre intención, crear mensaje consultivo
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7)
        
        prompt = ChatPromptTemplate.from_template(RESEARCH_ROUTER_PROMPT)
        
        response = llm.invoke(
            prompt.format(
                business_info=business_info,
                routing_context=routing_context,
                research_readiness=f"{research_readiness:.1%}"
            )
        )
        
        router_message = response.content
        
        logger.info(f"🤔 Pregunta de routing generada: {router_message[:100]}...")
        
        return {
            "messages": [AIMessage(content=router_message)],
            "answer": router_message,
            "stage": "research_routing",
            "awaiting_research_decision": True
        }
        
    except Exception as e:
        logger.error(f"Error in research_router_node: {str(e)}")
        fallback_message = "¿Te gustaría que investigue oportunidades para tu negocio?"
        return {
            "messages": [AIMessage(content=fallback_message)],
            "answer": fallback_message
        }

def conversational_agent_node(state: PYMESState) -> Dict[str, Any]:
    """
    Agente conversacional que mantiene contexto empresarial.
    """
    try:
        logger.info("💬 conversational_agent_node: Iniciando conversación contextual...")
        
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7)
        
        # Obtener contexto empresarial
        business_info = state.get("business_info", {})
        
        # Crear contexto de conversación
        messages = state.get("messages", [])
        recent_context = []
        for msg in messages[-4:]:  # Últimos 4 mensajes
            if isinstance(msg, HumanMessage):
                recent_context.append(f"Usuario: {msg.content}")
            elif isinstance(msg, AIMessage):
                recent_context.append(f"Asistente: {msg.content}")
        
        conversation_context = "\n".join(recent_context)
        
        # Usar herramientas si es necesario (importar del módulo de nodos existente)
        try:
            from app.graph.nodes import search, search_documents
            tools = [search, search_documents]
            
            # Crear agente ReAct con contexto empresarial
            enhanced_prompt = CONVERSATIONAL_PROMPT + f"\n\nTOOLS DISPONIBLES: Puedes usar búsqueda web y de documentos si necesitas información específica."
            
            agent = create_react_agent(llm, tools, prompt=enhanced_prompt)
            
            # Crear estado mejorado con contexto
            enhanced_state = {**state}
            enhanced_state["business_context"] = business_info
            enhanced_state["conversation_summary"] = conversation_context
            
            result = agent.invoke(enhanced_state)
            
            return {
                "messages": result["messages"],
                "stage": "conversational"
            }
            
        except ImportError:
            # Fallback sin herramientas
            prompt = ChatPromptTemplate.from_template(CONVERSATIONAL_PROMPT)
            
            response = llm.invoke(
                prompt.format(
                    business_info=business_info,
                    conversation_context=conversation_context
                )
            )
            
            return {
                "messages": [AIMessage(content=response.content)],
                "answer": response.content,
                "stage": "conversational"
            }
            
    except Exception as e:
        logger.error(f"Error in conversational_agent_node: {str(e)}")
        fallback_message = "¿En qué puedo ayudarte con tu negocio?"
        return {
            "messages": [AIMessage(content=fallback_message)],
            "answer": fallback_message
        } 