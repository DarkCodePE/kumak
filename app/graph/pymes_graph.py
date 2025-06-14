import logging
from typing import Literal, Dict, Any
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.graph.nodes import generate_response, human_feedback, end_node, tools
from app.graph.business_info_extraction import (
    extract_business_info_node, 
    validate_business_info_node, 
    save_to_long_term_memory
)
from app.graph.research_subgraph import (
    research_opportunities_node, 
    validate_research_results_node
)
from app.database.postgres import get_postgres_saver, get_postgres_store
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


def determine_initial_flow(state: PYMESState) -> Literal["extract_business_info", "generate_response"]:
    """
    Determina si necesitamos recopilar información del negocio o si ya podemos conversar.
    """
    business_info = state.get("business_info", {})
    stage = state.get("stage", "info_gathering")
    
    # Si no tenemos información básica del negocio, iniciar extracción
    required_fields = ["nombre_empresa", "sector", "productos_servicios_principales", "ubicacion"]
    missing_fields = [field for field in required_fields if not business_info.get(field)]
    
    if missing_fields and stage in ["info_gathering", None]:
        logger.info(f"Información faltante del negocio: {missing_fields}. Iniciando extracción.")
        return "extract_business_info"
    else:
        logger.info("Información del negocio disponible. Continuando con conversación normal.")
        return "generate_response"


def route_after_extraction(state: PYMESState) -> Literal["validate_business_info", "research_opportunities"]:
    """
    Ruta después de la extracción de información.
    """
    stage = state.get("stage", "")
    
    if stage == "info_gathering":
        return "validate_business_info"
    elif stage == "research_needed":
        return "research_opportunities"
    else:
        return "validate_business_info"


def route_after_validation(state: PYMESState) -> Literal["save_to_memory", "extract_business_info"]:
    """
    Ruta después de la validación de información del negocio.
    """
    stage = state.get("stage", "")
    
    if stage == "analysis":
        return "save_to_memory"
    else:
        return "extract_business_info"  # Volver a extraer si necesita correcciones


def route_after_memory_save(state: PYMESState) -> Literal["research_opportunities", "generate_response"]:
    """
    Ruta después de guardar en memoria.
    """
    stage = state.get("stage", "")
    
    if stage == "info_completed":
        return "research_opportunities"
    else:
        return "generate_response"


def route_after_research(state: PYMESState) -> Literal["validate_research_results", "generate_response"]:
    """
    Ruta después de la investigación.
    """
    stage = state.get("stage", "")
    
    if stage == "research_completed":
        return "validate_research_results"
    else:
        return "generate_response"


def route_conversation_flow(state: PYMESState) -> Literal["action", "human_feedback"]:
    """
    Ruta el flujo de conversación normal (igual que el chat_graph original).
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    # Si el último mensaje es de la IA y tiene llamadas a herramientas, ir al nodo de acción
    if isinstance(last_message, AIMessage) and getattr(last_message, 'tool_calls', None) and last_message.tool_calls:
        logger.info("Routing: LLM solicitó herramientas -> action")
        return "action"
    # De lo contrario, ir a feedback humano
    else:
        logger.info("Routing: LLM generó respuesta directa -> human_feedback")
        return "human_feedback"


def welcome_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo de bienvenida que inicia el proceso de recopilación de información.
    """
    try:
        logger.info("Iniciando proceso PYMES con mensaje de bienvenida")
        
        # Verificar si ya tenemos información del negocio
        business_info = state.get("business_info", {})
        
        if business_info and business_info.get("nombre_empresa"):
            # Ya tenemos información, saludar y ofrecer ayuda
            welcome_message = f"""
¡Hola! Veo que ya tengo información sobre **{business_info.get('nombre_empresa')}**.

¿En qué puedo ayudarte hoy?
- 🔍 **Investigar nuevas oportunidades** de crecimiento
- 📈 **Generar un plan de acción** específico
- 💬 **Conversar** sobre desafíos o dudas específicas
- ✏️ **Actualizar información** del negocio

¿Qué te gustaría hacer?
"""
        else:
            # No tenemos información, iniciar proceso de recopilación
            welcome_message = """
¡Hola! Soy tu asistente especializado en PYMES 🚀

Te ayudo a identificar oportunidades de crecimiento y desarrollar estrategias específicas para tu negocio.

Para comenzar, necesito conocer algunos detalles básicos sobre tu empresa. Este proceso es rápido y me permitirá brindarte recomendaciones personalizadas.

📝 **¿Podrías contarme el nombre de tu empresa y a qué se dedica?**

*Por ejemplo: "Mi empresa se llama [Nombre] y nos dedicamos a [actividad principal]"*
"""
        
        return {
            "messages": [AIMessage(content=welcome_message)],
            "stage": "info_gathering" if not business_info.get("nombre_empresa") else "conversation"
        }
        
    except Exception as e:
        logger.error(f"Error en welcome_node: {str(e)}")
        return {
            "messages": [AIMessage(content="¡Hola! Soy tu asistente para PYMES. ¿Cómo puedo ayudarte hoy?")],
            "stage": "conversation"
        }


