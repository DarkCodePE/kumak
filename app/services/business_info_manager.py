import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from functools import lru_cache

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config.settings import LLM_MODEL
from app.services.memory_service import get_memory_service

logger = logging.getLogger(__name__)


class BusinessInfoAnalysis(BaseModel):
    """Resultado del análisis de un mensaje para información empresarial."""
    
    class Config:
        extra = "forbid"  # Esto hace que additionalProperties sea false

    is_important: bool = Field(
        ...,
        description="Si el mensaje contiene información empresarial importante para extraer",
    )
    extracted_info: Optional[Dict[str, str]] = Field(
        None, 
        description="La información empresarial extraída y formateada del mensaje como diccionario simple"
    )


class BusinessInfoManager:
    """Manager class para manejar extracción de información empresarial."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm = ChatOpenAI(
            model=LLM_MODEL,
            temperature=0.1,
            max_retries=2,
        ).with_structured_output(BusinessInfoAnalysis, method="function_calling")

    async def _analyze_business_info(self, message: str, current_info: Dict[str, Any]) -> BusinessInfoAnalysis:
        """Analiza un mensaje para determinar importancia y extraer información empresarial."""
        prompt = f"""Extrae y formatea información empresarial importante del mensaje del usuario.
        Enfócate en información factual, no en solicitudes o comentarios sobre recordar cosas.

        Información empresarial importante incluye:
        - nombre_empresa: Nombre de la empresa o negocio
        - sector: Sector o industria
        - productos_servicios_principales: Productos o servicios principales (como string separado por comas)
        - desafios_principales: Desafíos o problemas del negocio (como string separado por comas)
        - ubicacion: Ubicación de operación
        - descripcion_negocio: Descripción del negocio
        - anos_operacion: Años de operación (como string)
        - num_empleados: Número de empleados (como string)

        Reglas:
        1. Solo extrae información factual nueva, no solicitudes o meta-comentarios
        2. Convierte la información en declaraciones claras y estructuradas
        3. Si no hay información empresarial factual, marca como no importante
        4. Fusiona con información existente sin duplicar
        5. Devuelve valores como strings simples

        Información actual: {current_info}

        Ejemplos:
        Input: "Mi empresa se llama TechSolutions y nos dedicamos al desarrollo de software"
        Output: {{
            "is_important": true,
            "extracted_info": {{
                "nombre_empresa": "TechSolutions",
                "sector": "Desarrollo de software"
            }}
        }}

        Input: "Vendemos productos de belleza y tenemos 5 empleados"
        Output: {{
            "is_important": true,
            "extracted_info": {{
                "productos_servicios_principales": "Productos de belleza",
                "num_empleados": "5"
            }}
        }}

        Input: "¿Podrías recordar mis datos para la próxima vez?"
        Output: {{
            "is_important": false,
            "extracted_info": null
        }}

        Input: "Hola, ¿cómo estás hoy?"
        Output: {{
            "is_important": false,
            "extracted_info": null
        }}

        Mensaje: {message}
        """
        return await self.llm.ainvoke(prompt)

    async def extract_and_store_business_info(self, message: BaseMessage, current_info: Dict[str, Any], thread_id: str = None) -> Dict[str, Any]:
        """Extrae información empresarial importante de un mensaje y la almacena."""
        if message.type != "human":
            self.logger.info("ℹ️ Mensaje no es de usuario, devolviendo información actual")
            return current_info

        self.logger.info(f"🔍 Analizando mensaje: '{message.content[:100]}...' para thread_id: {thread_id}")
        self.logger.info(f"📊 Estado actual business_info: {current_info}")

        # Analizar el mensaje para importancia y formateo
        analysis = await self._analyze_business_info(message.content, current_info)
        
        if analysis.is_important and analysis.extracted_info:
            # Fusionar información nueva con la existente
            updated_info = current_info.copy()
            
            for field, value in analysis.extracted_info.items():
                if value is not None and value.strip():  # Solo valores no vacíos
                    # Para simplificar, tratamos todo como strings
                    updated_info[field] = value.strip()
            
            # Verificar si hay cambios significativos
            if updated_info != current_info:
                self.logger.info(f"✅ Nueva información empresarial extraída: {analysis.extracted_info}")
                self.logger.info(f"📈 Estado business_info ANTES: {current_info}")
                self.logger.info(f"📈 Estado business_info DESPUÉS: {updated_info}")
                
                # Guardar en memoria a largo plazo si hay cambios y tenemos thread_id
                if thread_id:
                    try:
                        memory_service = get_memory_service()
                        await memory_service.save_business_info(thread_id, updated_info)
                        self.logger.info(f"💾 Información guardada en memoria a largo plazo para thread: {thread_id}")
                    except Exception as e:
                        self.logger.error(f"Error guardando en memoria: {str(e)}")
                else:
                    self.logger.warning("⚠️ No se proporcionó thread_id, no se guardará en memoria a largo plazo")
            else:
                self.logger.info("ℹ️ No se detectaron cambios en la información empresarial")
            
            return updated_info
        else:
            self.logger.info("ℹ️ No se encontró información empresarial importante en el mensaje")
        
        return current_info

    def get_relevant_business_info(self, context: str, current_info: Dict[str, Any]) -> str:
        """Recupera información empresarial relevante basada en el contexto actual."""
        if not current_info:
            return ""
        
        # Formatear información para el prompt
        info_parts = []
        for field, value in current_info.items():
            if value:
                info_parts.append(f"- {field}: {value}")
        
        return "\n".join(info_parts)

    def format_business_info_for_prompt(self, business_info: Dict[str, Any]) -> str:
        """Formatea información empresarial como puntos para el prompt."""
        if not business_info:
            return ""
        
        formatted_parts = []
        for field, value in business_info.items():
            if value:
                formatted_parts.append(f"- {field.replace('_', ' ').title()}: {value}")
        
        return "\n".join(formatted_parts)


@lru_cache
def get_business_info_manager() -> BusinessInfoManager:
    """Get a BusinessInfoManager instance."""
    return BusinessInfoManager() 