"""
Orquestador Central Refinado - Arquitectura ReAct Profesional
Implementa el patrón ReAct puro con ToolNode real y mejores prácticas de LangGraph.
"""

import logging
import traceback
from typing import Literal, Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.graph.central_agent_tools import CENTRAL_AGENT_TOOLS
from app.database.postgres import get_async_postgres_saver
from app.core.prompt import CENTRAL_ORCHESTRATOR_PROMPT
from app.services.business_info_manager import get_business_context
import asyncio

logger = logging.getLogger(__name__)

# === AGENTE CENTRAL REFINADO ===

def create_central_orchestrator_llm():
    """Crea el LLM para el agente central con configuración optimizada."""
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.3,  # Menor temperatura para decisiones más consistentes
        max_tokens=150,   # Límite para WhatsApp
        model_kwargs={
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }
    )

# Crear instancia del LLM
llm = create_central_orchestrator_llm()

async def central_orchestrator_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo central del orquestrador que procesa mensajes y decide qué herramientas usar.
    """
    logger.info("🧠 central_orchestrator_node: Procesando mensaje...")
    
    # Preparar mensajes para el LLM
    messages = state["messages"].copy()
    
    # Agregar contexto empresarial si existe
    if state.get("business_context"):
        business_info = f"\\n\\n### CONTEXTO EMPRESARIAL:\\n{state['business_context']}"
        if messages and isinstance(messages[-1], HumanMessage):
            messages[-1].content += business_info
    
    # Invocar el LLM con herramientas
    llm_with_tools = llm.bind_tools(CENTRAL_AGENT_TOOLS)
    result = await llm_with_tools.ainvoke([
        {"role": "system", "content": CENTRAL_ORCHESTRATOR_PROMPT},
        *[{"role": m.type, "content": m.content} for m in messages]
    ])
    
    # Log de la respuesta
    tool_calls = len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
    logger.info(f"✅ Agente central respondió: {len(result.content)} chars, {tool_calls} tool calls")
    
    return {"messages": [result]}

# === LÓGICA DE CONTROL DEL GRAFO ===

def should_continue(state: PYMESState) -> str:
    """Función de control que decide si continuar o terminar."""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info(f"🔧 should_continue: Ejecutando {len(last_message.tool_calls)} herramientas...")
        return "tools"
    else:
        logger.info("✅ should_continue: Finalizando turno del asistente")
        return END

# === MANEJO ROBUSTO DE CHECKPOINTER ===

async def create_checkpointer_with_retry(max_retries: int = 3, retry_delay: float = 1.0):
    """
    Crea un checkpointer con retry automático en caso de fallos de conexión.
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"🔧 Creando checkpointer PostgreSQL (intento {attempt + 1}/{max_retries})...")
            checkpointer = await get_async_postgres_saver()
            logger.info("✅ Checkpointer PostgreSQL creado exitosamente")
            return checkpointer
        except Exception as e:
            logger.warning(f"⚠️ Error creando checkpointer (intento {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
            else:
                logger.error(f"❌ Falló la creación del checkpointer después de {max_retries} intentos")
                raise e

# === CONSTRUCCIÓN DEL GRAFO ===

async def create_central_orchestrator_graph():
    """
    Crea y compila el grafo del orquestrador central con manejo robusto de errores.
    """
    logger.info("🏗️ Creando grafo de agente central refinado...")
    
    # Crear el grafo
    workflow = StateGraph(PYMESState)
    
    # Agregar nodos
    workflow.add_node("agent", central_orchestrator_node)
    workflow.add_node("tools", ToolNode(CENTRAL_AGENT_TOOLS))
    
    # Definir flujo con control de herramientas
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    
    # Crear checkpointer y compilar
    checkpointer = await create_checkpointer_with_retry(max_retries=2)
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=None,  # No hay interrupciones automáticas
        interrupt_after=None    # Patrón ReAct puro
    )
    
    logger.info("✅ Grafo de agente central (Patrón ReAct Puro) compilado exitosamente")
    return compiled_graph

# === FUNCIÓN PRINCIPAL CON MANEJO ROBUSTO DE ERRORES ===

