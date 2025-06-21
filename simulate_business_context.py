#!/usr/bin/env python3
"""
Script para simular el contexto empresarial basado en la conversación de WhatsApp
"""

from app.graph.supervisor_architecture import create_supervisor_pymes_graph
from app.services.memory_service import get_memory_service
import asyncio

def simulate_previous_business_info():
    """Simular información empresarial previa basada en la conversación"""
    print("🎭 SIMULANDO CONTEXTO EMPRESARIAL PREVIO")
    print("=" * 50)
    
    # Información que debería existir basada en la conversación previa
    simulated_business_info = {
        "nombre_empresa": "Pollería Orlando",
        "sector": "Restaurante", 
        "productos_servicios_principales": "Pollos a la brasa, bebidas",
        "desafios_principales": "Competencia, costos",
        # ubicacion se agregará con el nuevo mensaje
    }
    
    print(f"📊 Información empresarial simulada:")
    for key, value in simulated_business_info.items():
        print(f"   {key}: {value}")
    
    return simulated_business_info

async def save_simulated_info():
    """Guardar información simulada en memoria"""
    print(f"\n💾 GUARDANDO INFORMACIÓN SIMULADA")
    print("=" * 50)
    
    try:
        memory_service = get_memory_service()
        thread_id = "whatsapp_51962933641"
        
        simulated_info = simulate_previous_business_info()
        
        # Guardar en memoria
        success = await memory_service.save_business_info(thread_id, simulated_info)
        
        if success:
            print("✅ Información simulada guardada exitosamente")
        else:
            print("❌ Error guardando información simulada")
        
        # Verificar que se guardó
        loaded_info = memory_service.load_business_info(thread_id)
        print(f"📊 Información cargada después de guardar: {loaded_info}")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def test_enhanced_evaluator():
    """Probar el evaluator mejorado con información simulada"""
    print(f"\n🧪 PROBANDO EVALUATOR MEJORADO")
    print("=" * 50)
    
    try:
        # Crear grafo
        graph = create_supervisor_pymes_graph()
        thread_id = "whatsapp_51962933641"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Simular mensaje de usuario
        from langgraph.types import Command
        message = "Tengo un local físico"
        
        print(f"📊 Simulando mensaje: {message}")
        print(f"📊 Thread ID: {thread_id}")
        
        # Ejecutar grafo con el mensaje
        result = graph.invoke(Command(resume=message), config)
        
        print(f"✅ Grafo ejecutado exitosamente")
        
        # Verificar resultado
        business_info = result.get("business_info", {})
        print(f"📊 Business info resultante: {business_info}")
        
        # Verificar si tiene información completa
        expected_fields = ["nombre_empresa", "sector", "productos_servicios_principales", "ubicacion"]
        missing_fields = [field for field in expected_fields if not business_info.get(field)]
        
        if not missing_fields:
            print("✅ ¡Información completa! El contexto se cargó correctamente")
        else:
            print(f"⚠️ Campos faltantes: {missing_fields}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

async def main():
    """Función principal"""
    print("🚀 INICIANDO SIMULACIÓN DE CONTEXTO EMPRESARIAL")
    print("=" * 60)
    
    # Paso 1: Simular información previa
    simulate_previous_business_info()
    
    # Paso 2: Guardar información simulada
    await save_simulated_info()
    
    # Paso 3: Probar evaluator mejorado
    test_enhanced_evaluator()
    
    print(f"\n🏁 SIMULACIÓN COMPLETADA")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 