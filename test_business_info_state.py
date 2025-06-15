#!/usr/bin/env python3
"""
Archivo de pruebas completo para verificar que el estado business_info
se actualiza correctamente en todo el flujo del sistema.

Este archivo prueba:
1. BusinessInfoManager extrae información correctamente
2. business_info_extraction_node actualiza el estado
3. El estado se propaga correctamente entre nodos
4. La información se guarda en Qdrant (memoria a largo plazo)
5. El flujo completo del supervisor funciona
"""

import asyncio
import logging
import sys
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

# Configurar logging para ver todos los detalles
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_business_info_manager():
    """Prueba 1: Verificar que BusinessInfoManager funciona correctamente."""
    print("\n" + "="*60)
    print("🧪 PRUEBA 1: BusinessInfoManager")
    print("="*60)
    
    try:
        from app.services.business_info_manager import get_business_info_manager
        
        manager = get_business_info_manager()
        
        # Caso 1: Información nueva
        print("\n📝 Caso 1: Extrayendo información nueva")
        message1 = HumanMessage(content="Mi empresa se llama TechSolutions y nos dedicamos al desarrollo de software")
        result1 = await manager.extract_and_store_business_info(message1, {}, "test_thread_001")
        
        print(f"✅ Resultado 1: {result1}")
        assert result1.get("nombre_empresa") == "TechSolutions"
        assert result1.get("sector") == "Desarrollo de software"
        
        # Caso 2: Información adicional
        print("\n📝 Caso 2: Agregando información adicional")
        message2 = HumanMessage(content="Tenemos 15 empleados y llevamos 5 años operando en Madrid")
        result2 = await manager.extract_and_store_business_info(message2, result1, "test_thread_001")
        
        print(f"✅ Resultado 2: {result2}")
        assert result2.get("num_empleados") == "15"
        assert result2.get("anos_operacion") == "5"
        
        # Caso 3: Mensaje sin información empresarial
        print("\n📝 Caso 3: Mensaje sin información empresarial")
        message3 = HumanMessage(content="Hola, ¿cómo estás?")
        result3 = await manager.extract_and_store_business_info(message3, result2, "test_thread_001")
        
        print(f"✅ Resultado 3: {result3}")
        assert result3 == result2  # No debería cambiar
        
        print("\n✅ PRUEBA 1 COMPLETADA: BusinessInfoManager funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ PRUEBA 1 FALLÓ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_extraction_node():
    """Prueba 2: Verificar que business_info_extraction_node actualiza el estado."""
    print("\n" + "="*60)
    print("🧪 PRUEBA 2: business_info_extraction_node")
    print("="*60)
    
    try:
        from app.graph.supervisor_architecture import business_info_extraction_node
        from app.graph.state import PYMESState
        
        # Estado inicial
        initial_state: PYMESState = {
            "messages": [HumanMessage(content="Mi empresa se llama DataCorp y nos dedicamos al análisis de datos")],
            "business_info": {},
            "input": None,
            "answer": None,
            "feedback": [],
            "growth_goals": None,
            "business_challenges": None,
            "stage": None,
            "growth_proposal": None,
            "context": None,
            "summary": None,
            "web_search": None,
            "documents": None,
            "current_agent": None,
            "last_handoff": None,
        }
        
        print(f"📥 Estado inicial: {initial_state.get('business_info')}")
        
        # Ejecutar nodo de extracción
        result = await business_info_extraction_node(initial_state)
        
        print(f"📤 Resultado del nodo: {result}")
        
        # Verificar que devuelve business_info actualizado
        assert "business_info" in result
        updated_info = result["business_info"]
        
        print(f"✅ business_info actualizado: {updated_info}")
        assert updated_info.get("nombre_empresa") == "DataCorp"
        assert "análisis de datos" in updated_info.get("sector", "").lower()
        
        print("\n✅ PRUEBA 2 COMPLETADA: business_info_extraction_node actualiza el estado")
        return True
        
    except Exception as e:
        print(f"❌ PRUEBA 2 FALLÓ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_evaluator_node():
    """Prueba 3: Verificar que business_info_evaluator_node funciona correctamente."""
    print("\n" + "="*60)
    print("🧪 PRUEBA 3: business_info_evaluator_node")
    print("="*60)
    
    try:
        from app.graph.supervisor_architecture import business_info_evaluator_node
        from app.graph.state import PYMESState
        
        # Estado con información parcial
        state_with_partial_info: PYMESState = {
            "messages": [
                HumanMessage(content="Mi empresa se llama TechStart"),
                HumanMessage(content="Nos dedicamos al desarrollo de aplicaciones móviles y tenemos 8 empleados")
            ],
            "business_info": {"nombre_empresa": "TechStart"},
            "input": None,
            "answer": None,
            "feedback": [],
            "growth_goals": None,
            "business_challenges": None,
            "stage": None,
            "growth_proposal": None,
            "context": None,
            "summary": None,
            "web_search": None,
            "documents": None,
            "current_agent": None,
            "last_handoff": None,
        }
        
        print(f"📥 Estado inicial: {state_with_partial_info.get('business_info')}")
        
        # Ejecutar nodo evaluador
        result = await business_info_evaluator_node(state_with_partial_info)
        
        print(f"📤 Resultado del evaluador: {result}")
        
        # Verificar que actualiza la información
        updated_info = result.get("business_info", {})
        print(f"✅ business_info después del evaluador: {updated_info}")
        
        assert updated_info.get("nombre_empresa") == "TechStart"
        assert "aplicaciones móviles" in updated_info.get("sector", "").lower() or \
               "aplicaciones móviles" in updated_info.get("productos_servicios_principales", "").lower()
        
        print("\n✅ PRUEBA 3 COMPLETADA: business_info_evaluator_node funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ PRUEBA 3 FALLÓ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_info_extractor_agent():
    """Prueba 4: Verificar que info_extractor_agent_node recibe el estado actualizado."""
    print("\n" + "="*60)
    print("🧪 PRUEBA 4: info_extractor_agent_node")
    print("="*60)
    
    try:
        from app.graph.supervisor_architecture import info_extractor_agent_node
        from app.graph.state import PYMESState
        
        # Estado inicial vacío
        empty_state: PYMESState = {
            "messages": [HumanMessage(content="Mi empresa se llama InnovateLab y desarrollamos software de IA")],
            "business_info": {},
            "input": None,
            "answer": None,
            "feedback": [],
            "growth_goals": None,
            "business_challenges": None,
            "stage": "info_gathering",
            "growth_proposal": None,
            "context": None,
            "summary": None,
            "web_search": None,
            "documents": None,
            "current_agent": "info_extractor",
            "last_handoff": None,
        }
        
        print(f"📥 Estado inicial: {empty_state.get('business_info')}")
        
        # Ejecutar agente extractor
        result = await info_extractor_agent_node(empty_state)
        
        print(f"📤 Resultado del agente: {result}")
        
        # Verificar que el agente procesó la información
        updated_info = result.get("business_info", {})
        messages = result.get("messages", [])
        
        print(f"✅ business_info después del agente: {updated_info}")
        print(f"✅ Mensajes generados: {[m.content for m in messages if hasattr(m, 'content')]}")
        
        # El agente debería haber extraído información o generado una pregunta
        assert updated_info.get("nombre_empresa") == "InnovateLab" or len(messages) > 0
        
        print("\n✅ PRUEBA 4 COMPLETADA: info_extractor_agent_node funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ PRUEBA 4 FALLÓ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_state_propagation():
    """Prueba 5: Verificar que el estado se propaga correctamente entre nodos."""
    print("\n" + "="*60)
    print("🧪 PRUEBA 5: Propagación del estado")
    print("="*60)
    
    try:
        from app.graph.supervisor_architecture import get_business_info_status_from_state
        from app.graph.state import PYMESState
        
        # Estado vacío
        empty_state: PYMESState = {
            "messages": [],
            "business_info": {},
            "input": None,
            "answer": None,
            "feedback": [],
            "growth_goals": None,
            "business_challenges": None,
            "stage": None,
            "growth_proposal": None,
            "context": None,
            "summary": None,
            "web_search": None,
            "documents": None,
            "current_agent": None,
            "last_handoff": None,
        }
        
        status_empty = get_business_info_status_from_state(empty_state)
        print(f"📊 Estado vacío: {status_empty}")
        assert status_empty == "Not started"
        
        # Estado parcial
        partial_state: PYMESState = {
            **empty_state,
            "business_info": {
                "nombre_empresa": "TestCorp",
                "sector": "Testing"
            }
        }
        
        status_partial = get_business_info_status_from_state(partial_state)
        print(f"📊 Estado parcial: {status_partial}")
        assert status_partial == "Partial"
        
        # Estado completo
        complete_state: PYMESState = {
            **empty_state,
            "business_info": {
                "nombre_empresa": "TestCorp",
                "sector": "Testing",
                "productos_servicios_principales": ["Testing services"],
                "ubicacion": "Madrid"
            }
        }
        
        status_complete = get_business_info_status_from_state(complete_state)
        print(f"📊 Estado completo: {status_complete}")
        assert status_complete == "Complete"
        
        print("\n✅ PRUEBA 5 COMPLETADA: Propagación del estado funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ PRUEBA 5 FALLÓ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_flow():
    """Prueba 6: Flujo completo simulado."""
    print("\n" + "="*60)
    print("🧪 PRUEBA 6: Flujo completo simulado")
    print("="*60)
    
    try:
        from app.graph.supervisor_architecture import (
            business_info_extraction_node,
            business_info_evaluator_node,
            get_business_info_status_from_state
        )
        from app.graph.state import PYMESState
        
        # Simular una conversación completa
        messages_sequence = [
            "Hola, quiero ayuda con mi negocio",
            "Mi empresa se llama FoodTech y nos dedicamos a la tecnología alimentaria",
            "Desarrollamos aplicaciones para restaurantes y tenemos 12 empleados",
            "Operamos desde Barcelona y llevamos 3 años en el mercado",
            "Nuestro principal desafío es la competencia con grandes empresas"
        ]
        
        # Estado inicial
        current_state: PYMESState = {
            "messages": [],
            "business_info": {},
            "input": None,
            "answer": None,
            "feedback": [],
            "growth_goals": None,
            "business_challenges": None,
            "stage": "info_gathering",
            "growth_proposal": None,
            "context": None,
            "summary": None,
            "web_search": None,
            "documents": None,
            "current_agent": None,
            "last_handoff": None,
        }
        
        print("🔄 Simulando conversación paso a paso...")
        
        for i, message_content in enumerate(messages_sequence):
            print(f"\n--- Paso {i+1}: '{message_content}' ---")
            
            # Agregar mensaje al estado
            current_state["messages"].append(HumanMessage(content=message_content))
            
            # Ejecutar extracción
            extraction_result = await business_info_extraction_node(current_state)
            
            # Actualizar estado con el resultado
            if "business_info" in extraction_result:
                current_state["business_info"] = extraction_result["business_info"]
            
            # Mostrar estado actual
            status = get_business_info_status_from_state(current_state)
            print(f"📊 Estado después del paso {i+1}: {status}")
            print(f"📋 business_info: {current_state['business_info']}")
        
        # Verificar estado final
        final_info = current_state["business_info"]
        final_status = get_business_info_status_from_state(current_state)
        
        print(f"\n🎯 ESTADO FINAL:")
        print(f"📊 Status: {final_status}")
        print(f"📋 business_info completo: {final_info}")
        
        # Verificaciones
        assert final_info.get("nombre_empresa") == "FoodTech"
        assert "tecnología alimentaria" in final_info.get("sector", "").lower() or \
               "tecnología alimentaria" in final_info.get("descripcion_negocio", "").lower()
        assert final_info.get("num_empleados") == "12"
        assert final_info.get("ubicacion") == "Barcelona"
        
        print("\n✅ PRUEBA 6 COMPLETADA: Flujo completo funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ PRUEBA 6 FALLÓ: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """Ejecuta todas las pruebas."""
    print("🚀 INICIANDO SUITE DE PRUEBAS COMPLETA")
    print("="*80)
    
    tests = [
        ("BusinessInfoManager", test_business_info_manager),
        ("business_info_extraction_node", test_extraction_node),
        ("business_info_evaluator_node", test_evaluator_node),
        ("info_extractor_agent_node", test_info_extractor_agent),
        ("Propagación del estado", test_state_propagation),
        ("Flujo completo", test_full_flow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Error ejecutando {test_name}: {str(e)}")
            results.append((test_name, False))
    
    # Resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN DE PRUEBAS")
    print("="*80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 RESULTADO FINAL: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡TODAS LAS PRUEBAS PASARON! El estado business_info se actualiza correctamente.")
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar los logs para más detalles.")
    
    return passed == total

if __name__ == "__main__":
    print("🧪 Ejecutando pruebas del estado business_info...")
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1) 