"""Tests para classifier.py y config.clasificar_perfusion."""

import numpy as np
import sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import BioConnectClassifier
from config import clasificar_perfusion, clasificar_parametro


class TestBioConnectClassifier:
    """Tests para BioConnectClassifier."""

    @pytest.fixture
    def trained_classifier(self):
        """Clasificador entrenado con datos sintéticos simples."""
        clf = BioConnectClassifier()
        # Adecuada: T1 bajo, T2 bajo, pendiente alta, indice alto
        # Comprometida: T1 alto, T2 alto, pendiente baja, indice bajo
        rng = np.random.default_rng(42)
        n = 100
        X_adeq = np.column_stack([
            rng.normal(5, 2, n),    # T1
            rng.normal(20, 5, n),   # T2
            rng.normal(10, 2, n),   # pendiente
            rng.normal(70, 10, n),  # indice_NIR
        ])
        X_comp = np.column_stack([
            rng.normal(15, 3, n),
            rng.normal(40, 5, n),
            rng.normal(2, 1, n),
            rng.normal(25, 8, n),
        ])
        X = np.vstack([X_adeq, X_comp])
        y = np.array([0] * n + [1] * n)
        clf.fit(X, y)
        return clf

    def test_not_fitted_raises(self):
        clf = BioConnectClassifier()
        with pytest.raises(RuntimeError):
            clf.predict_proba(np.zeros((1, 4)))

    def test_fit_sets_is_fitted(self):
        clf = BioConnectClassifier()
        X = np.random.default_rng(0).normal(size=(20, 4))
        y = np.array([0] * 10 + [1] * 10)
        clf.fit(X, y)
        assert clf.is_fitted is True

    def test_predict_proba_shape(self, trained_classifier):
        X = np.zeros((5, 4))
        proba = trained_classifier.predict_proba(X)
        assert proba.shape == (5,)

    def test_predict_proba_range(self, trained_classifier):
        X = np.random.default_rng(1).normal(size=(50, 4))
        proba = trained_classifier.predict_proba(X)
        assert np.all(proba >= 0) and np.all(proba <= 1)

    def test_predict_binary(self, trained_classifier):
        X = np.random.default_rng(2).normal(size=(10, 4))
        preds = trained_classifier.predict(X)
        assert set(preds).issubset({0, 1})

    def test_predict_from_params(self, trained_classifier):
        params_list = [
            {"T1": 5.0, "T2": 20.0, "pendiente": 10.0, "indice_NIR": 70.0},
            {"T1": 15.0, "T2": 40.0, "pendiente": 2.0, "indice_NIR": 25.0},
        ]
        proba = trained_classifier.predict_proba_from_params(params_list)
        assert proba.shape == (2,)
        # La muestra adecuada debería tener menor prob de leak
        assert proba[0] < proba[1]

    def test_get_coefficients(self, trained_classifier):
        coefs = trained_classifier.get_coefficients()
        assert "coefficients" in coefs
        assert "intercept" in coefs
        assert len(coefs["coefficients"]) == 4

    def test_save_load(self, trained_classifier, tmp_path):
        filepath = str(tmp_path / "test_model.joblib")
        trained_classifier.save(filepath)
        clf2 = BioConnectClassifier()
        clf2.load(filepath)
        assert clf2.is_fitted is True
        # Mismas predicciones
        X = np.zeros((3, 4))
        np.testing.assert_array_almost_equal(
            trained_classifier.predict_proba(X),
            clf2.predict_proba(X),
        )

    def test_load_nonexistent_raises(self):
        clf = BioConnectClassifier()
        with pytest.raises(FileNotFoundError):
            clf.load("/tmp/no_existe_xyz.joblib")


class TestClasificarPerfusion:
    """Tests para clasificar_perfusion de config.py."""

    def test_adecuada(self):
        params = {"T1": 5.0, "T2": 20.0, "pendiente": 10.0, "indice_NIR": 70.0}
        veredicto, color, n_ok, detalle = clasificar_perfusion(params)
        assert veredicto == "ADECUADA"
        assert n_ok == 4

    def test_comprometida(self):
        params = {"T1": 15.0, "T2": 40.0, "pendiente": 2.0, "indice_NIR": 30.0}
        veredicto, color, n_ok, detalle = clasificar_perfusion(params)
        assert veredicto == "COMPROMETIDA"
        assert n_ok < 3

    def test_borderline(self):
        # 3/4 pasan: T1 ok, T2 ok, pendiente ok, indice_NIR falla
        params = {"T1": 5.0, "T2": 20.0, "pendiente": 8.0, "indice_NIR": 30.0}
        veredicto, color, n_ok, detalle = clasificar_perfusion(params)
        assert veredicto == "BORDERLINE"
        assert n_ok == 3

    def test_detalle_keys(self):
        params = {"T1": 5.0, "T2": 20.0, "pendiente": 8.0, "indice_NIR": 70.0}
        _, _, _, detalle = clasificar_perfusion(params)
        assert set(detalle.keys()) == {"T1", "T2", "pendiente", "indice_NIR"}


class TestClasificarParametro:
    """Tests para clasificar_parametro."""

    def test_t1_ok(self):
        assert clasificar_parametro("T1", 5.0) is True

    def test_t1_fail(self):
        assert clasificar_parametro("T1", 15.0) is False

    def test_pendiente_ok(self):
        assert clasificar_parametro("pendiente", 8.0) is True

    def test_pendiente_fail(self):
        assert clasificar_parametro("pendiente", 2.0) is False

    def test_parametro_desconocido(self):
        with pytest.raises(ValueError):
            clasificar_parametro("inventado", 5.0)
