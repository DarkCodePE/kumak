import logging
import time
from typing import Dict, Any, List, Literal, Annotated, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.services.memory_service import get_memory_service
from app.services.business_info_manager import get_business_info_manager

logger = logging.getLogger(__name__)


# === MODELOS PYDANTIC PARA STRUCTURED OUTPUT ===

class BusinessInfoExtracted(BaseModel):
    """Modelo Pydantic para extracción estructurada de información del negocio."""
    nombre_empresa: Optional[str] = Field(None, description="Nombre de la empresa o negocio")
    sector: Optional[str] = Field(None, description="Sector o industria (ej: Restaurantes, Software, Retail)")
    productos_servicios_principales: Optional[List[str]] = Field(None, description="Lista de productos o servicios principales")
    desafios_principales: Optional[List[str]] = Field(None, description="Principales desafíos o problemas del negocio")
    ubicacion: Optional[str] = Field(None, description="Ubicación de operación (ciudad, país, online)")
    descripcion_negocio: Optional[str] = Field(None, description="Descripción general del negocio")
    anos_operacion: Optional[int] = Field(None, description="Años de operación del negocio")
    num_empleados: Optional[int] = Field(None, description="Número de empleados")
    
    # Campos de confianza para saber qué tan seguro está el modelo
    confidence_score: Optional[float] = Field(None, description="Puntuación de confianza (0.0-1.0)")
    extracted_fields: Optional[List[str]] = Field(None, description="Lista de campos que se extrajeron en esta pasada")


# === PATRÓN DEL CÓDIGO DE REFERENCIA ===

# === NODOS SIGUIENDO EL PATRÓN DE REFERENCIA ===

def business_info_extraction_node(state: PYMESState) -> Dict[str, Any]:
    """Extract and store important business information from the last message."""
    logger.info("🚀 business_info_extraction_node iniciado")
    
    if not state.get("messages"):
        logger.warning("⚠️ No hay mensajes en el estado")
        return {}

    # Obtener thread_id del estado
    thread_id = get_thread_id_from_state(state)
    logger.info(f"🔗 Thread ID obtenido: {thread_id}")

    business_info_manager = get_business_info_manager()
    current_info = state.get("business_info", {})
    last_message = state["messages"][-1]
    
    logger.info(f"📥 Estado business_info ANTES de extracción: {current_info}")
    logger.info(f"💬 Procesando mensaje: {last_message.content[:100]}...")
    
    # Ejecutar función async de manera robusta
    import asyncio
    try:
        # Intentar ejecutar la función async
        try:
            # Primero intentar obtener el loop actual
            loop = asyncio.get_running_loop()
            # Si hay un loop corriendo, usar ThreadPoolExecutor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    business_info_manager.extract_and_store_business_info(
                        last_message, current_info, thread_id
                    )
                )
                updated_info = future.result()
        except RuntimeError:
            # No hay loop corriendo, usar asyncio.run directamente
            updated_info = asyncio.run(
                business_info_manager.extract_and_store_business_info(
                    last_message, current_info, thread_id
                )
            )
    except Exception as async_error:
        logger.error(f"Error ejecutando función async: {async_error}")
        # En caso de error, devolver la información actual sin cambios
        updated_info = current_info
    
    logger.info(f"📤 Estado business_info DESPUÉS de extracción: {updated_info}")
    
    # Verificar si hubo cambios
    if updated_info != current_info:
        logger.info("✅ ESTADO BUSINESS_INFO ACTUALIZADO - Devolviendo cambios al grafo")
    else:
        logger.info("ℹ️ No hubo cambios en business_info")
    
    result = {"business_info": updated_info}
    logger.info(f"🔄 Devolviendo al grafo: {result}")
    
    return result

def business_info_injection_node(state: PYMESState) -> Dict[str, Any]:
    """Retrieve and inject relevant business information into the context."""
    business_info_manager = get_business_info_manager()
    business_info = state.get("business_info", {})
    
    # Get relevant business info based on recent conversation
    recent_context = " ".join([m.content for m in state.get("messages", [])[-3:]])
    business_context = business_info_manager.format_business_info_for_prompt(business_info)
    
    return {"business_context": business_context}


# === FUNCIONES AUXILIARES ===

