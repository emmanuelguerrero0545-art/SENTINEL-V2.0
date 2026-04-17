"""Tests para config.py — umbrales y funciones de configuración."""

import sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    UMBRALES_CANONICOS,
    UMBRALES_ADICIONALES,
    EXTRACTION_PARAMS,
    SYNTHETIC_PARAMS,
    VALIDATION_PARAMS,
    get_umbral,
    get_umbral_dict,
    calcular_score_riesgo,
)


class TestUmbralesDefinidos:
    """Verifica que todos los umbrales estén correctamente definidos."""

    def test_4_umbrales_canonicos(self):
        expected = {"T1", "T2", "pendiente", "indice_NIR"}
        assert set(UMBRALES_CANONICOS.keys()) == expected

    def test_3_umbrales_adicionales(self):
        expected = {"Fmax", "T_half", "slope_ratio"}
        assert set(UMBRALES_ADICIONALES.keys()) == expected

    def test_cada_umbral_tiene_valor_operador_unidad(self):
        for nombre, u in UMBRALES_CANONICOS.items():
            assert "valor" in u, f"{nombre} sin valor"
            assert "operador" in u, f"{nombre} sin operador"
            assert "unidad" in u, f"{nombre} sin unidad"
            assert u["operador"] in ("<=", ">="), f"{nombre} operador inválido"

    def test_umbrales_adicionales_estructura(self):
        for nombre, u in UMBRALES_ADICIONALES.items():
            assert "valor" in u, f"{nombre} sin valor"
            assert "operador" in u, f"{nombre} sin operador"

    def test_valores_canonicos_positivos(self):
        for nombre, u in UMBRALES_CANONICOS.items():
            assert u["valor"] > 0, f"{nombre} valor no positivo"


class TestGetUmbral:
    """Tests para get_umbral()."""

    def test_t1(self):
        assert get_umbral("T1") == 10.0

    def test_t2(self):
        assert get_umbral("T2") == 30.0

    def test_pendiente(self):
        assert get_umbral("pendiente") == 5.0

    def test_indice_nir(self):
        assert get_umbral("indice_NIR") == 50.0

    def test_desconocido_raises(self):
        with pytest.raises(ValueError):
            get_umbral("inventado")

    def test_get_umbral_dict_keys(self):
        d = get_umbral_dict()
        assert set(d.keys()) == {"T1", "T2", "pendiente", "indice_NIR"}


class TestCalcularScoreRiesgo:
    """Tests para calcular_score_riesgo."""

    def test_perfusion_adecuada_score_alto(self):
        params = {"T1": 3.0, "T2": 15.0, "pendiente": 15.0, "indice_NIR": 75.0}
        score = calcular_score_riesgo(params)
        assert score >= 70

    def test_perfusion_comprometida_score_bajo(self):
        params = {"T1": 18.0, "T2": 55.0, "pendiente": 1.0, "indice_NIR": 10.0}
        score = calcular_score_riesgo(params)
        assert score <= 30

    def test_score_rango_0_100(self):
        params = {"T1": 5.0, "T2": 20.0, "pendiente": 10.0, "indice_NIR": 70.0}
        score = calcular_score_riesgo(params)
        assert 0 <= score <= 100

    def test_score_con_extras(self):
        params = {
            "T1": 5.0, "T2": 20.0, "pendiente": 10.0, "indice_NIR": 70.0,
            "Fmax": 80.0, "T_half": 8.0, "slope_ratio": 1.2,
        }
        score = calcular_score_riesgo(params)
        assert 0 <= score <= 100

    def test_score_sin_extras_vs_con_extras(self):
        base = {"T1": 5.0, "T2": 20.0, "pendiente": 10.0, "indice_NIR": 70.0}
        con_extras = {
            **base, "Fmax": 80.0, "T_half": 8.0, "slope_ratio": 1.2,
        }
        s1 = calcular_score_riesgo(base)
        s2 = calcular_score_riesgo(con_extras)
        # Ambos deben ser válidos; no necesariamente iguales
        assert 0 <= s1 <= 100
        assert 0 <= s2 <= 100


class TestExtractionParams:
    """Verifica parámetros de extracción."""

    def test_savgol_window_impar(self):
        assert EXTRACTION_PARAMS["savgol_window"] % 2 == 1

    def test_savgol_polyorder_menor_que_window(self):
        assert EXTRACTION_PARAMS["savgol_polyorder"] < EXTRACTION_PARAMS["savgol_window"]

    def test_t1_threshold_entre_0_1(self):
        assert 0 < EXTRACTION_PARAMS["t1_threshold_percent"] < 1


class TestValidationParams:
    """Verifica parámetros de validación."""

    def test_ratios_suman_1(self):
        total = VALIDATION_PARAMS["train_ratio"] + VALIDATION_PARAMS["test_ratio"]
        assert abs(total - 1.0) < 1e-9

    def test_n_sinteticas_suficiente(self):
        assert VALIDATION_PARAMS["n_sinteticas"] >= 100

    def test_auc_threshold_razonable(self):
        assert 0.5 < VALIDATION_PARAMS["auc_threshold"] < 1.0
