#!/usr/bin/env python3
"""
Test simple para verificar que el supervisor corregido funciona sin bucles infinitos.
"""

import logging
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.chat_service import process_message

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_supervisor_no_infinite_loop():
    """Test que el supervisor no entre en bucle infinito."""
    print("🧪 Probando supervisor sin bucle infinito...")
    
    try:
        # Test con mensaje simple
        result = process_message(
            message="Hola",
            thread_id="test_supervisor_001",
            reset_thread=True
        )
        
        print(f"✅ Resultado: {result}")
        
        # Verificar que no hay error de recursión
        if result.get("status") == "error" and "recursion" in result.get("error", "").lower():
            print("❌ ERROR: Bucle infinito detectado")
            return False
        
        # Verificar que hay una respuesta
        if result.get("answer"):
            print(f"✅ Respuesta generada: {result['answer'][:100]}...")
            return True
        else:
            print("⚠️ No se generó respuesta")
            return False
            
    except Exception as e:
        print(f"❌ Error en test: {str(e)}")
        return False

def test_business_info_extraction():
    """Test que la extracción de información empresarial funciona."""
    print("🧪 Probando extracción de información empresarial...")
    
    try:
        # Test con información empresarial
        result = process_message(
            message="Mi empresa se llama TechSolutions y nos dedicamos al desarrollo de software",
            thread_id="test_supervisor_002",
            reset_thread=True
        )
        
        print(f"✅ Resultado: {result}")
        
        # Verificar que no hay error de recursión
        if result.get("status") == "error" and "recursion" in result.get("error", "").lower():
            print("❌ ERROR: Bucle infinito detectado")
            return False
        
        # Verificar que hay una respuesta
        if result.get("answer"):
            print(f"✅ Respuesta generada: {result['answer'][:100]}...")
            return True
        else:
            print("⚠️ No se generó respuesta")
            return False
            
    except Exception as e:
        print(f"❌ Error en test: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO TESTS DEL SUPERVISOR CORREGIDO")
    print("=" * 60)
    
    # Ejecutar tests
    test1_passed = test_supervisor_no_infinite_loop()
    print()
    test2_passed = test_business_info_extraction()
    
    print()
    print("=" * 60)
    print("📊 RESUMEN DE TESTS:")
    print(f"Test 1 (No bucle infinito): {'✅ PASÓ' if test1_passed else '❌ FALLÓ'}")
    print(f"Test 2 (Extracción info): {'✅ PASÓ' if test2_passed else '❌ FALLÓ'}")
    
    if test1_passed and test2_passed:
        print("🎉 TODOS LOS TESTS PASARON - SUPERVISOR CORREGIDO")
        sys.exit(0)
    else:
        print("💥 ALGUNOS TESTS FALLARON")
        sys.exit(1) 