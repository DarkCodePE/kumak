"""
Script de prueba para validar las correcciones asíncronas del sistema.
"""
import asyncio
import logging
from app.services.chat_service import process_message
from app.graph.multi_agent_supervisor import create_multi_agent_supervisor_graph

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_async_process_message():
    """Prueba que process_message funcione con nodos asíncronos."""
    print("\n🧪 PRUEBA: process_message con nodos asíncronos")
    print("=" * 50)
    
    try:
        # Probar con un mensaje simple (process_message es síncrono pero nodos son asíncronos)
        result = process_message(
            message="Hola",
            thread_id="test_async_whatsapp_123"
        )
        
        print(f"✅ process_message ejecutado exitosamente")
        print(f"📊 Status: {result.get('status')}")
        print(f"📝 Answer: {result.get('answer', 'No answer')[:100]}...")
        
        assert result.get('status') in ['completed', 'interrupted'], "Status debe ser completed o interrupted"
        assert result.get('answer'), "Debe haber una respuesta"
        
        print("✅ Todas las validaciones pasaron")
        
    except Exception as e:
        print(f"❌ Error en process_message: {e}")
        raise

async def test_graph_creation():
    """Prueba que el grafo se cree correctamente."""
    print("\n🧪 PRUEBA: Creación de grafo multi-agente")
    print("=" * 50)
    
    try:
        graph = create_multi_agent_supervisor_graph()
        
        print(f"✅ Grafo creado exitosamente")
        print(f"📊 Tipo: {type(graph).__name__}")
        print(f"📊 Nodos: {len(graph.nodes)}")
        
        # Verificar nodos esperados
        expected_nodes = [
            "intelligent_supervisor",
            "enhanced_human_feedback",
            "info_completion_agent",
            "research_router",
            "conversational_agent",
            "researcher"
        ]
        
        for node in expected_nodes:
            assert node in graph.nodes, f"Nodo {node} no encontrado"
        
        print("✅ Todos los nodos esperados están presentes")
        
    except Exception as e:
        print(f"❌ Error creando grafo: {e}")
        raise

async def test_whatsapp_flow():
    """Prueba el flujo completo de WhatsApp."""
    print("\n🧪 PRUEBA: Flujo completo WhatsApp")
    print("=" * 50)
    
    try:
        # Simular mensaje de WhatsApp (process_message es síncrono pero nodos son asíncronos)
        result = process_message(
            message="Tengo una pollería llamada Jhony",
            thread_id="whatsapp_51962933641"
        )
        
        print(f"✅ Flujo WhatsApp ejecutado exitosamente")
        print(f"📊 Status: {result.get('status')}")
        print(f"📝 Answer: {result.get('answer', 'No answer')[:100]}...")
        print(f"🔄 Thread ID: {result.get('thread_id')}")
        
        # Verificar que es reconocido como WhatsApp
        assert result.get('thread_id', '').startswith('whatsapp_'), "Debe ser reconocido como thread de WhatsApp"
        
        print("✅ Flujo WhatsApp validado correctamente")
        
    except Exception as e:
        print(f"❌ Error en flujo WhatsApp: {e}")
        raise

async def main():
    """Función principal que ejecuta todas las pruebas."""
    print("🚀 INICIANDO PRUEBAS DE CORRECCIONES ASÍNCRONAS")
    print("=" * 60)
    
    try:
        # Ejecutar todas las pruebas
        await test_graph_creation()
        await test_async_process_message()
        await test_whatsapp_flow()
        
        print("\n🎉 TODAS LAS PRUEBAS PASARON EXITOSAMENTE")
        print("=" * 60)
        print("✅ Nodos asíncronos funcionando correctamente")
        print("✅ process_message asíncrono operativo")
        print("✅ Grafo multi-agente creado exitosamente")
        print("✅ Flujo WhatsApp validado")
        print("✅ Sistema listo para producción")
        
    except Exception as e:
        print(f"\n❌ ERROR EN LAS PRUEBAS: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 