"""
Supervisor inteligente con routing dinámico basado en BusinessInfo y contexto de conversación.
Implementa una arquitectura más natural y flexible que el supervisor anterior.
"""

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

from app.graph.state import PYMESState
from app.graph.intelligent_routing import (
    intelligent_router_node, 
    route_after_intelligent_router
)
from app.graph.specialized_agents import (
    info_completion_agent_node,
    research_router_node,
    conversational_agent_node
)
from app.graph.supervisor_architecture import (
    business_info_evaluator_node,
    researcher_agent_node
)
from app.database.postgres import get_postgres_saver, get_postgres_store

logger = logging.getLogger(__name__)


def enhanced_human_feedback_node(state: PYMESState) -> Command:
    """
    Enhanced human feedback node que usa la respuesta más reciente y maneja routing inteligente.
    """
    logger.info("🔄 enhanced_human_feedback_node: Esperando entrada del usuario...")

    # Obtener la respuesta más reciente del último mensaje AI
    messages = state.get("messages", [])
    latest_answer = "Esperando respuesta del asistente."
    
    # Buscar el último mensaje AI (más reciente)
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            latest_answer = message.content
            break
    
    logger.info(f"🔄 enhanced_human_feedback_node: Usando respuesta más reciente: {latest_answer[:100]}...")

    # Usar interrupt() con la respuesta más reciente
    user_input_from_interrupt = interrupt({
        "answer": latest_answer,
        "message": "Proporcione su respuesta:"
    })

    logger.info(f"🔄 enhanced_human_feedback_node: Entrada recibida: {user_input_from_interrupt}")

    # Actualizar historial de feedback
    updated_feedback_list = state.get("feedback", []) + [user_input_from_interrupt]

    # Crear mensaje de usuario para el historial
    user_message_for_history = HumanMessage(content=user_input_from_interrupt)

    # Payload de actualización
    update_payload = {
        "messages": [user_message_for_history],
        "feedback": updated_feedback_list,
        "input": user_input_from_interrupt
    }

    # Verificar si el usuario quiere terminar
    termination_words = ["done", "thanks", "bye", "adios", "terminate", "exit", "gracias", "chau", "fin"]
    if user_input_from_interrupt.strip().lower() in termination_words:
        logger.info(f"🔄 enhanced_human_feedback_node: Usuario terminó conversación: {user_input_from_interrupt}")
        return Command(update=update_payload, goto=END)
    else:
        logger.info(f"🔄 enhanced_human_feedback_node: Usuario continúa conversación: {user_input_from_interrupt}")
        # Ir al evaluador de business info para extraer información primero
        return Command(update=update_payload, goto="business_evaluator")


def enhanced_business_evaluator_node(state: PYMESState) -> Dict[str, Any]:
    """
    Enhanced business evaluator que extrae información y luego pasa al router inteligente.
    """
    logger.info("🔍 enhanced_business_evaluator_node: Analizando mensaje...")
    
    # Primero ejecutar el evaluador original para extraer información
    extraction_result = business_info_evaluator_node(state)
    
    # Luego ejecutar el router inteligente con la información actualizada
    updated_state = {**state, **extraction_result}
    routing_result = intelligent_router_node(updated_state)
    
    # Combinar resultados
    final_result = {**extraction_result, **routing_result}
    
    logger.info(f"🧠 Enhanced evaluator: routing to {final_result.get('current_agent', 'unknown')}")
    
    return final_result


def route_after_enhanced_evaluator(state: PYMESState) -> Literal[
    "info_completion_agent", "research_router", "conversational_agent", "researcher"
]:
    """Routing después del enhanced evaluator basado en decisión inteligente."""
    current_agent = state.get("current_agent", "info_completion")
    
    # Si el router inteligente decidió ir directamente a researcher
    if current_agent == "researcher":
        logger.info("🎯 Routing directo a researcher")
        return "researcher"
    
    # Usar el routing estándar del router inteligente
    return route_after_intelligent_router(state)


def route_after_agents(state: PYMESState) -> Literal["enhanced_human_feedback"]:
    """
    Route después de agentes especializados - siempre ir a human feedback.
    """
    logger.info("🔀 route_after_agents: Dirigiendo a enhanced_human_feedback")
    return "enhanced_human_feedback"


def create_intelligent_supervisor_graph():
    """
    Crear el grafo del supervisor inteligente con routing dinámico.
    """
    try:
        logger.info("Creating intelligent supervisor graph...")

        # Crear el grafo
        workflow = StateGraph(PYMESState)

        # === AGREGAR NODOS ===
        
        # Nodos principales
        workflow.add_node("business_evaluator", enhanced_business_evaluator_node)
        workflow.add_node("enhanced_human_feedback", enhanced_human_feedback_node)
        
        # Agentes especializados (nuevos)
        workflow.add_node("info_completion_agent", info_completion_agent_node)
        workflow.add_node("research_router", research_router_node)
        workflow.add_node("conversational_agent", conversational_agent_node)
        
        # Agente de investigación (reutilizado)
        workflow.add_node("researcher", researcher_agent_node)

        # === DEFINIR FLUJO ===

        # Inicio -> Business evaluator (extrae info + routing inteligente)
        workflow.add_edge(START, "business_evaluator")

        # Business evaluator -> Agentes especializados basado en routing inteligente
        workflow.add_conditional_edges(
            "business_evaluator",
            route_after_enhanced_evaluator,
            {
                "info_completion_agent": "info_completion_agent",
                "research_router": "research_router", 
                "conversational_agent": "conversational_agent",
                "researcher": "researcher"
            }
        )

        # Todos los agentes -> enhanced_human_feedback
        workflow.add_conditional_edges(
            "info_completion_agent",
            route_after_agents,
            {
                "enhanced_human_feedback": "enhanced_human_feedback"
            }
        )

        workflow.add_conditional_edges(
            "research_router",
            route_after_agents,
            {
                "enhanced_human_feedback": "enhanced_human_feedback"
            }
        )

        workflow.add_conditional_edges(
            "conversational_agent",
            route_after_agents,
            {
                "enhanced_human_feedback": "enhanced_human_feedback"
            }
        )

        workflow.add_conditional_edges(
            "researcher",
            route_after_agents,
            {
                "enhanced_human_feedback": "enhanced_human_feedback"
            }
        )

        # Enhanced human feedback usa Command para decidir donde ir
        # No necesita edge estático porque usa Command(goto=...)

        # === COMPILAR ===
        store = get_postgres_store()
        checkpointer = get_postgres_saver()

        compiled_graph = workflow.compile(
            checkpointer=checkpointer,
            store=store
        )

        logger.info("Intelligent supervisor graph compiled successfully")
        return compiled_graph

    except Exception as e:
        logger.error(f"Error creating intelligent supervisor graph: {str(e)}")
        raise


# Función de compatibilidad para reemplazar la anterior
def create_supervisor_pymes_graph():
    """Función de compatibilidad que devuelve el nuevo supervisor inteligente."""
    return create_intelligent_supervisor_graph()


def create_chat_graph():
    """Función de compatibilidad que devuelve el nuevo supervisor inteligente."""
    return create_intelligent_supervisor_graph() 