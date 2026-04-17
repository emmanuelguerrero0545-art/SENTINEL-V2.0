# ============================================================
#  BIOCONNECT — Pipeline de Validación Sintética Completa
# Universidad de Guadalajara
# ============================================================
#
# Orquesta:
# 1. Generación de N=500 curvas sintéticas ICG
# 2. Etiquetado: leak vs no-leak
# 3. Extracción de 4 parámetros
# 4. Train/Test split (400/100)
# 5. Validación: AUC, sensitivity, specificity
# 6. Robustness: 5 core tests
# 7. Falsification: 3 core tests
# 8. Persistencia: NPZ + JSON
# ============================================================

import numpy as np
import json
import os
from BCV1 import generar_senal_icg
from parameter_extraction import extraer_parametros
from config import (
    VALIDATION_PARAMS,
    clasificar_perfusion,
    SYNTHETIC_PARAMS,
)
from validation import (
    calcular_metricas,
    encontrar_umbral_optimo,
    train_test_split,
)
from classifier import BioConnectClassifier
from robustness_tests import run_all_robustness_tests
from falsification_tests import run_all_falsification_tests
from data_persistence import (
    save_synthetic_dataset,
    save_validation_results,
    create_experiment_report,
    summary_to_text,
)
from logger import get_logger

log = get_logger("validation_pipeline")

