import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState, BusinessInfo

logger = logging.getLogger(__name__)

# Prompts para la extracción de información
BUSINESS_INFO_EXTRACTION_PROMPT = """
Eres un consultor especializado en PYMES que ayuda a recopilar información esencial del negocio.

Tu objetivo es extraer la siguiente información del usuario de manera conversacional y amigable:

INFORMACIÓN REQUERIDA:
1. **Nombre de la empresa**: Nombre oficial o comercial del negocio
2. **Sector**: Industria o sector específico (ej: "Restaurantes", "Software (SaaS)", "Retail de moda")
3. **Productos/Servicios principales**: Lista de los principales productos o servicios que ofrece
4. **Desafíos principales**: Principales problemas o obstáculos que enfrenta el negocio
5. **Ubicación**: Dónde opera el negocio (ej: "Lima, Perú", "Online", "Nacional")
6. **Descripción del negocio**: Breve descripción de qué hace la empresa y cómo opera

INFORMACIÓN OPCIONAL:
- Años de operación
- Número de empleados

INSTRUCCIONES:
- Haz UNA pregunta específica a la vez
- Sé conversacional y empático
- Si el usuario da información parcial, pide más detalles específicos
- Confirma la información antes de continuar al siguiente punto
- Usa ejemplos para ayudar al usuario a entender qué tipo de información necesitas

INFORMACIÓN YA RECOPILADA:
{business_info_current}

SIGUIENTE PREGUNTA A HACER:
{next_question_focus}

Historial de conversación:
{conversation_history}

Mensaje actual del usuario: {user_message}

Responde de manera natural y enfócate en la siguiente información que necesitas recopilar.
"""

class BusinessInfoExtractor:
    """Extractor de información del negocio con validación paso a paso."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        self.required_fields = [
            "nombre_empresa",
            "sector", 
            "productos_servicios_principales",
            "desafios_principales",
            "ubicacion",
            "descripcion_negocio"
        ]
    
    def get_missing_fields(self, business_info: Dict[str, Any]) -> List[str]:
        """Obtiene los campos que faltan por completar."""
        missing = []
        for field in self.required_fields:
            if not business_info.get(field):
                missing.append(field)
        return missing
    
    def get_next_question_focus(self, missing_fields: List[str]) -> str:
        """Determina qué pregunta hacer a continuación."""
        if not missing_fields:
            return "validacion_final"
        
        field_questions = {
            "nombre_empresa": "el nombre de la empresa",
            "sector": "el sector o industria específica",
            "productos_servicios_principales": "los productos o servicios principales",
            "desafios_principales": "los principales desafíos del negocio",
            "ubicacion": "la ubicación donde opera",
            "descripcion_negocio": "una descripción general del negocio"
        }
        
        return field_questions.get(missing_fields[0], "información general")
    
    def extract_info_from_response(self, user_message: str, current_focus: str, business_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae información específica del mensaje del usuario."""
        extraction_prompt = f"""
        Extrae información específica del mensaje del usuario para el campo: {current_focus}
        
        Mensaje del usuario: {user_message}
        Información actual: {business_info}
        
        Devuelve SOLO la información nueva extraída en formato JSON.
        Si no hay información relevante, devuelve un dict vacío.
        
        Ejemplo para productos_servicios_principales: {{"productos_servicios_principales": ["servicio1", "servicio2"]}}
        """
        
        # Simplificado: en producción usarías un LLM con schema structured output
        # Por ahora, parseamos manualmente según el focus
        updated_info = business_info.copy()
        
        if current_focus == "nombre_empresa" and not updated_info.get("nombre_empresa"):
            # Extraer nombre de empresa del mensaje
            lines = user_message.strip().split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ["empresa", "negocio", "llamo", "llama"]):
                    # Lógica simple de extracción
                    updated_info["nombre_empresa"] = line.strip()
                    break
            if not updated_info.get("nombre_empresa"):
                updated_info["nombre_empresa"] = user_message.strip()
        
        elif current_focus == "sector" and not updated_info.get("sector"):
            updated_info["sector"] = user_message.strip()
        
        elif current_focus == "productos_servicios_principales":
            if not updated_info.get("productos_servicios_principales"):
                updated_info["productos_servicios_principales"] = []
            # Dividir por comas o líneas
            services = [s.strip() for s in user_message.replace('\n', ',').split(',') if s.strip()]
            updated_info["productos_servicios_principales"].extend(services)
        
        elif current_focus == "desafios_principales":
            if not updated_info.get("desafios_principales"):
                updated_info["desafios_principales"] = []
            challenges = [s.strip() for s in user_message.replace('\n', ',').split(',') if s.strip()]
            updated_info["desafios_principales"].extend(challenges)
        
        elif current_focus == "ubicacion" and not updated_info.get("ubicacion"):
            updated_info["ubicacion"] = user_message.strip()
        
        elif current_focus == "descripcion_negocio" and not updated_info.get("descripcion_negocio"):
            updated_info["descripcion_negocio"] = user_message.strip()
        
        return updated_info