def business_info_evaluator_node(state: PYMESState) -> Dict[str, Any]:
    """
    Simple business info extraction node following the reference pattern.
    Replaces the complex evaluator with the simple extraction pattern.
    """
    try:
        logger.info("🔍 business_info_evaluator_node activado")
        
        # Obtener estado actual para logging
        current_business_info = state.get("business_info", {})
        logger.info(f"📊 Estado business_info al INICIO del evaluador: {current_business_info}")
        
        # Obtener thread_id del estado
        thread_id = get_thread_id_from_state(state)
        logger.info(f"🔗 Thread ID obtenido: {thread_id}")

        if not state.get("messages"):
            logger.warning("⚠️ No hay mensajes en el estado")
            return {}

        # Usar el BusinessInfoManager directamente (sin async)
        business_info_manager = get_business_info_manager()
        last_message = state["messages"][-1]
        
        logger.info(f"💬 Procesando mensaje: {last_message.content[:100]}...")
        
        # Ejecutar función async de manera robusta
        import asyncio
        try:
            # Intentar ejecutar la función async
            try:
                # Primero intentar obtener el loop actual
                loop = asyncio.get_running_loop()
                # Si hay un loop corriendo, usar ThreadPoolExecutor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        business_info_manager.extract_and_store_business_info(
                            last_message, current_business_info, thread_id
                        )
                    )
                    updated_info = future.result()
            except RuntimeError:
                # No hay loop corriendo, usar asyncio.run directamente
                updated_info = asyncio.run(
                    business_info_manager.extract_and_store_business_info(
                        last_message, current_business_info, thread_id
                    )
                )
        except Exception as async_error:
            logger.error(f"Error ejecutando función async: {async_error}")
            # En caso de error, devolver la información actual sin cambios
            updated_info = current_business_info
        
        logger.info(f"📤 Estado business_info DESPUÉS de extracción: {updated_info}")
        
        # Verificar si hubo cambios
        if updated_info != current_business_info:
            logger.info("✅ EVALUADOR CONFIRMÓ CAMBIOS EN BUSINESS_INFO")
        else:
            logger.info("ℹ️ Evaluador no detectó cambios")
        
        result = {"business_info": updated_info}
        logger.info(f"🔄 Devolviendo al grafo: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in business info extraction: {str(e)}")
        return {}


def get_thread_id_from_state(state: PYMESState) -> str:
    """Extract thread_id from the state."""
    # Try to get from different sources
    thread_id = state.get("thread_id")

    if not thread_id:
        messages = state.get("messages", [])
        for msg in messages:
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('thread_id'):
                return msg.additional_kwargs['thread_id']

    return thread_id or f"temp_{int(time.time())}"


def extract_business_info_from_conversation(messages: List, current_state: PYMESState) -> Dict[str, Any]:
    """
    DEPRECATED: Simple function replaced by business_info_evaluator_node.
    Kept for compatibility.
    """
    # This function now only returns the current state's information
    return current_state.get("business_info", {})


def extract_research_from_messages(messages: List) -> str:
    """Extract research content from the messages."""
    try:
        research_content = ""
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content
                # Search for research indicators
                if any(keyword in content.lower() for keyword in
                       ["research", "analysis", "opportunities", "trends", "market"]):
                    research_content += content + "\n"

        return research_content.strip() if research_content else None

    except Exception as e:
        logger.error(f"Error extracting research: {str(e)}")
        return None


# === HANDOFF TOOLS BETWEEN AGENTS ===

def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """Creates a handoff tool following the LangGraph pattern."""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transfer control to {agent_name} agent."

    @tool(name, description=description)
    def handoff_tool(
            task_description: Annotated[
                str,
                "Description of what the next agent should do, including all relevant context.",
            ],
            state: Annotated[PYMESState, InjectedState],
    ) -> Command:
        """Execute handoff to the specified agent."""
        # Create task message for the next agent
        task_message = AIMessage(content=f"Transferring to {agent_name}: {task_description}")

        return Command(
            goto=agent_name,
            update={
                "messages": [task_message],
                "current_agent": agent_name,
                "last_handoff": task_description
            }
        )

    return handoff_tool


# Create specific handoff tools
transfer_to_info_extractor = create_handoff_tool(
    agent_name="info_extractor",
    description="Transfer to the business information extraction specialist when you need to collect or update basic company data."
)

