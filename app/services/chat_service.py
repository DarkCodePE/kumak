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

        # Create the chat graph
        logger.info(f"Creating chat graph for thread {thread_id} (WhatsApp: {is_whatsapp})")
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
                "messages": [HumanMessage(content=message)],  # Agregar mensaje inicial directamente
                "business_info": {},
                "growth_goals": {},
                "business_challenges": {},
                "stage": "info_gathering",
                "growth_proposal": None,
                "context": "",
                "summary": "",
                "web_search": None,
                "documents": None
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
        state_snapshot = graph.get_state(config)

        # Check for interrupts - more robust checking
        is_interrupted = False
        interrupt_info = None

        # Check if there are pending tasks with interrupts
        if state_snapshot.tasks:
            for task in state_snapshot.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    is_interrupted = True
                    interrupt_info = task.interrupts[0].value if task.interrupts else None
                    logger.info(f"Graph interrupted for thread {thread_id}, interrupt data: {interrupt_info}")
                    break

        # Alternative check: see if next node is human_feedback
        if not is_interrupted and state_snapshot.next:
            if any("human_feedback" in str(node) for node in state_snapshot.next):
                is_interrupted = True
                logger.info(f"Graph interrupted at human_feedback for thread {thread_id}")

        # Extract the final answer
        final_answer = "No se pudo generar una respuesta."
        final_state_values = state_snapshot.values
        all_messages: List[BaseMessage] = final_state_values.get("messages", [])

        if all_messages:
            # Search for the last AI message
            for msg in reversed(all_messages):
                if isinstance(msg, AIMessage):
                    final_answer = msg.content
                    logger.info(f"Found last AI message content for thread {thread_id}")
                    break
        else:
            logger.warning(f"No messages found in final state values for thread {thread_id}")

        # Prepare response based on channel
        response = {
            "thread_id": thread_id,
            "message": message,
            "answer": final_answer,
            "status": "interrupted" if is_interrupted else "completed"
        }

        # Add interrupt-specific information
        if is_interrupted:
            response["interrupt_message"] = "Proporcione su feedback o escriba 'done' para finalizar"
            if interrupt_info:
                response["interrupt_data"] = interrupt_info

        # Add WhatsApp-specific handling
        if is_whatsapp:
            response["channel"] = "whatsapp"
            # Truncate very long messages for WhatsApp
            if len(final_answer) > 4000:
                response["answer"] = final_answer[:3990] + "...\n\n💬 Mensaje truncado"

        logger.info(f"Message processed successfully for thread {thread_id}, status: {response['status']}")
        return response

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