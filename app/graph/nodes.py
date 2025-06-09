import logging
from typing import Dict, Any, Literal, List

from dotenv import load_dotenv
from langchain_community.tools import TavilySearchResults
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_qdrant import Qdrant
from langgraph.types import interrupt, Command
from numpy.f2py.crackfortran import previous_context
from qdrant_client import QdrantClient

from app.config.settings import LLM_MODEL, QDRANT_URL, QDRANT_API_KEY
from app.core.prompt import SALES_AUTO_NORT_TALK_PROMPT_2
from app.graph.state import PYMESState

from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)


# --- Definición de Herramientas ---
@tool
def search(query: str) -> str:
    """
    Llama a esta herramienta para buscar en la WEB información externa como precios de mercado actuales,
    reseñas de usuarios recientes, comparativas con modelos de OTRAS marcas, noticias sobre Toyota,
    o cualquier información que NO se espere encontrar en la documentación interna del concesionario.
    """
    try:
        # Crear la instancia de la herramienta Tavily
        # max_results=3 es un buen punto de partida para no sobrecargar al LLM
        tavily_search_tool = TavilySearchResults(
            max_results=3,
            # include_answer=True # Opcional: Tavily puede intentar dar una respuesta directa
            # search_depth="advanced" # Opcional: Búsqueda más profunda (puede ser más lenta)
        )

        # Invocar la herramienta
        # Tavily puede manejar directamente el string de la consulta
        results = tavily_search_tool.invoke(query)

        # Procesar y formatear los resultados para el LLM
        if not results:
            logger.info("Tavily no devolvió resultados.")
            return "No se encontraron resultados relevantes en la búsqueda web."

        # Formatear la salida como un string legible
        formatted_output = f"Resultados de la búsqueda web para '{query}':\n\n"
        # results es una lista de diccionarios
        for i, result in enumerate(results):
            if isinstance(result, dict) and 'content' in result and 'url' in result:
                formatted_output += f"Resultado {i + 1}:\n"
                formatted_output += f"  Contenido: {result.get('content', 'N/A')}\n"  # Usar .get para seguridad
                formatted_output += f"  Fuente URL: {result.get('url', 'N/A')}\n\n"
                # Opcional: incluir 'title' si es útil:
                # title = result.get('title')
                # if title: formatted_output += f"  Título: {title}\n"
            else:
                logger.warning(f"Formato de resultado inesperado de Tavily: {result}")
                formatted_output += f"Resultado {i + 1}: (Formato de datos inesperado)\n\n"

        logger.info(f"Tavily devolvió {len(results)} resultados.")
        return formatted_output.strip()

    except Exception as e:
        logger.error(f"Error durante la búsqueda con Tavily: {str(e)}")
        return f"Se produjo un error al intentar realizar la búsqueda web: {str(e)}"


@tool
def search_documents(query: str, limit: int = 3):
    """
    Busca en la BASE DE DATOS INTERNA del concesionario (documentos, manuales, especificaciones oficiales de Toyota Perú,
    folletos, listas de características) información específica sobre modelos Toyota, versiones, equipamiento,
    detalles técnicos proporcionados por Toyota, etc. Usa esta herramienta cuando necesites datos precisos
    de la documentación oficial de AUTONORT o Toyota Perú. NO la uses para buscar precios de mercado generales o reseñas externas.
    """
    try:
        document_service = get_document_service()
        results = document_service.search_documents(query, limit=limit)

        # Formatear los resultados para mayor legibilidad
        if not results:
            return "No se encontraron documentos relevantes."

        formatted_results = []
        for i, doc in enumerate(results, 1):
            title = doc["metadata"].get("name", f"Documento {i}")
            formatted_results.append(f"Documento {i}: {title}\n{doc['content']}")

        logger.info(f"Búsqueda de documentos para '{query[:50]}...' encontró {len(formatted_results)} resultados")
        return "\n\n---\n\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Error en search_documents: {str(e)}")
        return "Error al buscar documentos."


# Lista de herramientas disponibles para el LLM
tools = [search, search_documents]

# Singleton document service
_document_service = None


def get_document_service() -> DocumentService:
    """Get or create a DocumentService singleton."""
    global _document_service
    if _document_service is None:
        try:
            _document_service = DocumentService()
        except Exception as e:
            logger.error(f"Error initializing document service: {str(e)}")
            raise
    return _document_service


