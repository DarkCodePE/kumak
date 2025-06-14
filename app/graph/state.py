from typing import List, Optional, Dict, Any, TypedDict, Annotated
from operator import add

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
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


class PYMESState(TypedDict):
    """Estado principal del agente PYMES."""
    # Mensajes de conversación
    messages: Annotated[List[BaseMessage], add_messages]

    # Entrada actual del usuario
    input: Optional[str]
    answer: Optional[str]
    feedback: List[str]

    # Información del negocio
    business_info: Optional[BusinessInfo]
    growth_goals: Optional[GrowthGoals]
    business_challenges: Optional[BusinessChallenges]

    # Estado del proceso
    stage: Optional[str]  # "info_gathering", "analysis", "proposal_generation", "conversation"

    # Propuesta generada
    growth_proposal: Optional[GrowthProposal]

    # Contexto y memoria
    context: Optional[str]
    summary: Optional[str]
    web_search: Optional[str]
    documents: Optional[List[Document]]
    
    # Multi-agent state
    current_agent: Optional[str]  # Agente activo actual
    last_handoff: Optional[str]   # Última descripción de handoff