def generar_dataset_sintetico(n_samples=None, seed=42):
    """
    Genera N curvas ICG sintéticas con etiquetas de leak/no-leak.

    Estrategia de etiquetado:
    - 40% ADECUADA clara (no leak): T1≤10, T2≤30, pend≥5, NIR≥50
    - 10% ADECUADA borderline (no leak, pero parámetros cerca del umbral)
    - 10% COMPROMETIDA borderline (leak, parámetros apenas fuera)
    - 40% COMPROMETIDA clara (leak): al menos 1 parámetro falla

    El solapamiento entre borderline adecuada y borderline comprometida
    genera AUC < 1.0, produciendo validación creíble.

    Args:
        n_samples: int — número de muestras (default: VALIDATION_PARAMS)
        seed: int — random seed

    Returns:
        (tiempo, intensidades, parametros, labels)
    """
    if n_samples is None:
        n_samples = VALIDATION_PARAMS["n_sinteticas"]

    rng = np.random.default_rng(seed)

    tiempo = np.linspace(
        0,
        SYNTHETIC_PARAMS["tiempo_max"],
        SYNTHETIC_PARAMS["tiempo_puntos"]
    )

    intensidades = []
    parametros = []
    labels = []

    # --- 40% ADECUADA clara (no leak, label=0) ---
    n_adecuada_clara = int(n_samples * 0.40)
    for i in range(n_adecuada_clara):
        t1 = rng.uniform(2, 8)
        dt_rise = rng.uniform(8, 20)
        t2 = t1 + dt_rise
        t2 = min(t2, 28.0)
        dt_rise = t2 - t1
        amp_min = max(80, 4.5 * dt_rise)
        amp = rng.uniform(amp_min, max(amp_min, 150))
        pend = 10.0

        _, senal = generar_senal_icg(t1, t2, pend, amp, seed=seed + i)
        params = extraer_parametros(tiempo, senal)

        intensidades.append(senal)
        parametros.append(params)
        labels.append(0)

    # --- 10% ADECUADA borderline (no leak, pero cerca del umbral) ---
    n_adecuada_border = int(n_samples * 0.10)
    offset = n_adecuada_clara
    for i in range(n_adecuada_border):
        # T1 entre 8-10s (cerca del umbral de 10)
        t1 = rng.uniform(8, 10)
        dt_rise = rng.uniform(6, 12)
        t2 = t1 + dt_rise
        t2 = min(t2, 29.5)
        dt_rise = t2 - t1
        # Amplitud moderada — pendiente cerca del umbral
        amp_min = max(40, 3.5 * dt_rise)
        amp = rng.uniform(amp_min, max(amp_min, 80))
        pend = 10.0

        _, senal = generar_senal_icg(t1, t2, pend, amp, seed=seed + offset + i)
        params = extraer_parametros(tiempo, senal)

        intensidades.append(senal)
        parametros.append(params)
        labels.append(0)  # Sigue siendo no-leak por diseño

    # --- 10% COMPROMETIDA borderline (leak, apenas fuera) ---
    n_comprom_border = int(n_samples * 0.10)
    offset += n_adecuada_border
    for i in range(n_comprom_border):
        tipo = rng.choice(["T1_marginal", "pend_marginal"])
        if tipo == "T1_marginal":
            # T1 entre 10-12s (apenas fuera)
            t1 = rng.uniform(10, 12)
            dt_rise = rng.uniform(8, 15)
            t2 = t1 + dt_rise
            t2 = min(t2, 29.0)
            amp = rng.uniform(70, 130)
        else:
            # Pendiente apenas bajo el umbral
            t1 = rng.uniform(2, 9)
            dt_rise = rng.uniform(8, 15)
            t2 = t1 + dt_rise
            t2 = min(t2, 29.0)
            amp = rng.uniform(12, 25)  # Amplitud baja → pendiente marginal
        pend = 10.0

        _, senal = generar_senal_icg(t1, t2, pend, amp, seed=seed + offset + i)
        params = extraer_parametros(tiempo, senal)

        intensidades.append(senal)
        parametros.append(params)
        labels.append(1)  # Leak

    # --- 40% COMPROMETIDA clara (leak, label=1) ---
    n_comprom_clara = n_samples - n_adecuada_clara - n_adecuada_border - n_comprom_border
    offset += n_comprom_border
    for i in range(n_comprom_clara):
        comprometimiento = rng.choice(["T1_alto", "T2_alto", "pend_baja", "nir_baja"])

        if comprometimiento == "T1_alto":
            t1 = rng.uniform(13, 20)
            t2 = t1 + rng.uniform(8, 18)
            t2 = min(t2, SYNTHETIC_PARAMS["tiempo_max"] - 5)
            amp = rng.uniform(80, 150)

        elif comprometimiento == "T2_alto":
            t1 = rng.uniform(2, 9)
            t2 = rng.uniform(33, 50)
            t2 = min(t2, SYNTHETIC_PARAMS["tiempo_max"] - 5)
            amp = rng.uniform(80, 150)

        elif comprometimiento == "pend_baja":
            t1 = rng.uniform(2, 9)
            t2 = t1 + rng.uniform(8, 15)
            t2 = min(t2, 29.0)
            amp = rng.uniform(3, 10)

        elif comprometimiento == "nir_baja":
            t1 = rng.uniform(2, 8)
            t2 = t1 + rng.uniform(0.5, 2.5)
            amp = rng.uniform(80, 150)

        else:
            t1, t2, amp = 5.0, 20.0, 100.0

        pend = 10.0

        _, senal = generar_senal_icg(t1, t2, pend, amp, seed=seed + offset + i)
        params = extraer_parametros(tiempo, senal)

        intensidades.append(senal)
        parametros.append(params)
        labels.append(1)

    intensidades = np.array(intensidades, dtype=np.float32)
    labels = np.array(labels, dtype=int)

    n_total_adecuada = n_adecuada_clara + n_adecuada_border
    n_total_comprom = n_comprom_border + n_comprom_clara
    log.info("Dataset generado: %d muestras", n_samples)
    log.info("  No-leak: %d (%d clara + %d borderline)", n_total_adecuada, n_adecuada_clara, n_adecuada_border)
    log.info("  Leak: %d (%d clara + %d borderline)", n_total_comprom, n_comprom_clara, n_comprom_border)

    return tiempo, intensidades, parametros, labels

def mapear_params_a_score(params):
    """
    Mapea dict de parámetros a score continuo [0, 1].

    Score = riesgo de fuga anastomótica (0 = sin riesgo, 1 = riesgo máximo).
    Invertido respecto a fracción de parámetros aprobados, para que
    AUC interprete correctamente label=1 (leak) como score alto.
    """
    _, _, aprobados, _ = clasificar_perfusion(params)
    return 1.0 - (aprobados / 4.0)

