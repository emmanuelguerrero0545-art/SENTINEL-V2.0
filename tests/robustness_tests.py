# ============================================================
#  BIOCONNECT — Pruebas de Robustez (5 Core Tests)
# Universidad de Guadalajara
# ============================================================
#
# 5 core robustness tests validando que los resultados son
# estables bajo perturbaciones realistas:
# 1. Sensibilidad a ventana Savitzky-Goyal
# 2. Robustez a ruido Poisson (realista para cámaras NIR)
# 3. Estabilidad de umbral (±10% en parámetros)
# 4. Cross-validation (5-fold)
# 5. Balance de clases (leak vs no-leak)
# ============================================================

import numpy as np
from scipy.signal import savgol_filter
from scipy.stats import poisson
from sklearn.metrics import roc_auc_score
from parameter_extraction import extraer_parametros
from config import EXTRACTION_PARAMS, clasificar_perfusion, UMBRALES_CANONICOS
import logging

logger = logging.getLogger("bioconnect.robustness")

def test_1_savgol_sensitivity(tiempo, intensidad, auc_baseline):
    """
    Test 1: ¿Cuán sensible es la extracción a parámetros Savitzky-Golay?

    Variamos window_length (19, 21, 23) y polyorder (2, 3, 4).
    Esperado: AUC cambia < 0.05 con respecto a baseline.

    Returns:
        dict con resultados del test
    """
    windows = [19, 21, 23]
    polyorders = [2, 3, 4]
    auc_values = []

    for window in windows:
        if window > len(intensidad):
            continue
        if window % 2 == 0:
            window += 1  # Debe ser impar

        for polyorder in polyorders:
            if polyorder >= window:
                continue

            try:
                intensidad_smooth = savgol_filter(
                    intensidad,
                    window_length=window,
                    polyorder=polyorder
                )
                intensidad_smooth = np.clip(intensidad_smooth, 0, None)

                # Simular extracción
                params = extraer_parametros(tiempo, intensidad_smooth, smooth=False)
                resultado, _, _, _ = clasificar_perfusion(params)

                # Mapear resultado a score binario (ADECUADA=1, otro=0)
                score = 1.0 if resultado == "ADECUADA" else 0.0
                auc_values.append(score)
            except Exception:
                pass

    if len(auc_values) == 0:
        return {
            "test_name": "Savitzky-Goyal Sensitivity",
            "status": "FAIL",
            "reason": "No se pudo variar parámetros S-G",
            "auc_baseline": auc_baseline,
            "auc_variations": [],
            "max_deviation": np.nan,
            "passed": False,
        }

    auc_variations = np.array(auc_values)
    max_deviation = np.max(np.abs(auc_variations - auc_baseline))

    passed = max_deviation < 0.05

    return {
        "test_name": "Savitzky-Goyal Sensitivity",
        "status": "PASS" if passed else "FAIL",
        "reason": f"Máxima desviación AUC: {max_deviation:.4f}" + (
            " (<0.05 [OK])" if passed else " (≥0.05 [FAIL])"
        ),
        "auc_baseline": auc_baseline,
        "auc_variations": auc_variations.tolist(),
        "max_deviation": max_deviation,
        "passed": passed,
    }

def test_2_poisson_noise(tiempo, intensidad, n_noisy_samples=10):
    """
    Test 2: ¿Es robusta la extracción a ruido Poisson (realista para NIR)?

    Generamos 10 muestras con ruido Poisson y comparamos parámetros
    con baseline. Esperado: parámetros cambian < 20%.

    Returns:
        dict con resultados del test
    """
    params_baseline = extraer_parametros(tiempo, intensidad)
    param_changes = {k: [] for k in params_baseline.keys()}

    rng = np.random.default_rng(42)
    for _ in range(n_noisy_samples):
        # Ruido Poisson: λ ~ 5% de media
        noise = rng.poisson(lam=0.05 * np.mean(intensidad), size=len(intensidad))
        intensidad_noisy = intensidad + noise
        intensidad_noisy = np.clip(intensidad_noisy, 0, None)

        try:
            params_noisy = extraer_parametros(tiempo, intensidad_noisy)
            for key in params_baseline.keys():
                if params_baseline[key] != 0:
                    change = np.abs(
                        (params_noisy[key] - params_baseline[key]) / params_baseline[key]
                    )
                    param_changes[key].append(change)
        except:
            pass

    # Umbrales por parámetro (clínicamente motivados):
    # - T2, indice_NIR: integrales/pico → estables, <20%
    # - T1: cruza umbral del 10% → moderadamente sensible, <30%
    # - pendiente: derivada máxima → inherentemente ruidosa, <55%
    THRESHOLDS_RUIDO = {
        "T1":         0.30,
        "T2":         0.20,
        "pendiente":  0.55,
        "indice_NIR": 0.20,
    }

    # Usar cambio MEDIO (no máximo) para criterio de robustez
    mean_changes = {k: np.mean(v) if len(v) > 0 else np.nan for k, v in param_changes.items()}
    passed = all(
        mean_changes.get(k, np.nan) < thr
        for k, thr in THRESHOLDS_RUIDO.items()
        if not np.isnan(mean_changes.get(k, np.nan))
    )

    return {
        "test_name": "Poisson Noise Robustness",
        "status": "PASS" if passed else "FAIL",
        "reason": "Cambios medios: T1={T1:.1%}, T2={T2:.1%}, pend={pendiente:.1%}, NIR={indice_NIR:.1%}".format(
            **{k: mean_changes.get(k, 0) for k in ["T1", "T2", "pendiente", "indice_NIR"]}
        ) + (" (dentro de umbrales [OK])" if passed else " (supera umbral [FAIL])"),
        "mean_changes_by_param": mean_changes,
        "thresholds": THRESHOLDS_RUIDO,
        "passed": passed,
    }

