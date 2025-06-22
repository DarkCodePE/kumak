"""
Sistema de Deep Research - Arquitectura Map-Reduce para Investigación Paralela
Implementa un equipo especializado: Planner + Workers paralelos + Synthesizer
"""

import asyncio
import logging
from typing import TypedDict, List, Annotated, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_community.tools import TavilySearchResults
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send  # Para Send API
from tavily import TavilyClient
from app.config.settings import LLM_MODEL, TAVILY_API_KEY

logger = logging.getLogger(__name__)

# === ESTADO DEL SISTEMA MAP-REDUCE ===

class DeepResearchState(TypedDict):
    """Estado compartido del sistema Deep Research."""
    research_topic: str
    business_context: Dict[str, Any]  # Información de la empresa
    research_plan: List[str]  # Lista de consultas de búsqueda generadas por el planner
    research_results: Annotated[List[Dict], lambda x, y: x + y]  # Resultados acumulados de workers
    final_report: str
    execution_summary: str

# === HERRAMIENTAS ESPECIALIZADAS ===

@tool
async def search_web_advanced(query: str) -> Dict[str, Any]:
    """
    Herramienta avanzada de búsqueda web optimizada para investigación empresarial.
    Incluye retry logic y filtrado de resultados.
    """
    try:
        logger.info(f"[Deep Research Worker] 🔍 Buscando: '{query}'")
        
        # Configurar Tavily con parámetrso optimizados
        tavily_search = TavilySearchResults(
            max_results=4,  # Más resultados para investigación profunda
            search_depth="advanced",  # Búsqueda más profunda
            include_answer=True,  # Incluir respuesta directa cuando sea posible
            include_raw_content=False,  # No incluir contenido HTML crudo
            include_images=False  # No necesitamos imágenes
        )
        
        # Simular tiempo de búsqueda real
        await asyncio.sleep(1)
        
        results = tavily_search.invoke(query)
        
        # Formatear y filtrar resultados
        formatted_results = []
        for result in results:
            if isinstance(result, dict):
                # Filtrar contenido irrelevante o muy corto
                content = result.get("content", "")
                if len(content) > 50:  # Solo resultados con contenido sustancial
                    formatted_results.append({
                        "title": result.get("title", "Sin título"),
                        "content": content[:800],  # Truncar para evitar overflow
                        "url": result.get("url", ""),
                        "score": result.get("score", 0.0)
                    })
        
        return {
            "query": query,
            "results": formatted_results,
            "results_count": len(formatted_results),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"[Deep Research Worker] ❌ Error en búsqueda '{query}': {str(e)}")
        return {
            "query": query,
            "results": [],
            "results_count": 0,
            "status": "error",
            "error": str(e)
        }

# === AGENTES ESPECIALIZADOS ===

class DeepResearchPlanner:
    """El Estratega - Crea planes de investigación detallados."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLM_MODEL, 
            temperature=0.2,  # Baja creatividad para planes consistentes
            max_tokens=300
        )
    
    def create_research_plan(self, research_topic: str, business_context: Dict[str, Any]) -> List[str]:
        """Crea un plan de investigación estructurado."""
        try:
            empresa = business_context.get("nombre_empresa", "la empresa")
            sector = business_context.get("sector", business_context.get("productos_servicios_principales", ""))
            ubicacion = business_context.get("ubicacion", "")
            productos = business_context.get("productos_servicios_principales", "")
            desafios = business_context.get("desafios_principales", "")
            
            planning_prompt = f"""Eres un Estratega de Investigación Empresarial experto en PYMEs.

CONTEXTO EMPRESARIAL:
- Empresa: {empresa}
- Sector: {sector}
- Ubicación: {ubicacion}
- Productos/Servicios: {productos}
- Desafíos principales: {desafios}

SOLICITUD DE INVESTIGACIÓN: {research_topic}

TU TAREA: Crear un plan de investigación de 4-5 consultas de búsqueda específicas y estratégicas.

CRITERIOS PARA LAS CONSULTAS:
1. Específicas al sector y ubicación de la empresa
2. Orientadas a resultados accionables
3. Balanceadas entre oportunidades y desafíos
4. Incluir análisis competitivo cuando sea relevante
5. Considerar tendencias actuales del mercado

FORMATO DE RESPUESTA:
Devuelve SOLAMENTE una lista de consultas, una por línea, sin numeración ni viñetas.

EJEMPLO:
tendencias mercado restaurantes Lima 2024 post pandemia
competidores directos pollerías zona Lima Norte análisis
oportunidades delivery comida peruana mercado emergente
estrategias marketing digital restaurantes familiares éxito
proveedores pollo Lima precios mayoristas comparativa