transfer_to_researcher = create_handoff_tool(
    agent_name="researcher",
    description="Transfer to the market research specialist when you need to analyze market opportunities, trends, or competitive research."
)

transfer_to_consultant = create_handoff_tool(
    agent_name="consultant",
    description="Transfer to the conversational consultant for general questions, specific doubts, or fluid business conversation."
)


@tool
def get_business_info_status():
    """Check the current status of business information collected."""
    # This tool will check the current status
    return "Business information: In progress/Complete/Missing"


@tool
def get_research_status():
    """Check if market research has been done for this business."""
    return "Research: Not started/In progress/Completed"


# === PROMPTS FOR EACH AGENT ===

SUPERVISOR_PROMPT = """
You are the SUPERVISOR of a team of specialized consultants for PYMES. Your job is to coordinate and direct conversations towards the correct agent.

AVAILABLE AGENTS:
1. **info_extractor**: Specialist in collecting basic business information (name, sector, products, challenges, location, etc.)
2. **researcher**: Specialist in market research, analyzing opportunities and trends in the sector
3. **consultant**: Conversational consultant for specific questions, general questions, and personalized advice

CURRENT STATE:
- Business information: {business_info_status}
- Research done: {research_status}

DECISION RULES:
1. If NO basic business information → **transfer_to_info_extractor**
2. If basic information but NO research → **transfer_to_researcher** 
3. If the user asks specific questions or wants to chat → **transfer_to_consultant**
4. If the user wants to update/correct information → **transfer_to_info_extractor**
5. If the user wants new research → **transfer_to_researcher**

Analyze the user's message and current state, then transfer to the appropriate agent.
DO NOT attempt to answer directly - always transfer to a specialist.
"""

INFO_EXTRACTOR_PROMPT = """
You are a SPECIALIST IN BUSINESS INFORMATION COLLECTION FOR PYMES.

Your job is to collect conversational and friendly the following information:

REQUIRED INFORMATION:
- �� **Company Name**
- 🏭 **Sector/Industry** (e.g. "Restaurants", "Software", "Retail")
- 💼 **Main Products/Services** 
- ⚠️ **Main Challenges** of the business
- 📍 **Location** of operation
- �� **Description** of the business

OPTIONAL INFORMATION:
- Operation years
- Number of employees

INSTRUCTIONS:
- Ask ONE specific question at a time
- Be conversational and empathetic
- Confirm information before continuing
- Use examples to help the user
- When you have ALL the required information, use **transfer_to_researcher**

AVAILABLE TOOLS:
- transfer_to_researcher: When you have complete information
- transfer_to_consultant: If the user has doubts not related to basic data
"""

RESEARCHER_PROMPT = """
You are a SPECIALIST IN MARKET RESEARCH AND OPPORTUNITIES FOR PYMES.

Your job is:
1. Analyze the business information available
2. Perform specific web research on:
   - Sector trends
   - Market opportunities
   - Best practices
   - Competitive analysis
   - Solutions to identified challenges
3. Present structured analysis and recommendations

AVAILABLE TOOLS:
- search: Web search for market research
- transfer_to_consultant: For conversation about results
- transfer_to_info_extractor: If you need more business information

When presenting results, be specific and practical. Ask the user if they want to delve deeper into a specific area.
"""

CONSULTANT_PROMPT = """
You are a CONVERSATIONAL CONSULTANT specialized in PYMES.

Your job is:
- Respond to specific questions about the business
- Provide personalized advice
- Clarify doubts about recommendations
- Maintain fluid and useful conversation
- Generate detailed action plans

AVAILABLE TOOLS:
- search: Web search for specific information
- search_documents: Internal document search
- transfer_to_info_extractor: If you need to update basic information
- transfer_to_researcher: If you need new research

You are empathetic, practical, and results-oriented. Always seek to be useful and actionable.
"""


# === STATE FUNCTIONS ===

def get_business_info_status_from_state(state: PYMESState) -> str:
    """Get the current status of business information."""
    business_info = state.get("business_info", {})
    required_fields = ["nombre_empresa", "sector", "productos_servicios_principales", "ubicacion"]

    if not business_info:
        return "Not started"

    missing_fields = [field for field in required_fields if not business_info.get(field)]

    if not missing_fields:
        return "Complete"
    elif len(missing_fields) < len(required_fields):
        return "Partial"
    else:
        return "Missing"