def generate_response(state: PYMESState) -> Dict[str, Any]:
    """
    Generate a response based on chat history, context, and summary.

    Args:
        state: The current state including user input, chat history, and context.

    Returns:
        Updated state with the generated answer.
    """
    try:
        llm = ChatOpenAI(model=LLM_MODEL)
        llm_with_tools = llm.bind_tools(tools)

        messages: List[BaseMessage] = state.get("messages",
                                                [])
        if not messages:
            logger.warning("Agent node called with empty messages state.")
            return {"messages": [AIMessage(
                content="Estimado (a) cliente buen día, le saluda Jordy Merejildo de Autonort TOYOTA  ¿Cómo podemos ayudarte?")]}

        user_query = state["input"]
        # Limitar la cantidad de mensajes en el historial
        recent_messages = state["messages"][-7:] if len(state["messages"]) > 7 else state["messages"]

        # Construir el mensaje del sistema con el contexto y resumen
        system_message_content = SALES_AUTO_NORT_TALK_PROMPT_2.format(
            user_query=user_query,
        )
        system_message_content += "\n\n**Instrucciones Adicionales:** Tienes acceso a una herramienta de búsqueda web (`search`). Úsala si la información proporcionada (contexto, historial) no es suficiente para responder la pregunta del usuario, o si pide explícitamente información externa (ej. reseñas, comparativas actuales, precios de mercado)."

        # Construir el prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message_content),
            MessagesPlaceholder(variable_name="messages"),
            # La entrada del usuario ya debe estar en state["messages"] añadida por el reducer o el servicio
        ])

        # Ejecutar la cadena con el LLM vinculado a herramientas
        chain = prompt | llm_with_tools
        # La entrada para invoke es el estado actual del grafo relevante para el placeholder
        response_message = chain.invoke({"messages": state["messages"]})

        return {
            "messages": [response_message],
        }

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise Exception("I'm sorry, I encountered an error generating a response.")


def summarize_conversation(state: PYMESState) -> Dict[str, Any]:
    """
    Summarizes the conversation and removes old messages.

    Args:
        state: The current state including chat history.

    Returns:
        Updated state with summary and trimmed messages.
    """
    llm = ChatOpenAI(model=LLM_MODEL)

    summary = state.get("summary", "")
    summary_prompt = (
        f"This is the current summary: {summary}\nExtend it with the new messages:"
        if summary else "Create a summary of the conversation above:"
    )

    # Agregar el prompt al historial y ejecutar el resumen con el modelo
    messages = state["messages"] + [HumanMessage(content=summary_prompt)]
    response = llm.invoke(messages)

    # Eliminar todos los mensajes excepto los 2 más recientes
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]

    return {"summary": response.content, "messages": delete_messages}


def human_feedback(state: PYMESState) -> Command:
    """
    Nodo de feedback humano para una conversación multi-turno.
    Espera la retroalimentación del usuario y actualiza el estado.
    Si el usuario escribe "done", "gracias" o "adiós", finaliza la conversación;
    en caso contrario, retorna al nodo de generación para continuar.
    """
    # El print "[human_feedback] Esperando retroalimentación del usuario..."
    # se imprimirá ANTES de que la interrupción ocurra.
    # Cuando el webhook recibe el mensaje del usuario y llama a process_message
    # con is_resuming=True, y luego graph.invoke(Command(resume=user_actual_message)),
    # es entonces cuando la función interrupt() "devuelve" user_actual_message.

    # El siguiente print es útil para ver qué valor se "inyectó" en la interrupción.
    # No se imprimirá hasta que la interrupción se haya reanudado.
    # print("\n[human_feedback] DEBUG: Justo antes de llamar a interrupt()")

    user_input_from_interrupt = interrupt({
        # "answer" aquí es el último AIMessage que el LLM generó antes de este nodo.
        # En la primera vuelta, state["answer"] estará vacío si no se inicializó.
        # En las siguientes, será la respuesta del LLM del turno anterior.
        "answer": state.get("answer", "Esperando respuesta inicial del asistente."), # Proporcionar un default
        "message": "Proporcione su feedback o escriba 'done' para finalizar la conversación:"
    })

    # Este print ahora sí mostrará el feedback real que el usuario envió y que reanudó la interrupción
    print(f"\n[human_feedback] Feedback recibido del usuario (tras reanudar interrupt): {user_input_from_interrupt}")

    # Actualiza el historial de feedback (esto es para tu propio tracking si lo necesitas)
    updated_feedback_list = state.get("feedback", []) + [user_input_from_interrupt]

    # El mensaje del usuario DEBE ser añadido al historial de conversación
    # para que generate_response lo vea.
    user_message_for_history = HumanMessage(content=user_input_from_interrupt)

    # El campo 'input' del estado se usa en generate_response para el prompt.
    # Es correcto actualizarlo con la última entrada del usuario.
    current_user_input_for_state = user_input_from_interrupt

    update_payload = {
        "messages": [user_message_for_history],  # Esto será recogido por add_messages
        "feedback": updated_feedback_list,
        "input": current_user_input_for_state
    }

    if user_input_from_interrupt.strip().lower() in ["done", "gracias", "adiós", "adios"]:
        logger.info(f"Usuario {state.get('thread_id', 'unknown')} finalizó conversación con: {user_input_from_interrupt}")
        return Command(update=update_payload, goto="end_node")
    else:
        logger.info(f"Usuario {state.get('thread_id', 'unknown')} continúa conversación con: {user_input_from_interrupt}")
        return Command(update=update_payload, goto="generate_response")


def end_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo final para cerrar la conversación.

    Args:
        state: El estado actual de la conversación.

    Returns:
        Estado final con información de resumen.
    """
    logger.info("Conversation completed successfully.")
    return {
        "answer": f"Gracias por su consulta sobre vehículos Toyota. Esperamos haberle sido de ayuda.",
        "feedback": state.get("feedback", [])
    }