def create_pymes_graph():
    """
    Crea el grafo principal de PYMES con todos los sub-grafos integrados.
    """
    try:
        # Crear el grafo
        workflow = StateGraph(PYMESState)
        
        # Crear herramientas
        tool_node_executor = ToolNode(tools)
        
        # === NODOS PRINCIPALES ===
        workflow.add_node("welcome", welcome_node)
        workflow.add_node("extract_business_info", extract_business_info_node)
        workflow.add_node("validate_business_info", validate_business_info_node)
        workflow.add_node("save_to_memory", save_to_long_term_memory)
        workflow.add_node("research_opportunities", research_opportunities_node)
        workflow.add_node("validate_research_results", validate_research_results_node)
        
        # === NODOS DE CONVERSACIÓN ===
        workflow.add_node("generate_response", generate_response)
        workflow.add_node("action", tool_node_executor)
        workflow.add_node("human_feedback", human_feedback)
        workflow.add_node("end_node", end_node)
        
        # === FLUJO PRINCIPAL ===
        
        # 1. Inicio -> Bienvenida
        workflow.add_edge(START, "welcome")
        
        # 2. Bienvenida -> Determinar si extraer info o conversar
        workflow.add_conditional_edges(
            "welcome",
            determine_initial_flow,
            {
                "extract_business_info": "extract_business_info",
                "generate_response": "generate_response"
            }
        )
        
        # 3. Extracción de información -> Validación
        workflow.add_conditional_edges(
            "extract_business_info",
            route_after_extraction,
            {
                "validate_business_info": "validate_business_info",
                "research_opportunities": "research_opportunities"
            }
        )
        
        # 4. Validación -> Guardar en memoria o corregir
        workflow.add_conditional_edges(
            "validate_business_info",
            route_after_validation,
            {
                "save_to_memory": "save_to_memory",
                "extract_business_info": "extract_business_info"
            }
        )
        
        # 5. Guardar en memoria -> Investigación
        workflow.add_conditional_edges(
            "save_to_memory",
            route_after_memory_save,
            {
                "research_opportunities": "research_opportunities",
                "generate_response": "generate_response"
            }
        )
        
        # 6. Investigación -> Validación de resultados
        workflow.add_conditional_edges(
            "research_opportunities",
            route_after_research,
            {
                "validate_research_results": "validate_research_results",
                "generate_response": "generate_response"
            }
        )
        
        # 7. Validación de investigación -> Puede ir a varios lugares según respuesta
        workflow.add_edge("validate_research_results", "generate_response")
        
        # === FLUJO DE CONVERSACIÓN NORMAL ===
        
        # 8. Generación de respuesta -> Herramientas o feedback humano
        workflow.add_conditional_edges(
            "generate_response",
            route_conversation_flow,
            {
                "action": "action",
                "human_feedback": "human_feedback"
            }
        )
        
        # 9. Herramientas -> Volver a generar respuesta
        workflow.add_edge("action", "generate_response")
        
        # 10. Feedback humano -> Generar respuesta o finalizar
        workflow.add_edge("human_feedback", "generate_response")
        
        # 11. Punto final
        workflow.set_finish_point("end_node")
        
        # === COMPILACIÓN ===
        store = get_postgres_store()
        checkpointer = get_postgres_saver()
        
        compiled_graph = workflow.compile(
            checkpointer=checkpointer, 
            store=store
        )
        
        logger.info("Grafo principal de PYMES compilado exitosamente")
        return compiled_graph
        
    except Exception as e:
        logger.error(f"Error creando grafo principal de PYMES: {str(e)}")
        raise


# Función de conveniencia para usar en lugar del chat_graph
def create_chat_graph():
    """
    Función de compatibilidad que devuelve el grafo de PYMES.
    Mantiene compatibilidad con el código existente.
    """
    return create_pymes_graph() 