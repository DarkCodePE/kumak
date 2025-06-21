"""
Herramientas del Agente Central - Versión Mejorada con Deep Research
Incluye la nueva herramienta perform_deep_research que utiliza el equipo especializado
"""

import logging
import asyncio
from typing import Dict, Any, List, Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.graph.deep_research_system import perform_deep_research_analysis
from langgraph.prebuilt import InjectedState

logger = logging.getLogger(__name__)

# === MODELOS DE DATOS ===

class BusinessInfoResult(BaseModel):
    """Resultado de extracción de información empresarial."""
    success: bool = Field(description="Si la extracción fue exitosa")
    extracted_info: Dict[str, Any] = Field(description="Información extraída")
    updated_fields: List[str] = Field(description="Campos que se actualizaron")
    message: str = Field(description="Mensaje para el usuario")

class DeepResearchResult(BaseModel):
    """Resultado de investigación profunda con equipo especializado."""
    success: bool = Field(description="Si la investigación fue exitosa")
    research_type: str = Field(description="Tipo de investigación realizada")
    final_report: str = Field(description="Informe ejecutivo final")
    execution_summary: str = Field(description="Resumen de la ejecución")
    research_plan: List[str] = Field(description="Plan de investigación ejecutado")
    total_sources: int = Field(description="Número total de fuentes consultadas")
    message: str = Field(description="Mensaje para el usuario")

class ConsultationResult(BaseModel):
    """Resultado de consultoría empresarial."""
    success: bool = Field(description="Si la consultoría fue exitosa")
    consultation_type: str = Field(description="Tipo de consultoría")
    advice: str = Field(description="Consejo o recomendación")
    follow_up: List[str] = Field(description="Preguntas de seguimiento sugeridas")
    message: str = Field(description="Mensaje para el usuario")

# === HERRAMIENTAS PRINCIPALES ===

