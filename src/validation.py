# ============================================================
#  BIOCONNECT — Validación: Métricas, Train/Test, ROC
# Universidad de Guadalajara
# ============================================================

import numpy as np
from sklearn.metrics import (
    roc_auc_score, roc_curve, confusion_matrix
)
from scipy import stats
from config import VALIDATION_PARAMS, clasificar_perfusion

def calcular_metricas(y_true: np.ndarray, y_pred_score: np.ndarray, threshold: float = 0.5) -> dict:
    """
    Calcula AUC, sensitivity, specificity, confusion matrix.

    Args:
        y_true: np.array — etiquetas binarias (0=no leak, 1=leak)
        y_pred_score: np.array — scores continuos [0, 1]
        threshold: float — punto de corte para clasificación binaria

    Returns:
        dict con métricas y intervalos de confianza
    """
    y_pred_binary = (y_pred_score >= threshold).astype(int)

    # AUC
    if len(np.unique(y_true)) < 2:
        auc = np.nan
        fpr, tpr, thresholds = np.array([0, 1]), np.array([0, 1]), np.array([0, 1])
    else:
        auc = roc_auc_score(y_true, y_pred_score)
        fpr, tpr, thresholds = roc_curve(y_true, y_pred_score)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred_binary).ravel()

    # Sensitivity (Recall), Specificity
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else np.nan
    specificity = tn / (tn + fp) if (tn + fp) > 0 else np.nan
    ppv = tp / (tp + fp) if (tp + fp) > 0 else np.nan  # Precision
    npv = tn / (tn + fn) if (tn + fn) > 0 else np.nan

    # Intervalos de confianza (95%) usando método binomial exacto
    ci_sens = _wilson_ci(tp, tp + fn) if (tp + fn) > 0 else (np.nan, np.nan)
    ci_spec = _wilson_ci(tn, tn + fp) if (tn + fp) > 0 else (np.nan, np.nan)

    return {
        "auc": auc,
        "auc_ci": _bootstrap_ci(y_true, y_pred_score, roc_auc_score, n_iterations=1000),
        "sensitivity": sensitivity,
        "sensitivity_ci": ci_sens,
        "specificity": specificity,
        "specificity_ci": ci_spec,
        "ppv": ppv,
        "npv": npv,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "threshold": threshold,
    }

def _wilson_ci(successes, n, confidence=0.95):
    """
    Calcula intervalo de confianza exacto usando método de Wilson.
    Apropiado para proporciones con n pequeño.
    """
    if n == 0:
        return (np.nan, np.nan)

    p_hat = successes / n
    z = stats.norm.ppf((1 + confidence) / 2)
    denominator = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denominator
    adjustment = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denominator

    return (centre - adjustment, centre + adjustment)

def _bootstrap_ci(y_true, y_pred, metric_fn, n_iterations=1000, confidence=0.95):
    """
    Calcula intervalo de confianza bootstrap para una métrica.
    """
    bootstrap_scores = []
    n = len(y_true)
    rng = np.random.default_rng(42)

    for _ in range(n_iterations):
        indices = rng.choice(n, size=n, replace=True)
        y_true_boot = y_true[indices]
        y_pred_boot = y_pred[indices]

        if len(np.unique(y_true_boot)) < 2:
            continue  # Skip if bootstrap resample has only one class

        try:
            score = metric_fn(y_true_boot, y_pred_boot)
            bootstrap_scores.append(score)
        except Exception:
            continue

    if len(bootstrap_scores) == 0:
        return (np.nan, np.nan)

    alpha = 1 - confidence
    lower = np.percentile(bootstrap_scores, 100 * alpha / 2)
    upper = np.percentile(bootstrap_scores, 100 * (1 - alpha / 2))

    return (lower, upper)

def encontrar_umbral_optimo(y_true, y_pred_score):
    """
    Encuentra el umbral que maximiza Youden Index (sens + spec - 1).

    Args:
        y_true: np.array — etiquetas binarias
        y_pred_score: np.array — scores continuos

    Returns:
        dict con umbral óptimo y sus métricas asociadas
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_pred_score)
    youden = tpr - fpr
    optimal_idx = np.argmax(youden)
    optimal_threshold = thresholds[optimal_idx]

    metrics = calcular_metricas(y_true, y_pred_score, threshold=optimal_threshold)

    return {
        "threshold_optimo": optimal_threshold,
        "youden_index": youden[optimal_idx],
        **metrics
    }

def train_test_split(X, y, test_ratio=None, seed=42):
    """
    Divide datos en train/test respetando proporción.

    Args:
        X: np.array — features (N, P)
        y: np.array — labels (N,)
        test_ratio: float — fracción de test (default: VALIDATION_PARAMS["test_ratio"])
        seed: int — random seed

    Returns:
        X_train, X_test, y_train, y_test
    """
    if test_ratio is None:
        test_ratio = VALIDATION_PARAMS["test_ratio"]

    rng = np.random.default_rng(seed)
    n = len(y)
    indices = rng.permutation(n)

    split_idx = int(n * (1 - test_ratio))

    train_idx = indices[:split_idx]
    test_idx = indices[split_idx:]

    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]

def cross_validate(X, y, model_fn, k_folds=None):
    """
    K-fold cross-validation.

    Args:
        X: np.array — features
        y: np.array — labels
        model_fn: callable — función que entrena modelo y retorna predicciones
        k_folds: int — número de folds

    Returns:
        list de scores (uno por fold)
    """
    if k_folds is None:
        k_folds = VALIDATION_PARAMS["cv_folds"]

    n = len(X)
    fold_size = n // k_folds
    scores = []

    for fold in range(k_folds):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < k_folds - 1 else n

        test_idx = np.arange(test_start, test_end)
        train_idx = np.concatenate([np.arange(0, test_start), np.arange(test_end, n)])

        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        score = model_fn(X_train, X_test, y_train, y_test)
        scores.append(score)

    return scores
