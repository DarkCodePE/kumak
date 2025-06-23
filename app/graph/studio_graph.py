"""
Grafo específico para LangGraph Studio - Desarrollo y Pruebas
Simplifica el orquestador central para facilitar las pruebas en LangGraph Studio.
"""

import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode
from app.config.settings import LLM_MODEL
from app.graph.central_agent_tools import CENTRAL_AGENT_TOOLS
from app.core.prompt import CENTRAL_ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)

def create_studio_llm():
    """Crea el LLM optimizado para LangGraph Studio."""
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.3,
        max_tokens=300,  # Más tokens para Studio
        model_kwargs={
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }
    )

# Instancia del LLM para Studio
studio_llm = create_studio_llm()

def studio_agent_node(state: MessagesState) -> Dict[str, Any]:
    """
    Nodo del agente para LangGraph Studio.
    Usa MessagesState estándar para máxima compatibilidad.
    """
    logger.info("🎬 Studio Agent: Procesando mensaje...")
    
    # Obtener mensajes
    messages = state["messages"]
    
    # Crear el prompt del sistema
    system_message = {
        "role": "system", 
        "content": CENTRAL_ORCHESTRATOR_PROMPT
    }
    
    # Preparar mensajes para el LLM
    conversation_messages = [system_message]
    
    # Agregar historial de mensajes
    for msg in messages:
        if isinstance(msg, HumanMessage):
            conversation_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            if msg.tool_calls:
                conversation_messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls
                })
            else:
                conversation_messages.append({"role": "assistant", "content": msg.content})
    
    # Invocar LLM con herramientas
    llm_with_tools = studio_llm.bind_tools(CENTRAL_AGENT_TOOLS)
    result = llm_with_tools.invoke(conversation_messages)
    
    # Log
    tool_calls = len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
    logger.info(f"✅ Studio Agent respondió: {len(result.content)} chars, {tool_calls} tool calls")
    
    return {"messages": [result]}

def should_continue_studio(state: MessagesState) -> str:
    """Función de control para LangGraph Studio."""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info(f"🔧 Studio: Ejecutando {len(last_message.tool_calls)} herramientas...")
        return "tools"
    else:
        logger.info("✅ Studio: Finalizando turno")
        return END

def create_studio_graph():
    """
    Crea el grafo para LangGraph Studio.
    Usa MessagesState estándar para máxima compatibilidad.
    """
    logger.info("🎬 Creando grafo para LangGraph Studio...")
    
    # Crear el grafo con MessagesState estándar
    workflow = StateGraph(MessagesState)
    
    # Agregar nodos
    workflow.add_node("agent", studio_agent_node)
    workflow.add_node("tools", ToolNode(CENTRAL_AGENT_TOOLS))
    
    # Definir flujo
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue_studio,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    
    # Compilar sin checkpointer para Studio (más simple)
    compiled_graph = workflow.compile()
    
    logger.info("✅ Grafo para LangGraph Studio compilado exitosamente")
    return compiled_graph

# Crear la instancia del grafo para exportar
studio_graph = create_studio_graph()

# Información del grafo para debugging
def get_studio_graph_info():
    """Información sobre el grafo de Studio."""
    return {
        "name": "KUMAK Studio Graph",
        "description": "Grafo simplificado para desarrollo y pruebas en LangGraph Studio",
        "state_type": "MessagesState",
        "tools_count": len(CENTRAL_AGENT_TOOLS),
        "tools": [tool.name for tool in CENTRAL_AGENT_TOOLS],
        "features": [
            "Compatible con LangGraph Studio",
            "MessagesState estándar",
            "Sin checkpointer (desarrollo)",
            "Herramientas empresariales completas"
        ]
    } 