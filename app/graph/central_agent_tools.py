"""
Herramientas Refinadas para el Agente Central - Arquitectura Profesional
Usando InjectedState para acceso directo al estado y mejores prácticas de LangGraph.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

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
    state: Annotated[PYMESState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    nombre_empresa: Optional[str] = None,
    sector: Optional[str] = None,
    productos_servicios_principales: Optional[str] = None,
    ubicacion: Optional[str] = None,
    descripcion_negocio: Optional[str] = None,
    desafios_principales: Optional[str] = None,
    anos_operacion: Optional[int] = None,
    num_empleados: Optional[int] = None
) -> Command:
    """
    Actualiza campos específicos de información empresarial.
    
    IMPORTANTE: Solo pasa los campos que necesitas actualizar basándote en lo que el usuario acaba de mencionar.
    Los campos que no pases (None) se mantendrán con su valor actual.
    
    Args:
        nombre_empresa: Nombre de la empresa
        sector: Sector empresarial (ej: "Pizzería", "Software", "Retail")
        productos_servicios_principales: Productos o servicios principales
        ubicacion: Ubicación de la empresa
        descripcion_negocio: Breve descripción del negocio
        desafios_principales: Principales desafíos que enfrenta
        anos_operacion: Años de operación (número)
        num_empleados: Número de empleados (número)
    """
    try:
        logger.info("🔍 update_business_info: Actualizando campos específicos...")
        
        # Obtener información empresarial actual
        current_business_info = state.get("business_info", {}) or {}
        
        # Crear información actualizada: empezar con la actual y actualizar campos especificados
        updated_info = current_business_info.copy()
        
        # Actualizar solo los campos que el LLM ha especificado (no None)
        updates_made = []
        
        if nombre_empresa is not None:
            updated_info["nombre_empresa"] = nombre_empresa
            updates_made.append("nombre_empresa")
            
        if sector is not None:
            updated_info["sector"] = sector
            updates_made.append("sector")
            
        if productos_servicios_principales is not None:
            # Convertir string a lista si es necesario
            if isinstance(productos_servicios_principales, str):
                # Split por comas y limpiar espacios
                productos_list = [p.strip() for p in productos_servicios_principales.split(',')]
            else:
                productos_list = productos_servicios_principales
            updated_info["productos_servicios_principales"] = productos_list
            updates_made.append("productos_servicios_principales")
            
        if ubicacion is not None:
            updated_info["ubicacion"] = ubicacion
            updates_made.append("ubicacion")
            
        if descripcion_negocio is not None:
            updated_info["descripcion_negocio"] = descripcion_negocio
            updates_made.append("descripcion_negocio")
            
        if desafios_principales is not None:
            # Convertir string a lista si es necesario
            if isinstance(desafios_principales, str):
                # Split por comas y limpiar espacios
                desafios_list = [d.strip() for d in desafios_principales.split(',')]
            else:
                desafios_list = desafios_principales
            updated_info["desafios_principales"] = desafios_list
            updates_made.append("desafios_principales")
            
        if anos_operacion is not None:
            updated_info["anos_operacion"] = anos_operacion
            updates_made.append("anos_operacion")
            
        if num_empleados is not None:
            updated_info["num_empleados"] = num_empleados
            updates_made.append("num_empleados")
        
        # Evaluar completitud
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        missing_fields = [field for field in critical_fields if not updated_info.get(field)]
        completeness = (len(critical_fields) - len(missing_fields)) / len(critical_fields)
        
        # Generar mensaje apropiado
        if updates_made:
            if not missing_fields:
                empresa = updated_info.get("nombre_empresa", "tu empresa")
                message = f"¡Perfecto! 🎉 Información de {empresa} actualizada correctamente."
            else:
                message = f"Información actualizada: {', '.join(updates_made)}. ¡Gracias!"
        else:
            message = "No se especificaron campos para actualizar."
        
        # DEBUG: Mostrar qué información se está guardando
        logger.info(f"💾 DEBUG - Actualizando campos: {updates_made}")
        logger.info(f"📊 DEBUG - Información actualizada: {updated_info}")
        
        # CLAVE: Actualizar el estado del grafo usando Command
        tool_message = f"success=True updated_info={updated_info} missing_fields={missing_fields} completeness_score={completeness:.2f} message='{message}'"
        
        return Command(
            update={
                "business_info": updated_info,  # Actualizar información empresarial
                "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)]
            }
        )
        
    except Exception as e:
        logger.error(f"Error en update_business_info: {str(e)}")
        tool_message = f"success=False updated_info={state.get('business_info', {}) or {}} missing_fields=['error'] completeness_score=0.0 message='Hubo un error actualizando la información. ¿Podrías intentar nuevamente?'"
        
        return Command(
            update={
                "business_info": state.get("business_info", {}) or {},
                "messages": [ToolMessage(content=tool_message, tool_call_id=tool_call_id)]
            }
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
        
        # Acceder directamente al estado inyectado con valores por defecto
        business_info = state.get("business_info", {}) or {}
        
        # DEBUG: Mostrar información empresarial actual
        logger.info(f"📋 DEBUG - business_info actual: {business_info}")
        
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
        sector = business_info.get("sector", "")
        ubicacion = business_info.get("ubicacion", "")
        
        # Manejar productos_servicios_principales como lista o string
        productos_raw = business_info.get("productos_servicios_principales", "")
        if isinstance(productos_raw, list):
            productos = ", ".join(productos_raw)
        else:
            productos = productos_raw
        
        # Si no hay sector, usar los productos como contexto
        if not sector and productos:
            sector = productos
        
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
        
        # Acceder directamente al estado inyectado con valores por defecto
        messages = state.get("messages", [])
        business_info = state.get("business_info", {}) or {}
        
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
    business_info = state.get("business_info", {}) or {}
    
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