def get_research_status_from_state(state: PYMESState) -> str:
    """Get the current status of research."""
    context = state.get("context", "")
    web_search = state.get("web_search", "")
    stage = state.get("stage", "")

    if stage == "research_completed" or context or web_search:
        return "Completed"
    elif stage == "research_in_progress":
        return "In progress"
    else:
        return "Not started"


# === AGENT NODES ===

def supervisor_node(state: PYMESState) -> Dict[str, Any]:
    """Supervisor node that decides which agent to use using handoffs."""
    try:
        logger.info("Supervisor analyzing situation...")

        business_info_status = get_business_info_status_from_state(state)
        research_status = get_research_status_from_state(state)

        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        user_message = last_message.content if isinstance(last_message, HumanMessage) else ""

        # Supervisor decision logic (without LLM for simplicity)
        logger.info(f"Info status: {business_info_status}, research: {research_status}")

        # Decision based on clear rules
        if business_info_status in ["Not started", "Missing", "Partial"]:
            agent_target = "info_extractor"
            task_desc = "Collect basic business information that is missing"
        elif business_info_status == "Complete" and research_status == "Not started":
            agent_target = "researcher"
            task_desc = "Perform market research based on business information"
        else:
            agent_target = "consultant"
            task_desc = "Provide conversational advice"

        logger.info(f"Supervisor decided: {agent_target} - {task_desc}")

        # Use Command for handoff
        return {
            "current_agent": agent_target,
            "last_handoff": task_desc,
            "messages": [AIMessage(content=f"Transferring to {agent_target}: {task_desc}")]
        }

    except Exception as e:
        logger.error(f"Error in supervisor_node: {str(e)}")
        # Fallback: go to consultant if there's an error
        return {
            "current_agent": "consultant",
            "messages": [AIMessage(content="Error in supervisor, transferring to consultant...")]
        }


@tool
def save_business_info(info: str):
    """Save extracted business information in long-term memory."""
    try:
        # This tool simulates saving - in reality, it will be handled in the node
        logger.info(f"Saving business information: {info}")
        return "Business information saved successfully in long-term memory"
    except Exception as e:
        logger.error(f"Error saving information: {str(e)}")
        return "Error saving information"


def info_extractor_agent_node(state: PYMESState) -> Dict[str, Any]:
    """Specialized agent for extracting business information using intelligent evaluator."""
    try:
        logger.info("🤖 info_extractor_agent_node activado")
        
        # Verificar estado inicial
        initial_business_info = state.get("business_info", {})
        logger.info(f"📊 Estado business_info INICIAL en agente: {initial_business_info}")

        # First, execute the intelligent evaluator to extract information
        evaluator_result = business_info_evaluator_node(state)
        
        # Get the updated information from the evaluator
        updated_business_info = evaluator_result.get("business_info", {})
        logger.info(f"📊 Estado business_info DESPUÉS del evaluador: {updated_business_info}")
        
        # Verificar si el agente recibió los cambios
        if updated_business_info != initial_business_info:
            logger.info("✅ AGENTE CONFIRMÓ QUE RECIBIÓ ESTADO ACTUALIZADO")
        else:
            logger.info("ℹ️ Agente no detectó cambios en el estado")
        
        # Determine what information is missing
        required_fields = ["nombre_empresa", "sector", "productos_servicios_principales", "ubicacion"]
        missing_fields = [field for field in required_fields if not updated_business_info.get(field)]

        # Generate specific question or complete if we already have everything
        if missing_fields:
            # Generate question for the first missing field
            field = missing_fields[0]
            field_questions = {
                "nombre_empresa": "¡Hola! Para ayudarte mejor, ¿cuál es el nombre de tu empresa o negocio?",
                "sector": "¿En qué sector o industria opera tu negocio? (por ejemplo: restaurantes, software, retail, etc.)",
                "productos_servicios_principales": "¿Cuáles son los principales productos o servicios que ofreces?",
                "ubicacion": "¿Dónde opera tu negocio? (ciudad, país, o si es online)"
            }

            question = field_questions.get(field, "¿Podrías proporcionar más información sobre tu negocio?")

            # IMPORTANTE: Devolver directamente la respuesta sin redirigir a human_feedback
            # Esto evita el bucle infinito
            return {
                "messages": [AIMessage(content=question)],
                "business_info": updated_business_info,
                "answer": question,  # Agregar answer para compatibilidad
                "stage": "info_gathering"
            }
        else:
            # Complete information, transfer to researcher
            logger.info("Business information complete, transferring to researcher")
            
            completion_message = "¡Perfecto! He recopilado toda la información de tu negocio. Ahora voy a investigar oportunidades específicas para tu empresa."

            return {
                "messages": [AIMessage(content=completion_message)],
                "current_agent": "researcher",  # Handoff to researcher
                "last_handoff": "Complete information, start market research",
                "business_info": updated_business_info,
                "answer": completion_message,  # Agregar answer para compatibilidad
                "stage": "info_completed"
            }

    except Exception as e:
        logger.error(f"Error in info_extractor_agent_node: {str(e)}")
        error_message = "Hubo un error. ¿Podrías repetir tu información?"
        return {
            "messages": [AIMessage(content=error_message)],
            "answer": error_message
        }


