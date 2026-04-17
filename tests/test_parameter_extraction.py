"""Tests para parameter_extraction.py"""

import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parameter_extraction import extraer_parametros, validar_parametros


class TestExtraerParametros:
    """Tests para la función extraer_parametros."""

    def test_retorna_7_parametros(self, curva_adecuada):
        tiempo, senal = curva_adecuada
        params = extraer_parametros(tiempo, senal)
        assert "T1" in params
        assert "T2" in params
        assert "pendiente" in params
        assert "indice_NIR" in params
        assert "Fmax" in params
        assert "T_half" in params
        assert "slope_ratio" in params

    def test_parametros_core_son_float(self, curva_adecuada):
        tiempo, senal = curva_adecuada
        params = extraer_parametros(tiempo, senal)
        for key in ["T1", "T2", "pendiente", "indice_NIR", "Fmax"]:
            assert isinstance(params[key], float), f"{key} no es float"

    def test_t1_menor_que_t2(self, curva_adecuada):
        tiempo, senal = curva_adecuada
        params = extraer_parametros(tiempo, senal)
        assert params["T1"] < params["T2"]

    def test_pendiente_positiva(self, curva_adecuada):
        tiempo, senal = curva_adecuada
        params = extraer_parametros(tiempo, senal)
        assert params["pendiente"] > 0

    def test_indice_nir_positivo(self, curva_adecuada):
        tiempo, senal = curva_adecuada
        params = extraer_parametros(tiempo, senal)
        assert params["indice_NIR"] > 0

    def test_fmax_positivo(self, curva_adecuada):
        tiempo, senal = curva_adecuada
        params = extraer_parametros(tiempo, senal)
        assert params["Fmax"] > 0

    def test_maneja_nan_input(self):
        tiempo = np.linspace(0, 60, 600)
        senal = np.full(600, np.nan)
        params = extraer_parametros(tiempo, senal)
        assert params is not None

    def test_maneja_ceros(self):
        tiempo = np.linspace(0, 60, 600)
        senal = np.zeros(600)
        params = extraer_parametros(tiempo, senal)
        assert params["pendiente"] == 0.0


class TestValidarParametros:
    """Tests para validar_parametros."""

    def test_valido_con_4_params(self, params_adecuada):
        assert validar_parametros(params_adecuada) is True

    def test_invalido_sin_T1(self):
        params = {"T2": 20.0, "pendiente": 8.0, "indice_NIR": 75.0}
        assert validar_parametros(params) is False

    def test_valido_con_params_adicionales(self):
        params = {
            "T1": 5.0, "T2": 20.0, "pendiente": 8.0, "indice_NIR": 75.0,
            "Fmax": 100.0, "T_half": 5.0, "slope_ratio": 1.0,
        }
        assert validar_parametros(params) is True

    def test_valido_con_none_adicionales(self):
        params = {
            "T1": 5.0, "T2": 20.0, "pendiente": 8.0, "indice_NIR": 75.0,
            "Fmax": 100.0, "T_half": None, "slope_ratio": None,
        }
        assert validar_parametros(params) is True
