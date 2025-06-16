"""
Herramientas Refinadas para el Agente Central - Arquitectura Profesional
Usando InjectedState para acceso directo al estado y mejores prácticas de LangGraph.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Annotated
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.prebuilt import InjectedState

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.services.business_info_manager import get_business_info_manager
from app.services.memory_service import get_memory_service

logger = logging.getLogger(__name__)

# === MODELOS PARA RESULTADOS ===

class BusinessInfoUpdate(BaseModel):
    """Resultado de actualización de información empresarial."""
    success: bool = Field(description="Si la actualización fue exitosa")
    updated_info: Dict[str, Any] = Field(description="Información empresarial actualizada")
    missing_fields: List[str] = Field(description="Campos que aún faltan")
    completeness_score: float = Field(description="Porcentaje de completitud (0.0-1.0)")
    message: str = Field(description="Mensaje para el usuario")

class MarketResearchResult(BaseModel):
    """Resultado de investigación de mercado."""
    success: bool = Field(description="Si la investigación fue exitosa")
    research_content: str = Field(description="Contenido de la investigación")
    research_type: str = Field(description="Tipo de investigación realizada")
    recommendations: List[str] = Field(description="Recomendaciones específicas")
    message: str = Field(description="Mensaje para el usuario")

# === HERRAMIENTAS PRINCIPALES CON INJECTEDSTATE ===

@tool
def update_business_info(
    state: Annotated[PYMESState, InjectedState]
) -> BusinessInfoUpdate:
    """
    Extrae y actualiza información empresarial del último mensaje del usuario.
    
    Usa esta herramienta cuando:
    - El usuario menciona información de su negocio (nombre, productos, ubicación, etc.)
    - Necesitas completar campos faltantes de BusinessInfo
    - El usuario quiere corregir información existente
    
    La herramienta accede automáticamente al estado del grafo para obtener el mensaje del usuario
    y la información empresarial actual.
    """
    try:
        logger.info("🔍 update_business_info: Analizando mensaje del usuario...")
        
        # Acceder directamente al estado inyectado
        messages = state.get("messages", [])
        current_business_info = state.get("business_info", {})
        
        # Obtener el último mensaje del usuario
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        if not user_message:
            return BusinessInfoUpdate(
                success=False,
                updated_info=current_business_info,
                missing_fields=["no_message"],
                completeness_score=0.0,
                message="No se encontró mensaje del usuario para procesar."
            )
        
        logger.info(f"📝 Procesando mensaje: {user_message[:50]}...")
        
        # Usar BusinessInfoManager para extraer información
        business_manager = get_business_info_manager()
        thread_id = f"temp_{hash(user_message) % 10000}"
        
        # Ejecutar extracción de manera asíncrona
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, business_manager.extract_info(user_message, thread_id, current_business_info))
                updated_info = future.result()
        except RuntimeError:
            updated_info = asyncio.run(business_manager.extract_info(user_message, thread_id, current_business_info))
        
        # Evaluar completitud
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        missing_fields = [field for field in critical_fields if not updated_info.get(field)]
        completeness = (len(critical_fields) - len(missing_fields)) / len(critical_fields)
        
        # Guardar en memoria si hay nueva información
        if updated_info != current_business_info:
            logger.info("✅ Nueva información empresarial extraída")
            try:
                memory_service = get_memory_service()
                memory_service.save_business_info(thread_id, updated_info)
                logger.info(f"💾 Información guardada en memoria para thread: {thread_id}")
            except Exception as e:
                logger.warning(f"Error guardando en memoria: {str(e)}")
        
        # Generar mensaje apropiado basado en completitud
        if not missing_fields:
            empresa = updated_info.get("nombre_empresa", "tu empresa")
            message = f"¡Perfecto! 🎉 Tengo toda la información de {empresa}. ¿En qué puedo ayudarte ahora?"
        elif len(missing_fields) < len(critical_fields):
            next_field_map = {
                "nombre_empresa": "¿Cuál es el nombre de tu empresa?",
                "ubicacion": "¿En qué ciudad o país opera tu negocio?",
                "productos_servicios_principales": "¿Qué productos o servicios principales ofreces?",
                "descripcion_negocio": "¿Podrías describir brevemente tu negocio?"
            }
            next_question = next_field_map.get(missing_fields[0], "¿Podrías darme más información sobre tu negocio?")
            message = f"Gracias por la información. {next_question}"
        else:
            message = "¡Hola! Me gustaría ayudarte con tu negocio. ¿Podrías contarme sobre tu empresa: nombre, qué productos/servicios ofreces y dónde opera?"
        
        return BusinessInfoUpdate(
            success=True,
            updated_info=updated_info,
            missing_fields=missing_fields,
            completeness_score=completeness,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error en update_business_info: {str(e)}")
        return BusinessInfoUpdate(
            success=False,
            updated_info=state.get("business_info", {}),
            missing_fields=["error"],
            completeness_score=0.0,
            message="Hubo un error procesando la información. ¿Podrías repetir?"
        )

@tool
def perform_market_research(
    state: Annotated[PYMESState, InjectedState],
    research_type: str = "general"
) -> MarketResearchResult:
    """
    Realiza investigación de mercado basada en la información empresarial.
    
    IMPORTANTE: Esta herramienta primero verifica que business_info esté completo.
    Si falta información crítica, devuelve un mensaje indicando qué falta.
    
    Usa esta herramienta cuando:
    - El usuario solicita investigación de mercado
    - Menciona palabras como "investiga", "analiza", "oportunidades", "competencia"
    - Quiere conocer tendencias de su sector
    
    Args:
        research_type: Tipo de investigación (general, competencia, oportunidades, tendencias)
    """
    try:
        logger.info(f"🔬 perform_market_research: Iniciando investigación tipo '{research_type}'...")
        
        # Acceder directamente al estado inyectado
        business_info = state.get("business_info", {})
        
        # 1. VALIDACIÓN: Verificar información crítica
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        missing_fields = [field for field in critical_fields if not business_info.get(field)]
        
        if missing_fields:
            missing_text = ", ".join(missing_fields)
            message = f"Para realizar investigación de mercado, necesito completar la información de tu negocio. Falta: {missing_text}. ¿Podrías proporcionarla?"
            
            return MarketResearchResult(
                success=False,
                research_content="",
                research_type=research_type,
                recommendations=[],
                message=message
            )
        
        # 2. INVESTIGACIÓN: Generar análisis de mercado
        empresa = business_info.get("nombre_empresa", "la empresa")
        sector = business_info.get("sector", business_info.get("productos_servicios_principales", ""))
        ubicacion = business_info.get("ubicacion", "")
        productos = business_info.get("productos_servicios_principales", "")
        
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7, max_tokens=150)  # Límite para WhatsApp
        
        research_prompts = {
            "general": f"""Eres un analista de mercado experto. Analiza las oportunidades para {empresa}:

EMPRESA: {empresa}
SECTOR: {sector} 
UBICACIÓN: {ubicacion}
PRODUCTOS/SERVICIOS: {productos}

Proporciona un análisis conciso con:
1. 2-3 oportunidades principales de crecimiento
2. 2-3 recomendaciones específicas y accionables

FORMATO: Respuesta directa, máximo 150 tokens, enfocada en acciones concretas.""",
            
            "competencia": f"""Analiza la competencia para {empresa} en {sector} en {ubicacion}.

Proporciona:
1. Principales competidores típicos en este sector
2. Estrategias para diferenciarse
3. Oportunidades de nicho

Máximo 150 tokens, recomendaciones accionables.""",
            
            "oportunidades": f"""Identifica oportunidades de mercado específicas para {empresa}:

CONTEXTO: {sector} en {ubicacion}
PRODUCTOS: {productos}

Enfócate en:
1. Mercados no atendidos
2. Tendencias emergentes
3. Expansión geográfica/digital

Máximo 150 tokens, oportunidades concretas.""",
            
            "tendencias": f"""Analiza tendencias actuales relevantes para {empresa} en {sector}.

Incluye:
1. Tendencias del sector que afectan a {productos}
2. Cambios en comportamiento del consumidor
3. Oportunidades tecnológicas