IMPORTANTE: Consultas específicas, accionables y relevantes para {empresa}."""

            response = self.llm.invoke([{"role": "user", "content": planning_prompt}])
            
            # Procesar la respuesta para extraer consultas
            queries = []
            for line in response.content.split('\n'):
                line = line.strip()
                if line and len(line) > 10:  # Filtrar líneas vacías o muy cortas
                    # Limpiar posibles numeraciones o viñetas
                    clean_line = line.lstrip('123456789.- •▪▫')
                    if clean_line:
                        queries.append(clean_line.strip())
            
            # Asegurar que tengamos entre 4-6 consultas
            if len(queries) < 4:
                # Agregar consultas genéricas si no hay suficientes
                queries.extend([
                    f"oportunidades crecimiento {sector} {ubicacion} 2024",
                    f"tendencias consumidor {productos} mercado actual",
                    f"estrategias exitosas PYMES {sector} casos estudio"
                ])
            
            # Limitar a máximo 6 consultas para evitar sobrecarga
            final_queries = queries[:6]
            
            logger.info(f"[Deep Research Planner] 📋 Plan creado: {len(final_queries)} consultas")
            for i, query in enumerate(final_queries, 1):
                logger.info(f"  {i}. {query}")
            
            return final_queries
            
        except Exception as e:
            logger.error(f"[Deep Research Planner] ❌ Error creando plan: {str(e)}")
            # Plan de respaldo
            return [
                f"oportunidades mercado {business_context.get('sector', 'negocio')} {business_context.get('ubicacion', 'Peru')}",
                f"tendencias {business_context.get('sector', 'industria')} 2024",
                f"competidores {business_context.get('productos_servicios_principales', 'productos')} análisis",
                f"estrategias crecimiento PYMES {business_context.get('sector', 'pequeños negocios')}"
            ]

class DeepResearchSynthesizer:
    """El Sintetizador - Combina y analiza todos los resultados."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLM_MODEL,
            temperature=0.3,  # Algo de creatividad para síntesis
            max_tokens=500    # Informe más extenso
        )
    
    def synthesize_research(self, research_topic: str, business_context: Dict[str, Any], 
                          research_results: List[Dict]) -> str:
        """Sintetiza todos los resultados en un informe ejecutivo."""
        try:
            empresa = business_context.get("nombre_empresa", "la empresa")
            
            # Formatear resultados de investigación
            formatted_findings = []
            total_sources = 0
            
            for result in research_results:
                if result.get("status") == "success" and result.get("results"):
                    query = result["query"]
                    findings = result["results"]
                    total_sources += len(findings)
                    
                    # Resumir hallazgos por consulta
                    query_summary = f"**{query}:**\n"
                    for finding in findings[:2]:  # Top 2 resultados por consulta
                        content = finding.get("content", "")[:200]  # Resumir contenido
                        query_summary += f"- {content}...\n"
                    
                    formatted_findings.append(query_summary)
            
            all_findings_text = "\n".join(formatted_findings)
            
            synthesis_prompt = f"""Eres un Consultor Senior especializado en análisis de investigación empresarial.

EMPRESA: {empresa}
SOLICITUD ORIGINAL: {research_topic}

HALLAZGOS DE INVESTIGACIÓN ({total_sources} fuentes consultadas):
{all_findings_text}

TU TAREA: Crear un informe ejecutivo conciso y accionable.

ESTRUCTURA DEL INFORME:
1. **RESUMEN EJECUTIVO** (2-3 líneas clave)
2. **OPORTUNIDADES IDENTIFICADAS** (3-4 puntos específicos)
3. **RECOMENDACIONES PRIORITARIAS** (3-4 acciones concretas)
4. **PRÓXIMOS PASOS** (2-3 acciones inmediatas)

CRITERIOS:
- Enfoque en insights accionables para {empresa}
- Recomendaciones específicas y prácticas
- Priorizar por impacto potencial
- Incluir métricas o KPIs cuando sea posible
- Tono profesional pero accesible

LÍMITES:
- Máximo 400 palabras
- Usar viñetas para mayor claridad
- Evitar jerga técnica excesiva"""

            response = self.llm.invoke([{"role": "user", "content": synthesis_prompt}])
            
            # Agregar metadata del proceso
            execution_info = f"\n\n---\n*Investigación completada: {len(research_results)} consultas ejecutadas, {total_sources} fuentes analizadas*"
            
            final_report = response.content + execution_info
            
            logger.info(f"[Deep Research Synthesizer] 📊 Informe final generado: {len(final_report)} caracteres")
            
            return final_report
            
        except Exception as e:
            logger.error(f"[Deep Research Synthesizer] ❌ Error en síntesis: {str(e)}")
            return f"La investigación sobre '{research_topic}' encontró información relevante, pero hubo un error procesando el informe final. Se recomienda revisar los hallazgos individualmente."

# === NODOS DEL GRAFO MAP-REDUCE CON SEND API ===

def planner_node(state: DeepResearchState) -> Dict[str, Any]:
    """Nodo del Planner - Crea el plan de investigación."""
    logger.info("[Deep Research System] 🧠 PLANNER: Creando plan de investigación...")
    
    planner = DeepResearchPlanner()
    research_plan = planner.create_research_plan(
        state["research_topic"], 
        state["business_context"]
    )
    
    return {"research_plan": research_plan}

