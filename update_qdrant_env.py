#!/usr/bin/env python3
"""
Script para actualizar las variables de entorno de Qdrant
"""

import os
import sys

# Nuevas credenciales de Qdrant
NEW_QDRANT_URL = "https://fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io:6333"
NEW_QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.0N96GVClA31Gbjp4yOG7m_4ZwyLtduyU54hWUcoycQs"

def create_env_file():
    """Crear archivo .env con las nuevas credenciales"""
    print("🔧 CREANDO ARCHIVO .ENV")
    print("=" * 40)
    
    env_content = f"""# Qdrant Configuration - NUEVAS CREDENCIALES
QDRANT_URL={NEW_QDRANT_URL}
QDRANT_API_KEY={NEW_QDRANT_API_KEY}

# PostgreSQL Configuration (mantener valores por defecto para desarrollo local)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=123456
POSTGRES_DB=chat_rag

# API Configuration
API_HOST=0.0.0.0
API_PORT=9027
API_WORKERS=2

# LLM Configuration
LLM_MODEL=gpt-4o-mini
LLM_MODEL_LARGE=gpt-4o
OPENAI_API_KEY=your_openai_api_key_here

# Tavily Web Search
TAVILY_API_KEY=your_tavily_api_key_here

# Google Drive
GOOGLE_APPLICATION_CREDENTIALS=

# Logging
LOG_LEVEL=INFO
"""
    
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✅ Archivo .env creado exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error creando archivo .env: {str(e)}")
        return False

def set_environment_variables():
    """Establecer variables de entorno en el proceso actual"""
    print(f"\n🔧 ESTABLECIENDO VARIABLES DE ENTORNO")
    print("=" * 40)
    
    try:
        os.environ["QDRANT_URL"] = NEW_QDRANT_URL
        os.environ["QDRANT_API_KEY"] = NEW_QDRANT_API_KEY
        
        print("✅ Variables de entorno establecidas:")
        print(f"   QDRANT_URL: {NEW_QDRANT_URL}")
        print(f"   QDRANT_API_KEY: ***{NEW_QDRANT_API_KEY[-8:]}")
        return True
    except Exception as e:
        print(f"❌ Error estableciendo variables: {str(e)}")
        return False

def test_new_credentials():
    """Probar las nuevas credenciales"""
    print(f"\n🧪 PROBANDO NUEVAS CREDENCIALES")
    print("=" * 40)
    
    try:
        # Forzar recarga de configuración
        import importlib
        import app.config.settings
        importlib.reload(app.config.settings)
        
        from app.services.memory_service import get_memory_service
        
        # Crear servicio de memoria
        memory_service = get_memory_service()
        print(f"✅ MemoryService creado")
        print(f"📊 Qdrant disponible: {memory_service.qdrant_available}")
        
        if memory_service.qdrant_available:
            print("🎉 ¡QDRANT FUNCIONANDO CON NUEVAS CREDENCIALES!")
            
            # Verificar colecciones
            collections = memory_service.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            print(f"📊 Colecciones disponibles: {collection_names}")
            
            return True
        else:
            print("❌ Qdrant aún no está disponible")
            return False
            
    except Exception as e:
        print(f"❌ Error probando credenciales: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def show_instructions():
    """Mostrar instrucciones para aplicar los cambios"""
    print(f"\n📋 INSTRUCCIONES PARA APLICAR CAMBIOS")
    print("=" * 50)
    print("1. 🔄 Reinicia tu aplicación/servidor para cargar las nuevas variables")
    print("2. 🐳 Si usas Docker, reconstruye el contenedor:")
    print("   docker-compose down")
    print("   docker-compose up --build")
    print("3. ☁️ Si está en producción, actualiza las variables de entorno del contenedor")
    print("4. 🔍 Verifica que el sistema use las nuevas credenciales en los logs")

if __name__ == "__main__":
    print("🚀 INICIANDO ACTUALIZACIÓN DE CREDENCIALES QDRANT")
    print("=" * 60)
    
    success_count = 0
    
    # Crear archivo .env
    if create_env_file():
        success_count += 1
    
    # Establecer variables de entorno
    if set_environment_variables():
        success_count += 1
    
    # Probar credenciales
    if test_new_credentials():
        success_count += 1
        print(f"\n🏆 ¡ACTUALIZACIÓN COMPLETADA EXITOSAMENTE!")
        print(f"✅ {success_count}/3 pasos completados")
    else:
        print(f"\n⚠️ ACTUALIZACIÓN PARCIAL")
        print(f"✅ {success_count}/3 pasos completados")
        print("📋 Las variables están configuradas pero puede necesitar reinicio")
    
    # Mostrar instrucciones
    show_instructions()
    
    print(f"\n🏁 PROCESO COMPLETADO")
    print("=" * 60) 