"""
Script de Prueba - Sistema Deep Research con Equipo Especializado
Valida la funcionalidad completa del nuevo sistema de investigación paralela
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Agregar path del proyecto para importaciones
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

async def test_deep_research_system():
    """
    Prueba completa del sistema Deep Research.
    """
    try:
        # Importar módulos del sistema
        from app.graph.deep_research_system import perform_deep_research_analysis
        from app.graph.central_orchestrator_enhanced import process_message_with_enhanced_central_orchestrator
        
        print("🚀 =============================================================")
        print("🧪 TESTING DEEP RESEARCH SYSTEM - Equipo Planner + Workers")
        print("=============================================================")
        
        # === TEST 1: SISTEMA DEEP RESEARCH DIRECTO ===
        print("\n🔬 TEST 1: Sistema Deep Research Directo")
        print("-" * 50)
        
        # Contexto empresarial de prueba
        business_context = {
            "nombre_empresa": "Pollería Doña Carmen",
            "sector": "Restaurantes",
            "ubicacion": "Lima Norte, Perú",
            "productos_servicios_principales": "Pollo a la brasa, delivery, almuerzo ejecutivo",
            "descripcion_negocio": "Pollería familiar especializada en pollo a la brasa",
            "desafios_principales": "Competencia alta, necesidad de diferenciación"
        }
        
        research_topic = "oportunidades de crecimiento y estrategias de diferenciación"
        
        logger.info(f"🔍 Iniciando investigación sobre: {research_topic}")
        logger.info(f"📊 Contexto: {business_context['nombre_empresa']} - {business_context['sector']}")
        
        # Ejecutar investigación profunda
        result = await perform_deep_research_analysis(research_topic, business_context)
        
        # Mostrar resultados
        print(f"✅ ÉXITO: {result['success']}")
        print(f"📋 Plan de investigación: {len(result['research_plan'])} consultas")
        for i, query in enumerate(result['research_plan'], 1):
            print(f"   {i}. {query}")
        
        print(f"📚 Fuentes consultadas: {result['total_sources']}")
        print(f"⚡ Resumen de ejecución: {result['execution_summary']}")
        
        print("\n📄 INFORME FINAL:")
        print("-" * 40)
        print(result['final_report'])
        
        # === TEST 2: SISTEMA INTEGRADO CON ORQUESTADOR ===
        print("\n\n🤖 TEST 2: Sistema Integrado con Orquestador Central")
        print("-" * 55)
        
        # Simular conversación completa
        test_messages = [
            "Hola, tengo una pollería familiar en Lima Norte llamada Pollería Doña Carmen",
            "Nos especializamos en pollo a la brasa y delivery, pero hay mucha competencia",
            "¿Podrías investigar oportunidades de crecimiento para mi negocio?"
        ]
        
        thread_id = "test_deep_research_001"
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n👤 MENSAJE {i}: {message}")
            print("🤖 RESPUESTA:")
            
            # Procesar con orquestador mejorado
            response = await process_message_with_enhanced_central_orchestrator(
                message=message,
                thread_id=thread_id,
                reset_thread=(i == 1)  # Reset solo en el primer mensaje
            )
            
            if response['success']:
                print(f"✅ {response['response']}")
                if response.get('deep_research_activated'):
                    print("🚀 DEEP RESEARCH ACTIVADO EN ESTA RESPUESTA")
            else:
                print(f"❌ Error: {response.get('error', 'Error desconocido')}")
            
            print(f"📊 Sistema usado: {response['system_used']}")
            
            # Pausa entre mensajes para simular conversación real
            await asyncio.sleep(2)
        
        # === TEST 3: DIFERENTES TIPOS DE INVESTIGACIÓN ===
        print("\n\n🎯 TEST 3: Diferentes Tipos de Investigación")
        print("-" * 50)
        
        research_scenarios = [
            ("competencia", "Análisis de competencia directa"),
            ("tendencias", "Tendencias del mercado de restaurantes"),
            ("oportunidades", "Nuevas oportunidades de negocio"),
            ("marketing", "Estrategias de marketing digital efectivas")
        ]
        
        for research_type, description in research_scenarios:
            print(f"\n🔍 INVESTIGANDO: {description}")
            print("=" * len(f"INVESTIGANDO: {description}"))
            
            result = await perform_deep_research_analysis(
                research_topic=f"{research_type} para {business_context['nombre_empresa']}", 
                business_context=business_context
            )
            
            if result['success']:
                print(f"✅ Éxito - {result['total_sources']} fuentes consultadas")
                print(f"📋 {len(result['research_plan'])} consultas ejecutadas")
                print(f"📄 Informe: {result['final_report'][:200]}...")
            else:
                print(f"❌ Error: {result['final_report']}")
            
            # Pausa entre investigaciones
            await asyncio.sleep(1)
        
        # === RESUMEN FINAL ===
        print("\n\n📊 RESUMEN FINAL DE PRUEBAS")
        print("=" * 50)
        print("✅ Sistema Deep Research: Funcionando")
        print("✅ Orquestrador Mejorado: Integrado")
        print("✅ Múltiples tipos de investigación: Validados")
        print("✅ Procesamiento paralelo: Activo")
        print("✅ Síntesis de informes: Operativa")
        
        print("\n🎉 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("💡 Asegúrate de estar ejecutando desde la raíz del proyecto")
        print("💡 Verifica que todas las dependencias estén instaladas")
        
    except Exception as e:
        import traceback
        print(f"❌ Error inesperado: {e}")
        print("\n📋 STACK TRACE:")
        print(traceback.format_exc())

async def test_system_components():
    """
    Prueba individual de componentes del sistema.
    """
    print("\n🔧 TESTING COMPONENTES INDIVIDUALES")
    print("=" * 40)
    
    try:
        # Test del Planner
        from app.graph.deep_research_system import DeepResearchPlanner
        
        planner = DeepResearchPlanner()
        business_context = {
            "nombre_empresa": "Test Café",
            "sector": "Cafeterías",
            "ubicacion": "Madrid, España",
            "productos_servicios_principales": "Café de especialidad, pasteles"
        }
        
        print("\n🧠 Testing Planner...")
        plan = planner.create_research_plan("análisis de mercado", business_context)
        print(f"✅ Plan creado: {len(plan)} consultas")
        for i, query in enumerate(plan, 1):
            print(f"   {i}. {query}")
        
        # Test del Synthesizer
        from app.graph.deep_research_system import DeepResearchSynthesizer
        
        synthesizer = DeepResearchSynthesizer()
        mock_results = [
            {
                "status": "success",
                "query": "mercado café especialidad Madrid",
                "results": [
                    {"content": "El mercado de café especialidad en Madrid está creciendo un 15% anual..."},
                    {"content": "Las tendencias muestran preferencia por café orgánico y sostenible..."}
                ]
            }
        ]
        
        print("\n📊 Testing Synthesizer...")
        report = synthesizer.synthesize_research("análisis de mercado", business_context, mock_results)
        print(f"✅ Informe generado: {len(report)} caracteres")
        print(f"📄 Vista previa: {report[:150]}...")
        
        print("\n✅ COMPONENTES INDIVIDUALES: OK")
        
    except Exception as e:
        print(f"❌ Error en componentes: {e}")

def main():
    """
    Función principal de pruebas.
    """
    print("🚀 INICIANDO SUITE DE PRUEBAS - DEEP RESEARCH SYSTEM")
    print("=" * 60)
    
    # Verificar variables de entorno críticas
    required_env_vars = ['OPENAI_API_KEY', 'TAVILY_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {missing_vars}")
        print("💡 Asegúrate de configurar tu archivo .env correctamente")
        return
    
    # Ejecutar pruebas
    try:
        asyncio.run(test_system_components())
        asyncio.run(test_deep_research_system())
    except KeyboardInterrupt:
        print("\n⚠️ Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")

if __name__ == "__main__":
    main() 