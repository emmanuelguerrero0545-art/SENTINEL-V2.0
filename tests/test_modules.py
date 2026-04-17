#!/usr/bin/env python3
# ============================================================
#  BIOCONNECT — Test de Módulos
#  Verifica que todos los módulos se cargan correctamente
# ============================================================

import sys
import traceback

def test_imports():
    """Prueba que todos los módulos se importan sin errores."""
    modules_to_test = [
        ("config", "Configuración centralizada"),
        ("parameter_extraction", "Extracción de parámetros"),
        ("validation", "Validación y métricas"),
        ("robustness_tests", "Pruebas de robustez"),
        ("falsification_tests", "Pruebas de falsificación"),
        ("data_persistence", "Persistencia de datos"),
        ("BCV1", "Motor ICG + UI"),
    ]

    print("\n" + "=" * 70)
    print("BIOCONNECT v2.0 — MODULE IMPORT TEST")
    print("=" * 70 + "\n")

    failed = []

    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print(f"[PASS] {module_name:30s} | {description}")
        except ImportError as e:
            print(f"[FAIL] {module_name:30s} | ERROR: {e}")
            failed.append((module_name, str(e)))
        except Exception as e:
            print(f"[FAIL] {module_name:30s} | ERROR: {e}")
            failed.append((module_name, str(e)))

    print("\n" + "-" * 70)

    if failed:
        print(f"\n[ERROR] {len(failed)} module(s) failed to import:\n")
        for module_name, error in failed:
            print(f"  {module_name}:")
            print(f"    {error}\n")
        return False
    else:
        print("\n[PASS] All modules imported successfully!\n")
        return True

def test_config_thresholds():
    """Verifica que la configuración de umbrales sea correcta."""
    print("Testing Configuration Thresholds...")

    from config import (
        UMBRALES_CANONICOS,
        clasificar_parametro,
        clasificar_perfusion,
    )

    # Test 1: Verify all parameters are present
    expected_params = {"T1", "T2", "pendiente", "indice_NIR"}
    actual_params = set(UMBRALES_CANONICOS.keys())

    if expected_params != actual_params:
        print(f"[FAIL] Missing parameters: {expected_params - actual_params}")
        return False

    print(f"[PASS] All parameters present: {list(actual_params)}")

    # Test 2: Verify thresholds are consistent
    test_params_pass = {
        "T1": 8.0,
        "T2": 25.0,
        "pendiente": 6.0,
        "indice_NIR": 55.0,
    }

    resultado, color, aprobados, detalle = clasificar_perfusion(test_params_pass)

    if resultado != "ADECUADA" or aprobados != 4:
        print(f"[FAIL] Classification failed: {resultado}, {aprobados}/4")
        return False

    print(f"[PASS] Classification logic works: {resultado}")

    return True

def test_parameter_extraction():
    """Prueba que la extracción de parámetros funciona."""
    print("\nTesting Parameter Extraction...")

    import numpy as np
    from BCV1 import generar_senal_icg
    from parameter_extraction import extraer_parametros, validar_parametros

    # Generate synthetic signal
    tiempo, senal = generar_senal_icg(
        t1_real=5.0,
        t2_real=20.0,
        pendiente_real=0.5,
        indice_real=100.0,
    )

    params = extraer_parametros(tiempo, senal)

    if not validar_parametros(params):
        print(f"[FAIL] Parameter validation failed")
        return False

    print(f"[PASS] Parameters extracted: T1={params['T1']}, T2={params['T2']}, pend={params['pendiente']}, NIR={params['indice_NIR']}")

    return True

def test_validation_metrics():
    """Prueba que el cálculo de métricas funciona."""
    print("\nTesting Validation Metrics...")

    import numpy as np
    from validation import calcular_metricas

    # Dummy data: perfect AUC
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_pred = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])

    metrics = calcular_metricas(y_true, y_pred, threshold=0.5)

    if metrics["auc"] < 0.99:  # Should be nearly perfect
        print(f"[FAIL] AUC calculation seems wrong: {metrics['auc']}")
        return False

    print(f"[PASS] Metrics calculated: AUC={metrics['auc']:.4f}, Sens={metrics['sensitivity']:.4f}, Spec={metrics['specificity']:.4f}")

    return True

def main():
    """Ejecuta todas las pruebas."""
    tests = [
        ("Module Imports", test_imports),
        ("Config Thresholds", test_config_thresholds),
        ("Parameter Extraction", test_parameter_extraction),
        ("Validation Metrics", test_validation_metrics),
    ]

    results = []

    for test_name, test_fn in tests:
        try:
            result = test_fn()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[ERROR] {test_name} raised exception:")
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status:7s} | {test_name}")

    print("-" * 70)
    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! Ready to run synthetic_validation_pipeline.py\n")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} test(s) failed. Please fix errors above.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