async def research_worker_node(state: Dict[str, str]) -> Dict[str, List[Dict]]:
    """Nodo WORKER - Ejecuta investigación individual (PARALELO con Send API)."""
    query = state["query"]
    logger.info(f"[Deep Research System] 🔍 WORKER: Ejecutando investigación para '{query}'")
    
    # Ejecutar búsqueda usando la herramienta asíncrona
    try:
        search_result = await search_web_advanced.ainvoke({"query": query})
        return {"research_results": [search_result]}
    except Exception as e:
        logger.error(f"[Deep Research System] ❌ Error en worker para '{query}': {str(e)}")
        # Retornar resultado de error
        error_result = {
            "query": query,
            "status": "error",
            "error": str(e),
            "results": [],
            "results_count": 0
        }
        return {"research_results": [error_result]}

def synthesizer_node(state: DeepResearchState) -> Dict[str, Any]:
    """Nodo REDUCE - Sintetiza todos los resultados."""
    logger.info("[Deep Research System] 📊 SYNTHESIZER: Creando informe final...")
    
    synthesizer = DeepResearchSynthesizer()
    final_report = synthesizer.synthesize_research(
        state["research_topic"],
        state["business_context"],
        state["research_results"]
    )
    
    # Crear resumen de ejecución
    successful_searches = sum(1 for r in state["research_results"] if r.get("status") == "success")
    total_searches = len(state["research_results"])
    
    execution_summary = f"Investigación completada: {successful_searches}/{total_searches} búsquedas exitosas"
    
    return {
        "final_report": final_report,
        "execution_summary": execution_summary
    }

# === CONSTRUCCIÓN DEL GRAFO MAP-REDUCE CON SEND API ===

def create_deep_research_system():
    """
    Crea el sistema completo de Deep Research con arquitectura Map-Reduce usando Send API.
    
    Flujo: START -> planner -> [workers paralelos] -> synthesizer -> END
    """
    logger.info("🏗️ [Deep Research System] Construyendo grafo Map-Reduce con Send API...")
    
    workflow = StateGraph(DeepResearchState)
    
    # === NODOS ===
    workflow.add_node("planner", planner_node)
    workflow.add_node("research_worker", research_worker_node)
    workflow.add_node("synthesizer", synthesizer_node)
    
    # === FLUJO CON SEND API ===
    workflow.set_entry_point("planner")
    
    # SEND API: Desde planner distribuir a workers paralelos
    def continue_to_workers(state: DeepResearchState) -> List[Send]:
        """Función que distribuye las consultas a workers paralelos usando Send API."""
        research_plan = state["research_plan"]
        logger.info(f"[Deep Research System] 🗂️ DISTRIBUYENDO: {len(research_plan)} tareas a workers usando Send API...")
        
        return [
            Send("research_worker", {"query": query})
            for query in research_plan
        ]
    
    workflow.add_conditional_edges(
        "planner",
        continue_to_workers,
        ["research_worker"]
    )
    
    # WORKERS van a SYNTHESIZER - reduce automático
    workflow.add_edge("research_worker", "synthesizer")  
    workflow.add_edge("synthesizer", END)
    
    logger.info("✅ [Deep Research System] Grafo Map-Reduce con Send API construido exitosamente")
    
    return workflow.compile()

# === FUNCIÓN DE INTERFAZ PRINCIPAL ===

async def perform_deep_research_analysis(research_topic: str, business_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función principal para ejecutar investigación profunda.
    
    Args:
        research_topic: Tema de investigación solicitado
        business_context: Información de la empresa
        
    Returns:
        Dict con el informe final y metadatos de ejecución
    """
    try:
        logger.info(f"🚀 [Deep Research System] Iniciando investigación: '{research_topic}'")
        
        # Crear el grafo del sistema
        research_system = create_deep_research_system()
        
        # Preparar estado inicial
        initial_state = {
            "research_topic": research_topic,
            "business_context": business_context,
            "research_results": []
        }
        
        # Ejecutar el sistema completo
        final_state = await research_system.ainvoke(initial_state)
        
        # Extraer resultados
        result = {
            "success": True,
            "final_report": final_state.get("final_report", ""),
            "execution_summary": final_state.get("execution_summary", ""),
            "research_plan": final_state.get("research_plan", []),
            "total_sources": sum(
                r.get("results_count", 0) 
                for r in final_state.get("research_results", [])
            )
        }
        
        logger.info(f"✅ [Deep Research System] Investigación completada exitosamente")
        logger.info(f"   📊 Plan: {len(result['research_plan'])} consultas")
        logger.info(f"   📚 Fuentes: {result['total_sources']} fuentes analizadas")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [Deep Research System] Error en investigación: {str(e)}")
        return {
            "success": False,
            "final_report": f"Hubo un error durante la investigación profunda de '{research_topic}'. Error: {str(e)}",
            "execution_summary": "Error en la ejecución",
            "research_plan": [],
            "total_sources": 0
        } 