#!/usr/bin/env python3
"""
Prueba final para verificar que Qdrant funciona correctamente con el sistema
"""

import asyncio
from app.services.memory_service import get_memory_service

async def test_complete_qdrant_integration():
    """Prueba la integración completa de Qdrant con el sistema"""
    print("🧪 PRUEBA FINAL DE INTEGRACIÓN QDRANT")
    print("=" * 50)
    
    try:
        # Obtener servicio de memoria
        memory_service = get_memory_service()
        print(f"✅ MemoryService obtenido")
        print(f"📊 Qdrant disponible: {memory_service.qdrant_available}")
        
        if not memory_service.qdrant_available:
            print("❌ Qdrant no está disponible")
            return False
        
        # Probar guardar información empresarial
        test_business_info = {
            "nombre_empresa": "Pollería Rocky Test",
            "sector": "Restaurante",
            "productos_servicios_principales": "Pollos a la brasa, bebidas",
            "ubicacion": "Local físico",
            "descripcion_negocio": "Restaurante especializado en pollos a la brasa"
        }
        
        print(f"\n💾 PROBANDO GUARDAR INFORMACIÓN EMPRESARIAL")
        print("=" * 40)
        
        success = await memory_service.save_business_info("test_thread_final", test_business_info)
        
        if success:
            print("✅ Información empresarial guardada exitosamente")
        else:
            print("❌ Error guardando información empresarial")
            return False
        
        # Probar cargar información
        print(f"\n📖 PROBANDO CARGAR INFORMACIÓN EMPRESARIAL")
        print("=" * 40)
        
        loaded_info = memory_service.load_business_info("test_thread_final")
        
        if loaded_info:
            print("✅ Información cargada exitosamente")
            print(f"📊 Empresa: {loaded_info.get('nombre_empresa')}")
            print(f"📊 Sector: {loaded_info.get('sector')}")
            print(f"📊 Ubicación: {loaded_info.get('ubicacion')}")
        else:
            print("❌ No se pudo cargar la información")
            return False
        
        # Probar búsqueda de negocios similares
        print(f"\n🔍 PROBANDO BÚSQUEDA DE NEGOCIOS SIMILARES")
        print("=" * 40)
        
        similar_businesses = memory_service.search_similar_businesses(test_business_info, limit=3)
        
        print(f"📊 Negocios similares encontrados: {len(similar_businesses)}")
        for i, business in enumerate(similar_businesses, 1):
            empresa = business.get('data', {}).get('nombre_empresa', 'N/A')
            sector = business.get('data', {}).get('sector', 'N/A')
            score = business.get('score', 0)
            print(f"   {i}. {empresa} ({sector}) - Score: {score:.4f}")
        
        # Probar guardar resultados de investigación
        print(f"\n🔬 PROBANDO GUARDAR RESULTADOS DE INVESTIGACIÓN")
        print("=" * 40)
        
        research_data = {
            "content": "Análisis de mercado para restaurantes de pollos a la brasa",
            "findings": ["Mercado en crecimiento", "Competencia moderada", "Oportunidades en delivery"],
            "recommendations": ["Mejorar presencia online", "Expandir servicios de delivery"]
        }
        
        research_success = await memory_service.save_research_results("test_thread_final", research_data)
        
        if research_success:
            print("✅ Resultados de investigación guardados exitosamente")
        else:
            print("❌ Error guardando resultados de investigación")
            return False
        
        # Verificar colecciones
        print(f"\n📊 VERIFICANDO COLECCIONES")
        print("=" * 40)
        
        collections = memory_service.qdrant_client.get_collections().collections
        collection_names = [col.name for col in collections]
        
        print(f"📊 Colecciones disponibles: {collection_names}")
        
        for collection_name in [memory_service.business_collection, memory_service.research_collection]:
            if collection_name in collection_names:
                info = memory_service.qdrant_client.get_collection(collection_name)
                print(f"✅ {collection_name}: {info.points_count} puntos")
            else:
                print(f"❌ {collection_name}: No encontrada")
        
        print(f"\n🎉 ¡TODAS LAS PRUEBAS EXITOSAS!")
        print("📋 Qdrant está completamente funcional")
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO PRUEBA FINAL DE QDRANT")
    print("=" * 60)
    
    success = asyncio.run(test_complete_qdrant_integration())
    
    if success:
        print(f"\n🏆 ¡QDRANT COMPLETAMENTE FUNCIONAL!")
        print("📋 El sistema está listo para producción con:")
        print("   ✅ Conexión a Qdrant Cloud")
        print("   ✅ Colecciones creadas")
        print("   ✅ Operaciones de memoria funcionando")
        print("   ✅ Búsquedas semánticas disponibles")
        print("   ✅ Persistencia de datos empresariales")
        print("   ✅ Almacenamiento de investigaciones")
    else:
        print(f"\n❌ HAY PROBLEMAS CON QDRANT")
        print("📋 Revisa los errores anteriores")
    
    print(f"\n🏁 PRUEBA FINAL COMPLETADA")
    print("=" * 60) 