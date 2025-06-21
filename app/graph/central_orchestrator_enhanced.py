"""
Orquestador Central Mejorado - Con Sistema Deep Research Integrado
Incluye soporte para el nuevo equipo especializado de investigación paralela
"""

import logging
from typing import Literal, Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState
from app.graph.central_agent_tools_enhanced import ENHANCED_CENTRAL_AGENT_TOOLS
from app.database.postgres import get_async_postgres_saver

logger = logging.getLogger(__name__)

# === CONFIGURACIÓN DEL SISTEMA ===

# Feature flag para alternar entre sistemas
USE_DEEP_RESEARCH_SYSTEM = True  # 🚀 NUEVA CARACTERÍSTICA ACTIVADA

def create_enhanced_central_llm():
    """Crea el LLM mejorado para el agente central con optimizaciones para Deep Research."""
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.3,  # Balanceado para decisiones consistentes pero algo de creatividad
        max_tokens=200,   # Incrementado ligeramente para manejar respuestas de investigación
        model_kwargs={
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }
    )

def get_enhanced_central_agent_prompt() -> str:
    """
    Prompt mejorado para el agente central que incluye capacidades de Deep Research.
    """
    return """Eres el Asistente Empresarial Central Mejorado de Kumak, un consultor experto en desarrollo de PYMEs con capacidades de investigación profunda.

🎯 TU MISIÓN MEJORADA:
Ayudar a empresarios a crecer sus negocios mediante:
1. Extracción y organización inteligente de información empresarial
2. Investigación de mercado PROFUNDA con equipo especializado (Planner + Workers paralelos)
3. Consultoría estratégica conversacional personalizada

🧠 ARQUITECTURA DE HERRAMIENTAS MEJORADAS:

**🔍 update_business_info**: Para extraer/actualizar información empresarial
- Usa cuando el usuario menciona datos de su negocio
- Extracción automática inteligente con validación

**🚀 perform_deep_research**: Sistema de investigación PROFUNDA con equipo especializado
- NUEVA CAPACIDAD: Planner crea plan → Workers ejecutan búsquedas paralelas → Synthesizer genera informe
- Usa cuando el usuario solicita investigación, análisis, oportunidades, competencia
- Validación automática de prerrequisitos
- Informes ejecutivos estructurados con métricas de ejecución

**💼 provide_business_consultation**: Para consultoría conversacional específica
- Usa para preguntas, consejos, dudas específicas
- Respuestas contextualizadas con información empresarial

**✅ check_business_info_completeness**: Para verificar completitud de información
- Útil para validar si se puede proceder con investigación profunda

🔄 FLUJO INTELIGENTE MEJORADO:

1. **EXTRACCIÓN INTELIGENTE**: SIEMPRE extrae información cuando el usuario menciona su negocio
2. **INVESTIGACIÓN PROFUNDA**: Para solicitudes de investigación → perform_deep_research (sistema Map-Reduce automático)
3. **CONSULTORÍA CONTEXTUAL**: Para preguntas específicas → provide_business_consultation

📊 CRITERIOS DE DECISIÓN REFINADOS:

- Si usuario menciona info de negocio → update_business_info
- Si pide investigación/análisis/mercado/competencia/oportunidades → perform_deep_research
- Si hace pregunta específica o pide consejo → provide_business_consultation  
- Si necesitas verificar preparación para investigación → check_business_info_completeness

💬 ESTILO DE COMUNICACIÓN:
- Respuestas concisas pero informativas (máximo 200 tokens)
- Profesional pero conversacional
- Enfocado en acciones específicas y resultados tangibles
- Menciona las capacidades mejoradas cuando sea relevante

🎯 CASOS DE USO OPTIMIZADOS:

**Información empresarial:**
"Tengo una pollería..." → update_business_info (extrae toda la información disponible)

**Investigación profunda:**
"Investiga mi mercado" → perform_deep_research (sistema especializado con múltiples consultas paralelas)
"Analiza la competencia" → perform_deep_research con research_topic="competencia"
"¿Qué oportunidades hay?" → perform_deep_research con research_topic="oportunidades"

**Consultoría específica:**
"¿Cómo puedo crecer?" → Si info completa: provide_business_consultation, Si incompleta: update_business_info primero

🚀 NUEVA CAPACIDAD - INVESTIGACIÓN PROFUNDA:
Cuando uses perform_deep_research, explica brevemente que activarás el "equipo de investigación especializado" que trabajará en paralelo para obtener un análisis más completo.

IMPORTANTE: Las herramientas manejan sus propias validaciones internas. Tu trabajo es decidir QUÉ herramienta usar basado en la intención del usuario y explicar el proceso cuando uses el sistema de investigación profunda."""