@tool
def save_research_results(results: str):
    """Save research results in long-term memory."""
    try:
        logger.info(f"Saving research results: {results[:100]}...")
        return "Research results saved successfully"
    except Exception as e:
        logger.error(f"Error saving research: {str(e)}")
        return "Error saving research results"


def researcher_agent_node(state: PYMESState):
    """Specialized agent for market research."""
    try:
        logger.info("Researcher agent activated")

        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)

        # Tools for the researcher
        from app.graph.nodes import search  # Import existing search tool
        researcher_tools = [search, transfer_to_consultant, transfer_to_info_extractor, save_research_results]

        # Create ReAct agent with business information in the prompt
        business_info = state.get("business_info", {})
        enhanced_prompt = RESEARCHER_PROMPT

        if business_info:
            business_context = f"\n\nAVAILABLE BUSINESS INFORMATION:\n{business_info}\n\nUse this information to generate specific and relevant research."
            enhanced_prompt += business_context

        # Create ReAct agent
        agent = create_react_agent(llm, researcher_tools, state_modifier=enhanced_prompt)

        # Execute agent
        result = agent.invoke(state)

        # Save research results if generated
        messages = result["messages"]
        research_content = extract_research_from_messages(messages)

        if research_content:
            memory_service = get_memory_service()
            thread_id = get_thread_id_from_state(state)
            memory_service.save_research_results(thread_id, {"content": research_content, "timestamp": time.time()})

            return {
                "messages": result["messages"],
                "context": research_content,
                "web_search": "Research completed",
                "stage": "research_completed"
            }

        return {"messages": result["messages"]}

    except Exception as e:
        logger.error(f"Error in researcher_agent_node: {str(e)}")
        return {"messages": [AIMessage(content="There was an error in research. Let's try again.")]}


def consultant_agent_node(state: PYMESState):
    """Conversational consultant agent (original chatbot)."""
    try:
        logger.info("Conversational consultant agent activated")

        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)

        # Tools for the consultant
        from app.graph.nodes import search, search_documents
        consultant_tools = [search, search_documents, transfer_to_info_extractor, transfer_to_researcher]

        # Create ReAct agent
        agent = create_react_agent(llm, consultant_tools, state_modifier=CONSULTANT_PROMPT)

        # Execute agent
        result = agent.invoke(state)

        return {"messages": result["messages"]}

    except Exception as e:
        logger.error(f"Error in consultant_agent_node: {str(e)}")
        return {"messages": [AIMessage(content="There was an error. How can I help you?")]}


def human_feedback_node(state: PYMESState) -> Command:
    """
    Human feedback node for the supervisor architecture.
    Based on the successful pattern from the reference code.
    """
    logger.info("🔄 human_feedback_node: Esperando entrada del usuario...")

    # Usar interrupt() siguiendo el patrón del código de referencia
    # NO usar try-catch aquí porque interrupt() es el comportamiento esperado
    user_input_from_interrupt = interrupt({
        "answer": state.get("answer", "Esperando respuesta del asistente."),
        "message": "Proporcione su respuesta:"
    })

    logger.info(f"🔄 human_feedback_node: Entrada recibida: {user_input_from_interrupt}")

    # Actualizar historial de feedback
    updated_feedback_list = state.get("feedback", []) + [user_input_from_interrupt]

    # Crear mensaje de usuario para el historial
    user_message_for_history = HumanMessage(content=user_input_from_interrupt)

    # Payload de actualización
    update_payload = {
        "messages": [user_message_for_history],
        "feedback": updated_feedback_list,
        "input": user_input_from_interrupt
    }

    # Verificar si el usuario quiere terminar
    termination_words = ["done", "thanks", "bye", "adios", "terminate", "exit", "gracias", "chau", "fin"]
    if user_input_from_interrupt.strip().lower() in termination_words:
        logger.info(f"🔄 human_feedback_node: Usuario terminó conversación: {user_input_from_interrupt}")
        return Command(update=update_payload, goto=END)
    else:
        logger.info(f"🔄 human_feedback_node: Usuario continúa conversación: {user_input_from_interrupt}")
        # Volver al business_evaluator para procesar la nueva entrada
        return Command(update=update_payload, goto="business_evaluator")