def extract_business_info_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo principal para extraer información del negocio.
    Maneja el flujo de preguntas y extracción paso a paso.
    """
    try:
        logger.info("Iniciando extracción de información del negocio")
        
        extractor = BusinessInfoExtractor()
        business_info = state.get("business_info", {})
        messages = state.get("messages", [])
        
        # Obtener el último mensaje del usuario
        user_message = ""
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, HumanMessage):
                user_message = last_message.content
        
        # Determinar qué información falta
        missing_fields = extractor.get_missing_fields(business_info)
        next_question_focus = extractor.get_next_question_focus(missing_fields)
        
        logger.info(f"Campos faltantes: {missing_fields}")
        logger.info(f"Siguiente enfoque: {next_question_focus}")
        
        # Si ya tenemos toda la información, ir a validación
        if not missing_fields:
            return validate_business_info_node(state)
        
        # Extraer información del mensaje actual si hay contexto
        if user_message and len(messages) > 1:  # No es el primer mensaje
            current_focus = extractor.get_next_question_focus(missing_fields)
            business_info = extractor.extract_info_from_response(
                user_message, current_focus, business_info
            )
            logger.info(f"Información actualizada: {business_info}")
        
        # Generar la siguiente pregunta
        conversation_history = "\n".join([
            f"{'Usuario' if isinstance(msg, HumanMessage) else 'Asistente'}: {msg.content}"
            for msg in messages[-5:]  # Últimos 5 mensajes
        ])
        
        prompt = ChatPromptTemplate.from_template(BUSINESS_INFO_EXTRACTION_PROMPT)
        chain = prompt | extractor.llm
        
        response = chain.invoke({
            "business_info_current": str(business_info),
            "next_question_focus": next_question_focus,
            "conversation_history": conversation_history,
            "user_message": user_message
        })
        
        # Actualizar el estado
        return {
            "business_info": business_info,
            "stage": "info_gathering",
            "messages": [AIMessage(content=response.content)]
        }
        
    except Exception as e:
        logger.error(f"Error en extract_business_info_node: {str(e)}")
        return {
            "messages": [AIMessage(content="Disculpa, hubo un error. ¿Podrías repetir tu respuesta?")]
        }


def validate_business_info_node(state: PYMESState) -> Command:
    """
    Valida que la información recopilada esté completa y correcta.
    Usa human-in-the-loop para confirmación final.
    """
    try:
        logger.info("Validando información del negocio")
        
        business_info = state.get("business_info", {})
        
        # Generar resumen de la información recopilada
        summary_parts = []
        if business_info.get("nombre_empresa"):
            summary_parts.append(f"🏢 **Empresa**: {business_info['nombre_empresa']}")
        if business_info.get("sector"):
            summary_parts.append(f"🏭 **Sector**: {business_info['sector']}")
        if business_info.get("ubicacion"):
            summary_parts.append(f"📍 **Ubicación**: {business_info['ubicacion']}")
        if business_info.get("productos_servicios_principales"):
            services = ", ".join(business_info['productos_servicios_principales'])
            summary_parts.append(f"💼 **Productos/Servicios**: {services}")
        if business_info.get("desafios_principales"):
            challenges = ", ".join(business_info['desafios_principales'])
            summary_parts.append(f"⚠️ **Desafíos**: {challenges}")
        if business_info.get("descripcion_negocio"):
            summary_parts.append(f"📝 **Descripción**: {business_info['descripcion_negocio']}")
        
        summary_text = "\n".join(summary_parts)
        
        validation_message = f"""
✅ **INFORMACIÓN RECOPILADA COMPLETADA**

He recopilado la siguiente información sobre tu negocio:

{summary_text}

🔍 **¿Es correcta toda esta información?**

