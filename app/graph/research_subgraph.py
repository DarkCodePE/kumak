import logging
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.tools import TavilySearchResults
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from app.config.settings import LLM_MODEL
from app.graph.state import PYMESState

logger = logging.getLogger(__name__)

# Prompt para investigación de oportunidades
RESEARCH_OPPORTUNITIES_PROMPT = """
Eres un consultor experto en PYMES especializado en identificar oportunidades de crecimiento y mejora.

INFORMACIÓN DEL NEGOCIO:
{business_info}

INSTRUCCIONES:
1. Analiza la información del negocio proporcionada
2. Identifica áreas clave de oportunidad basadas en:
   - Sector y mercado actual
   - Desafíos identificados
   - Ubicación y alcance
   - Productos/servicios actuales

3. Genera búsquedas específicas para investigar:
   - Tendencias del sector
   - Mejores prácticas de la industria
   - Oportunidades de mercado
   - Soluciones a los desafíos identificados
   - Casos de éxito similares

FORMATO DE RESPUESTA:
Devuelve una lista de consultas de búsqueda específicas, una por línea, que permitan investigar oportunidades relevantes.

Ejemplo:
- Tendencias 2024 sector restaurantes Lima Perú
- Mejores prácticas marketing digital restaurantes pequeños
- Oportunidades delivery comida Lima mercado
- Soluciones problemas personal restaurantes PYMES

"""

ANALYSIS_PROMPT = """
Eres un consultor de PYMES experto en análisis de oportunidades de crecimiento.

INFORMACIÓN DEL NEGOCIO:
{business_info}

RESULTADOS DE INVESTIGACIÓN:
{research_results}

INSTRUCCIONES:
Basándote en la información del negocio y los resultados de la investigación, genera un análisis completo que incluya:

1. **OPORTUNIDADES IDENTIFICADAS**: Lista las principales oportunidades de crecimiento encontradas
2. **TENDENCIAS RELEVANTES**: Tendencias del sector que pueden aprovechar
3. **MEJORES PRÁCTICAS**: Prácticas exitosas que pueden implementar
4. **SOLUCIONES A DESAFÍOS**: Soluciones específicas para los desafíos mencionados
5. **RECOMENDACIONES PRIORITARIAS**: 3-5 recomendaciones principales ordenadas por impacto

Sé específico y práctico. Todas las recomendaciones deben ser aplicables al contexto específico del negocio.
"""


class ResearchAgent:
    """Agente de investigación para PYMES."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model=LLM_MODEL, temperature=0.1)
        self.search_tool = TavilySearchResults(max_results=3)
    
    def generate_search_queries(self, business_info: Dict[str, Any]) -> List[str]:
        """Genera consultas de búsqueda específicas basadas en la información del negocio."""
        try:
            prompt = ChatPromptTemplate.from_template(RESEARCH_OPPORTUNITIES_PROMPT)
            chain = prompt | self.llm
            
            response = chain.invoke({"business_info": str(business_info)})
            
            # Extraer las consultas del resultado
            queries = []
            for line in response.content.split('\n'):
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•')):
                    query = line.lstrip('-• ').strip()
                    if query:
                        queries.append(query)
            
            logger.info(f"Generadas {len(queries)} consultas de búsqueda")
            return queries[:5]  # Limitar a 5 búsquedas para no sobrecargar
            
        except Exception as e:
            logger.error(f"Error generando consultas de búsqueda: {str(e)}")
            return [
                f"oportunidades crecimiento {business_info.get('sector', 'negocio')} {business_info.get('ubicacion', 'Peru')}",
                f"tendencias {business_info.get('sector', 'industria')} 2024",
                f"mejores prácticas PYMES {business_info.get('sector', 'pequeños negocios')}"
            ]
    
    def search_opportunities(self, queries: List[str]) -> List[Dict[str, str]]:
        """Realiza búsquedas web para cada consulta."""
        all_results = []
        
        for query in queries:
            try:
                logger.info(f"Buscando: {query}")
                results = self.search_tool.invoke(query)
                
                for result in results:
                    if isinstance(result, dict):
                        all_results.append({
                            "query": query,
                            "content": result.get("content", ""),
                            "url": result.get("url", ""),
                            "title": result.get("title", "")
                        })
                
            except Exception as e:
                logger.error(f"Error en búsqueda '{query}': {str(e)}")
                continue
        
        logger.info(f"Recopilados {len(all_results)} resultados de investigación")
        return all_results
    
    def analyze_opportunities(self, business_info: Dict[str, Any], research_results: List[Dict[str, str]]) -> str:
        """Analiza los resultados y genera recomendaciones."""
        try:
            # Formatear los resultados de investigación
            formatted_results = []
            for result in research_results:
                formatted_results.append(
                    f"**Búsqueda**: {result['query']}\n"
                    f"**Fuente**: {result.get('title', 'N/A')}\n"
                    f"**Contenido**: {result['content']}\n"
                    f"**URL**: {result.get('url', 'N/A')}\n"
                )
            
            research_text = "\n---\n".join(formatted_results)
            
            prompt = ChatPromptTemplate.from_template(ANALYSIS_PROMPT)
            chain = prompt | self.llm
            
            response = chain.invoke({
                "business_info": str(business_info),
                "research_results": research_text
            })
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error en análisis de oportunidades: {str(e)}")
            return "Hubo un error analizando las oportunidades encontradas."


def research_opportunities_node(state: PYMESState) -> Dict[str, Any]:
    """
    Nodo principal de investigación de oportunidades.
    """
    try:
        logger.info("Iniciando investigación de oportunidades")
        
        business_info = state.get("business_info", {})
        if not business_info:
            logger.warning("No hay información del negocio disponible para investigar")
            return {
                "messages": [AIMessage(content="No tengo información suficiente del negocio para realizar la investigación.")],
                "stage": "error"
            }
        
        research_agent = ResearchAgent()
        
        # Generar consultas de búsqueda
        queries = research_agent.generate_search_queries(business_info)
        logger.info(f"Consultas generadas: {queries}")
        
        # Realizar búsquedas
        research_results = research_agent.search_opportunities(queries)
        
        # Analizar resultados
        analysis = research_agent.analyze_opportunities(business_info, research_results)
        
        return {
            "web_search": f"Investigación completada con {len(research_results)} resultados",
            "context": analysis,
            "stage": "research_completed",
            "messages": [AIMessage(content=f"🔍 **INVESTIGACIÓN COMPLETADA**\n\nHe analizado las oportunidades para tu negocio **{business_info.get('nombre_empresa', 'N/A')}**.\n\n{analysis}")]
        }
        
    except Exception as e:
        logger.error(f"Error en research_opportunities_node: {str(e)}")
        return {
            "messages": [AIMessage(content="Hubo un error durante la investigación. Intentaré nuevamente.")],
            "stage": "error"
        }


def validate_research_results_node(state: PYMESState) -> Command:
    """
    Valida los resultados de investigación con el usuario.
    """
    try:
        logger.info("Validando resultados de investigación")
        
        context = state.get("context", "")
        business_info = state.get("business_info", {})
        
        validation_message = f"""
