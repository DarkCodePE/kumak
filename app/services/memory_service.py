import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config.settings import QDRANT_URL, QDRANT_API_KEY
from app.database.postgres import get_postgres_store, with_retry
from app.graph.state import BusinessInfo

logger = logging.getLogger(__name__)


class MemoryService:
    """Servicio de memoria a largo plazo para información de negocios usando Qdrant."""
    
    def __init__(self):
        # ✅ QDRANT - Memoria vectorial para búsquedas semánticas
        self.qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # ✅ POSTGRESQL - Solo para checkpoint de LangGraph
        self.store = get_postgres_store()
        
        # Colecciones en Qdrant
        self.business_collection = "business_memory"
        self.research_collection = "research_memory"
        
        self._ensure_collections_exist()
        logger.info("MemoryService inicializado con Qdrant para memoria vectorial")
    
    def _ensure_collections_exist(self):
        """Asegurar que las colecciones de Qdrant existan."""
        try:
            # Verificar si Qdrant está disponible
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            for collection_name in [self.business_collection, self.research_collection]:
                if collection_name not in collection_names:
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=1536,  # text-embedding-3-small
                            distance=models.Distance.COSINE
                        )
                    )
                    logger.info(f"Colección Qdrant creada: {collection_name}")
            
            logger.info("Qdrant conectado y colecciones verificadas")
            self.qdrant_available = True
                    
        except Exception as e:
            logger.warning(f"Qdrant no disponible, usando solo PostgreSQL: {str(e)}")
            self.qdrant_available = False
            # No hacer raise para que el sistema funcione sin Qdrant
    
    @with_retry()
    async def save_business_info(self, thread_id: str, business_info: Dict[str, Any]) -> bool:
        """
        Guarda información del negocio en Qdrant para búsquedas semánticas.
        
        Args:
            thread_id: ID del hilo de conversación
            business_info: Información del negocio a guardar
            
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            logger.info(f"Guardando información del negocio para thread {thread_id}")
            
            # Crear texto descriptivo para embeddings
            business_text = self._create_business_description(business_info)
            
            # Crear embedding
            vector = await self.embeddings.aembed_query(business_text)
            
            # Metadata completa
            metadata = {
                "thread_id": thread_id,
                "empresa": business_info.get("nombre_empresa", "Unknown"),
                "sector": business_info.get("sector", "Unknown"),
                "ubicacion": business_info.get("ubicacion", "Unknown"),
                "productos_servicios": business_info.get("productos_servicios_principales", []),
                "desafios": business_info.get("desafios_principales", []),
                "anos_operacion": business_info.get("anos_operacion"),
                "num_empleados": business_info.get("num_empleados"),
                "timestamp": datetime.now().isoformat(),
                "type": "business_info"
            }
            
            # Guardar en Qdrant solo si está disponible
            if self.qdrant_available:
                try:
                    point_id = f"business_{thread_id}"
                    self.qdrant_client.upsert(
                        collection_name=self.business_collection,
                        points=[models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                "content": business_text,
                                "data": business_info,
                                "metadata": metadata
                            }
                        )]
                    )
                    logger.info(f"Información guardada en Qdrant para {thread_id}")
                except Exception as e:
                    logger.warning(f"Error guardando en Qdrant, continuando con PostgreSQL: {str(e)}")
                    self.qdrant_available = False
            
            # También guardar en PostgresStore para checkpoint
            try:
                business_doc = Document(
                    page_content=json.dumps(business_info, ensure_ascii=False),
                    metadata=metadata
                )
                namespace = f"business_info:{thread_id}"
                self.store.put(namespace, f"info_{thread_id}", business_doc)
                logger.info(f"Información guardada en PostgreSQL para {thread_id}")
            except Exception as e:
                logger.warning(f"Error guardando en PostgreSQL: {str(e)}")
                # Continuar sin guardar en PostgreSQL
            
            logger.info(f"Información del negocio guardada para {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando información del negocio: {str(e)}")
            return False
    
    def _create_business_description(self, business_info: Dict[str, Any]) -> str:
        """Crear descripción textual para embeddings."""
        parts = []
        
        if empresa := business_info.get("nombre_empresa"):
            parts.append(f"Empresa: {empresa}")
        
        if sector := business_info.get("sector"):
            parts.append(f"Sector: {sector}")
            
        if ubicacion := business_info.get("ubicacion"):
            parts.append(f"Ubicación: {ubicacion}")
            
        if descripcion := business_info.get("descripcion_negocio"):
            parts.append(f"Descripción: {descripcion}")
            
        if productos := business_info.get("productos_servicios_principales"):
            parts.append(f"Productos/Servicios: {', '.join(productos)}")
            
        if desafios := business_info.get("desafios_principales"):
            parts.append(f"Desafíos: {', '.join(desafios)}")
            
        return ". ".join(parts)
    
    @with_retry()
    def load_business_info(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Carga información del negocio desde Qdrant.
        
        Args:
            thread_id: ID del hilo de conversación
            
        Returns:
            Dict con información del negocio o None si no existe
        """
        try:
            logger.info(f"Cargando información del negocio para thread {thread_id}")
            
            # Buscar en Qdrant por ID específico solo si está disponible
            if self.qdrant_available:
                try:
                    point_id = f"business_{thread_id}"
                    points = self.qdrant_client.retrieve(
                        collection_name=self.business_collection,
                        ids=[point_id]
                    )
                    
                    if points:
                        business_info = points[0].payload.get("data", {})
                        logger.info(f"Información cargada desde Qdrant para {thread_id}")
                        return business_info
                        
                except Exception as e:
                    logger.warning(f"Error en Qdrant, usando PostgreSQL: {str(e)}")
                    self.qdrant_available = False
            
            # Fallback a PostgresStore
            try:
                namespace = f"business_info:{thread_id}"
                key = f"info_{thread_id}"
                documents = self.store.get(namespace, [key])
                
                if documents and len(documents) > 0:
                    doc = documents[0]
                    if doc and doc.page_content:
                        business_info = json.loads(doc.page_content)
                        logger.info(f"Información cargada desde PostgreSQL para {thread_id}")
                        return business_info
            except Exception as e:
                logger.warning(f"Error cargando desde PostgreSQL: {str(e)}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error cargando información del negocio: {str(e)}")
            return None
    
    @with_retry()
    def search_similar_businesses(self, business_info: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Busca negocios similares usando búsqueda vectorial semántica.
        
        Args:
            business_info: Información del negocio actual
            limit: Número máximo de resultados
            
        Returns:
            Lista de negocios similares
        """
        try:
            logger.info("Buscando negocios similares con Qdrant")
            
            # Crear descripción del negocio actual
            business_text = self._create_business_description(business_info)
            
            # Crear embedding de consulta
            query_vector = self.embeddings.embed_query(business_text)
            
            # Buscar en Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.business_collection,
                query_vector=query_vector,
                limit=limit + 1,  # +1 porque podría incluir el negocio actual
                score_threshold=0.7  # Solo resultados relevantes
            )
            
            # Filtrar y formatear resultados
            similar_businesses = []
            current_thread = business_info.get("thread_id")
            
            for result in search_results:
                payload = result.payload
                metadata = payload.get("metadata", {})
                
                # Excluir el negocio actual
                if metadata.get("thread_id") == current_thread:
                    continue
                    
                similar_businesses.append({
                    "thread_id": metadata.get("thread_id"),
                    "nombre_empresa": metadata.get("empresa"),
                    "sector": metadata.get("sector"),
                    "ubicacion": metadata.get("ubicacion"),
                    "similarity_score": result.score,
                    "data": payload.get("data", {})
                })
            
            logger.info(f"Encontrados {len(similar_businesses)} negocios similares")
            return similar_businesses[:limit]
            
        except Exception as e:
            logger.error(f"Error buscando negocios similares: {str(e)}")
            return []
    
    @with_retry()
    async def save_research_results(self, thread_id: str, research_data: Dict[str, Any]) -> bool:
        """
        Guarda resultados de investigación en Qdrant.
        
        Args:
            thread_id: ID del hilo de conversación
            research_data: Datos de investigación
            
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            logger.info(f"Guardando resultados de investigación para thread {thread_id}")
            
            # Crear texto para embeddings
            research_text = self._create_research_description(research_data)
            
            # Crear embedding
            vector = await self.embeddings.aembed_query(research_text)
            
            # Metadata
            metadata = {
                "thread_id": thread_id,
                "timestamp": datetime.now().isoformat(),
                "type": "research_results"
            }
            
            # Guardar en Qdrant
            point_id = f"research_{thread_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.qdrant_client.upsert(
                collection_name=self.research_collection,
                points=[models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "content": research_text,
                        "data": research_data,
                        "metadata": metadata
                    }
                )]
            )
            
            # También guardar en PostgresStore para checkpoint
            research_doc = Document(
                page_content=json.dumps(research_data, ensure_ascii=False),
                metadata=metadata
            )
            namespace = f"research:{thread_id}"
            self.store.put(namespace, f"research_{thread_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}", research_doc)
            
            logger.info(f"Resultados de investigación guardados en Qdrant y PostgreSQL para {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando resultados de investigación: {str(e)}")
            return False
    
    def _create_research_description(self, research_data: Dict[str, Any]) -> str:
        """Crear descripción textual de los resultados de investigación."""
        parts = []
        
        if opportunities := research_data.get("opportunities"):
            if isinstance(opportunities, list):
                parts.append(f"Oportunidades: {', '.join(opportunities)}")
            else:
                parts.append(f"Oportunidades: {opportunities}")
            
        if market_analysis := research_data.get("market_analysis"):
            parts.append(f"Análisis de mercado: {market_analysis}")
            
        if recommendations := research_data.get("recommendations"):
            if isinstance(recommendations, list):
                parts.append(f"Recomendaciones: {', '.join(recommendations)}")
            else:
                parts.append(f"Recomendaciones: {recommendations}")
                
        if trends := research_data.get("trends"):
            if isinstance(trends, list):
                parts.append(f"Tendencias: {', '.join(trends)}")
            else:
                parts.append(f"Tendencias: {trends}")
            
        return ". ".join(parts) if parts else "Resultados de investigación"
    
    @with_retry()
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
            
            # Obtener investigaciones desde Qdrant
            try:
                # Buscar todas las investigaciones de este thread
                search_results = self.qdrant_client.scroll(
                    collection_name=self.research_collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="metadata.thread_id",
                                match=models.MatchValue(value=thread_id)
                            )
                        ]
                    ),
                    limit=100  # Máximo 100 investigaciones
                )
                
                for point in search_results[0]:
                    payload = point.payload
                    research_data = payload.get("data", {})
                    metadata = payload.get("metadata", {})
                    
                    history.append({
                        "type": "research",
                        "data": research_data,
                        "timestamp": metadata.get("timestamp", "")
                    })
                    
            except Exception as e:
                logger.warning(f"Error obteniendo investigaciones desde Qdrant: {str(e)}")
                
                # Fallback a PostgresStore
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
    
    @with_retry()
    def search_research_by_topic(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca investigaciones relacionadas con un tema específico.
        
        Args:
            topic: Tema a buscar
            limit: Número máximo de resultados
            
        Returns:
            Lista de investigaciones relacionadas
        """
        try:
            logger.info(f"Buscando investigaciones sobre: {topic}")
            
            # Crear embedding del tema
            query_vector = self.embeddings.embed_query(topic)
            
            # Buscar en Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.research_collection,
                query_vector=query_vector,
                limit=limit,
                score_threshold=0.6  # Umbral de relevancia
            )
            
            # Formatear resultados
            research_results = []
            for result in search_results:
                payload = result.payload
                metadata = payload.get("metadata", {})
                
                research_results.append({
                    "thread_id": metadata.get("thread_id"),
                    "timestamp": metadata.get("timestamp"),
                    "similarity_score": result.score,
                    "content": payload.get("content", ""),
                    "data": payload.get("data", {})
                })
            
            logger.info(f"Encontradas {len(research_results)} investigaciones sobre {topic}")
            return research_results
            
        except Exception as e:
            logger.error(f"Error buscando investigaciones por tema: {str(e)}")
            return []


# Singleton para el servicio de memoria
_memory_service = None

def get_memory_service() -> MemoryService:
    """Obtiene o crea una instancia singleton del servicio de memoria."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service 