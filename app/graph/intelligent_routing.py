"""
Routing inteligente para el flujo de conversación basado en BusinessInfo y contexto.
Implementa la lógica para determinar si proceder con investigación o recopilar más información.
"""

import logging
from typing import Dict, Any, Literal, Optional, List
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState

logger = logging.getLogger(__name__)

# === MODELOS PARA ROUTING INTELIGENTE ===

class BusinessInfoCompleteness(BaseModel):
    """Evaluación de completitud de información empresarial."""
    has_minimum_for_research: bool = Field(description="Si tiene información mínima para investigación")
    missing_critical_fields: List[str] = Field(description="Campos críticos faltantes")
    missing_optional_fields: List[str] = Field(description="Campos opcionales faltantes")
    completeness_percentage: float = Field(description="Porcentaje de completitud (0.0-1.0)")
    can_start_research: bool = Field(description="Si puede comenzar investigación inmediatamente")
    research_readiness_score: float = Field(description="Puntuación de preparación para investigación (0.0-1.0)")

class UserIntent(BaseModel):
    """Intención detectada del usuario."""
    wants_research: bool = Field(description="Si el usuario quiere investigación de oportunidades")
    wants_more_info_gathering: bool = Field(description="Si quiere proporcionar más información")
    wants_conversation: bool = Field(description="Si quiere conversación general")
    wants_to_change_info: bool = Field(description="Si quiere cambiar información previamente proporcionada")
    confidence_score: float = Field(description="Confianza en la detección de intención (0.0-1.0)")
    detected_intent: str = Field(description="Descripción textual de la intención detectada")

# === PROMPTS PARA ROUTING ===

BUSINESS_INFO_EVALUATION_PROMPT = """
Eres un evaluador experto de información empresarial. Tu trabajo es determinar si la información disponible es suficiente para realizar investigación de mercado.

INFORMACIÓN EMPRESARIAL DISPONIBLE:
{business_info}

CRITERIOS DE EVALUACIÓN:

CAMPOS CRÍTICOS MÍNIMOS (necesarios para investigación):
- nombre_empresa: Nombre del negocio
- ubicacion: Dónde opera (ciudad, país, online)
- productos_servicios_principales: Qué vende o ofrece
- descripcion_negocio: Descripción general del negocio

CAMPOS OPCIONALES (mejoran la investigación):
- sector: Industria específica
- desafios_principales: Problemas que enfrenta
- anos_operacion: Tiempo en operación
- num_empleados: Tamaño de la empresa

INSTRUCCIONES:
1. Evalúa si tiene los 4 campos críticos mínimos
2. Identifica qué campos críticos faltan (si hay)
3. Identifica qué campos opcionales faltan
4. Calcula porcentaje de completitud considerando ambos tipos
5. Determina si puede comenzar investigación (tiene mínimos críticos)
6. Asigna puntuación de preparación (mayor score = mejor investigación posible)

Responde SOLO con el JSON estructurado.
"""