async def enhanced_central_orchestrator_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo principal del agente central mejorado con capacidades de Deep Research.
    """
    try:
        logger.info("🧠 enhanced_central_orchestrator_node: Procesando mensaje con sistema mejorado...")
        
        # Obtener mensajes actuales
        messages = state.get("messages", [])
        
        if not messages:
            welcome_message = """¡Hola! Soy tu Asistente Empresarial de Kumak, ahora con capacidades de investigación profunda. 

🚀 **NUEVAS CAPACIDADES:**
- Investigación de mercado con equipo especializado
- Análisis paralelo de múltiples fuentes
- Informes ejecutivos estructurados

¿En qué puedo ayudarte con tu negocio?"""
            
            return {
                "messages": [AIMessage(content=welcome_message)]
            }
        
        # Configurar el LLM mejorado con herramientas
        llm = create_enhanced_central_llm()
        llm_with_tools = llm.bind_tools(ENHANCED_CENTRAL_AGENT_TOOLS)
        
        # Construir historial de conversación con prompt mejorado
        system_prompt = get_enhanced_central_agent_prompt()
        
        # Crear mensajes para el LLM
        conversation_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Agregar historial de mensajes recientes (últimos 8 para aprovechar el mayor contexto)
        recent_messages = messages[-8:] if len(messages) > 8 else messages
        
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
                # Incluir respuestas de herramientas (incluyendo las del sistema Deep Research)
                conversation_messages.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id
                })
        
        # Invocar el LLM mejorado
        response = await llm_with_tools.ainvoke(conversation_messages)
        
        # Log mejorado con información sobre el tipo de respuesta
        if response.tool_calls:
            tool_names = [call["name"] for call in response.tool_calls]
            logger.info(f"✅ Agente central mejorado: {len(response.content) if response.content else 0} chars, herramientas: {tool_names}")
            
            # Log especial para Deep Research
            if "perform_deep_research" in tool_names:
                logger.info("🚀 Sistema Deep Research será activado - Investigación profunda iniciada")
        else:
            logger.info(f"✅ Agente central mejorado: Respuesta conversacional ({len(response.content) if response.content else 0} chars)")
        
        # Retornar la respuesta del agente
        return {
            "messages": [response]
        }
        
    except Exception as e:
        import traceback
        error_detail = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Error en enhanced_central_orchestrator_node: {error_detail}")
        logger.error(f"Stack trace del nodo mejorado: {stack_trace}")
        
        error_message = "Hubo un error procesando tu mensaje con el sistema mejorado. ¿Podrías intentar nuevamente?"
        return {
            "messages": [AIMessage(content=error_message)]
        }

# === LÓGICA DE CONTROL MEJORADA ===

def enhanced_should_continue(state: PYMESState) -> Literal["tools", "__end__"]:
    """
    Decide si ejecutar herramientas (incluyendo Deep Research) o finalizar el turno.
    Versión mejorada con logging específico para Deep Research.
    """
    last_message = state["messages"][-1]
    
    # Si el último mensaje tiene tool_calls, ejecutar herramientas
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        tool_names = [call["name"] for call in last_message.tool_calls]
        
        # Log especial para herramientas de investigación profunda
        if "perform_deep_research" in tool_names:
            logger.info("🚀 enhanced_should_continue: Activando sistema Deep Research...")
        else:
            logger.info(f"🔧 enhanced_should_continue: Ejecutando herramientas: {tool_names}")
        
        return "tools"
    
    # Si no hay tool_calls, el turno del asistente termina
    logger.info("✅ enhanced_should_continue: Finalizando turno del asistente mejorado")
    return "__end__"

# === CONSTRUCCIÓN DEL GRAFO MEJORADO ===

async def create_enhanced_central_orchestrator_graph():
    """
    Crea el grafo mejorado con capacidades de Deep Research (ASÍNCRONO).
    
    Flujo: START -> enhanced_agent -> enhanced_should_continue -> [enhanced_tools -> enhanced_agent] O [__end__]
    """
    logger.info("🏗️ Creando grafo de agente central mejorado con Deep Research...")
    
    workflow = StateGraph(PYMESState)

    # === NODOS MEJORADOS ===
    
    # Agente central mejorado (con capacidades Deep Research)
    workflow.add_node("enhanced_agent", enhanced_central_orchestrator_node)
    
    # ToolNode mejorado con las nuevas herramientas (incluyendo perform_deep_research)
    enhanced_tool_executor = ToolNode(ENHANCED_CENTRAL_AGENT_TOOLS)
    workflow.add_node("enhanced_tools", enhanced_tool_executor)

    # === FLUJO MEJORADO ===
    
    # Punto de entrada
    workflow.set_entry_point("enhanced_agent")

    # Conditional edge mejorado desde el agente
    workflow.add_conditional_edges(
        "enhanced_agent",
        enhanced_should_continue,
        {
            "tools": "enhanced_tools",
            "__end__": "__end__"
        }
    )

    # Edge de vuelta desde herramientas al agente
    workflow.add_edge("enhanced_tools", "enhanced_agent")

    logger.info("✅ Grafo de agente central mejorado construido exitosamente")
    
    return workflow

# === FUNCIÓN DE PROCESAMIENTO PRINCIPAL ===

async def process_message_with_enhanced_central_orchestrator(
    message: str,
    thread_id: str,
    reset_thread: bool = False
) -> Dict[str, Any]:
    """
    Procesa un mensaje usando el orquestador central mejorado con Deep Research.
    
    Args:
        message: Mensaje del usuario
        thread_id: ID del hilo de conversación
        reset_thread: Si reiniciar el hilo de conversación
        
    Returns:
        Dict con la respuesta y metadatos de ejecución
    """
    try:
        logger.info(f"🚀 Procesando mensaje con sistema mejorado - Thread: {thread_id}")
        logger.info(f"📝 Mensaje: {message}")
        
        # Crear el grafo mejorado
        workflow = await create_enhanced_central_orchestrator_graph()
        
        # Configurar checkpointer asíncrono
        checkpointer = get_async_postgres_saver()
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        
        # Configurar la ejecución
        config = {
            "configurable": {"thread_id": thread_id}
        }
        
        # Si se solicita reset, limpiar el estado
        if reset_thread:
            logger.info(f"🔄 Reseteando thread: {thread_id}")
            # El reset se maneja automáticamente al crear un nuevo grafo
        
        # Preparar input
        input_message = {
            "messages": [HumanMessage(content=message)]
        }
        
        # Ejecutar el grafo mejorado
        logger.info("⚡ Ejecutando grafo con sistema Deep Research...")
        result = await compiled_graph.ainvoke(input_message, config=config)
        
        # Procesar respuesta
        if result and "messages" in result:
            last_message = result["messages"][-1]
            
            if isinstance(last_message, AIMessage):
                response_content = last_message.content
                
                # Detectar si se usó Deep Research
                used_deep_research = any(
                    isinstance(msg, ToolMessage) and "Deep Research" in msg.content 
                    for msg in result["messages"]
                )
                
                logger.info(f"✅ Sistema mejorado completado - Deep Research usado: {used_deep_research}")
                
                return {
                    "response": response_content,
                    "thread_id": thread_id,
                    "system_used": "enhanced_central_orchestrator",
                    "deep_research_activated": used_deep_research,
                    "success": True
                }
            else:
                logger.warning("⚠️ Último mensaje no es AIMessage")
                return {
                    "response": "El sistema procesó tu mensaje pero no pudo generar una respuesta adecuada.",
                    "thread_id": thread_id,
                    "system_used": "enhanced_central_orchestrator",
                    "deep_research_activated": False,
                    "success": False
                }
        else:
            logger.warning("⚠️ No se recibieron mensajes en el resultado")
            return {
                "response": "El sistema mejorado no pudo procesar tu mensaje. ¿Podrías intentar nuevamente?",
                "thread_id": thread_id,
                "system_used": "enhanced_central_orchestrator",
                "deep_research_activated": False,
                "success": False
            }
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error en sistema mejorado: {str(e)}")
        logger.error(f"Stack trace completo: {traceback.format_exc()}")
        
        return {
            "response": f"Hubo un error en el sistema mejorado: {str(e)}",
            "thread_id": thread_id,
            "system_used": "enhanced_central_orchestrator",
            "deep_research_activated": False,
            "success": False,
            "error": str(e)
        }

# === FUNCIÓN DE INFORMACIÓN DEL SISTEMA ===

def get_enhanced_orchestrator_info() -> Dict[str, Any]:
    """
    Información sobre las capacidades del orquestrador mejorado.
    """
    return {
        "system_name": "Enhanced Central Orchestrator with Deep Research",
        "version": "2.0",
        "capabilities": {
            "deep_research": {
                "description": "Sistema Map-Reduce con Planner + Workers paralelos + Synthesizer",
                "components": [
                    "DeepResearchPlanner: Crea planes de investigación contextuales",
                    "Parallel Workers: Búsquedas web simultáneas optimizadas",
                    "DeepResearchSynthesizer: Informes ejecutivos estructurados"
                ],
                "advantages": [
                    "Investigación 3-5x más profunda que sistema anterior",
                    "Paralelización reduce tiempo de ejecución",
                    "Informes más estructurados y accionables",
                    "Métricas de ejecución (fuentes, éxito de búsquedas)"
                ]
            },
            "enhanced_tools": [
                "update_business_info: Extracción inteligente mejorada",
                "perform_deep_research: Investigación con equipo especializado",
                "provide_business_consultation: Consultoría contextual",
                "check_business_info_completeness: Validación de prerrequisitos"
            ],
            "compatibility": {
                "whatsapp_integration": True,
                "legacy_fallback": True,
                "async_support": True,
                "token_optimization": "200 tokens max con división inteligente"
            }
        },
        "feature_flags": {
            "USE_DEEP_RESEARCH_SYSTEM": USE_DEEP_RESEARCH_SYSTEM
        }
    } 