@tool
def update_business_info(
    state: Annotated[PYMESState, InjectedState],
    user_message: str
) -> BusinessInfoResult:
    """
    Extrae y actualiza información empresarial del mensaje del usuario.
    
    Usa esta herramienta cuando el usuario menciona:
    - Nombre de su empresa o negocio
    - Sector, industria o tipo de negocio
    - Productos o servicios que ofrece
    - Ubicación donde opera
    - Desafíos o problemas que enfrenta
    - Años de operación, empleados, etc.
    
    Args:
        user_message: El mensaje del usuario del cual extraer información
    """
    try:
        logger.info(f"🔍 update_business_info: Extrayendo información de: '{user_message}'")
        
        current_info = state.get("business_info", {})
        
        # LLM para extracción estructurada
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1, max_tokens=200)
        
        extraction_prompt = f"""Analiza el siguiente mensaje y extrae TODA la información empresarial mencionada:

MENSAJE: "{user_message}"

INFORMACIÓN ACTUAL: {current_info}

Extrae y/o actualiza la siguiente información si está presente:
- nombre_empresa: Nombre del negocio/empresa
- sector: Industria o sector (ej: "Restaurantes", "Retail", "Servicios")
- productos_servicios_principales: Qué vende o ofrece
- ubicacion: Ciudad, región o zona donde opera
- descripcion_negocio: Descripción general del negocio
- desafios_principales: Problemas o desafíos mencionados
- anos_operacion: Años funcionando (si se menciona)
- num_empleados: Número de empleados (si se menciona)

Devuelve solo los campos que encuentres en el mensaje en formato JSON.
Si no encuentras información empresarial relevante, devuelve {{}}.

FORMATO:
{{"nombre_empresa": "valor", "sector": "valor", ...}}"""

        response = llm.invoke([{"role": "user", "content": extraction_prompt}])
        
        # Parsear respuesta JSON
        try:
            import json
            extracted_data = json.loads(response.content.strip())
        except:
            # Fallback si no es JSON válido
            extracted_data = {}
        
        # Actualizar información existente
        updated_fields = []
        for key, value in extracted_data.items():
            if value and value.strip():  # Solo actualizar valores no vacíos
                current_info[key] = value.strip()
                updated_fields.append(key)
        
        # Actualizar el estado
        state["business_info"] = current_info
        
        if updated_fields:
            fields_text = ", ".join(updated_fields)
            message = f"✅ Información actualizada: {fields_text}. ¿Hay algo más sobre tu negocio que quieras compartir?"
        else:
            message = "No encontré información empresarial nueva en tu mensaje. ¿Podrías contarme más sobre tu negocio?"
        
        logger.info(f"✅ Información extraída: {len(updated_fields)} campos actualizados")
        
        return BusinessInfoResult(
            success=len(updated_fields) > 0,
            extracted_info=extracted_data,
            updated_fields=updated_fields,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error en update_business_info: {str(e)}")
        return BusinessInfoResult(
            success=False,
            extracted_info={},
            updated_fields=[],
            message="Hubo un error procesando la información. ¿Podrías intentar nuevamente?"
        )

@tool
async def perform_deep_research(
    state: Annotated[PYMESState, InjectedState],
    research_topic: str = "análisis general de mercado"
) -> DeepResearchResult:
    """
    Realiza investigación de mercado profunda usando un equipo especializado de Planner + Workers paralelos.
    
    IMPORTANTE: Esta herramienta verifica automáticamente que business_info esté completo.
    Si falta información crítica, pedirá completarla antes de investigar.
    
    El equipo especializado funciona así:
    1. PLANNER: Crea un plan de 4-6 consultas específicas basadas en el negocio
    2. WORKERS: Ejecutan búsquedas web en paralelo 
    3. SYNTHESIZER: Combina resultados en un informe ejecutivo
    
    Usa esta herramienta cuando:
    - El usuario solicita investigación de mercado
    - Menciona palabras como "investiga", "analiza", "oportunidades", "competencia"  
    - Quiere conocer tendencias de su sector
    - Necesita análisis competitivo o estrategias de crecimiento
    
    Args:
        research_topic: Tipo de investigación específica (ej: "competencia", "oportunidades", "tendencias")
    """
    try:
        logger.info(f"🚀 perform_deep_research: Iniciando investigación profunda sobre '{research_topic}'...")
        
        # Acceder al estado inyectado
        business_info = state.get("business_info", {})
        
        # 1. VALIDACIÓN: Verificar información crítica
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        missing_fields = [field for field in critical_fields if not business_info.get(field)]
        
        if missing_fields:
            missing_text = ", ".join(missing_fields)
            message = f"Para realizar investigación profunda, necesito completar la información de tu negocio. Falta: {missing_text}. ¿Podrías proporcionarla?"
            
            return DeepResearchResult(
                success=False,
                research_type=research_topic,
                final_report="",
                execution_summary="Validación fallida - información incompleta",
                research_plan=[],
                total_sources=0,
                message=message
            )
        
        # 2. PREPARAR CONTEXTO para el equipo de investigación
        empresa = business_info.get("nombre_empresa", "")
        
        # Formatear el tópico de investigación con contexto empresarial
        contextualized_topic = f"{research_topic} para {empresa}"
        
        logger.info(f"🧠 Delegando investigación al equipo especializado: Planner + Workers paralelos")
        
        # 3. EJECUTAR INVESTIGACIÓN PROFUNDA con el equipo especializado
        research_result = await perform_deep_research_analysis(
            research_topic=contextualized_topic,
            business_context=business_info
        )
        
        # 4. PROCESAR RESULTADOS
        if research_result["success"]:
            final_report = research_result["final_report"]
            
            # Formatear mensaje para WhatsApp/usuario
            message = f"🔍 **INVESTIGACIÓN PROFUNDA COMPLETADA**\n\n📊 **Análisis para {empresa}:**\n\n{final_report}"
            
            logger.info(f"✅ Investigación completada: {research_result['total_sources']} fuentes, {len(research_result['research_plan'])} consultas")
            
            return DeepResearchResult(
                success=True,
                research_type=research_topic,
                final_report=final_report,
                execution_summary=research_result["execution_summary"],
                research_plan=research_result["research_plan"],
                total_sources=research_result["total_sources"],
                message=message
            )
        else:
            # Error en la investigación
            logger.error(f"❌ Error en investigación profunda: {research_result.get('final_report', 'Error desconocido')}")
            
            return DeepResearchResult(
                success=False,
                research_type=research_topic,
                final_report=research_result["final_report"],
                execution_summary=research_result["execution_summary"],
                research_plan=[],
                total_sources=0,
                message="Hubo un error durante la investigación profunda. ¿Podrías intentar con un tema más específico?"
            )
        
    except Exception as e:
        logger.error(f"Error en perform_deep_research: {str(e)}")
        return DeepResearchResult(
            success=False,
            research_type=research_topic,
            final_report="",
            execution_summary="Error en la ejecución",
            research_plan=[],
            total_sources=0,
            message="Hubo un error realizando la investigación. ¿Podrías intentar nuevamente?"
        )

@tool
def provide_business_consultation(
    state: Annotated[PYMESState, InjectedState],
    question: str
) -> ConsultationResult:
    """
    Proporciona consultoría empresarial conversacional basada en la información del negocio.
    
    Usa esta herramienta cuando:
    - El usuario hace preguntas específicas sobre su negocio
    - Solicita consejos o recomendaciones
    - Tiene dudas sobre estrategias o decisiones
    - Necesita orientación general empresarial
    
    Args:
        question: La pregunta o consulta específica del usuario
    """
    try:
        logger.info(f"💼 provide_business_consultation: Consultando sobre '{question}'")
        
        business_info = state.get("business_info", {})
        
        # LLM para consultoría contextual
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.5, max_tokens=200)
        
        # Construir contexto empresarial si está disponible
        if business_info:
            empresa = business_info.get("nombre_empresa", "tu negocio")
            sector = business_info.get("sector", "")
            ubicacion = business_info.get("ubicacion", "")
            productos = business_info.get("productos_servicios_principales", "")
            desafios = business_info.get("desafios_principales", "")
            
            business_context = f"""
CONTEXTO DE LA EMPRESA:
- Empresa: {empresa}
- Sector: {sector}
- Ubicación: {ubicacion}  
- Productos/Servicios: {productos}
- Desafíos: {desafios}
"""
        else:
            business_context = "CONTEXTO: Sin información específica del negocio disponible."
        
        consultation_prompt = f"""Eres un consultor empresarial experto en PYMEs.

{business_context}

PREGUNTA/CONSULTA: {question}

Proporciona:
1. Consejo específico y accionable
2. 2-3 recomendaciones concretas
3. 1-2 preguntas de seguimiento para profundizar

CRITERIOS:
- Respuesta concisa (máximo 150 tokens para WhatsApp)
- Enfoque práctico y realista
- Considerar el contexto empresarial disponible
- Tono profesional pero accesible"""

        response = llm.invoke([{"role": "user", "content": consultation_prompt}])
        advice = response.content
        
        # Generar preguntas de seguimiento
        follow_up = [
            "¿Te gustaría que profundice en algún aspecto específico?",
            "¿Hay algún desafío particular que te preocupe más?"
        ]
        
        message = f"💡 **CONSULTORÍA EMPRESARIAL**\n\n{advice}"
        
        logger.info("✅ Consultoría proporcionada exitosamente")
        
        return ConsultationResult(
            success=True,
            consultation_type="consultoría general",
            advice=advice,
            follow_up=follow_up,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error en provide_business_consultation: {str(e)}")
        return ConsultationResult(
            success=False,
            consultation_type="error",
            advice="",
            follow_up=[],
            message="Hubo un error procesando tu consulta. ¿Podrías reformular tu pregunta?"
        )

@tool
def check_business_info_completeness(
    state: Annotated[PYMESState, InjectedState]
) -> Dict[str, Any]:
    """
    Verifica la completitud de la información empresarial actual.
    
    Útil para validar si se puede proceder con investigación o análisis avanzados.
    """
    try:
        business_info = state.get("business_info", {})
        
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        optional_fields = ["sector", "desafios_principales", "anos_operacion", "num_empleados"]
        
        missing_critical = [field for field in critical_fields if not business_info.get(field)]
        missing_optional = [field for field in optional_fields if not business_info.get(field)]
        
        completeness = (len(critical_fields) - len(missing_critical)) / len(critical_fields)
        can_research = len(missing_critical) == 0
        
        status_message = ""
        if can_research:
            status_message = "✅ Información completa - Lista para investigación profunda"
        else:
            missing_text = ", ".join(missing_critical)
            status_message = f"⚠️ Información incompleta - Falta: {missing_text}"
        
        return {
            "missing_critical": missing_critical,
            "missing_optional": missing_optional,
            "completeness_percentage": completeness,
            "can_start_deep_research": can_research,
            "status": "complete" if can_research else "incomplete",
            "status_message": status_message
        }
        
    except Exception as e:
        logger.error(f"Error en check_business_info_completeness: {str(e)}")
        return {
            "missing_critical": [],
            "missing_optional": [],
            "completeness_percentage": 0.0,
            "can_start_deep_research": False,
            "status": "error",
            "status_message": "Error verificando completitud de información"
        }

# === LISTA DE HERRAMIENTAS MEJORADAS ===

ENHANCED_CENTRAL_AGENT_TOOLS = [
    update_business_info,
    perform_deep_research,  # 🚀 NUEVA: Sistema de investigación profunda con equipo especializado
    provide_business_consultation,
    check_business_info_completeness
]

# === FUNCIÓN DE COMPARACIÓN ===

def get_tool_comparison() -> Dict[str, Any]:
    """
    Compara las herramientas originales vs las mejoradas.
    """
    return {
        "enhanced_tools": {
            "perform_deep_research": {
                "description": "Sistema Map-Reduce con Planner + Workers paralelos + Synthesizer",
                "capabilities": [
                    "Plan de investigación inteligente y contextual",
                    "Búsquedas web paralelas (4-6 consultas simultáneas)",
                    "Síntesis automática en informe ejecutivo estructurado",
                    "Validación automática de prerrequisitos",
                    "Métricas de ejecución (fuentes consultadas, éxito de búsquedas)"
                ],
                "advantages": [
                    "Investigación más profunda y completa",
                    "Paralelización reduce tiempo de ejecución",
                    "Informes más estructurados y accionables",
                    "Mayor cobertura de fuentes y perspectivas"
                ]
            }
        },
        "original_tools": {
            "perform_market_research": {
                "description": "Investigación simple con LLM + validación básica",
                "limitations": [
                    "Una sola búsqueda por ejecución",
                    "Análisis menos profundo",
                    "No paralelización",
                    "Informes más básicos"
                ]
            }
        }
    } 