USER_INTENT_DETECTION_PROMPT = """
Eres un detector experto de intenciones de usuario en conversaciones de negocios.

MENSAJE DEL USUARIO: "{user_message}"

CONTEXTO DE LA CONVERSACIÓN:
- Estado actual: {current_stage}
- Información empresarial disponible: {business_info}
- Último mensaje del asistente: {last_assistant_message}

INTENCIONES POSIBLES:
1. INVESTIGACIÓN: Quiere que analicemos oportunidades de mercado, competencia, crecimiento
2. MÁS INFORMACIÓN: Quiere proporcionar más detalles sobre su negocio
3. CONVERSACIÓN: Quiere conversar sobre temas específicos, hacer preguntas generales  
4. CAMBIAR INFORMACIÓN: Quiere corregir o actualizar información previamente proporcionada

REGLAS DE CLASIFICACIÓN:

🔬 INVESTIGACIÓN:
- Palabras clave: "investiga", "analiza", "oportunidades", "mercado", "competencia", "crecimiento", "estrategia"
- Frases: "quiero que investigues", "analiza mi negocio", "busca oportunidades"

📝 MÁS INFORMACIÓN: 
- Si el mensaje contiene datos empresariales (nombre, ubicación, productos, descripción)
- Palabras: "tengo", "somos", "vendemos", "ofrecemos", "mi empresa", "mi negocio"  
- Contexto: Está proporcionando información nueva sobre su negocio

💬 CONVERSACIÓN:
- Preguntas de consulta: "qué opinas", "cómo puedo", "ayúdame con", "necesito consejo"
- Temas específicos: marketing, ventas, operaciones, finanzas
- NO contiene información empresarial nueva

🔄 CAMBIAR INFORMACIÓN:
- Palabras: "corrección", "cambiar", "actualizar", "no es", "mejor dicho", "en realidad"
- Contexto: Corrigiendo información previamente proporcionada

EJEMPLOS:
- "Hola, soy Orlando de Pollería Orlando. Vendemos pollos a la brasa en Lima" → MÁS INFORMACIÓN
- "¿Qué opinas sobre las redes sociales para mi restaurante?" → CONVERSACIÓN  
- "Quiero que investigues oportunidades de crecimiento" → INVESTIGACIÓN
- "Mi restaurante está en Arequipa, no en Lima" → CAMBIAR INFORMACIÓN

INSTRUCCIONES:
- Analiza el contenido del mensaje, no solo palabras clave
- Si contiene información empresarial nueva = MÁS INFORMACIÓN
- Si hace preguntas de consulta = CONVERSACIÓN
- Si solicita análisis/investigación = INVESTIGACIÓN
- Si corrige información = CAMBIAR INFORMACIÓN

Responde SOLO con el JSON estructurado.
"""

# === NODOS DE ROUTING INTELIGENTE ===

def evaluate_business_info_completeness(state: PYMESState) -> BusinessInfoCompleteness:
    """Evalúa la completitud de la información empresarial."""
    try:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        
        business_info = state.get("business_info", {})
        
        prompt = ChatPromptTemplate.from_template(BUSINESS_INFO_EVALUATION_PROMPT)
        
        # Configurar LLM para output estructurado
        structured_llm = llm.with_structured_output(BusinessInfoCompleteness)
        
        result = structured_llm.invoke(
            prompt.format(business_info=business_info)
        )
        
        logger.info(f"📊 Evaluación de completitud: {result.completeness_percentage:.1%}")
        logger.info(f"🔍 Puede investigar: {result.can_start_research}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error evaluating business info completeness: {str(e)}")
        # Fallback manual
        business_info = state.get("business_info", {})
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        missing_critical = [field for field in critical_fields if not business_info.get(field)]
        
        return BusinessInfoCompleteness(
            has_minimum_for_research=len(missing_critical) == 0,
            missing_critical_fields=missing_critical,
            missing_optional_fields=[],
            completeness_percentage=max(0.0, (len(critical_fields) - len(missing_critical)) / len(critical_fields)),
            can_start_research=len(missing_critical) == 0,
            research_readiness_score=0.5 if len(missing_critical) == 0 else 0.2
        )

def detect_user_intent(state: PYMESState, user_message: str) -> UserIntent:
    """Detecta la intención del usuario basada en su mensaje y contexto."""
    try:
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        
        # Obtener contexto
        current_stage = state.get("stage", "unknown")
        business_info = state.get("business_info", {})
        
        # Obtener último mensaje del asistente
        messages = state.get("messages", [])
        last_assistant_message = "Ninguno"
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_assistant_message = msg.content
                break
        
        prompt = ChatPromptTemplate.from_template(USER_INTENT_DETECTION_PROMPT)
        
        # Configurar LLM para output estructurado
        structured_llm = llm.with_structured_output(UserIntent)
        
        result = structured_llm.invoke(
            prompt.format(
                user_message=user_message,
                current_stage=current_stage,
                business_info=business_info,
                last_assistant_message=last_assistant_message[:200]  # Limitar longitud
            )
        )
        
        logger.info(f"🎯 Intención detectada: {result.detected_intent}")
        logger.info(f"🔍 Confianza: {result.confidence_score:.1%}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error detecting user intent: {str(e)}")
        # Fallback simple basado en palabras clave
        message_lower = user_message.lower()
        
        research_keywords = ["investiga", "analiza", "oportunidades", "mercado", "competencia", "crecimiento"]
        wants_research = any(keyword in message_lower for keyword in research_keywords)
        
        return UserIntent(
            wants_research=wants_research,
            wants_more_info_gathering=not wants_research,
            wants_conversation=False,
            wants_to_change_info=False,
            confidence_score=0.6,
            detected_intent="Detección simple por palabras clave"
        )

