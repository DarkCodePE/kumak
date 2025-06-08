from typing import List, Optional, Dict, Any, TypedDict, Annotated
from operator import add

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel


class BusinessInfo(TypedDict):
    """Información básica del negocio."""
    nombre_empresa: Optional[str]
    sector: Optional[str]
    descripcion: Optional[str]
    anos_operacion: Optional[int]
    num_empleados: Optional[int]
    ubicacion: Optional[str]


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
    input: str
    answer: str

    # Información del negocio
    business_info: BusinessInfo
    growth_goals: GrowthGoals
    business_challenges: BusinessChallenges

    # Estado del proceso
    stage: str  # "info_gathering", "analysis", "proposal_generation", "conversation"

    # Propuesta generada
    growth_proposal: Optional[GrowthProposal]

    # Contexto y memoria
    context: str
    summary: Optional[str]
    web_search: Optional[str]
    documents: Optional[List[Document]]