Responde:
- ✅ **"SÍ"** si toda la información es correcta
- ✏️ **"CORREGIR [campo]"** si necesitas cambiar algo específico
- 📝 **"AGREGAR [información]"** si falta algo importante

*Por ejemplo: "CORREGIR sector" o "AGREGAR más servicios"*
"""

        # Usar interrupt para esperar confirmación del usuario
        user_validation = interrupt({
            "message": validation_message,
            "business_info": business_info,
            "stage": "validation"
        })
        
        logger.info(f"Validación recibida: {user_validation}")
        
        # Procesar la respuesta de validación
        user_response = user_validation.lower().strip()
        
        if user_response in ["sí", "si", "yes", "correcto", "ok", "está bien"]:
            # Información validada, continuar al siguiente paso
            logger.info("Información del negocio validada correctamente")
            return Command(
                update={
                    "business_info": business_info,
                    "stage": "analysis",
                    "messages": [AIMessage(content="¡Perfecto! He registrado toda la información de tu negocio. Ahora procederé a analizar oportunidades de crecimiento.")]
                },
                goto="research_subgraph"  # Ir al sub-grafo de investigación
            )
        
        elif "corregir" in user_response or "cambiar" in user_response:
            # El usuario quiere corregir algo, volver a la extracción
            logger.info("Usuario quiere corregir información")
            return Command(
                update={
                    "messages": [HumanMessage(content=user_validation)]
                },
                goto="extract_business_info"
            )
        
        else:
            # Respuesta ambigua, pedir clarificación
            return Command(
                update={
                    "messages": [AIMessage(content="No entendí tu respuesta. Por favor responde 'SÍ' si la información es correcta, o 'CORREGIR [campo]' si necesitas cambiar algo.")]
                },
                goto="validate_business_info"
            )
    
    except Exception as e:
        logger.error(f"Error en validate_business_info_node: {str(e)}")
        return Command(
            update={
                "messages": [AIMessage(content="Hubo un error en la validación. ¿Podrías confirmar si la información mostrada es correcta?")]
            },
            goto="validate_business_info"
        )


def save_to_long_term_memory(state: PYMESState) -> Dict[str, Any]:
    """
    Guarda la información validada en memoria a largo plazo.
    """
    try:
        logger.info("Guardando información en memoria a largo plazo")
        
        business_info = state.get("business_info", {})
        messages = state.get("messages", [])
        
        # Obtener thread_id del estado o de los mensajes
        thread_id = state.get("thread_id")
        if not thread_id and messages:
            # Intentar extraer thread_id de algún mensaje con metadata
            for msg in messages:
                if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('thread_id'):
                    thread_id = msg.additional_kwargs['thread_id']
                    break
        
        if not thread_id:
            thread_id = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.warning(f"No se encontró thread_id, usando temporal: {thread_id}")
        
        # Usar el servicio de memoria para guardar
        from app.services.memory_service import get_memory_service
        memory_service = get_memory_service()
        
        success = memory_service.save_business_info(thread_id, business_info)
        
        if success:
            logger.info("Información guardada exitosamente en memoria a largo plazo")
            return {
                "stage": "info_completed",
                "context": f"Información del negocio guardada: {business_info.get('nombre_empresa', 'N/A')}"
            }
        else:
            logger.error("Error guardando información en memoria a largo plazo")
            return {
                "stage": "error",
                "context": "Error guardando información"
            }
        
    except Exception as e:
        logger.error(f"Error guardando en memoria a largo plazo: {str(e)}")
        return {
            "stage": "error", 
            "context": f"Error: {str(e)}"
        }


def create_business_info_extraction_graph():
    """
    Crea el sub-grafo para extracción de información del negocio.
    """
    try:
        # Crear el grafo
        workflow = StateGraph(PYMESState)
        
        # Agregar nodos
        workflow.add_node("extract_business_info", extract_business_info_node)
        workflow.add_node("validate_business_info", validate_business_info_node)
        workflow.add_node("save_to_memory", save_to_long_term_memory)
        
        # Definir flujo
        workflow.add_edge(START, "extract_business_info")
        workflow.add_edge("extract_business_info", "validate_business_info")
        workflow.add_edge("validate_business_info", "save_to_memory")
        workflow.add_edge("save_to_memory", END)
        
        logger.info("Sub-grafo de extracción de información creado exitosamente")
        return workflow.compile()
        
    except Exception as e:
        logger.error(f"Error creando sub-grafo de extracción: {str(e)}")
        raise 