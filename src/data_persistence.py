# ============================================================
#  BIOCONNECT — Persistencia de Datos
# Universidad de Guadalajara
# ============================================================

import json
import numpy as np
import os
from datetime import datetime

from logger import get_logger

log = get_logger("data_persistence")

def save_synthetic_dataset(tiempo, intensidades, parametros, labels, filepath="synthetic_dataset.npz"):
    """
    Guarda dataset sintético en formato NPZ.

    Args:
        tiempo: np.array — vector temporal común
        intensidades: np.array (N, M) — N curvas, M puntos cada una
        parametros: list of dicts — parámetros extraídos
        labels: np.array — etiquetas (0=no leak, 1=leak)
        filepath: str — ruta de salida
    """
    np.savez_compressed(
        filepath,
        tiempo=tiempo,
        intensidades=intensidades,
        labels=labels,
        n_samples=len(labels),
        timestamp=datetime.now().isoformat(),
    )

    # Guardar parámetros como JSON
    json_path = filepath.replace(".npz", "_params.json")
    with open(json_path, "w") as f:
        json.dump(
            {
                "parametros": parametros,
                "n_samples": len(parametros),
                "timestamp": datetime.now().isoformat(),
            },
            f,
            indent=2,
        )

    log.info("Dataset guardado: %s", filepath)
    log.info("Parámetros guardados: %s", json_path)

def load_synthetic_dataset(filepath="synthetic_dataset.npz"):
    """
    Carga dataset sintético desde NPZ.

    Returns:
        (tiempo, intensidades, labels)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    with np.load(filepath, allow_pickle=True) as data:
        tiempo = data["tiempo"]
        intensidades = data["intensidades"]
        labels = data["labels"]

    log.info("Dataset cargado: %s (%d muestras)", filepath, len(labels))
    return tiempo, intensidades, labels

def load_parameters(filepath_json):
    """
    Carga parámetros extraídos desde JSON.

    Returns:
        list of dicts
    """
    if not os.path.exists(filepath_json):
        raise FileNotFoundError(f"Archivo no encontrado: {filepath_json}")

    with open(filepath_json, "r") as f:
        data = json.load(f)

    return data["parametros"]

def save_validation_results(results_dict, filepath="validation_results.json"):
    """
    Guarda resultados de validación (métricas, robustness, falsification).

    Args:
        results_dict: dict — results from validation/robustness/falsification
        filepath: str — ruta de salida
    """
    # Convertir numpy types a native Python types
    results_serializable = _make_serializable(results_dict)

    with open(filepath, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "results": results_serializable,
            },
            f,
            indent=2,
        )

    log.info("Resultados guardados: %s", filepath)

def load_validation_results(filepath="validation_results.json"):
    """
    Carga resultados de validación desde JSON.

    Returns:
        dict con resultados
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    with open(filepath, "r") as f:
        data = json.load(f)

    return data["results"]

def _make_serializable(obj):
    """
    Convierte numpy types y otros objetos a tipos serializables JSON.
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, (float, int, str, bool, type(None))):
        return obj
    else:
        return str(obj)

def create_experiment_report(
    synthetic_dataset_path,
    validation_metrics,
    robustness_results,
    falsification_results,
    experiment_name="BioConnect_v1",
    output_path="experiment_report.json",
):
    """
    Crea un reporte consolidado de toda la validación.

    Args:
        synthetic_dataset_path: str
        validation_metrics: dict
        robustness_results: list of dicts
        falsification_results: list of dicts
        experiment_name: str
        output_path: str
    """
    report = {
        "experiment_name": experiment_name,
        "timestamp": datetime.now().isoformat(),
        "synthetic_dataset": synthetic_dataset_path,
        "validation_metrics": _make_serializable(validation_metrics),
        "robustness_tests": [_make_serializable(r) for r in robustness_results],
        "falsification_tests": [_make_serializable(r) for r in falsification_results],
        "summary": {
            "auc": validation_metrics.get("auc", np.nan),
            "sensitivity": validation_metrics.get("sensitivity", np.nan),
            "specificity": validation_metrics.get("specificity", np.nan),
            "robustness_all_pass": all(r.get("passed", False) for r in robustness_results),
            "falsification_all_pass": all(r.get("passed", False) for r in falsification_results),
        },
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    log.info("Reporte consolidado guardado: %s", output_path)

    return report

def summary_to_text(report, output_path="experiment_summary.txt"):
    """
    Convierte reporte JSON a texto legible para documentación.

    Args:
        report: dict — reporte consolidado
        output_path: str
    """
    lines = []
    lines.append("=" * 70)
    lines.append("BIOCONNECT VALIDATION EXPERIMENT SUMMARY")
    lines.append("=" * 70)
    lines.append(f"\nExperiment: {report['experiment_name']}")
    lines.append(f"Date: {report['timestamp']}\n")

    lines.append("--- VALIDATION METRICS ---")
    metrics = report.get("validation_metrics", {})
    lines.append(f"AUC: {metrics.get('auc', 'N/A'):.4f}" if isinstance(metrics.get('auc'), float) else f"AUC: {metrics.get('auc', 'N/A')}")
    lines.append(f"Sensitivity: {metrics.get('sensitivity', 'N/A'):.4f}" if isinstance(metrics.get('sensitivity'), float) else f"Sensitivity: {metrics.get('sensitivity', 'N/A')}")
    lines.append(f"Specificity: {metrics.get('specificity', 'N/A'):.4f}" if isinstance(metrics.get('specificity'), float) else f"Specificity: {metrics.get('specificity', 'N/A')}")

    lines.append("\n--- ROBUSTNESS TESTS (5 Core Tests) ---")
    for i, test in enumerate(report.get("robustness_tests", []), 1):
        lines.append(f"{i}. {test.get('test_name', 'Unknown')}")
        lines.append(f"   Status: {test.get('status', 'UNKNOWN')}")
        lines.append(f"   Reason: {test.get('reason', 'N/A')}")

    lines.append("\n--- FALSIFICATION TESTS (3 Core Tests) ---")
    for i, test in enumerate(report.get("falsification_tests", []), 1):
        lines.append(f"{i}. {test.get('test_name', 'Unknown')}")
        lines.append(f"   Status: {test.get('status', 'UNKNOWN')}")
        lines.append(f"   Reason: {test.get('reason', 'N/A')}")

    lines.append("\n--- OVERALL SUMMARY ---")
    summary = report.get("summary", {})
    lines.append(f"Robustness Tests Pass: {'YES' if summary.get('robustness_all_pass') else 'NO'}")
    lines.append(f"Falsification Tests Pass: {'YES' if summary.get('falsification_all_pass') else 'NO'}")

    lines.append("\n" + "=" * 70)

    text = "\n".join(lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    log.info("Resumen en texto guardado: %s", output_path)

    return text
