import logging
import platform

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from app.graph.nodes import generate_response, summarize_conversation, human_feedback, \
   end_node, tools
from app.database.postgres import get_postgres_saver, get_postgres_store, get_async_postgres_saver
import os
from dotenv import load_dotenv
from typing import Optional, Literal

from app.graph.state import PYMESState

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


def should_summarize(state: PYMESState) -> str:
    """Decide si resumir o continuar."""
    return "summarize_conversation" if len(state["messages"]) > 6 else "generate_response"


# --- Función de Enrutamiento Condicional ---
def should_continue(state: PYMESState) -> Literal["action", "human_feedback"]:
    """
    Decide si ejecutar herramientas o pedir feedback humano.
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    # Si el último mensaje es de la IA y tiene llamadas a herramientas, ir al nodo de acción
    if isinstance(last_message, AIMessage) and getattr(last_message, 'tool_calls', None) and last_message.tool_calls:
        logger.info("Routing: LLM solicitó herramientas -> action")
        return "action"
    # De lo contrario, ir a feedback humano
    else:
        logger.info("Routing: LLM generó respuesta directa o hubo un error -> human_feedback")
        return "human_feedback"


def create_chat_graph():
    """
    Create and compile the chat graph with the node functions.

    Returns:
        The compiled graph ready to be invoked
    """
    try:
        # Create the graph with our State type
        workflow = StateGraph(PYMESState)
        tool_node_executor = ToolNode(tools)

        # Añadir los nodos al grafo
        workflow.add_node("generate_response", generate_response)

        workflow.add_node("action", tool_node_executor)
        workflow.add_node("human_feedback", human_feedback)
        # workflow.add_node("summarize_conversation", summarize_conversation) # Si se usa
        workflow.add_node("end_node", end_node)

        # Definir el punto de entrada
        workflow.add_edge(START, "generate_response")
        # Después de generate_response, decidir si ejecutar herramientas o pedir feedback
        workflow.add_conditional_edges(
            "generate_response",  # Nodo de origen
            should_continue,  # Función que decide la ruta
            {
                "action": "action",  # Si should_continue devuelve "action", ir a 'action'
                "human_feedback": "human_feedback"  # Si devuelve "human_feedback", ir a 'human_feedback'
            }
        )

        # Después de ejecutar las herramientas ('action'), volver a llamar al LLM ('generate_response')
        workflow.add_edge("action", "generate_response")

        # Después del feedback humano ('human_feedback'):
        #    - Si el usuario responde 'done', etc., el nodo human_feedback usa Command(goto='end_node')
        #    - Si el usuario da feedback normal, volvemos a 'generate_response' para procesarlo
        workflow.add_edge("human_feedback", "generate_response")  # Conexión por defecto si no se va a end_node

        # Definir punto final (se llega a través del Command en human_feedback)
        workflow.set_finish_point("end_node")

        store = get_postgres_store()
        checkpointer = get_postgres_saver()
        # Compile the graph with the checkpointer
        compiled_graph = workflow.compile(checkpointer=checkpointer, store=store)

        logger.info("Chat graph compiled successfully")
        return compiled_graph

    except Exception as e:
        print(f"Error creating chat graph: {str(e)}")
        logger.error(f"Error creating chat graph: {str(e)}")
        raise