Máximo 150 tokens, trends accionables."""
        }
        
        prompt = research_prompts.get(research_type, research_prompts["general"])
        response = llm.invoke([{"role": "user", "content": prompt}])
        research_content = response.content
        
        # Generar recomendaciones específicas
        recommendations = [
            "Considerar expansión digital si no la tienes",
            "Analizar precios de competencia local",
            "Explorar alianzas estratégicas en tu sector"
        ]
        
        message = f"📊 **Análisis de mercado para {empresa}:**\n\n{research_content}"
        
        logger.info(f"✅ Investigación completada para {empresa}")
        
        return MarketResearchResult(
            success=True,
            research_content=research_content,
            research_type=research_type,
            recommendations=recommendations,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error en perform_market_research: {str(e)}")
        return MarketResearchResult(
            success=False,
            research_content="",
            research_type=research_type,
            recommendations=[],
            message="Hubo un error realizando la investigación. ¿Podrías intentar nuevamente?"
        )

@tool
def provide_business_consultation(
    state: Annotated[PYMESState, InjectedState],
    consultation_topic: str = "general"
) -> str:
    """
    Proporciona consultoría conversacional sobre temas específicos del negocio.
    
    Usa esta herramienta cuando:
    - El usuario hace preguntas específicas sobre su negocio
    - Solicita consejos o recomendaciones puntuales
    - Quiere discutir estrategias particulares
    - Pregunta sobre implementación de ideas
    
    Args:
        consultation_topic: Tema específico de consultoría (marketing, ventas, operaciones, etc.)
    """
    try:
        logger.info(f"💬 provide_business_consultation: Tema '{consultation_topic}'...")
        
        # Acceder directamente al estado inyectado
        messages = state.get("messages", [])
        business_info = state.get("business_info", {})
        
        # Obtener la pregunta del usuario desde el último mensaje
        user_question = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break
        
        empresa = business_info.get("nombre_empresa", "tu negocio")
        sector = business_info.get("sector", business_info.get("productos_servicios_principales", ""))
        
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7, max_tokens=150)
        
        prompt = f"""Eres un consultor empresarial experto ayudando al dueño de {empresa}.

CONTEXTO DEL NEGOCIO:
{business_info}

PREGUNTA DEL USUARIO:
{user_question}

TEMA DE CONSULTORÍA: {consultation_topic}

Proporciona una respuesta útil, específica y accionable:
- Máximo 150 tokens para WhatsApp
- Enfócate en consejos prácticos
- Usa el contexto del negocio para personalizar la respuesta
- Sé conversacional y directo"""
        
        response = llm.invoke([{"role": "user", "content": prompt}])
        consultation_response = response.content
        
        logger.info(f"✅ Consulta respondida para {empresa}")
        return consultation_response
        
    except Exception as e:
        logger.error(f"Error en provide_business_consultation: {str(e)}")
        return "Hubo un error procesando tu consulta. ¿Podrías reformular tu pregunta?"

# === HERRAMIENTAS AUXILIARES ===

@tool
def check_business_info_completeness(
    state: Annotated[PYMESState, InjectedState]
) -> Dict[str, Any]:
    """
    Verifica la completitud de la información empresarial actual.
    
    Útil para validar si se puede proceder con investigación o análisis avanzados.
    """
    business_info = state.get("business_info", {})
    
    critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
    optional_fields = ["sector", "desafios_principales", "anos_operacion", "num_empleados"]
    
    missing_critical = [field for field in critical_fields if not business_info.get(field)]
    missing_optional = [field for field in optional_fields if not business_info.get(field)]
    
    completeness = (len(critical_fields) - len(missing_critical)) / len(critical_fields)
    can_research = len(missing_critical) == 0
    
    return {
        "missing_critical": missing_critical,
        "missing_optional": missing_optional,
        "completeness_percentage": completeness,
        "can_start_research": can_research,
        "status": "complete" if can_research else "incomplete"
    }

# === LISTA DE HERRAMIENTAS PARA EL AGENTE CENTRAL ===

CENTRAL_AGENT_TOOLS = [
    update_business_info,
    perform_market_research,
    provide_business_consultation,
    check_business_info_completeness
] 