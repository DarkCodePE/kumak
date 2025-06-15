"""
Supervisor multi-agente mejorado usando handoffs, Command, y Send().
Implementa las mejores prácticas de LangGraph para sistemas multi-agente.
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.graph.state import PYMESState
from app.graph.handoff_system import (
    intelligent_supervisor_node,
    enhanced_human_feedback_node,
    conditional_entry_point
)
from app.graph.enhanced_agents import (
    enhanced_info_completion_node,
    enhanced_research_router_node,
    enhanced_conversational_node,
    enhanced_researcher_node
)
from app.database.postgres import get_postgres_saver, get_postgres_store

logger = logging.getLogger(__name__)

def create_multi_agent_supervisor_graph():
    """
    Crea el grafo del supervisor multi-agente mejorado.
    Usa handoffs, Command, y Send() en lugar de conditional edges complejos.
    """
    try:
        logger.info("🚀 Creando supervisor multi-agente mejorado...")

        # Crear el grafo
        workflow = StateGraph(PYMESState)

        # === AGREGAR NODOS ===
        
        # Nodo supervisor principal (usa Command para routing dinámico)
        workflow.add_node("intelligent_supervisor", intelligent_supervisor_node)
        
        # Nodo de feedback humano (usa Command para control de flujo)
        workflow.add_node("enhanced_human_feedback", enhanced_human_feedback_node)
        
        # Agentes especializados (todos usan Command)
        workflow.add_node("info_completion_agent", enhanced_info_completion_node)
        workflow.add_node("research_router", enhanced_research_router_node)
        workflow.add_node("conversational_agent", enhanced_conversational_node)
        workflow.add_node("researcher", enhanced_researcher_node)

        # === DEFINIR FLUJO CON ENTRY POINTS Y EDGES SIMPLIFICADOS ===

        # Entry point condicional (puede expandirse para lógica más compleja)
        workflow.add_conditional_edges(
            START,
            conditional_entry_point,
            {
                "intelligent_supervisor": "intelligent_supervisor"
            }
        )

        # El supervisor usa Command para routing dinámico - no necesita edges explícitos
        # Los nodos de agentes usan Command para volver al feedback - no necesitan edges explícitos
        
        # === COMPILAR CON CHECKPOINTER ===
        store = get_postgres_store()
        checkpointer = get_postgres_saver()

        compiled_graph = workflow.compile(
            checkpointer=checkpointer,
            store=store
        )

        logger.info("✅ Supervisor multi-agente mejorado compilado exitosamente")
        return compiled_graph

    except Exception as e:
        logger.error(f"❌ Error creando supervisor multi-agente: {str(e)}")
        raise

def create_enhanced_chat_graph():
    """Función de compatibilidad que devuelve el supervisor multi-agente mejorado."""
    return create_multi_agent_supervisor_graph()

# === DIAGRAMA DE FLUJO ===

def get_flow_description():
    """Retorna descripción del flujo mejorado."""
    return """
🔄 FLUJO MULTI-AGENTE MEJORADO CON HANDOFFS

┌─────────────────┐
│      START      │
└─────────┬───────┘
          │ conditional_entry_point()
          ▼
┌─────────────────┐
│ intelligent_    │ ◄─── Command(goto=...) desde human_feedback
│ supervisor      │
└─────────┬───────┘
          │ Command(goto=agent, update=state)
          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ info_completion │    │ research_router │    │ conversational  │
│ _agent          │    │                 │    │ _agent          │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ Command(goto="enhanced_human_feedback")     │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ enhanced_human_ │    │ researcher      │    │      END        │
│ feedback        │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────────────┘
          │                      │
          │ Command(goto="intelligent_supervisor")    │
          ▼                      ▼
          └──────────────────────┘

CARACTERÍSTICAS CLAVE:
✅ Handoffs explícitos entre agentes usando Command
✅ Send() para comunicación directa con payloads específicos  
✅ Conditional edges solo donde es necesario (entry point)
✅ Command combina state updates + control flow
✅ Agentes pueden hacer handoffs entre sí usando herramientas
✅ Routing dinámico basado en contexto y intención
✅ Eliminación de conditional edges complejos

HERRAMIENTAS DE HANDOFF:
🔄 transfer_to_[agent]: Handoff simple con todo el estado
📋 assign_task_to_[agent]: Handoff con Send() y tarea específica
🎯 Cada agente tiene herramientas apropiadas para su rol
"""

# === FUNCIONES DE UTILIDAD ===

def validate_graph_structure(graph):
    """Valida que el grafo esté correctamente estructurado."""
    try:
        # Verificar que los nodos existen
        expected_nodes = [
            "intelligent_supervisor",
            "enhanced_human_feedback", 
            "info_completion_agent",
            "research_router",
            "conversational_agent",
            "researcher"
        ]
        
        actual_nodes = list(graph.nodes.keys())
        missing_nodes = [node for node in expected_nodes if node not in actual_nodes]
        
        if missing_nodes:
            logger.warning(f"⚠️ Nodos faltantes en el grafo: {missing_nodes}")
            return False
        
        logger.info("✅ Estructura del grafo validada correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error validando estructura del grafo: {str(e)}")
        return False

def get_graph_statistics(graph):
    """Retorna estadísticas del grafo."""
    try:
        stats = {
            "total_nodes": len(graph.nodes),
            "node_names": list(graph.nodes.keys()),
            "uses_handoffs": True,
            "uses_command": True,
            "uses_send": True,
            "architecture": "Multi-Agent Supervisor with Handoffs"
        }
        
        logger.info(f"📊 Estadísticas del grafo: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
        return {}

# Función de compatibilidad para reemplazar supervisores anteriores
def create_supervisor_pymes_graph():
    """Función de compatibilidad que devuelve el supervisor multi-agente mejorado."""
    return create_multi_agent_supervisor_graph()

def create_intelligent_supervisor_graph():
    """Función de compatibilidad que devuelve el supervisor multi-agente mejorado.""" 
    return create_multi_agent_supervisor_graph() 