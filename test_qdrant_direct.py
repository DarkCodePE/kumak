#!/usr/bin/env python3
"""
Prueba directa de Qdrant con las nuevas credenciales
"""

import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Forzar las nuevas credenciales
NEW_QDRANT_URL = "https://fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io:6333"
NEW_QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.0N96GVClA31Gbjp4yOG7m_4ZwyLtduyU54hWUcoycQs"

def test_qdrant_direct():
    """Probar Qdrant directamente con las nuevas credenciales"""
    print("🔍 PROBANDO QDRANT DIRECTAMENTE")
    print("=" * 50)
    
    try:
        # Crear cliente con credenciales específicas
        client = QdrantClient(
            url=NEW_QDRANT_URL,
            api_key=NEW_QDRANT_API_KEY
        )
        
        print(f"📊 URL: {NEW_QDRANT_URL}")
        print(f"📊 API Key: ***{NEW_QDRANT_API_KEY[-8:]}")
        
        # Verificar colecciones
        collections = client.get_collections()
        print(f"✅ Colecciones: {[c.name for c in collections.collections]}")
        
        # Probar guardar información empresarial
        thread_id = "whatsapp_51962933641"
        business_info = {
            "nombre_empresa": "Pollería Orlando",
            "sector": "Restaurante", 
            "productos_servicios_principales": "Pollos a la brasa, bebidas",
            "desafios_principales": "Competencia, costos",
            "ubicacion": "Local físico"
        }
        
        # Crear punto en business_memory
        point_id = f"business_{thread_id}"
        business_text = f"Empresa: {business_info['nombre_empresa']}, Sector: {business_info['sector']}, Ubicación: {business_info['ubicacion']}"
        
        # Vector dummy (en producción usaríamos embeddings reales)
        vector = [0.1] * 1536  # Dimensión de text-embedding-3-small
        
        # Guardar punto
        client.upsert(
            collection_name="business_memory",
            points=[models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "content": business_text,
                    "data": business_info,
                    "metadata": {
                        "thread_id": thread_id,
                        "empresa": business_info["nombre_empresa"],
                        "sector": business_info["sector"],
                        "type": "business_info"
                    }
                }
            )]
        )
        
        print(f"✅ Información guardada con ID: {point_id}")
        
        # Recuperar información
        points = client.retrieve(
            collection_name="business_memory",
            ids=[point_id]
        )
        
        if points:
            retrieved_data = points[0].payload.get("data", {})
            print(f"✅ Información recuperada: {retrieved_data}")
            return retrieved_data
        else:
            print("❌ No se pudo recuperar la información")
            return None
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

def test_memory_service_with_new_credentials():
    """Probar el servicio de memoria forzando las nuevas credenciales"""
    print(f"\n🧠 PROBANDO MEMORY SERVICE CON NUEVAS CREDENCIALES")
    print("=" * 50)
    
    try:
        # Forzar variables de entorno
        os.environ["QDRANT_URL"] = NEW_QDRANT_URL
        os.environ["QDRANT_API_KEY"] = NEW_QDRANT_API_KEY
        
        # Importar después de cambiar las variables
        from app.services.memory_service import MemoryService
        
        # Crear nueva instancia del servicio
        memory_service = MemoryService()
        
        # Información empresarial
        thread_id = "whatsapp_51962933641"
        business_info = {
            "nombre_empresa": "Pollería Orlando",
            "sector": "Restaurante", 
            "productos_servicios_principales": "Pollos a la brasa, bebidas",
            "desafios_principales": "Competencia, costos",
            "ubicacion": "Local físico"
        }
        
        async def test_save_and_load():
            # Guardar información
            success = await memory_service.save_business_info(thread_id, business_info)
            print(f"📊 Guardado exitoso: {success}")
            
            # Cargar información
            loaded_info = memory_service.load_business_info(thread_id)
            print(f"📊 Información cargada: {loaded_info}")
            
            return loaded_info
        
        # Ejecutar prueba async
        result = asyncio.run(test_save_and_load())
        return result
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

def test_evaluator_with_forced_context():
    """Probar el evaluator con contexto forzado"""
    print(f"\n🔧 PROBANDO EVALUATOR CON CONTEXTO FORZADO")
    print("=" * 50)
    
    try:
        # Forzar variables de entorno
        os.environ["QDRANT_URL"] = NEW_QDRANT_URL
        os.environ["QDRANT_API_KEY"] = NEW_QDRANT_API_KEY
        
        from app.graph.supervisor_architecture import create_supervisor_pymes_graph
        from langgraph.types import Command
        
        # Crear grafo
        graph = create_supervisor_pymes_graph()
        thread_id = "whatsapp_51962933641"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Ejecutar con mensaje
        result = graph.invoke(Command(resume="Tengo un local físico"), config)
        
        # Verificar resultado
        business_info = result.get("business_info", {})
        print(f"📊 Business info resultante: {business_info}")
        
        # Verificar respuesta
        answer = result.get("answer", "")
        print(f"📊 Respuesta: {answer[:200]}...")
        
        return business_info
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

if __name__ == "__main__":
    print("🚀 INICIANDO PRUEBAS DIRECTAS DE QDRANT")
    print("=" * 60)
    
    tests = [
        ("Qdrant directo", test_qdrant_direct),
        ("Memory Service con nuevas credenciales", test_memory_service_with_new_credentials),
        ("Evaluator con contexto forzado", test_evaluator_with_forced_context)
    ]
    
    for test_name, test_func in tests:
        print(f"\n🧪 EJECUTANDO: {test_name}")
        print("=" * 60)
        
        result = test_func()
        if result:
            print(f"✅ {test_name} - ÉXITO")
        else:
            print(f"❌ {test_name} - FALLO")
    
    print(f"\n🏁 PRUEBAS COMPLETADAS")
    print("=" * 60) 