🎯 **ANÁLISIS DE OPORTUNIDADES COMPLETADO**

He investigado oportunidades específicas para **{business_info.get('nombre_empresa', 'tu negocio')}** y encontré información muy relevante.

{context}

📋 **¿Te gustaría que desarrolle un plan de acción detallado basado en estas oportunidades?**

Responde:
- ✅ **"SÍ"** para generar un plan de acción completo
- 🔄 **"MÁS INFORMACIÓN"** si necesitas investigación adicional sobre algún punto específico
- 💬 **"PREGUNTAS"** si tienes dudas sobre alguna recomendación

*También puedes hacer preguntas específicas sobre cualquier oportunidad mencionada.*
"""

        from langgraph.types import interrupt
        user_response = interrupt({
            "message": validation_message,
            "context": context,
            "stage": "research_validation"
        })
        
        logger.info(f"Respuesta del usuario: {user_response}")
        
        response_lower = user_response.lower().strip()
        
        if response_lower in ["sí", "si", "yes", "generar plan", "plan de acción"]:
            return Command(
                update={
                    "stage": "plan_generation",
                    "messages": [HumanMessage(content=user_response)]
                },
                goto="generate_growth_plan"
            )
        
        elif "más información" in response_lower or "investigación" in response_lower:
            return Command(
                update={
                    "messages": [HumanMessage(content=user_response)]
                },
                goto="research_opportunities"
            )
        
        else:
            # Respuesta general o pregunta - continuar conversación
            return Command(
                update={
                    "input": user_response,
                    "messages": [HumanMessage(content=user_response)],
                    "stage": "conversation"
                },
                goto="generate_response"  # Ir al nodo de conversación general
            )
            
    except Exception as e:
        logger.error(f"Error en validate_research_results_node: {str(e)}")
        return Command(
            update={
                "messages": [AIMessage(content="Hubo un error validando los resultados. ¿Podrías repetir tu respuesta?")]
            },
            goto="validate_research_results"
        )


def create_research_subgraph():
    """
    Crea el sub-grafo de investigación de oportunidades.
    """
    try:
        # Crear el grafo
        workflow = StateGraph(PYMESState)
        
        # Agregar nodos
        workflow.add_node("research_opportunities", research_opportunities_node)
        workflow.add_node("validate_research_results", validate_research_results_node)
        
        # Definir flujo
        workflow.add_edge(START, "research_opportunities")
        workflow.add_edge("research_opportunities", "validate_research_results")
        workflow.add_edge("validate_research_results", END)
        
        logger.info("Sub-grafo de investigación creado exitosamente")
        return workflow.compile()
        
    except Exception as e:
        logger.error(f"Error creando sub-grafo de investigación: {str(e)}")
        raise 