#!/usr/bin/env python3
"""
Script para corregir la persistencia del estado business_info
"""

import asyncio
from app.graph.supervisor_architecture import create_supervisor_pymes_graph
from app.services.memory_service import get_memory_service

def test_state_persistence():
    """Probar la persistencia del estado"""
    print("🔍 PROBANDO PERSISTENCIA DEL ESTADO")
    print("=" * 50)
    
    thread_id = "whatsapp_51962933641"
    
    try:
        # Crear grafo
        graph = create_supervisor_pymes_graph()
        config = {"configurable": {"thread_id": thread_id}}
        
        print(f"📊 Thread ID: {thread_id}")
        
        # Obtener estado actual
        state = graph.get_state(config)
        print(f"📊 Estado actual:")
        print(f"   Next nodes: {state.next}")
        print(f"   Values: {state.values}")
        
        # Verificar business_info específicamente
        business_info = state.values.get("business_info", {}) if state.values else {}
        print(f"📊 Business info actual: {business_info}")
        
        # Verificar mensajes
        messages = state.values.get("messages", []) if state.values else []
        print(f"📊 Número de mensajes: {len(messages)}")
        
        if messages:
            print("📊 Últimos 3 mensajes:")
            for i, msg in enumerate(messages[-3:], 1):
                print(f"   {i}. {type(msg).__name__}: {msg.content[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def test_memory_service():
    """Probar el servicio de memoria"""
    print(f"\n🧠 PROBANDO SERVICIO DE MEMORIA")
    print("=" * 50)
    
    try:
        memory_service = get_memory_service()
        thread_id = "whatsapp_51962933641"
        
        # Buscar información empresarial guardada
        print(f"📊 Buscando información para thread: {thread_id}")
        
        business_info = memory_service.load_business_info(thread_id)
        print(f"📊 Business info desde memoria: {business_info}")
        
        # Buscar con diferentes thread_ids que podrían existir
        possible_threads = [
            "whatsapp_51962933641",
            "temp_1749976443",  # Del log original
            "temp_1749976451",  # Del log original
            "temp_1749976463",  # Del log original
            "temp_1749976470"   # Del log original
        ]
        
        print(f"\n🔍 Buscando en threads posibles:")
        for thread in possible_threads:
            info = memory_service.load_business_info(thread)
            if info:
                print(f"✅ {thread}: {info}")
            else:
                print(f"❌ {thread}: No encontrado")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def fix_business_info_loading():
    """Corregir la carga de business_info en el evaluator"""
    print(f"\n🔧 ANALIZANDO CARGA DE BUSINESS_INFO")
    print("=" * 50)
    
    # El problema está en business_info_evaluator_node
    # Necesitamos verificar si está cargando correctamente el estado
    
    print("📋 Problema identificado:")
    print("   1. El evaluator inicia con business_info: {}")
    print("   2. Debería cargar el estado existente del thread")
    print("   3. El thread ya tiene información previa guardada")
    
    print(f"\n💡 Solución propuesta:")
    print("   1. Modificar business_info_evaluator_node")
    print("   2. Cargar business_info desde memoria al inicio")
    print("   3. Fusionar con información nueva extraída")
    
    return True

if __name__ == "__main__":
    print("🚀 INICIANDO DIAGNÓSTICO DE PERSISTENCIA")
    print("=" * 60)
    
    tests = [
        ("Persistencia del estado", test_state_persistence),
        ("Servicio de memoria", test_memory_service),
        ("Análisis de carga", fix_business_info_loading)
    ]
    
    for test_name, test_func in tests:
        print(f"\n🧪 EJECUTANDO: {test_name}")
        print("=" * 60)
        test_func()
    
    print(f"\n🏁 DIAGNÓSTICO COMPLETADO")
    print("=" * 60) 