async def process_message_with_central_orchestrator(
    user_message: str, 
    thread_id: str,
    is_whatsapp: bool = False,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Procesa un mensaje usando el orquestador central con manejo robusto de errores de PostgreSQL.
    """
    logger.info(f"🚀 Procesando mensaje con orquestador central: {user_message[:50]}...")
    
    # Estado inicial compatible con PYMESState
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "business_context": await get_business_context(thread_id),
        "current_agent": "central_orchestrator",  # Requerido por PYMESState
        "next_action": "",
        "needs_human_feedback": False
    }
    
    # Configuración del thread
    thread_config = {"configurable": {"thread_id": thread_id}}
    
    # RETRY LOGIC PARA MANEJO DE ERRORES DE POSTGRESQL
    for attempt in range(max_retries):
        try:
            # Crear el grafo compilado
            graph = await create_central_orchestrator_graph()
            logger.info("✅ Grafo de agente central obtenido exitosamente")
            
            # Ejecutar el grafo
            logger.info(f"⚡ Ejecutando grafo para thread: {thread_id}")
            final_state = await graph.ainvoke(initial_state, config=thread_config)
            
            # Procesar resultado exitoso
            if final_state and "messages" in final_state:
                assistant_message = final_state["messages"][-1]
                response_text = assistant_message.content if hasattr(assistant_message, 'content') else "Respuesta procesada"
                
                logger.info(f"✅ Respuesta generada: {len(response_text)} caracteres")
                
                return {
                    "status": "completed",
                    "answer": response_text,  # Cambiar 'response' a 'answer' para compatibilidad
                    "thread_id": thread_id,
                    "is_whatsapp": is_whatsapp
                }
            else:
                raise Exception("Estado final inválido del grafo")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error en orquestador central (intento {attempt + 1}/{max_retries}): {error_msg}")
            
            # Si es un error de PostgreSQL y no es el último intento, reintentamos
            if ("server closed the connection" in error_msg or 
                "connection" in error_msg.lower() or 
                "postgresql" in error_msg.lower()) and attempt < max_retries - 1:
                
                logger.info(f"🔄 Reintentando debido a error de conexión PostgreSQL...")
                await asyncio.sleep(2.0 * (attempt + 1))  # Backoff exponencial
                continue
            
            # Si llegamos aquí, el error es irrecuperable o agotamos los reintentos
            logger.error(f"❌ Error irrecuperable en orquestador central: {error_msg}")
            logger.error(f"Stack trace completo: {traceback.format_exc()}")
            
            return {
                "status": "error",
                "answer": "Lo siento, hay un problema técnico temporalmente. Por favor intenta nuevamente en unos momentos.",
                "error": error_msg,
                "thread_id": thread_id,
                "is_whatsapp": is_whatsapp
            }
    
    # Este punto no debería alcanzarse nunca
    return {
        "status": "error",
        "answer": "Error inesperado en el sistema.",
        "thread_id": thread_id,
        "is_whatsapp": is_whatsapp
    }

# === FUNCIONES AUXILIARES ===

def get_orchestrator_info() -> Dict[str, Any]:
    """Información sobre el orquestador central para debugging."""
    return {
        "agent_type": "central_orchestrator",
        "pattern": "react_pure",
        "tools_count": len(CENTRAL_AGENT_TOOLS),
        "tools": [tool.name for tool in CENTRAL_AGENT_TOOLS],
        "features": [
            "InjectedState para herramientas",
            "ToolNode real",
            "Patrón ReAct puro",
            "Validaciones internas",
            "Límite de tokens para WhatsApp"
        ]
    }

# ===================================================================
# COMPATIBILIDAD CON LANGGRAPH STUDIO
# ===================================================================

def central_orchestrator_node_studio(state: PYMESState) -> Dict[str, Any]:
    """
    Versión síncrona del nodo central para compatibilidad con LangGraph Studio.
    Mantiene la misma lógica pero sin async/await.
    """
    logger.info("🎬 central_orchestrator_node_studio: Procesando mensaje...")
    
    # Preparar mensajes para el LLM
    messages = state["messages"].copy()
    
    # Simular contexto empresarial para Studio
    if messages and isinstance(messages[-1], HumanMessage):
        user_message = messages[-1].content.lower()
        if any(word in user_message for word in ["pollería", "restaurante", "negocio", "empresa", "tienda"]):
            business_context = "\\n\\n### CONTEXTO EMPRESARIAL:\\nUsuario mencionó información sobre su negocio. Usar update_business_info para extraer detalles."
            messages[-1].content += business_context
    
    # Invocar el LLM con herramientas (LÓGICA IDÉNTICA A PRODUCCIÓN)
    llm_with_tools = llm.bind_tools(CENTRAL_AGENT_TOOLS)
    
    # Preparar mensajes para el LLM
    conversation_messages = [
        {"role": "system", "content": CENTRAL_ORCHESTRATOR_PROMPT}
    ]
    
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
        elif hasattr(msg, 'tool_call_id'):  # ToolMessage
            conversation_messages.append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": msg.tool_call_id
            })
    
    # Invocar el LLM (LÓGICA IDÉNTICA A PRODUCCIÓN)
    result = llm_with_tools.invoke(conversation_messages)
    
    # Log de la respuesta (IGUAL QUE PRODUCCIÓN)
    tool_calls = len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
    logger.info(f"✅ Studio Agent respondió: {len(result.content)} chars, {tool_calls} tool calls")
    
    return {"messages": [result]}

def should_continue_studio(state: PYMESState) -> str:
    """Función de control para Studio (LÓGICA IDÉNTICA A PRODUCCIÓN)."""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info(f"🔧 Studio: Ejecutando {len(last_message.tool_calls)} herramientas...")
        return "tools"
    else:
        logger.info("✅ Studio: Finalizando turno")
        return END

def create_central_orchestrator_studio_graph():
    """
    Crea el grafo del orquestador central para LangGraph Studio.
    ARQUITECTURA IDÉNTICA A PRODUCCIÓN pero compatible con Studio.
    """
    logger.info("🎬 Creando grafo central para LangGraph Studio (versión producción)...")
    
    # Crear el grafo con PYMESState (ahora compatible con Studio)
    workflow = StateGraph(PYMESState)
    
    # Agregar nodos (IGUAL QUE PRODUCCIÓN)
    workflow.add_node("agent", central_orchestrator_node_studio)
    workflow.add_node("tools", ToolNode(CENTRAL_AGENT_TOOLS))
    
    # Definir flujo con control de herramientas (IGUAL QUE PRODUCCIÓN)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue_studio,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    
    # Compilar sin checkpointer para Studio (en producción usa PostgreSQL)
    compiled_graph = workflow.compile()
    
    logger.info("✅ Grafo central para Studio (versión producción) compilado exitosamente")
    return compiled_graph

# Crear la instancia del grafo para LangGraph Studio
central_orchestrator_studio = create_central_orchestrator_studio_graph() 