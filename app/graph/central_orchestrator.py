"""
Orquestador Central Refinado - Arquitectura ReAct Profesional
Implementa el patrón ReAct puro con ToolNode real y mejores prácticas de LangGraph.
"""

import logging
import traceback
from typing import Literal, Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, create_react_agent, tools_condition
from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.graph.central_agent_tools import CENTRAL_AGENT_TOOLS
from app.database.postgres import get_postgres_saver, get_async_postgres_saver
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

def get_central_agent_prompt() -> str:
    """
    Prompt refinado para el agente central que actúa como director de orquesta.
    """
    return """Eres el Asistente Empresarial Central de Kumak, un consultor experto en desarrollo de PYMEs.

TU MISIÓN: Ayudar a empresarios a crecer sus negocios mediante:
1. Extracción y organización de información empresarial
2. Investigación de mercado personalizada 
3. Consultoría estratégica conversacional

ARQUITECTURA DE HERRAMIENTAS:
- update_business_info: Para extraer/actualizar información empresarial del usuario
- perform_market_research: Para investigación de mercado (requiere info completa)
- provide_business_consultation: Para consultoría conversacional específica
- check_business_info_completeness: Para verificar completitud de información

REGLAS CRÍTICAS DE OPERACIÓN:

🔄 FLUJO INTELIGENTE:
1. SIEMPRE extrae información empresarial cuando el usuario menciona su negocio
2. Para investigación: PRIMERO verifica info completa, luego investiga
3. Para consultas: Usa contexto empresarial para personalizar respuestas

📊 CRITERIOS DE DECISIÓN:
- Si usuario menciona info de negocio → update_business_info
- Si pide investigación/análisis → perform_market_research (valida prerrequisitos internamente) 
- Si hace pregunta específica → provide_business_consultation
- Si necesitas verificar completitud → check_business_info_completeness

💬 ESTILO DE COMUNICACIÓN:
- Respuestas concisas (máximo 150 tokens para WhatsApp)
- Profesional pero conversacional 
- Enfocado en acciones específicas y resultados
- Pregunta por información faltante de manera natural

🎯 CASOS ESPECIALES:
- "Tengo pollería..." → update_business_info (extrae toda la info posible)
- "Investiga mercado..." → perform_market_research (la herramienta valida prerrequisitos)
- "¿Cómo puedo crecer?" → Si info incompleta: update_business_info, Si completa: provide_business_consultation

IMPORTANTE: Las herramientas manejan sus propias validaciones. Tu trabajo es decidir QUÉ herramienta usar basado en la intención del usuario."""

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

# === CONSTRUCCIÓN DEL GRAFO REFINADO ===

async def create_central_orchestrator_graph():
    """
    Crea el grafo simplificado con el patrón ReAct puro (ASÍNCRONO).
    
    Flujo: START -> agent -> should_continue -> [tools -> agent] O [__end__]
    """
    logger.info("🏗️ Creando grafo de agente central refinado...")
    
    workflow = StateGraph(PYMESState)

    # === NODOS ===
    
    # Agente central (director de orquesta)
    workflow.add_node("agent", central_orchestrator_node)
    
    # CORRECCIÓN CRÍTICA: Usar ToolNode real en lugar de placeholder
    tool_executor = ToolNode(CENTRAL_AGENT_TOOLS)
    workflow.add_node("tools", tool_executor)
    
    # ¡YA NO NECESITAMOS EL NODO human_feedback!

    # === FLUJO ===
    
    # Punto de entrada
    workflow.set_entry_point("agent")

    # Conditional edge desde el agente
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",      # Ejecutar herramientas
            "__end__": "__end__"   # Finalizar (el grafo termina automáticamente)
        }
    )

    # Edge de vuelta al agente después de ejecutar herramientas
    workflow.add_edge("tools", "agent")  # Bucle ReAct

    # === COMPILACIÓN ===
    
    # CORRECCIÓN CRÍTICA: Usar checkpointer asíncrono
    checkpointer = await get_async_postgres_saver()
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=None,  # No hay interrupciones automáticas
        interrupt_after=None    # Patrón ReAct puro
    )
    
    logger.info("✅ Grafo de agente central (Patrón ReAct Puro) compilado exitosamente")
    return compiled_graph

# === FUNCIÓN DE PROCESAMIENTO PRINCIPAL ===

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
            # Crear el grafo y checkpointer
            workflow = await create_central_orchestrator_graph()
            checkpointer = await create_checkpointer_with_retry(max_retries=2)
            
            # Compilar el grafo con checkpointer
            graph = workflow.compile(checkpointer=checkpointer)
            logger.info("✅ Grafo de agente central (Patrón ReAct Puro) compilado exitosamente")
            
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
                    "response": response_text,
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
                "response": "Lo siento, hay un problema técnico temporalmente. Por favor intenta nuevamente en unos momentos.",
                "error": error_msg,
                "thread_id": thread_id,
                "is_whatsapp": is_whatsapp
            }
    
    # Este punto no debería alcanzarse nunca
    return {
        "status": "error",
        "response": "Error inesperado en el sistema.",
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
    Crea y compila el grafo del orquestador central con manejo robusto de errores.
    """
    logger.info("🏗️ Creando grafo de agente central refinado...")
    
    # Crear el grafo
    workflow = StateGraph(PYMESState)
    
    # Agregar nodos
    workflow.add_node("central_orchestrator", central_orchestrator_node)
    workflow.add_node("tools", ToolNode(CENTRAL_AGENT_TOOLS))
    
    # Definir flujo con control de herramientas
    workflow.set_entry_point("central_orchestrator")
    workflow.add_conditional_edges(
        "central_orchestrator",
        should_continue,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "central_orchestrator")
    
    return workflow

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
            # Crear el grafo y checkpointer
            workflow = await create_central_orchestrator_graph()
            checkpointer = await create_checkpointer_with_retry(max_retries=2)
            
            # Compilar el grafo con checkpointer
            graph = workflow.compile(checkpointer=checkpointer)
            logger.info("✅ Grafo de agente central (Patrón ReAct Puro) compilado exitosamente")
            
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
                    "response": response_text,
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
                "response": "Lo siento, hay un problema técnico temporalmente. Por favor intenta nuevamente en unos momentos.",
                "error": error_msg,
                "thread_id": thread_id,
                "is_whatsapp": is_whatsapp
            }
    
    # Este punto no debería alcanzarse nunca
    return {
        "status": "error",
        "response": "Error inesperado en el sistema.",
        "thread_id": thread_id,
        "is_whatsapp": is_whatsapp
    } 