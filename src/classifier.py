# ============================================================
#  BIOCONNECT — Clasificador de Perfusión ICG
# Universidad de Guadalajara
# ============================================================
#
# Clasificador basado en Logistic Regression para predecir
# riesgo de fuga anastomótica a partir de 4 parámetros ICG.
# Reemplaza el mapeo tautológico (conteo de parámetros).
# ============================================================

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from typing import Optional
import joblib
import os

from logger import get_logger

log = get_logger("classifier")


class BioConnectClassifier:
    """
    Clasificador de perfusión ICG basado en Logistic Regression.

    Usa los 4 parámetros extraídos (T1, T2, pendiente, indice_NIR)
    para predecir probabilidad de fuga anastomótica (leak).

    Attributes:
        model: LogisticRegression — clasificador entrenado
        scaler: StandardScaler — normalizador de features
        is_fitted: bool — indica si el modelo está entrenado
        feature_names: list — nombres de los parámetros
    """

    FEATURE_NAMES = ["T1", "T2", "pendiente", "indice_NIR"]

    def __init__(self, C: float = 1.0, max_iter: int = 1000):
        """
        Args:
            C: float — parámetro de regularización inversa
            max_iter: int — iteraciones máximas para convergencia
        """
        self.model = LogisticRegression(
            C=C,
            max_iter=max_iter,
            solver="lbfgs",
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_names = self.FEATURE_NAMES

    def _params_to_array(self, params_list: list) -> np.ndarray:
        """
        Convierte lista de dicts de parámetros a array numpy.

        Args:
            params_list: list of dicts con claves {T1, T2, pendiente, indice_NIR}

        Returns:
            np.ndarray de shape (N, 4)
        """
        X = np.array([
            [p["T1"], p["T2"], p["pendiente"], p["indice_NIR"]]
            for p in params_list
        ], dtype=np.float64)
        return X

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "BioConnectClassifier":
        """
        Entrena el clasificador.

        Args:
            X_train: np.ndarray (N, 4) — features
            y_train: np.ndarray (N,) — labels (0=no leak, 1=leak)

        Returns:
            self
        """
        X_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_scaled, y_train)
        self.is_fitted = True
        return self

    def fit_from_params(self, params_list: list, y_train: np.ndarray) -> "BioConnectClassifier":
        """
        Entrena desde lista de dicts de parámetros.

        Args:
            params_list: list of dicts
            y_train: np.ndarray (N,)

        Returns:
            self
        """
        X = self._params_to_array(params_list)
        return self.fit(X, y_train)

    def predict_proba(self, X_test: np.ndarray) -> np.ndarray:
        """
        Predice probabilidades de leak.

        Args:
            X_test: np.ndarray (N, 4) — features

        Returns:
            np.ndarray (N,) — probabilidades de clase 1 (leak)
        """
        if not self.is_fitted:
            raise RuntimeError("El clasificador no ha sido entrenado. Ejecutar fit() primero.")
        X_scaled = self.scaler.transform(X_test)
        return self.model.predict_proba(X_scaled)[:, 1]

    def predict_proba_from_params(self, params_list: list) -> np.ndarray:
        """
        Predice probabilidades desde lista de dicts.

        Args:
            params_list: list of dicts

        Returns:
            np.ndarray (N,) — probabilidades de leak
        """
        X = self._params_to_array(params_list)
        return self.predict_proba(X)

    def predict(self, X_test: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """
        Clasificación binaria con umbral ajustable.

        Args:
            X_test: np.ndarray (N, 4) — features
            threshold: float — punto de corte

        Returns:
            np.ndarray (N,) — predicciones binarias (0 o 1)
        """
        proba = self.predict_proba(X_test)
        return (proba >= threshold).astype(int)

    def get_coefficients(self) -> dict:
        """
        Retorna coeficientes del modelo para interpretabilidad.

        Returns:
            dict con coeficientes e intercepto
        """
        if not self.is_fitted:
            raise RuntimeError("El clasificador no ha sido entrenado.")
        return {
            "coefficients": dict(zip(self.feature_names, self.model.coef_[0])),
            "intercept": float(self.model.intercept_[0]),
            "scaler_mean": dict(zip(self.feature_names, self.scaler.mean_)),
            "scaler_std": dict(zip(self.feature_names, self.scaler.scale_)),
        }

    def save(self, filepath: str = "bioconnect_classifier.joblib") -> None:
        """Guarda modelo entrenado a disco."""
        if not self.is_fitted:
            raise RuntimeError("El clasificador no ha sido entrenado.")
        joblib.dump({"model": self.model, "scaler": self.scaler}, filepath)
        log.info("Clasificador guardado: %s", filepath)

    def load(self, filepath: str = "bioconnect_classifier.joblib") -> "BioConnectClassifier":
        """Carga modelo desde disco."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Archivo no encontrado: {filepath}")
        data = joblib.load(filepath)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.is_fitted = True
        log.info("Clasificador cargado: %s", filepath)
        return self
