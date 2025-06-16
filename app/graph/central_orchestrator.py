"""
Orquestador Central Refinado - Arquitectura ReAct Profesional
Implementa el patrón ReAct puro con ToolNode real y mejores prácticas de LangGraph.
"""

import logging
from typing import Literal, Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, create_react_agent  # CORRECCIÓN CRÍTICA
from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.graph.central_agent_tools import CENTRAL_AGENT_TOOLS
from app.database.postgres import get_postgres_saver, get_async_postgres_saver

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
    Nodo principal del agente central que actúa como director de orquesta.
    Usa ReAct pattern para decidir qué herramientas invocar.
    """
    try:
        logger.info("🧠 central_orchestrator_node: Procesando mensaje...")
        
        # Obtener mensajes actuales
        messages = state.get("messages", [])
        
        if not messages:
            return {
                "messages": [AIMessage(content="¡Hola! Soy tu asistente empresarial. ¿En qué puedo ayudarte con tu negocio?")]
            }
        
        # Configurar el LLM con herramientas
        llm = create_central_orchestrator_llm()
        llm_with_tools = llm.bind_tools(CENTRAL_AGENT_TOOLS)
        
        # Construir historial de conversación con prompt del sistema
        system_prompt = get_central_agent_prompt()
        
        # Crear mensajes para el LLM
        conversation_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Agregar historial de mensajes recientes (últimos 6 para limitar tokens)
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        
        from langchain_core.messages import ToolMessage
        
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                conversation_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    # Mensaje con tool calls
                    conversation_messages.append({
                        "role": "assistant", 
                        "content": msg.content or "",
                        "tool_calls": msg.tool_calls
                    })
                else:
                    # Mensaje normal del asistente
                    conversation_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                # CORRECCIÓN CRÍTICA: Incluir respuestas de herramientas
                conversation_messages.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id
                })
        
        # Invocar el LLM
        response = await llm_with_tools.ainvoke(conversation_messages)
        
        logger.info(f"✅ Agente central respondió: {len(response.content) if response.content else 0} chars, {len(response.tool_calls) if response.tool_calls else 0} tool calls")
        
        # Retornar la respuesta del agente
        return {
            "messages": [response]
        }
        
    except Exception as e:
        import traceback
        error_detail = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Error en central_orchestrator_node: {error_detail}")
        logger.error(f"Stack trace del nodo: {stack_trace}")
        
        error_message = "Hubo un error procesando tu mensaje. ¿Podrías intentar nuevamente?"
        return {
            "messages": [AIMessage(content=error_message)]
        }

# === LÓGICA DE CONTROL DEL GRAFO ===

def should_continue(state: PYMESState) -> Literal["tools", "__end__"]:
    """
    Decide si ejecutar herramientas o finalizar el turno del asistente.
    Patrón ReAct puro - más simple y elegante.
    """
    last_message = state["messages"][-1]
    
    # Si el último mensaje tiene tool_calls, ejecutar herramientas
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info(f"🔧 should_continue: Ejecutando {len(last_message.tool_calls)} herramientas...")
        return "tools"
    
    # Si no hay tool_calls, el turno del asistente termina
    logger.info("✅ should_continue: Finalizando turno del asistente")
    return "__end__"

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
    message: str,
    thread_id: str,
    reset_thread: bool = False
) -> Dict[str, Any]:
    """
    Procesa un mensaje usando el orquestador central refinado.
    
    Args:
        message: Mensaje del usuario
        thread_id: ID del hilo de conversación
        reset_thread: Si reiniciar el hilo
        
    Returns:
        Dict con 'status', 'answer', y metadatos
    """
    try:
        logger.info(f"🚀 Procesando mensaje con orquestador central: {message[:50]}...")
        
        # Crear el grafo (ASÍNCRONO)
        graph = await create_central_orchestrator_graph()
        
        # Configurar el estado inicial
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "thread_id": thread_id,
            "business_info": {},  # Se poblará por las herramientas
        }
        
        # Configurar thread
        thread_config = {"configurable": {"thread_id": thread_id}}
        
        # Resetear thread si se solicita
        if reset_thread:
            logger.info(f"🔄 Reseteando thread: {thread_id}")
            # El checkpointer maneja esto automáticamente con el nuevo estado
        
        # Ejecutar el grafo
        logger.info(f"⚡ Ejecutando grafo para thread: {thread_id}")
        final_state = await graph.ainvoke(initial_state, config=thread_config)
        
        # Extraer la respuesta final
        messages = final_state.get("messages", [])
        last_ai_message = None
        
        # Buscar el último mensaje del asistente
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                last_ai_message = msg
                break
        
        if last_ai_message:
            response_text = last_ai_message.content
            logger.info(f"✅ Respuesta generada: {len(response_text)} caracteres")
            
            return {
                "status": "completed",
                "answer": response_text,
                "business_info": final_state.get("business_info", {}),
                "thread_id": thread_id,
                "metadata": {
                    "total_messages": len(messages),
                    "agent_type": "central_orchestrator",
                    "pattern": "react_pure"
                }
            }
        else:
            logger.warning("No se encontró respuesta del asistente")
            return {
                "status": "error",
                "answer": "No se pudo generar una respuesta. ¿Podrías intentar nuevamente?",
                "business_info": final_state.get("business_info", {}),
                "thread_id": thread_id
            }
            
    except Exception as e:
        import traceback
        error_detail = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Error en process_message_with_central_orchestrator: {error_detail}")
        logger.error(f"Stack trace completo: {stack_trace}")
        
        return {
            "status": "error",
            "answer": "Hubo un error procesando tu mensaje. ¿Podrías intentar nuevamente?",
            "business_info": {},
            "thread_id": thread_id,
            "error": error_detail,
            "stack_trace": stack_trace
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