def intelligent_router_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo de routing inteligente que decide el siguiente paso basado en:
    1. Completitud de información empresarial
    2. Intención del usuario
    3. Contexto de la conversación
    """
    try:
        logger.info("🧠 intelligent_router_node: Analizando situación...")
        
        # Obtener último mensaje del usuario
        messages = state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        # 1. Evaluar completitud de información
        completeness = evaluate_business_info_completeness(state)
        
        # 2. Detectar intención del usuario
        intent = detect_user_intent(state, user_message)
        
        # 3. Tomar decisión de routing
        logger.info(f"📊 Completitud: {completeness.completeness_percentage:.1%}")
        logger.info(f"🎯 Intención: {intent.detected_intent}")
        
        # LÓGICA DE DECISIÓN (reorganizada por prioridad)
        
        # PRIORIDAD 1: Si quiere cambiar información
        if intent.wants_to_change_info:
            logger.info("🔄 Routing: info_completion_agent (cambiar información)")
            return {
                "current_agent": "info_completion",
                "routing_reason": "Usuario quiere cambiar información existente",
                "change_mode": True
            }
        
        # PRIORIDAD 2: Si quiere investigación específica
        elif intent.wants_research:
            if completeness.can_start_research:
                logger.info("🔄 Routing: research_router (listo para investigación)")
                return {
                    "current_agent": "research_router",
                    "routing_reason": "Información suficiente y usuario quiere investigación",
                    "research_readiness": completeness.research_readiness_score
                }
            else:
                logger.info("🔄 Routing: info_completion_agent (investigación requiere más info)")
                return {
                    "current_agent": "info_completion",
                    "routing_reason": "Investigación solicitada pero falta información crítica",
                    "missing_fields": completeness.missing_critical_fields
                }
        
        # PRIORIDAD 3: Si quiere conversación general
        elif intent.wants_conversation:
            logger.info("🔄 Routing: conversational_agent")
            return {
                "current_agent": "conversational",
                "routing_reason": "Usuario quiere conversación general"
            }
        
        # PRIORIDAD 4: Si falta información crítica
        elif not completeness.can_start_research:
            logger.info("🔄 Routing: info_completion_agent (faltan datos críticos)")
            return {
                "current_agent": "info_completion",
                "routing_reason": "Faltan campos críticos para investigación",
                "missing_fields": completeness.missing_critical_fields,
                "completeness": completeness.completeness_percentage
            }
        
        # PRIORIDAD 5: Si tiene información completa pero no está claro qué quiere
        elif completeness.can_start_research and not intent.wants_research and not intent.wants_conversation:
            logger.info("🔄 Routing: research_router (preguntar sobre investigación)")
            return {
                "current_agent": "research_router",
                "routing_reason": "Información suficiente, consultar sobre investigación",
                "should_ask_research_intent": True
            }
        
        # Fallback: recopilar más información
        else:
            logger.info("🔄 Routing: info_completion_agent (fallback)")
            return {
                "current_agent": "info_completion",
                "routing_reason": "Fallback - recopilar más información",
                "missing_fields": completeness.missing_critical_fields
            }
            
    except Exception as e:
        logger.error(f"Error in intelligent_router_node: {str(e)}")
        return {
            "current_agent": "info_completion",
            "routing_reason": "Error en routing, fallback a recopilación de información"
        }

def route_after_intelligent_router(state: PYMESState) -> Literal[
    "info_completion_agent", "research_router", "conversational_agent"
]:
    """Función de routing basada en la decisión del intelligent_router_node."""
    current_agent = state.get("current_agent", "info_completion")
    
    routing_map = {
        "info_completion": "info_completion_agent",
        "research_router": "research_router",
        "conversational": "conversational_agent"
    }
    
    result = routing_map.get(current_agent, "info_completion_agent")
    logger.info(f"🎯 Routing to: {result}")
    return result 