"""
Sistema de handoffs mejorado para arquitectura multi-agente.
Implementa las mejores prácticas de LangGraph usando Command, Send(), y handoffs explícitos.
"""

import logging
from typing import Annotated, Literal, List, Dict, Any
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, Send
from langgraph.graph import StateGraph, START, END

from app.graph.state import PYMESState
from app.services.business_info_manager import get_business_info_manager

logger = logging.getLogger(__name__)

# === HANDOFF TOOLS ===

def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """Crea una herramienta de handoff para transferir control a otro agente."""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transferir control a {agent_name}"

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[PYMESState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Transferido exitosamente a {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        
        logger.info(f"🔄 Handoff: Transfiriendo control a {agent_name}")
        
        return Command(
            goto=agent_name,
            update={"messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )
    
    return handoff_tool

def create_task_handoff_tool(*, agent_name: str, description: str | None = None):
    """Crea una herramienta de handoff con descripción de tarea específica."""
    name = f"assign_task_to_{agent_name}"
    description = description or f"Asignar tarea específica a {agent_name}"

    @tool(name, description=description)
    def task_handoff_tool(
        task_description: Annotated[
            str,
            "Descripción detallada de la tarea que debe realizar el agente, incluyendo todo el contexto relevante."
        ],
        state: Annotated[PYMESState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        # Crear mensaje de tarea para el agente específico
        task_message = {"role": "user", "content": task_description}
        
        # Crear estado específico para el agente con la tarea
        agent_input = {
            **state,
            "messages": [task_message],
            "assigned_task": task_description,
            "requesting_agent": "supervisor"
        }
        
        logger.info(f"📋 Task Handoff: Asignando tarea a {agent_name}: {task_description[:100]}...")
        
        return Command(
            goto=[Send(agent_name, agent_input)],
            graph=Command.PARENT,
        )
    
    return task_handoff_tool

# === HERRAMIENTAS DE HANDOFF ESPECÍFICAS ===

# Handoffs simples (pasan todo el estado)
transfer_to_info_completion = create_handoff_tool(
    agent_name="info_completion_agent",
    description="Transferir a agente de recopilación de información empresarial"
)

transfer_to_research_router = create_handoff_tool(
    agent_name="research_router", 
    description="Transferir a router de investigación para evaluar necesidades de research"
)

transfer_to_researcher = create_handoff_tool(
    agent_name="researcher",
    description="Transferir a agente investigador para análisis de mercado"
)

transfer_to_conversational = create_handoff_tool(
    agent_name="conversational_agent",
    description="Transferir a agente conversacional para consultas generales"
)

# Handoffs con tareas específicas (usan Send())
assign_research_task = create_task_handoff_tool(
    agent_name="researcher",
    description="Asignar tarea específica de investigación de mercado"
)

assign_info_task = create_task_handoff_tool(
    agent_name="info_completion_agent", 
    description="Asignar tarea específica de recopilación de información"
)

assign_conversation_task = create_task_handoff_tool(
    agent_name="conversational_agent",
    description="Asignar consulta específica al agente conversacional"
)

# === NODOS CON COMMAND ===

def intelligent_supervisor_node(state: PYMESState) -> Command[Literal[
    "info_completion_agent", "research_router", "researcher", "conversational_agent", END
]]:
    """
    Supervisor inteligente que usa Command para routing dinámico.
    Combina evaluación de estado y decisión de routing en un solo nodo.
    """
    try:
        logger.info("🧠 intelligent_supervisor_node: Analizando situación y decidiendo routing...")
        
        # 1. Extraer información empresarial del último mensaje
        messages = state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        # 2. Extraer información empresarial si hay mensaje del usuario
        business_info = state.get("business_info", {})
        if user_message and len(messages) > 1:  # No es el primer mensaje
            try:
                business_manager = get_business_info_manager()
                thread_id = f"temp_{hash(user_message) % 10000}"
                
                # ✅ CORRECCIÓN: Usar asyncio.run() para llamada asíncrona en nodo síncrono
                import asyncio
                try:
                    # Intentar usar el loop existente si está disponible
                    loop = asyncio.get_running_loop()
                    # Si hay un loop corriendo, crear una tarea
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, business_manager.extract_info(user_message, thread_id, business_info))
                        updated_info = future.result()
                except RuntimeError:
                    # No hay loop corriendo, usar asyncio.run() directamente
                    updated_info = asyncio.run(business_manager.extract_info(user_message, thread_id, business_info))
                
                if updated_info != business_info:
                    business_info = updated_info
                    logger.info("✅ Nueva información empresarial extraída")
                    logger.info(f"📊 Información actualizada: {business_info}")
            except Exception as e:
                logger.warning(f"Error extrayendo información: {str(e)}")
        
        # 3. Evaluar completitud de información
        critical_fields = ["nombre_empresa", "ubicacion", "productos_servicios_principales", "descripcion_negocio"]
        missing_critical = [field for field in critical_fields if not business_info.get(field)]
        can_research = len(missing_critical) == 0
        
        # 4. Detectar intención del usuario
        message_lower = user_message.lower()
        wants_research = any(keyword in message_lower for keyword in 
                           ["investiga", "analiza", "oportunidades", "mercado", "competencia", "crecimiento"])
        wants_conversation = any(keyword in message_lower for keyword in 
                               ["qué opinas", "consejo específico", "recomienda algo", "tu opinión"])
        wants_to_change = any(keyword in message_lower for keyword in 
                            ["corrección", "cambiar", "actualizar", "mejor dicho", "en realidad"])
        
        # 5. Verificar terminación
        termination_words = ["done", "thanks", "bye", "adios", "terminate", "exit", "gracias", "chau", "fin"]
        if user_message.strip().lower() in termination_words:
            logger.info("🔚 Usuario terminó conversación")
            return Command(
                update={"business_info": business_info},
                goto=END
            )
        
        # 6. LÓGICA DE ROUTING CON COMMAND - PRIORIDAD CORREGIDA
        
        # PRIORIDAD 1: Cambiar información
        if wants_to_change:
            logger.info("🔄 Routing: info_completion_agent (cambiar información)")
            return Command(
                update={
                    "business_info": business_info,
                    "routing_reason": "Usuario quiere cambiar información",
                    "change_mode": True
                },
                goto="info_completion_agent"
            )
        
        # PRIORIDAD 2: ⚠️ CRÍTICO - Falta información necesaria (antes que conversación)
        elif not can_research:
            logger.info("🔄 Routing: info_completion_agent (faltan datos críticos)")
            return Command(
                update={
                    "business_info": business_info,
                    "routing_reason": "Faltan campos críticos",
                    "missing_fields": missing_critical,
                    "completeness": (len(critical_fields) - len(missing_critical)) / len(critical_fields)
                },
                goto="info_completion_agent"
            )
        
        # PRIORIDAD 3: Investigación específica (con información completa)
        elif wants_research:
            logger.info("🔄 Routing: researcher (investigación solicitada)")
            return Command(
                update={
                    "business_info": business_info,
                    "routing_reason": "Usuario solicita investigación",
                    "research_readiness": 1.0
                },
                goto="researcher"
            )
        
        # PRIORIDAD 4: Conversación general (solo con información completa)
        elif wants_conversation:
            logger.info("🔄 Routing: conversational_agent")
            return Command(
                update={
                    "business_info": business_info,
                    "routing_reason": "Usuario quiere conversación general"
                },
                goto="conversational_agent"
            )
        
        # PRIORIDAD 5: Información completa, preguntar sobre investigación
        else:
            logger.info("🔄 Routing: research_router (información completa)")
            return Command(
                update={
                    "business_info": business_info,
                    "routing_reason": "Información completa, consultar sobre investigación",
                    "should_ask_research_intent": True
                },
                goto="research_router"
            )
            
    except Exception as e:
        logger.error(f"Error in intelligent_supervisor_node: {str(e)}")
        return Command(
            update={"routing_reason": "Error en supervisor, fallback a info"},
            goto="info_completion_agent"
        )

def enhanced_human_feedback_node(state: PYMESState) -> Command[Literal["intelligent_supervisor"]]:
    """
    Nodo de feedback humano mejorado que usa Command para routing directo.
    """
    logger.info("🔄 enhanced_human_feedback_node: Esperando entrada del usuario...")

    # Obtener la respuesta más reciente del último mensaje AI
    messages = state.get("messages", [])
    latest_answer = "Esperando respuesta del asistente."
    
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            latest_answer = message.content
            break
    
    logger.info(f"🔄 Usando respuesta más reciente: {latest_answer[:100]}...")

    # Usar interrupt() con la respuesta más reciente
    from langgraph.types import interrupt
    user_input_from_interrupt = interrupt({
        "answer": latest_answer,
        "message": "Proporcione su respuesta:"
    })

    logger.info(f"🔄 Entrada recibida: {user_input_from_interrupt}")

    # Actualizar historial de feedback
    updated_feedback_list = state.get("feedback", []) + [user_input_from_interrupt]
    user_message_for_history = HumanMessage(content=user_input_from_interrupt)

    # Usar Command para actualizar estado y dirigir al supervisor
    return Command(
        update={
            "messages": [user_message_for_history],
            "feedback": updated_feedback_list,
            "input": user_input_from_interrupt
        },
        goto="intelligent_supervisor"
    )

# === FUNCIONES DE ROUTING SIMPLIFICADAS ===

def route_from_agents(state: PYMESState) -> Literal["enhanced_human_feedback"]:
    """Routing simple desde agentes especializados de vuelta al feedback humano."""
    logger.info("🔀 Routing desde agente especializado a human feedback")
    return "enhanced_human_feedback"

def conditional_entry_point(state: PYMESState) -> Literal["intelligent_supervisor"]:
    """Entry point condicional que siempre va al supervisor inteligente."""
    logger.info("🚀 Entry point: Dirigiendo al supervisor inteligente")
    return "intelligent_supervisor"

# === HERRAMIENTAS PARA AGENTES ESPECIALIZADOS ===

# Herramientas que pueden usar los agentes para hacer handoffs
HANDOFF_TOOLS = [
    transfer_to_info_completion,
    transfer_to_research_router, 
    transfer_to_researcher,
    transfer_to_conversational,
    assign_research_task,
    assign_info_task,
    assign_conversation_task
]

def get_handoff_tools_for_agent(agent_name: str) -> List:
    """Retorna las herramientas de handoff apropiadas para cada agente."""
    
    if agent_name == "info_completion_agent":
        return [transfer_to_research_router, transfer_to_conversational, assign_research_task]
    
    elif agent_name == "research_router":
        return [transfer_to_researcher, transfer_to_conversational, assign_research_task]
    
    elif agent_name == "researcher":
        return [transfer_to_info_completion, transfer_to_conversational, assign_conversation_task]
    
    elif agent_name == "conversational_agent":
        return [transfer_to_researcher, transfer_to_info_completion, assign_research_task]
    
    else:
        return HANDOFF_TOOLS  # Todas las herramientas por defecto 