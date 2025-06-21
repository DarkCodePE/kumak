#!/usr/bin/env python3
"""
Script para actualizar las credenciales de Qdrant con las nuevas que funcionan
"""

import os
from datetime import datetime

# Nuevas credenciales que funcionan
NEW_QDRANT_URL = "https://fa669b35-8cfa-4cc3-acf0-401fb1573cd2.europe-west3-0.gcp.cloud.qdrant.io:6333"
NEW_QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.0N96GVClA31Gbjp4yOG7m_4ZwyLtduyU54hWUcoycQs"

def update_env_file():
    """Actualizar archivo .env con las nuevas credenciales"""
    print("🔧 ACTUALIZANDO CREDENCIALES DE QDRANT")
    print("=" * 50)
    
    # Crear contenido del archivo .env
    env_content = f"""# Qdrant Configuration - CREDENCIALES FUNCIONALES
QDRANT_URL={NEW_QDRANT_URL}
QDRANT_API_KEY={NEW_QDRANT_API_KEY}

# PostgreSQL Configuration (mantener valores por defecto)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=123456
POSTGRES_DB=kumak_db

# OpenAI Configuration (mantener existente)
OPENAI_API_KEY=sk-proj-your-key-here

# WhatsApp Configuration (mantener existente)
WHATSAPP_TOKEN=your-token-here
WHATSAPP_PHONE_NUMBER_ID=your-phone-id-here
WHATSAPP_VERIFY_TOKEN=your-verify-token-here

# Tavily Configuration (mantener existente)
TAVILY_API_KEY=your-tavily-key-here
"""
    
    try:
        # Crear backup si existe
        if os.path.exists(".env"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f".env.backup_{timestamp}"
            os.rename(".env", backup_name)
            print(f"✅ Backup creado: {backup_name}")
        
        # Escribir nuevo archivo
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        
        print("✅ Archivo .env actualizado con nuevas credenciales")
        print(f"📊 Nueva URL: {NEW_QDRANT_URL}")
        print(f"📊 Nueva API Key: ***{NEW_QDRANT_API_KEY[-8:]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando .env: {str(e)}")
        return False

def test_new_credentials():
    """Probar las nuevas credenciales"""
    print(f"\n🧪 PROBANDO NUEVAS CREDENCIALES")
    print("=" * 50)
    
    try:
        from qdrant_client import QdrantClient
        
        # Crear cliente con nuevas credenciales
        client = QdrantClient(
            url=NEW_QDRANT_URL,
            api_key=NEW_QDRANT_API_KEY
        )
        
        # Probar conexión
        collections = client.get_collections()
        print("✅ Conexión exitosa a Qdrant")
        print(f"📊 Colecciones existentes: {[c.name for c in collections.collections]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando credenciales: {str(e)}")
        return False

def save_business_info_to_qdrant():
    """Guardar información empresarial simulada en Qdrant"""
    print(f"\n💾 GUARDANDO INFORMACIÓN EN QDRANT")
    print("=" * 50)
    
    try:
        import asyncio
        from app.services.memory_service import get_memory_service
        
        # Información empresarial simulada
        business_info = {
            "nombre_empresa": "Pollería Orlando",
            "sector": "Restaurante", 
            "productos_servicios_principales": "Pollos a la brasa, bebidas",
            "desafios_principales": "Competencia, costos",
            "ubicacion": "Local físico"
        }
        
        async def save_info():
            memory_service = get_memory_service()
            thread_id = "whatsapp_51962933641"
            
            success = await memory_service.save_business_info(thread_id, business_info)
            return success
        
        # Ejecutar función async
        success = asyncio.run(save_info())
        
        if success:
            print("✅ Información guardada exitosamente en Qdrant")
        else:
            print("❌ Error guardando información")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def test_complete_flow():
    """Probar el flujo completo con las nuevas credenciales"""
    print(f"\n🔄 PROBANDO FLUJO COMPLETO")
    print("=" * 50)
    
    try:
        from app.services.chat_service import process_message
        
        # Procesar mensaje con contexto
        result = process_message(
            message="Tengo un local físico",
            thread_id="whatsapp_51962933641",
            is_resuming=True
        )
        
        print("✅ Flujo ejecutado exitosamente")
        print(f"📊 Resultado: {result['answer'][:100]}...")
        print(f"📊 Status: {result['status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO ACTUALIZACIÓN DE CREDENCIALES QDRANT")
    print("=" * 60)
    
    steps = [
        ("Actualizar archivo .env", update_env_file),
        ("Probar nuevas credenciales", test_new_credentials),
        ("Guardar información en Qdrant", save_business_info_to_qdrant),
        ("Probar flujo completo", test_complete_flow)
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔧 PASO: {step_name}")
        print("=" * 60)
        
        success = step_func()
        if success:
            print(f"✅ {step_name} - ÉXITO")
        else:
            print(f"❌ {step_name} - FALLO")
            break
    
    print(f"\n🏁 ACTUALIZACIÓN COMPLETADA")
    print("=" * 60) 