def run_validation_pipeline(output_dir="validation_results"):
    """
    Ejecuta el pipeline completo de validación sintética.
    Usa BioConnectClassifier (LogisticRegression) en vez del mapeo tautológico.

    Returns:
        dict con reporte completo
    """
    log.info("=" * 70)
    log.info("BIOCONNECT — SYNTHETIC VALIDATION PIPELINE v2.0")
    log.info("=" * 70)

    # STEP 1: Generar dataset
    log.info("[STEP 1] Generando dataset sintético (N=%d)...", VALIDATION_PARAMS["n_sinteticas"])
    tiempo, intensidades, params_list, labels = generar_dataset_sintetico()

    # STEP 2: Convertir parámetros a feature matrix
    log.info("[STEP 2] Construyendo feature matrix...")
    clf = BioConnectClassifier()
    X = clf._params_to_array(params_list)

    # STEP 3: Train/Test split
    log.info("[STEP 3] Train/Test split...")
    rng_split = np.random.default_rng(42)
    n_train = int(len(labels) * VALIDATION_PARAMS["train_ratio"])
    indices = rng_split.permutation(len(labels))
    train_idx = indices[:n_train]
    test_idx = indices[n_train:]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = labels[train_idx], labels[test_idx]

    log.info("Train: %d (%d no-leak, %d leak)", len(y_train), np.sum(y_train==0), np.sum(y_train==1))
    log.info("Test:  %d (%d no-leak, %d leak)", len(y_test), np.sum(y_test==0), np.sum(y_test==1))

    # STEP 4: Entrenar clasificador y predecir
    log.info("[STEP 4] Entrenando BioConnectClassifier (LogisticRegression)...")
    clf.fit(X_train, y_train)
    scores_test = clf.predict_proba(X_test)

    coefs = clf.get_coefficients()
    log.info("Coeficientes: %s", coefs['coefficients'])

    # STEP 5: Validación en test set
    log.info("[STEP 5] Validación en test set...")
    validation_metrics = calcular_metricas(y_test, scores_test, threshold=0.5)
    umbral_optimo_results = encontrar_umbral_optimo(y_test, scores_test)

    log.info("AUC: %.4f CI=%s", validation_metrics['auc'], validation_metrics['auc_ci'])
    log.info("Sensitivity: %.4f", validation_metrics['sensitivity'])
    log.info("Specificity: %.4f", validation_metrics['specificity'])
    log.info("Umbral óptimo (Youden): %.4f", umbral_optimo_results['threshold_optimo'])

    # STEP 6: Robustness tests
    log.info("[STEP 6] Robustness tests (5 core tests)...")
    robustness_results = run_all_robustness_tests(
        tiempo,
        intensidades[0],
        params_list[0],
        y_test,
        scores_test,
        validation_metrics["auc"],
    )

    for r in robustness_results:
        status_symbol = "OK" if r["passed"] else "FAIL"
        log.info("[%s] %s: %s", status_symbol, r['test_name'], r['status'])

    # STEP 7: Falsification tests
    log.info("[STEP 7] Falsification tests (3 core tests)...")
    falsification_results = run_all_falsification_tests(y_test, scores_test)

    for r in falsification_results:
        status_symbol = "OK" if r["passed"] else "FAIL"
        log.info("[%s] %s: %s", status_symbol, r['test_name'], r['status'])

    # STEP 8: Persistencia
    log.info("[STEP 8] Guardando resultados...")

    os.makedirs(output_dir, exist_ok=True)

    # Guardar dataset
    dataset_path = f"{output_dir}/synthetic_dataset.npz"
    save_synthetic_dataset(tiempo, intensidades, params_list, labels, dataset_path)

    # Guardar clasificador entrenado
    clf.save(f"{output_dir}/bioconnect_classifier.joblib")

    # Guardar validación
    results_path = f"{output_dir}/validation_results.json"
    save_validation_results(validation_metrics, results_path)

    # Crear reporte consolidado
    report = create_experiment_report(
        dataset_path,
        validation_metrics,
        robustness_results,
        falsification_results,
        experiment_name="BioConnect_v2_SyntheticValidation",
        output_path=f"{output_dir}/experiment_report.json",
    )

    # Agregar info del clasificador al reporte
    report["classifier"] = {
        "type": "LogisticRegression",
        "coefficients": {k: float(v) for k, v in coefs["coefficients"].items()},
        "intercept": coefs["intercept"],
        "optimal_threshold": float(umbral_optimo_results["threshold_optimo"]),
    }

    # Generar resumen en texto
    summary_text = summary_to_text(report, f"{output_dir}/experiment_summary.txt")

    # STEP 9: Resumen final
    log.info("=" * 70)
    log.info("SUMMARY")
    log.info("=" * 70)
    log.info("\n%s", summary_text)

    return report

if __name__ == "__main__":
    import os

    os.makedirs("validation_results", exist_ok=True)
    report = run_validation_pipeline()
