"""Fixtures compartidas para tests de BioConnect."""

import sys
import os
import pytest
import numpy as np

# Agregar directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def curva_adecuada():
    """Genera curva ICG sintética con perfusión adecuada."""
    from BCV1 import generar_senal_icg
    tiempo, senal = generar_senal_icg(t1_real=5, t2_real=20, pendiente_real=10, indice_real=100, seed=42)
    return tiempo, senal


@pytest.fixture
def curva_comprometida():
    """Genera curva ICG sintética con perfusión comprometida."""
    from BCV1 import generar_senal_icg
    tiempo, senal = generar_senal_icg(t1_real=15, t2_real=40, pendiente_real=1, indice_real=20, seed=99)
    return tiempo, senal


@pytest.fixture
def params_adecuada():
    """Parámetros de perfusión adecuada."""
    return {"T1": 5.0, "T2": 20.0, "pendiente": 8.0, "indice_NIR": 75.0}


@pytest.fixture
def params_comprometida():
    """Parámetros de perfusión comprometida."""
    return {"T1": 15.0, "T2": 40.0, "pendiente": 2.0, "indice_NIR": 30.0}
