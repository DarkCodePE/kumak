#!/usr/bin/env python3
"""
Script para debuggear diferentes variaciones de la URL de Qdrant
"""

from qdrant_client import QdrantClient
import requests

# Credenciales proporcionadas
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.0N96GVClA31Gbjp4yOG7m_4ZwyLtduyU54hWUcoycQs"

# Diferentes variaciones de URL para probar
url_variations = [
    "https://fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io:6333",
    "https://fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io",
    "https://fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io:443",
    "fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io:6333",
    "fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io",
]

def test_http_request(url):
    """Probar request HTTP directo"""
    try:
        # Probar con diferentes endpoints
        test_endpoints = [
            "/collections",
            "/",
            "/health",
            ""
        ]
        
        for endpoint in test_endpoints:
            full_url = f"{url}{endpoint}"
            print(f"   🌐 Probando: {full_url}")
            
            headers = {"api-key": QDRANT_API_KEY}
            response = requests.get(full_url, headers=headers, timeout=10)
            
            print(f"      Status: {response.status_code}")
            if response.status_code == 200:
                print(f"      ✅ ¡ÉXITO! Contenido: {response.text[:100]}...")
                return True
            else:
                print(f"      ❌ Error: {response.text[:100]}")
        
        return False
        
    except Exception as e:
        print(f"      ❌ Excepción HTTP: {str(e)}")
        return False

def test_qdrant_client(url):
    """Probar con cliente Qdrant"""
    try:
        print(f"   🔧 Probando cliente Qdrant...")
        client = QdrantClient(url=url, api_key=QDRANT_API_KEY)
        collections = client.get_collections()
        print(f"      ✅ ¡ÉXITO! Colecciones: {len(collections.collections)}")
        return True, client
    except Exception as e:
        print(f"      ❌ Error cliente: {str(e)}")
        return False, None

def debug_qdrant_urls():
    """Debuggear todas las variaciones de URL"""
    print("🔍 DEBUGGEANDO URLS DE QDRANT")
    print("=" * 50)
    
    working_urls = []
    
    for i, url in enumerate(url_variations, 1):
        print(f"\n{i}. Probando URL: {url}")
        print("-" * 40)
        
        # Probar HTTP directo
        print("📡 HTTP Request:")
        http_works = test_http_request(url)
        
        # Probar cliente Qdrant
        print("🔧 Cliente Qdrant:")
        client_works, client = test_qdrant_client(url)
        
        if http_works or client_works:
            working_urls.append({
                'url': url,
                'http_works': http_works,
                'client_works': client_works,
                'client': client
            })
            print(f"✅ URL FUNCIONAL: {url}")
        else:
            print(f"❌ URL NO FUNCIONAL: {url}")
    
    return working_urls

def test_working_urls(working_urls):
    """Probar operaciones con URLs que funcionan"""
    print(f"\n🧪 PROBANDO OPERACIONES CON URLS FUNCIONALES")
    print("=" * 50)
    
    for url_info in working_urls:
        url = url_info['url']
        client = url_info['client']
        
        if not client:
            continue
            
        print(f"\n🔧 Probando operaciones con: {url}")
        print("-" * 40)
        
        try:
            # Listar colecciones
            collections = client.get_collections()
            print(f"✅ Colecciones: {[col.name for col in collections.collections]}")
            
            # Probar crear colección de prueba
            test_collection = "debug_test"
            
            try:
                # Eliminar si existe
                client.delete_collection(test_collection)
            except:
                pass
            
            # Crear colección
            from qdrant_client.http import models
            client.create_collection(
                collection_name=test_collection,
                vectors_config=models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE
                )
            )
            print(f"✅ Colección {test_collection} creada")
            
            # Insertar punto
            client.upsert(
                collection_name=test_collection,
                points=[models.PointStruct(
                    id=1,
                    vector=[0.1] * 1536,
                    payload={"test": "debug"}
                )]
            )
            print(f"✅ Punto insertado")
            
            # Recuperar punto
            points = client.retrieve(collection_name=test_collection, ids=[1])
            if points:
                print(f"✅ Punto recuperado: {points[0].payload}")
            
            # Limpiar
            client.delete_collection(test_collection)
            print(f"✅ Colección eliminada")
            
            print(f"🎉 ¡URL COMPLETAMENTE FUNCIONAL!: {url}")
            return url, client
            
        except Exception as e:
            print(f"❌ Error en operaciones: {str(e)}")
            continue
    
    return None, None

if __name__ == "__main__":
    print("🚀 INICIANDO DEBUG DE URLS QDRANT")
    print("=" * 60)
    
    # Debuggear URLs
    working_urls = debug_qdrant_urls()
    
    if working_urls:
        print(f"\n📊 URLS FUNCIONALES ENCONTRADAS: {len(working_urls)}")
        for url_info in working_urls:
            print(f"   ✅ {url_info['url']}")
        
        # Probar operaciones
        best_url, best_client = test_working_urls(working_urls)
        
        if best_url:
            print(f"\n🏆 MEJOR URL ENCONTRADA: {best_url}")
            print("📋 Usa esta URL en tu archivo .env")
        else:
            print(f"\n⚠️ Ninguna URL permite operaciones completas")
    else:
        print(f"\n❌ NO SE ENCONTRARON URLS FUNCIONALES")
        print("📋 Verifica las credenciales o el estado del cluster")
    
    print(f"\n🏁 DEBUG COMPLETADO")
    print("=" * 60) 