# === ROUTING FUNCTIONS ===

def route_after_supervisor(state: PYMESState) -> Literal[
    "info_extractor", "researcher", "consultant", "human_feedback"]:
    """Route after supervisor based on transfer decision."""
    # Check if there's a specified agent in the state
    current_agent = state.get("current_agent")
    if current_agent in ["info_extractor", "researcher", "consultant"]:
        return current_agent

    # Fallback: analyze messages for tool calls
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        tool_name = tool_call["name"]

        if tool_name == "transfer_to_info_extractor":
            return "info_extractor"
        elif tool_name == "transfer_to_researcher":
            return "researcher"
        elif tool_name == "transfer_to_consultant":
            return "consultant"

    # Default: go to human feedback
    return "human_feedback"


def route_after_agents(state: PYMESState) -> Literal["human_feedback"]:
    """
    Route after specialized agents.
    Siguiendo el patrón del código de referencia, siempre ir a human_feedback
    para evitar bucles infinitos.
    """
    logger.info("🔀 route_after_agents: Dirigiendo a human_feedback")
    
    # Siempre ir a human_feedback después de los agentes especializados
    # Esto evita bucles infinitos y sigue el patrón del código de referencia
    return "human_feedback"


def create_supervisor_pymes_graph():
    """
    Create the main graph with supervisor architecture.
    """
    try:
        logger.info("Creating supervisor PYMES graph...")

        # Create the graph
        workflow = StateGraph(PYMESState)

        # === ADD NODES ===
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("business_evaluator", business_info_evaluator_node)  # Intelligent evaluator node
        workflow.add_node("info_extractor", info_extractor_agent_node)
        workflow.add_node("researcher", researcher_agent_node)
        workflow.add_node("consultant", consultant_agent_node)
        workflow.add_node("human_feedback", human_feedback_node)

        # === DEFINE FLOW ===

        # Start -> Business evaluator -> Supervisor
        workflow.add_edge(START, "business_evaluator")
        workflow.add_edge("business_evaluator", "supervisor")

        # Supervisor -> Specialized agents or feedback
        workflow.add_conditional_edges(
            "supervisor",
            route_after_supervisor,
            {
                "info_extractor": "info_extractor",
                "researcher": "researcher",
                "consultant": "consultant",
                "human_feedback": "human_feedback"
            }
        )

        # Agents -> human_feedback (evita bucles infinitos)
        workflow.add_conditional_edges(
            "info_extractor",
            route_after_agents,
            {
                "human_feedback": "human_feedback"
            }
        )

        workflow.add_conditional_edges(
            "researcher",
            route_after_agents,
            {
                "human_feedback": "human_feedback"
            }
        )

        workflow.add_conditional_edges(
            "consultant",
            route_after_agents,
            {
                "human_feedback": "human_feedback"
            }
        )

        # Human feedback uses Command to decide where to go
        # No need for static edge because uses Command(goto=...)

        # === COMPILE ===
        from app.database.postgres import get_postgres_saver, get_postgres_store

        store = get_postgres_store()
        checkpointer = get_postgres_saver()

        compiled_graph = workflow.compile(
            checkpointer=checkpointer,
            store=store
        )

        logger.info("Supervisor PYMES graph compiled successfully")
        return compiled_graph

    except Exception as e:
        logger.error(f"Error creating supervisor graph: {str(e)}")
        raise


# Compatibility function
def create_chat_graph():
    """Compatibility function that returns the new supervisor graph."""
    return create_supervisor_pymes_graph()