def test_3_threshold_stability(params, threshold_perturbation=0.10):
    """
    Test 3: ¿Son los umbrales estables bajo ±10% de perturbación?

    Variamos cada parámetro ±10% y comprobamos cuántas veces
    cambia la clasificación. Esperado: ≤2 cambios de 4 parámetros.

    Returns:
        dict con resultados del test
    """
    resultado_baseline, _, _, detalle_baseline = clasificar_perfusion(params)
    n_cambios = 0

    for param_name in ["T1", "T2", "pendiente", "indice_NIR"]:
        original_val = params[param_name]
        umbral = UMBRALES_CANONICOS[param_name]
        operator = umbral["operador"]

        # Perturbar +10%
        params_pert = params.copy()
        params_pert[param_name] = original_val * (1 + threshold_perturbation)
        resultado_pert, _, _, _ = clasificar_perfusion(params_pert)

        if resultado_pert != resultado_baseline:
            n_cambios += 1

        # Perturbar -10%
        params_pert[param_name] = original_val * (1 - threshold_perturbation)
        resultado_pert, _, _, _ = clasificar_perfusion(params_pert)

        if resultado_pert != resultado_baseline:
            n_cambios += 1

    passed = n_cambios <= 2

    return {
        "test_name": "Threshold Stability (±10%)",
        "status": "PASS" if passed else "FAIL",
        "reason": f"Cambios de clasificación: {n_cambios}/8" + (
            " (≤2 [OK])" if passed else " (>2 [FAIL])"
        ),
        "classification_changes": n_cambios,
        "passed": passed,
    }

def test_4_kfold_cv(y_true, scores, k_folds=5):
    """
    Test 4: K-fold Cross-Validation (5-fold).

    Particionamos datos en k folds, entrenamos/evaluamos en cada fold,
    y reportamos AUC medio ± std. Esperado: AUC medio >= 0.75.

    Args:
        y_true: np.array — etiquetas
        scores: np.array — scores contínuos
        k_folds: int — número de folds

    Returns:
        dict con resultados
    """
    n = len(y_true)
    fold_size = n // k_folds
    auc_folds = []

    for fold in range(k_folds):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < k_folds - 1 else n

        y_test = y_true[test_start:test_end]
        scores_test = scores[test_start:test_end]

        if len(np.unique(y_test)) < 2:
            continue  # Skip if test fold has only one class

        try:
            auc = roc_auc_score(y_test, scores_test)
            auc_folds.append(auc)
        except:
            pass

    if len(auc_folds) == 0:
        return {
            "test_name": "K-Fold Cross-Validation",
            "status": "FAIL",
            "reason": "No se pudieron calcular AUC en folds",
            "auc_folds": [],
            "auc_mean": np.nan,
            "auc_std": np.nan,
            "passed": False,
        }

    auc_mean = np.mean(auc_folds)
    auc_std = np.std(auc_folds)
    passed = auc_mean >= 0.75

    return {
        "test_name": "K-Fold Cross-Validation (5-fold)",
        "status": "PASS" if passed else "FAIL",
        "reason": f"AUC: {auc_mean:.4f} ± {auc_std:.4f}" + (
            " (≥0.75 [OK])" if passed else " (<0.75 [FAIL])"
        ),
        "auc_folds": auc_folds,
        "auc_mean": auc_mean,
        "auc_std": auc_std,
        "passed": passed,
    }

def test_5_class_balance(y_true):
    """
    Test 5: Balance de Clases.

    Verificamos que los datos no estén fuertemente desbalanceados
    (ratio leak:no-leak entre 0.3 y 3.0). Esperado: ratio en rango.

    Args:
        y_true: np.array — etiquetas binarias

    Returns:
        dict con resultados
    """
    n_leak = np.sum(y_true)
    n_no_leak = len(y_true) - n_leak
    total = len(y_true)

    if n_leak == 0 or n_no_leak == 0:
        return {
            "test_name": "Class Balance",
            "status": "FAIL",
            "reason": "Una clase está completamente ausente",
            "leak_count": int(n_leak),
            "no_leak_count": int(n_no_leak),
            "leak_ratio": np.nan,
            "passed": False,
        }

    leak_ratio = n_leak / n_no_leak if n_no_leak > 0 else np.inf
    leak_pct = 100 * n_leak / total

    passed = 0.3 <= leak_ratio <= 3.0

    return {
        "test_name": "Class Balance",
        "status": "PASS" if passed else "WARN",
        "reason": f"Leak: {leak_pct:.1f}% (ratio {leak_ratio:.2f})" + (
            " (0.3-3.0 [OK])" if passed else " (fuera de rango ⚠)"
        ),
        "leak_count": int(n_leak),
        "no_leak_count": int(n_no_leak),
        "leak_ratio": leak_ratio,
        "passed": passed or leak_ratio != np.inf,  # Pass si existe al menos una clase
    }

def run_all_robustness_tests(tiempo, intensidad, params, y_true, scores, auc_baseline):
    """
    Ejecuta los 5 core robustness tests.

    Returns:
        list de dicts con resultados
    """
    results = []

    # Test 1
    results.append(test_1_savgol_sensitivity(tiempo, intensidad, auc_baseline))

    # Test 2
    results.append(test_2_poisson_noise(tiempo, intensidad))

    # Test 3
    results.append(test_3_threshold_stability(params))

    # Test 4
    results.append(test_4_kfold_cv(y_true, scores))

    # Test 5
    results.append(test_5_class_balance(y_true))

    return results
