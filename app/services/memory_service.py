import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config.settings import DATABASE_URL
from app.database.postgres import get_postgres_store
from app.graph.state import BusinessInfo

logger = logging.getLogger(__name__)


class MemoryService:
    """Servicio de memoria a largo plazo para información de negocios."""
    
    def __init__(self):
        # ✅ CORRECTO - PostgreSQL para persistencia
        self.engine = create_engine(DATABASE_URL)  # PostgreSQL
        self.Session = sessionmaker(bind=self.engine)
        self.store = get_postgres_store()          # LangGraph PostgresStore
        self.embeddings = OpenAIEmbeddings()
        
        logger.info("MemoryService inicializado con PostgreSQL para persistencia duradera")
    
    def save_business_info(self, thread_id: str, business_info: Dict[str, Any]) -> bool:
        """
        Guarda información del negocio en memoria a largo plazo.
        
        Args:
            thread_id: ID del hilo de conversación
            business_info: Información del negocio a guardar
            
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            logger.info(f"Guardando información del negocio para thread {thread_id}")
            
            # Crear un documento para el store
            business_doc = Document(
                page_content=json.dumps(business_info, ensure_ascii=False),
                metadata={
                    "type": "business_info",
                    "thread_id": thread_id,
                    "empresa": business_info.get("nombre_empresa", "Unknown"),
                    "sector": business_info.get("sector", "Unknown"),
                    "ubicacion": business_info.get("ubicacion", "Unknown"),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Guardar en el store de LangGraph
            namespace = f"business_info:{thread_id}"
            self.store.put(namespace, f"info_{thread_id}", business_doc)
            
            # También guardar en tabla SQL personalizada para búsquedas
            self._save_to_sql_table(thread_id, business_info)
            
            logger.info(f"Información del negocio guardada exitosamente para {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando información del negocio: {str(e)}")
            return False
    
    def _save_to_sql_table(self, thread_id: str, business_info: Dict[str, Any]):
        """Guarda información en tabla SQL personalizada."""
        try:
            with self.Session() as session:
                # Crear tabla si no existe
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS business_profiles (
                        id SERIAL PRIMARY KEY,
                        thread_id VARCHAR(255) UNIQUE NOT NULL,
                        nombre_empresa VARCHAR(255),
                        sector VARCHAR(255),
                        ubicacion VARCHAR(255),
                        productos_servicios TEXT[],
                        desafios_principales TEXT[],
                        descripcion_negocio TEXT,
                        anos_operacion INTEGER,
                        num_empleados INTEGER,
                        data_json JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Insertar o actualizar información
                session.execute(text("""
                    INSERT INTO business_profiles (
                        thread_id, nombre_empresa, sector, ubicacion, 
                        productos_servicios, desafios_principales, descripcion_negocio,
                        anos_operacion, num_empleados, data_json
                    ) VALUES (
                        :thread_id, :nombre_empresa, :sector, :ubicacion,
                        :productos_servicios, :desafios_principales, :descripcion_negocio,
                        :anos_operacion, :num_empleados, :data_json
                    )
                    ON CONFLICT (thread_id) DO UPDATE SET
                        nombre_empresa = EXCLUDED.nombre_empresa,
                        sector = EXCLUDED.sector,
                        ubicacion = EXCLUDED.ubicacion,
                        productos_servicios = EXCLUDED.productos_servicios,
                        desafios_principales = EXCLUDED.desafios_principales,
                        descripcion_negocio = EXCLUDED.descripcion_negocio,
                        anos_operacion = EXCLUDED.anos_operacion,
                        num_empleados = EXCLUDED.num_empleados,
                        data_json = EXCLUDED.data_json,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    "thread_id": thread_id,
                    "nombre_empresa": business_info.get("nombre_empresa"),
                    "sector": business_info.get("sector"),
                    "ubicacion": business_info.get("ubicacion"),
                    "productos_servicios": business_info.get("productos_servicios_principales", []),
                    "desafios_principales": business_info.get("desafios_principales", []),
                    "descripcion_negocio": business_info.get("descripcion_negocio"),
                    "anos_operacion": business_info.get("anos_operacion"),
                    "num_empleados": business_info.get("num_empleados"),
                    "data_json": json.dumps(business_info)
                })
                
                session.commit()
                logger.info(f"Información guardada en tabla SQL para {thread_id}")
                
        except Exception as e:
            logger.error(f"Error guardando en tabla SQL: {str(e)}")
            raise
    
    def load_business_info(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Carga información del negocio desde memoria a largo plazo.
        
        Args:
            thread_id: ID del hilo de conversación
            
        Returns:
            Dict con información del negocio o None si no existe
        """
        try:
            logger.info(f"Cargando información del negocio para thread {thread_id}")
            
            # Intentar cargar desde el store
            namespace = f"business_info:{thread_id}"
            documents = self.store.search(namespace)
            
            if documents:
                doc = documents[0]
                business_info = json.loads(doc.page_content)
                logger.info(f"Información cargada desde store para {thread_id}")
                return business_info
            
            # Si no existe en store, intentar desde SQL
            return self._load_from_sql_table(thread_id)
            
        except Exception as e:
            logger.error(f"Error cargando información del negocio: {str(e)}")
            return None
    
    def _load_from_sql_table(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Carga información desde tabla SQL."""
        try:
            with self.Session() as session:
                result = session.execute(text("""
                    SELECT data_json FROM business_profiles 
                    WHERE thread_id = :thread_id
                """), {"thread_id": thread_id})
                
                row = result.fetchone()
                if row:
                    business_info = dict(row._mapping["data_json"])
                    logger.info(f"Información cargada desde tabla SQL para {thread_id}")
                    return business_info
                
                return None
                
        except Exception as e:
            logger.error(f"Error cargando desde tabla SQL: {str(e)}")
            return None
    
    def search_similar_businesses(self, business_info: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Busca negocios similares basados en sector, ubicación, etc.
        
        Args:
            business_info: Información del negocio actual
            limit: Número máximo de resultados
            
        Returns:
            Lista de negocios similares
        """
        try:
            logger.info("Buscando negocios similares")
            
            sector = business_info.get("sector", "")
            ubicacion = business_info.get("ubicacion", "")
            
            with self.Session() as session:
                # Buscar por sector y ubicación similar
                result = session.execute(text("""
                    SELECT thread_id, nombre_empresa, sector, ubicacion, data_json
                    FROM business_profiles
                    WHERE sector ILIKE :sector
                       OR ubicacion ILIKE :ubicacion
                    ORDER BY 
                        CASE WHEN sector ILIKE :sector THEN 1 ELSE 2 END,
                        CASE WHEN ubicacion ILIKE :ubicacion THEN 1 ELSE 2 END
                    LIMIT :limit
                """), {
                    "sector": f"%{sector}%",
                    "ubicacion": f"%{ubicacion}%",
                    "limit": limit
                })
                
                similar_businesses = []
                for row in result:
                    row_dict = dict(row._mapping)
                    similar_businesses.append({
                        "thread_id": row_dict["thread_id"],
                        "nombre_empresa": row_dict["nombre_empresa"],
                        "sector": row_dict["sector"],
                        "ubicacion": row_dict["ubicacion"],
                        "data": row_dict["data_json"]
                    })
                
                logger.info(f"Encontrados {len(similar_businesses)} negocios similares")
                return similar_businesses
                
        except Exception as e:
            logger.error(f"Error buscando negocios similares: {str(e)}")
            return []
    
    def save_research_results(self, thread_id: str, research_data: Dict[str, Any]) -> bool:
        """
        Guarda resultados de investigación en memoria a largo plazo.
        
        Args:
            thread_id: ID del hilo de conversación
            research_data: Datos de investigación
            
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            logger.info(f"Guardando resultados de investigación para thread {thread_id}")
            
            # Crear documento para el store
            research_doc = Document(
                page_content=json.dumps(research_data, ensure_ascii=False),
                metadata={
                    "type": "research_results",
                    "thread_id": thread_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Guardar en el store
            namespace = f"research:{thread_id}"
            self.store.put(namespace, f"research_{thread_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}", research_doc)
            
            logger.info(f"Resultados de investigación guardados para {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando resultados de investigación: {str(e)}")
            return False
    
    def get_business_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene el historial completo de un negocio (info + investigaciones).
        
        Args:
            thread_id: ID del hilo de conversación
            
        Returns:
            Lista con el historial del negocio
        """
        try:
            logger.info(f"Obteniendo historial para thread {thread_id}")
            
            history = []
            
            # Obtener información del negocio
            business_info = self.load_business_info(thread_id)
            if business_info:
                history.append({
                    "type": "business_info",
                    "data": business_info,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Obtener investigaciones
            research_namespace = f"research:{thread_id}"
            research_docs = self.store.search(research_namespace)
            
            for doc in research_docs:
                research_data = json.loads(doc.page_content)
                history.append({
                    "type": "research",
                    "data": research_data,
                    "timestamp": doc.metadata.get("timestamp", "")
                })
            
            # Ordenar por timestamp
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            logger.info(f"Historial obtenido: {len(history)} elementos")
            return history
            
        except Exception as e:
            logger.error(f"Error obteniendo historial: {str(e)}")
            return []


# Singleton para el servicio de memoria
_memory_service = None

def get_memory_service() -> MemoryService:
    """Obtiene o crea una instancia singleton del servicio de memoria."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service 