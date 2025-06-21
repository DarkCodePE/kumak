#!/usr/bin/env python3
"""
Script para debuggear el flujo de WhatsApp y encontrar dónde se corta
"""

import logging
import traceback
from app.services.chat_service import process_message
from app.graph.supervisor_architecture import create_supervisor_pymes_graph

# Configurar logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_whatsapp_flow():
    """Probar el flujo completo de WhatsApp paso a paso"""
    print("🔍 DEBUGGEANDO FLUJO DE WHATSAPP")
    print("=" * 50)
    
    # Simular el escenario exacto del log
    thread_id = "whatsapp_51962933641"
    message = "Tengo un local físico"
    is_resuming = True
    
    print(f"📊 Parámetros de prueba:")
    print(f"   Thread ID: {thread_id}")
    print(f"   Mensaje: {message}")
    print(f"   Is Resuming: {is_resuming}")
    
    try:
        print(f"\n🔧 PASO 1: Creando grafo supervisor")
        print("-" * 30)
        
        # Crear el grafo paso a paso
        graph = create_supervisor_pymes_graph()
        print("✅ Grafo creado exitosamente")
        
        print(f"\n🔧 PASO 2: Configurando parámetros")
        print("-" * 30)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "reset_thread": False
            },
            "recursion_limit": 100
        }
        print("✅ Configuración creada")
        
        print(f"\n🔧 PASO 3: Preparando input para resuming")
        print("-" * 30)
        
        from langgraph.types import Command
        graph_input = Command(resume=message)
        print("✅ Command de resume creado")
        
        print(f"\n🔧 PASO 4: Obteniendo estado existente")
        print("-" * 30)
        
        try:
            existing_state = graph.get_state(config)
            print(f"✅ Estado existente obtenido")
            print(f"   Next nodes: {existing_state.next}")
            print(f"   Values keys: {list(existing_state.values.keys()) if existing_state.values else 'None'}")
        except Exception as e:
            print(f"⚠️ Error obteniendo estado: {str(e)}")
        
        print(f"\n🔧 PASO 5: Ejecutando grafo")
        print("-" * 30)
        
        print("🚀 Invocando graph.invoke()...")
        result = graph.invoke(graph_input, config)
        print("✅ Grafo ejecutado exitosamente")
        
        print(f"\n🔧 PASO 6: Analizando resultado")
        print("-" * 30)
        
        print(f"📊 Tipo de resultado: {type(result)}")
        if isinstance(result, dict):
            print(f"📊 Claves del resultado: {list(result.keys())}")
        
        # Obtener estado final
        final_state = graph.get_state(config)
        print(f"📊 Estado final - Next nodes: {final_state.next}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN PASO: {str(e)}")
        print(f"🔍 Tipo de error: {type(e).__name__}")
        print(f"📋 Traceback completo:")
        print(traceback.format_exc())
        return False

def test_process_message_directly():
    """Probar process_message directamente"""
    print(f"\n🧪 PROBANDO PROCESS_MESSAGE DIRECTAMENTE")
    print("=" * 50)
    
    try:
        result = process_message(
            message="Tengo un local físico",
            thread_id="whatsapp_51962933641",
            is_resuming=True
        )
        
        print("✅ process_message ejecutado exitosamente")
        print(f"📊 Resultado: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Error en process_message: {str(e)}")
        print(f"📋 Traceback:")
        print(traceback.format_exc())
        return False

def test_graph_compilation():
    """Probar solo la compilación del grafo"""
    print(f"\n🔨 PROBANDO COMPILACIÓN DEL GRAFO")
    print("=" * 50)
    
    try:
        print("🔧 Creando grafo...")
        graph = create_supervisor_pymes_graph()
        print("✅ Grafo compilado exitosamente")
        
        print("🔧 Verificando estructura del grafo...")
        print(f"📊 Nodos: {list(graph.nodes.keys()) if hasattr(graph, 'nodes') else 'No disponible'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error compilando grafo: {str(e)}")
        print(f"📋 Traceback:")
        print(traceback.format_exc())
        return False

def test_command_resume():
    """Probar específicamente el Command(resume=...)"""
    print(f"\n⚡ PROBANDO COMMAND RESUME")
    print("=" * 50)
    
    try:
        from langgraph.types import Command
        
        print("🔧 Creando Command...")
        cmd = Command(resume="Tengo un local físico")
        print("✅ Command creado exitosamente")
        print(f"📊 Command type: {type(cmd)}")
        print(f"📊 Command attributes: {dir(cmd)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creando Command: {str(e)}")
        print(f"📋 Traceback:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO DEBUG DEL FLUJO DE WHATSAPP")
    print("=" * 60)
    
    tests = [
        ("Compilación del grafo", test_graph_compilation),
        ("Command resume", test_command_resume),
        ("Flujo completo paso a paso", test_whatsapp_flow),
        ("Process message directo", test_process_message_directly)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🧪 EJECUTANDO: {test_name}")
        print("=" * 60)
        
        try:
            success = test_func()
            results[test_name] = "✅ ÉXITO" if success else "❌ FALLO"
        except Exception as e:
            results[test_name] = f"❌ EXCEPCIÓN: {str(e)}"
            print(f"❌ Excepción no capturada: {str(e)}")
    
    print(f"\n📊 RESUMEN DE RESULTADOS")
    print("=" * 60)
    
    for test_name, result in results.items():
        print(f"{result} - {test_name}")
    
    print(f"\n🏁 DEBUG COMPLETADO")
    print("=" * 60) 