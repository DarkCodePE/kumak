import logging
from typing import Dict, Any, List, Optional
import traceback
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.types import Command

from app.database.postgres import get_postgres_saver, get_async_postgres_saver
from app.graph.intelligent_supervisor import create_intelligent_supervisor_graph

logger = logging.getLogger(__name__)

def process_message(
        message: str,
        thread_id: str,
        is_resuming: bool = False,
        reset_thread: bool = False
) -> Dict[str, Any]:
    """
    Process a chat message using the LangGraph workflow.
    Supports both initial messages and resuming after interrupts.
    Optimized for WhatsApp integration.

    Args:
        message: The user's message
        thread_id: A unique identifier for this conversation thread
        is_resuming: Whether this is resuming after an interrupt
        reset_thread: Whether to reset the thread and start a new conversation

    Returns:
        dict: The result containing answer, status (completed/interrupted), and thread_id
    """
    try:
        # Detectar si es un thread de WhatsApp
        is_whatsapp = thread_id.startswith("whatsapp_")

        # Create the Supervisor PYMES graph
        logger.info(f"Creating Supervisor PYMES graph for thread {thread_id} (WhatsApp: {is_whatsapp})")
        graph = create_intelligent_supervisor_graph()
        logger.info(f"Supervisor PYMES graph created successfully for thread {thread_id}")

        # Set up configuration with the thread_id and recursion limit
        config = {
            "configurable": {
                "thread_id": thread_id,
                "reset_thread": reset_thread
            },
            "recursion_limit": 100  # Aumentar límite de recursión para evitar errores
        }

        # Check if we're resuming from an interrupt
        if is_resuming:
            logger.info(f"Resuming graph execution for thread {thread_id}")
            # Use Command to resume with the user's message
            graph_input = Command(resume=message)
        else:
            logger.info(f"Starting new graph execution for thread {thread_id}")

            # Try to get existing state for non-reset conversations
            state = None
            if not reset_thread:
                try:
                    state = graph.get_state(config)
                    logger.info(f"Retrieved existing state for thread {thread_id}")
                except Exception as e:
                    logger.info(f"No existing state found for thread {thread_id}: {str(e)}")

            # Prepare the initial state
            initial_state = {
                "input": message,
                "messages": [HumanMessage(content=message)],
                "business_info": {},
                "growth_goals": {},
                "business_challenges": {},
                "stage": "info_gathering",
                "growth_proposal": None,
                "context": "",
                "summary": "",
                "web_search": None,
                "documents": None,
                "answer": "",
                "human_feedback": []
            }

            graph_input = initial_state

        # Execute the graph
        try:
            logger.info(f"Invoking graph for thread {thread_id}")
            result = graph.invoke(graph_input, config)
            logger.info(f"Graph execution completed or paused for thread {thread_id}")
        except Exception as graph_error:
            logger.error(f"Error during graph execution: {str(graph_error)}")
            logger.error(f"Graph execution traceback: {traceback.format_exc()}")
            raise graph_error

        # Get the current state after execution
        state = graph.get_state(config)

        # Check if we're in an interrupt state
        is_interrupted = False
        interrupt_data = None
        
        # Check for interrupts in the state
        if hasattr(state, 'tasks') and state.tasks:
            for task in state.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    is_interrupted = True
                    interrupt_data = task.interrupts[0] if task.interrupts else None
                    logger.info(f"Graph interrupted with data: {interrupt_data}")
                    break
        
        # Fallback: check if next node is human_feedback
        if not is_interrupted and state.next and any("human_feedback" in node for node in state.next):
            is_interrupted = True
            logger.info(f"Graph interrupted at human_feedback for thread {thread_id}")

        # --- Obtener estado y comprobar interrupción ---
        # Obtener el checkpoint MÁS RECIENTE (que ahora sabemos es un dict)
        latest_checkpoint_dict: Optional[Dict] = graph.checkpointer.get(config)
        if not latest_checkpoint_dict:
            logger.error(f"[Thread: {thread_id}] CRITICAL: Checkpoint dictionary not found after invocation.")
            return {"status": "error", "error": "Checkpoint dict retrieval failed"}

        # *** CORRECCIÓN DEFINITIVA AQUÍ ***
        # Acceder directamente a la clave 'channel_values' del diccionario
        final_state_values: Dict[str, Any] = latest_checkpoint_dict.get('channel_values', {})  # Usa .get para seguridad
        # *********************************

        # Obtener 'next' del StateSnapshot (esto sigue igual)
        state_snapshot = graph.get_state(config)
        next_nodes = state_snapshot.next
        logger.info(f"[Thread: {thread_id}] Latest state retrieved. Next nodes: {next_nodes}")

        # --- Extraer la respuesta final (usando final_state_values) ---
        final_answer = "El asistente no generó una respuesta en este turno."
        
        # Si hay una interrupción, usar los datos de la interrupción
        if is_interrupted and interrupt_data:
            try:
                # interrupt_data es un objeto Interrupt de LangGraph
                if hasattr(interrupt_data, 'value') and isinstance(interrupt_data.value, dict):
                    interrupt_value = interrupt_data.value
                    if 'answer' in interrupt_value:
                        final_answer = interrupt_value['answer']
                        logger.info(f"[Thread: {thread_id}] Using interrupt answer: {final_answer[:100]}...")
                    else:
                        logger.info(f"[Thread: {thread_id}] Interrupt value keys: {list(interrupt_value.keys())}")
                elif isinstance(interrupt_data, dict) and 'answer' in interrupt_data:
                    final_answer = interrupt_data['answer']
                    logger.info(f"[Thread: {thread_id}] Using interrupt answer: {final_answer[:100]}...")
                else:
                    logger.info(f"[Thread: {thread_id}] Interrupt data format: {type(interrupt_data)}")
            except Exception as e:
                logger.error(f"[Thread: {thread_id}] Error extracting interrupt data: {str(e)}")
        
        # Si no hay datos de interrupción, buscar en los mensajes
        if final_answer == "El asistente no generó una respuesta en este turno.":
            # Usar .get() en el diccionario final_state_values
            all_messages: List[BaseMessage] = final_state_values.get("messages", [])
            # ***********************
            if all_messages:
                # Search for the last AI message that's not an error message
                for msg in reversed(all_messages):
                    if isinstance(msg, AIMessage):
                        # Skip error messages from human_feedback_node
                        if "Error procesando entrada" not in msg.content:
                            final_answer = msg.content
                            logger.info(f"[Thread: {thread_id}] Found last AI message content.")
                            break
                    # Handle other potential message formats
                    elif hasattr(msg, 'role') and msg.get('role') == 'ai':
                        content = msg.get('content', 'No content found')
                        if "Error procesando entrada" not in content:
                            final_answer = content
                            logger.info(f"[Thread: {thread_id}] Found last AI message from role.")
                            break
            else:
                logger.warning(f"[Thread: {thread_id}] No messages found in final state values.")

        # Return appropriate response based on whether we're interrupted
        return {
            "thread_id": thread_id,
            "message": message,
            "answer": final_answer,
            "status": "interrupted" if is_interrupted else "completed",
            "interrupt_message": "Proporcione su feedback o escriba 'done' para finalizar" if is_interrupted else None
        }

    except Exception as e:
        error_detail = str(e) if str(e) else "Unknown error (empty exception message)"
        stack_trace = traceback.format_exc()
        logger.error(f"Error processing message for thread {thread_id}: {error_detail}")
        logger.error(f"Stack trace: {stack_trace}")

        # Return user-friendly error based on channel
        error_message = "I'm sorry, I encountered an error. Technical details: " + error_detail
        if thread_id.startswith("whatsapp_"):
            error_message = "Disculpa, encontré un problema técnico. Por favor intenta nuevamente."

        return {
            "thread_id": thread_id,
            "message": message,
            "answer": error_message,
            "error": error_detail,
            "status": "error",
            "channel": "whatsapp" if thread_id.startswith("whatsapp_") else "api"
        }


