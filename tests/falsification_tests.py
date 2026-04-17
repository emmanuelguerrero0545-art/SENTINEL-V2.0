# ============================================================
#  BIOCONNECT — Pruebas de Falsificación (3 Core Tests)
# Universidad de Guadalajara
# ============================================================
#
# 3 core falsification tests que verifican la validez del modelo:
# 1. Label Permutation (¿el modelo aprende etiquetas reales?)
# 2. Reversed Threshold (¿la dirección del umbral es correcta?)
# 3. Null Hypothesis (¿AUC > 0.55 en datos aleatorios?)
# ============================================================

import numpy as np
from sklearn.metrics import roc_auc_score

def test_1_label_permutation(y_true, scores, n_permutations=100):
    """
    Test 1: Permutación de Etiquetas.

    Si permutamos aleatoriamente las etiquetas, el AUC debería
    caer significativamente (cercano a 0.5).

    Lógica:
    - AUC_real = AUC con etiquetas reales
    - AUC_perm = AUC promedio con etiquetas permutadas n veces
    - Esperado: AUC_real >> AUC_perm (diferencia > 0.10)

    Args:
        y_true: np.array — etiquetas reales
        scores: np.array — scores del modelo
        n_permutations: int — número de permutaciones

    Returns:
        dict con resultados
    """
    # AUC real
    auc_real = roc_auc_score(y_true, scores)

    # AUC con etiquetas permutadas
    rng = np.random.default_rng(42)
    auc_perms = []
    for _ in range(n_permutations):
        y_perm = rng.permutation(y_true)
        if len(np.unique(y_perm)) < 2:
            continue
        try:
            auc_perm = roc_auc_score(y_perm, scores)
            auc_perms.append(auc_perm)
        except Exception:
            pass

    if len(auc_perms) == 0:
        return {
            "test_name": "Label Permutation",
            "status": "FAIL",
            "reason": "No se pudieron calcular AUC permutados",
            "auc_real": auc_real,
            "auc_perm_mean": np.nan,
            "auc_perm_std": np.nan,
            "difference": np.nan,
            "passed": False,
        }

    auc_perm_mean = np.mean(auc_perms)
    auc_perm_std = np.std(auc_perms)
    difference = auc_real - auc_perm_mean

    # Esperado: diferencia > 0.10
    passed = difference > 0.10

    return {
        "test_name": "Label Permutation",
        "status": "PASS" if passed else "FAIL",
        "reason": f"AUC_real={auc_real:.4f}, AUC_perm={auc_perm_mean:.4f}±{auc_perm_std:.4f}, diff={difference:.4f}" + (
            " (>0.10 [OK])" if passed else " (≤0.10 [FAIL])"
        ),
        "auc_real": auc_real,
        "auc_perm_mean": auc_perm_mean,
        "auc_perm_std": auc_perm_std,
        "auc_perms": auc_perms,
        "difference": difference,
        "passed": passed,
    }

def test_2_reversed_threshold(y_true, scores):
    """
    Test 2: Umbral Invertido.

    Si invertimos el umbral (scores → 1 - scores), el AUC debería
    ser ~0.5 (máxima incertidumbre) o caer drásticamente.

    Lógica:
    - AUC_real = AUC normal
    - AUC_reversed = AUC con scores invertidos
    - Esperado: AUC_reversed << AUC_real O AUC_reversed ~ 0.5

    Args:
        y_true: np.array — etiquetas
        scores: np.array — scores del modelo

    Returns:
        dict con resultados
    """
    auc_real = roc_auc_score(y_true, scores)

    # Invertir scores
    scores_reversed = 1.0 - scores
    auc_reversed = roc_auc_score(y_true, scores_reversed)

    # Esperado: AUC_real > 0.5 y AUC_reversed < AUC_real por al menos 0.10
    # Nota: con AUC_real cercano a 1.0, AUC_reversed = 1 - AUC_real ≈ 0.0,
    # lo que demuestra que la dirección del score es correcta.
    difference = auc_real - auc_reversed
    passed = auc_real > 0.5 and difference > 0.10

    return {
        "test_name": "Reversed Threshold",
        "status": "PASS" if passed else "FAIL",
        "reason": f"AUC_real={auc_real:.4f}, AUC_reversed={auc_reversed:.4f}, diff={difference:.4f}" + (
            " (AUC_real >> AUC_reversed [OK])" if passed else " (sin diferencia significativa [FAIL])"
        ),
        "auc_real": auc_real,
        "auc_reversed": auc_reversed,
        "difference": difference,
        "passed": passed,
    }

def test_3_null_hypothesis(y_true, scores):
    """
    Test 3: Hipótesis Nula.

    Generamos scores aleatorios N(0,1) sin correlación con y_true.
    El AUC debería ser ~0.5 (chance). Si AUC_real >> AUC_null,
    el modelo aprendió algo real.

    Lógica:
    - AUC_real = AUC con scores reales
    - AUC_null = AUC con scores aleatorios
    - Esperado: AUC_real > 0.55 AND AUC_real > AUC_null + 0.10

    Args:
        y_true: np.array — etiquetas
        scores: np.array — scores del modelo
        n_null_samples: int — número de muestras nulas

    Returns:
        dict con resultados
    """
    auc_real = roc_auc_score(y_true, scores)

    # Scores nulos (aleatorios)
    rng_null = np.random.default_rng(123)
    scores_null = rng_null.uniform(0, 1, size=len(y_true))
    auc_null = roc_auc_score(y_true, scores_null)

    # Criterios
    criterion_1 = auc_real > 0.55  # Mejor que chance
    criterion_2 = auc_real > auc_null + 0.10  # Mejor que nulo

    passed = criterion_1 and criterion_2

    return {
        "test_name": "Null Hypothesis Test",
        "status": "PASS" if passed else "FAIL",
        "reason": f"AUC_real={auc_real:.4f} (>0.55: {'[OK]' if criterion_1 else '[FAIL]'}), AUC_null={auc_null:.4f}, diff={auc_real - auc_null:.4f} (>0.10: {'[OK]' if criterion_2 else '[FAIL]'})",
        "auc_real": auc_real,
        "auc_null": auc_null,
        "criterion_1_auc_gt_055": criterion_1,
        "criterion_2_auc_gt_null_plus_010": criterion_2,
        "passed": passed,
    }

def run_all_falsification_tests(y_true, scores):
    """
    Ejecuta los 3 core falsification tests.

    Args:
        y_true: np.array — etiquetas binarias
        scores: np.array — scores continuos [0, 1]

    Returns:
        list de dicts con resultados
    """
    results = []

    # Test 1
    results.append(test_1_label_permutation(y_true, scores, n_permutations=100))

    # Test 2
    results.append(test_2_reversed_threshold(y_true, scores))

    # Test 3
    results.append(test_3_null_hypothesis(y_true, scores))

    return results
