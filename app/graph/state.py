from typing import List, Optional, Dict, Any, Annotated
from typing_extensions import TypedDict
from operator import add

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages, MessagesState
from pydantic import BaseModel


class BusinessInfo(TypedDict, total=False):
    """Información fáctica y descriptiva del negocio."""
    nombre_empresa: str
    sector: str  # e.g., "Restaurantes", "Software (SaaS)", "Retail de moda"
    productos_servicios_principales: List[str]
    desafios_principales: List[str]
    ubicacion: str  # e.g., "Lima, Perú", "Online", "Nacional"
    descripcion_negocio: str  # 'descripcion' renombrada para mayor claridad
    anos_operacion: Optional[int]
    num_empleados: Optional[int]
    limitaciones_recursos: List[str]
    obstaculos_crecimiento: List[str]
    metas_financieras: List[str]
    objetivos_principales: List[str]
    expansion_deseada: List[str]
    timeline_objetivo: Optional[str]
    desafios_actuales: List[str]
    recursos_necesarios: List[str]
    riesgos_identificados: List[str]

class GrowthGoals(TypedDict):
    """Objetivos de crecimiento del negocio."""
    objetivos_principales: List[str]
    metas_financieras: List[str]
    expansion_deseada: List[str]
    timeline_objetivo: Optional[str]


class BusinessChallenges(TypedDict):
    """Desafíos principales del negocio."""
    desafios_actuales: List[str]
    limitaciones_recursos: List[str]
    obstaculos_crecimiento: List[str]


class GrowthProposal(TypedDict):
    """Propuesta de crecimiento generada."""
    resumen_ejecutivo: Optional[str]
    estrategias_principales: List[str]
    plan_accion: List[Dict[str, str]]  # [{"accion": "", "timeline": "", "responsable": ""}]
    metricas_exito: List[str]
    recursos_necesarios: List[str]
    riesgos_identificados: List[str]


class PYMESState(MessagesState, total=False):
    """
    Estado principal del agente PYMES.
    Hereda de MessagesState para compatibilidad con LangGraph Studio.
    """
    # NOTA: messages ya está incluido desde MessagesState
    
    # Entrada actual del usuario (OPCIONAL para Studio)
    input: Optional[str]
    answer: Optional[str]
    feedback: Optional[List[str]]

    # Información del negocio (OPCIONAL para Studio)
    business_info: Optional[BusinessInfo]
    growth_goals: Optional[GrowthGoals]
    business_challenges: Optional[BusinessChallenges]

    # Estado del proceso (OPCIONAL para Studio)
    stage: Optional[str]  # "info_gathering", "analysis", "proposal_generation", "conversation"

    # Propuesta generada (OPCIONAL para Studio)
    growth_proposal: Optional[GrowthProposal]

    # Contexto y memoria (OPCIONAL para Studio)
    context: Optional[str]
    summary: Optional[str]
    web_search: Optional[str]
    documents: Optional[List[Document]]
    
    # Multi-agent state (OPCIONAL para Studio)
    current_agent: Optional[str]  # Agente activo actual
    last_handoff: Optional[str]   # Última descripción de handoff
    
    # Campos adicionales para compatibilidad con Studio
    business_context: Optional[str]  # Contexto empresarial simulado
    needs_human_feedback: Optional[bool]  # Si necesita feedback humano
    next_action: Optional[str]  # Próxima acción a realizar