async def get_chat_history(thread_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve the chat history for a given thread.
    Enhanced for WhatsApp integration.

    Args:
        thread_id: The thread ID

    Returns:
        List of message objects with role and content
    """
    try:
        is_whatsapp = thread_id.startswith("whatsapp_")
        logger.info(f"Retrieving chat history for thread {thread_id} (WhatsApp: {is_whatsapp})")

        # Create the chat graph to access its API
        graph = create_chat_graph()

        # Create a configuration for the thread
        config = {"configurable": {"thread_id": thread_id}}

        # Retrieve the state
        try:
            state_snapshot = graph.get_state(config)
            logger.info(f"Retrieved state snapshot for thread {thread_id}")
        except Exception as e:
            logger.error(f"Error retrieving state from graph: {str(e)}")
            logger.error(traceback.format_exc())
            return []

        # Extract chat history from the values
        chat_history = state_snapshot.values.get("messages", [])

        if not chat_history:
            logger.info(f"Empty chat history for thread {thread_id}")
            return []

        # Format into a more user-friendly structure
        formatted_history = []

        # Process each message in the chat history
        for message in chat_history:
            # Skip any items that don't have the expected structure
            if not hasattr(message, 'content'):
                continue

            if isinstance(message, HumanMessage):
                formatted_history.append({
                    "role": "human",
                    "content": message.content,
                    "timestamp": getattr(message, 'timestamp', None)
                })
            elif isinstance(message, AIMessage):
                formatted_history.append({
                    "role": "ai",
                    "content": message.content,
                    "timestamp": getattr(message, 'timestamp', None),
                    "tool_calls": getattr(message, 'tool_calls', None)
                })

        logger.info(f"Retrieved {len(formatted_history)} messages for thread {thread_id}")
        return formatted_history

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error retrieving chat history for thread {thread_id}: {str(e)}")
        logger.error(f"Stack trace: {stack_trace}")
        return []


def get_active_whatsapp_threads() -> List[str]:
    """
    Get all active WhatsApp threads.
    Useful for monitoring and debugging.
    """
    try:
        # This would need to be implemented based on your persistence layer
        # For now, return empty list
        return []
    except Exception as e:
        logger.error(f"Error getting active WhatsApp threads: {str(e)}")
        return []