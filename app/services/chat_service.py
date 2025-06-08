import logging
from typing import Dict, Any, List, Optional
import traceback
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.types import Command

from app.database.postgres import get_postgres_saver, get_async_postgres_saver
from app.graph.chat_graph import create_chat_graph

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

    Args:
        message: The user's message
        thread_id: A unique identifier for this conversation thread
        is_resuming: Whether this is resuming after an interrupt
        reset_thread: Whether to reset the thread and start a new conversation

    Returns:
        dict: The result containing answer, status (completed/interrupted), and thread_id
    """
    final_state_values = {}
    try:
        # Create the chat graph
        logger.info(f"Creating chat graph for thread {thread_id}")
        graph = create_chat_graph()
        logger.info(f"Chat graph created successfully for thread {thread_id}")

        # Set up configuration with the thread_id
        config = {
            "configurable": {
                "thread_id": thread_id,
                "reset_thread": reset_thread
            }
        }

        # Check if we're resuming from an interrupt
        if is_resuming:
            logger.info(f"Resuming graph execution for thread {thread_id}")
            # Use Command to resume with the user's message
            graph_input = Command(resume=message)
        else:
            logger.info(f"Starting new graph execution for thread {thread_id}")
            # For new conversations, build the initial state
            state = None

            # Try to get existing state for non-reset conversations
            if not reset_thread:
                try:
                    state = graph.get_state(config)
                    logger.info(f"Retrieved existing state for thread {thread_id}")
                except Exception as e:
                    logger.info(f"No existing state found for thread {thread_id}: {str(e)}")

            # Prepare the initial state
            initial_state = {
                "input": message,
                "messages": [],
                "context": "",
                "answer": "",
                "vehicle_info": {},
                "human_feedback": [],
                "summary": ""
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

        # Check if we hit an interrupt (graph is waiting at human_feedback node)
        # Get the current state after execution
        state = graph.get_state(config)

        # If the next node to execute is human_feedback, we're in an interrupt
        is_interrupted = False
        if state.next and any("human_feedback" in node for node in state.next):
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
        final_answer_content = "El asistente no generó una respuesta en este turno."
        # Usar .get() en el diccionario final_state_values
        all_messages: List[BaseMessage] = final_state_values.get("messages", [])
        # ***********************
        if all_messages:
            # Search for the last AI message
            for msg in reversed(all_messages):
                if isinstance(msg, AIMessage):
                    final_answer = msg.content
                    logger.info(f"[Thread: {thread_id}] Found last AI message content.")
                    break
                # Handle other potential message formats
                elif hasattr(msg, 'role') and msg.get('role') == 'ai':
                    final_answer = msg.get('content', 'No content found')
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
        logger.error(f"Error processing message: {error_detail}")
        logger.error(f"Stack trace: {stack_trace}")
        return {
            "thread_id": thread_id,
            "message": message,
            "answer": f"I'm sorry, I encountered an error. Technical details: {error_detail}",
            "error": error_detail,
            "status": "error"
        }

async def get_chat_history(thread_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve the chat history for a given thread.

    Args:
        thread_id: The thread ID

    Returns:
        List of message objects with role and content
    """
    try:
        # Create the chat graph to access its API
        logger.info(f"Creating chat graph for thread {thread_id}")
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
                    "content": message.content
                })
            elif isinstance(message, AIMessage):
                formatted_history.append({
                    "role": "ai",
                    "content": message.content
                })
            elif hasattr(message, 'type') and message.type in ["human", "ai"]:
                formatted_history.append({
                    "role": message.type,
                    "content": message.content
                })
            elif hasattr(message, '__class__') and hasattr(message.__class__, '__name__'):
                # Fallback: Determine the role based on message class name
                role = "human" if "Human" in message.__class__.__name__ else "ai"
                formatted_history.append({
                    "role": role,
                    "content": message.content
                })

        logger.info(f"Retrieved {len(formatted_history)} messages for thread {thread_id}")
        return formatted_history

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Error retrieving chat history: {str(e)}")
        logger.error(f"Stack trace: {stack_trace}")
        return []
