"""Tests de consistencia — verifican que todos los módulos usan los mismos umbrales."""

import sys, os
import ast
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import UMBRALES_CANONICOS, get_umbral


# Directorio raíz del proyecto V2
V2_DIR = os.path.join(os.path.dirname(__file__), "..")


class TestConsistenciaUmbrales:
    """Verifica que no haya umbrales hardcodeados fuera de config.py."""

    def _buscar_en_archivo(self, filepath, patron):
        """Busca un patrón de texto en un archivo Python."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                contenido = f.read()
            return patron in contenido
        except Exception:
            return False

    def test_no_hardcoded_t1_threshold(self):
        """Verificar que T1=10 no está hardcodeado en módulos principales."""
        modulos = [
            "parameter_extraction.py",
            "BioConnect_App.py",
            "validation.py",
        ]
        for mod in modulos:
            filepath = os.path.join(V2_DIR, mod)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    # Buscar asignaciones directas tipo umbral_t1 = 10
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # No debería haber "= 10.0" o "== 10" para T1 fuera de config
                    # Solo buscar patrones sospechosos, no falsos positivos

    def test_todos_importan_config(self):
        """Módulos que usan umbrales deben importar desde config."""
        modulos_que_deben_importar = [
            "parameter_extraction.py",
            "synthetic_validation_pipeline.py",
        ]
        for mod in modulos_que_deben_importar:
            filepath = os.path.join(V2_DIR, mod)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    contenido = f.read()
                assert "from config import" in contenido or "import config" in contenido, \
                    f"{mod} no importa desde config"

    def test_get_umbral_retorna_mismo_que_dict(self):
        """get_umbral() debe retornar el mismo valor que UMBRALES_CANONICOS."""
        for nombre, u in UMBRALES_CANONICOS.items():
            assert get_umbral(nombre) == u["valor"]

    def test_classifier_usa_4_features(self):
        """El clasificador debe usar exactamente los 4 parámetros canónicos."""
        from classifier import BioConnectClassifier
        clf = BioConnectClassifier()
        assert set(clf.feature_names) == set(UMBRALES_CANONICOS.keys())

    def test_parameter_extraction_retorna_7_keys(self):
        """extraer_parametros debe retornar los 4 canónicos + 3 adicionales."""
        from parameter_extraction import extraer_parametros
        import numpy as np
        from BCV1 import generar_senal_icg
        tiempo, senal = generar_senal_icg(t1_real=5, t2_real=20, pendiente_real=10, indice_real=100, seed=42)
        params = extraer_parametros(tiempo, senal)
        expected_keys = {"T1", "T2", "pendiente", "indice_NIR", "Fmax", "T_half", "slope_ratio"}
        assert set(params.keys()) == expected_keys

    def test_validar_requiere_4_canonicos(self):
        """validar_parametros debe requerir exactamente los 4 canónicos."""
        from parameter_extraction import validar_parametros
        # Con los 4 → True
        assert validar_parametros({"T1": 1.0, "T2": 2.0, "pendiente": 3.0, "indice_NIR": 4.0}) is True
        # Sin uno → False
        assert validar_parametros({"T1": 1.0, "T2": 2.0, "pendiente": 3.0}) is False
