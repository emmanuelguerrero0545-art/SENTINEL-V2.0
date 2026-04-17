# ============================================================
#  BIOCONNECT — Extracción Centralizada de Parámetros ICG
# Universidad de Guadalajara
# ============================================================

import numpy as np
from scipy.signal import savgol_filter
from config import EXTRACTION_PARAMS, get_umbral

def extraer_parametros(tiempo: np.ndarray, intensidad: np.ndarray, smooth: bool = True) -> dict[str, float | None]:
    """
    Extrae 4 parámetros ICG de una curva de intensidad.

    Parámetros:
    - T1: Tiempo de llegada (10% del pico)
    - T2: Tiempo al pico (máximo)
    - pendiente: Máxima pendiente en la fase de subida (derivada)
    - indice_NIR: Integral normalizada (AUC / pico * 10)

    Args:
        tiempo: np.array — vector temporal (segundos)
        intensidad: np.array — vector de intensidad (a.u.)
        smooth: bool — si True, aplica Savitzky-Golay antes de extraer

    Returns:
        dict con claves {T1, T2, pendiente, indice_NIR}
    """
    intensidad = np.asarray(intensidad, dtype=np.float64)
    tiempo = np.asarray(tiempo, dtype=np.float64)

    # Validar que no haya NaN/Inf en los datos de entrada
    if np.isnan(intensidad).any() or np.isinf(intensidad).any():
        # Reemplazar NaN/Inf con ceros
        intensidad = np.nan_to_num(intensidad, nan=0.0, posinf=0.0, neginf=0.0)

    # Suavizado opcional
    if smooth and len(intensidad) > EXTRACTION_PARAMS["savgol_window"]:
        # Asegurar que la ventana es impar
        window = EXTRACTION_PARAMS["savgol_window"]
        if window % 2 == 0:
            window = window - 1
        if window < 3:
            window = 3

        intensidad = savgol_filter(
            intensidad,
            window_length=window,
            polyorder=EXTRACTION_PARAMS["savgol_polyorder"]
        )
        intensidad = np.clip(intensidad, 0, None)

    # T2: Tiempo al pico (máximo de intensidad)
    pico_idx = np.argmax(intensidad)
    pico_val = intensidad[pico_idx]
    t2 = tiempo[pico_idx]

    # T1: Llegada (10% del pico)
    umbral_t1 = EXTRACTION_PARAMS["t1_threshold_percent"] * pico_val
    idx_t1 = np.where(intensidad >= umbral_t1)[0]
    if len(idx_t1) > 0:
        t1 = tiempo[idx_t1[0]]
    else:
        t1 = np.nan

    # Pendiente: Máxima derivada en fase de subida (0 a pico)
    if pico_idx > 1:
        derivada = np.gradient(intensidad[:pico_idx], tiempo[:pico_idx])
        pendiente = np.max(derivada)
    else:
        pendiente = 0.0

    # Índice NIR: Integral normalizada
    if pico_val > 0:
        area = np.trapezoid(intensidad, tiempo)
        indice_nir = (area / pico_val) * 10
    else:
        indice_nir = 0.0

    # --- Parámetros adicionales (opcionales) ---

    # Fmax: Fluorescencia máxima normalizada (ya calculada como pico_val)
    fmax = float(pico_val)

    # T_half: Tiempo de semi-descenso post-pico
    t_half = np.nan
    if pico_idx < len(intensidad) - 1 and pico_val > 0:
        post_pico = intensidad[pico_idx:]
        half_val = 0.5 * pico_val
        idx_half = np.where(post_pico <= half_val)[0]
        if len(idx_half) > 0:
            t_half = tiempo[pico_idx + idx_half[0]] - t2

    # Slope ratio: pendiente de subida / pendiente de bajada
    slope_ratio = np.nan
    if pico_idx > 1 and pico_idx < len(intensidad) - 2:
        grad_bajada = np.gradient(intensidad[pico_idx:], tiempo[pico_idx:])
        pendiente_bajada = -np.min(grad_bajada) if len(grad_bajada) > 0 else 0.0
        if pendiente_bajada > 0:
            slope_ratio = float(pendiente) / pendiente_bajada

    return {
        "T1": round(float(t1), 2),
        "T2": round(float(t2), 2),
        "pendiente": round(float(pendiente), 3),
        "indice_NIR": round(float(indice_nir), 2),
        # Parámetros adicionales (informativos, no afectan clasificación primaria)
        "Fmax": round(fmax, 2),
        "T_half": round(float(t_half), 2) if not np.isnan(t_half) else None,
        "slope_ratio": round(float(slope_ratio), 3) if not np.isnan(slope_ratio) else None,
    }

def validar_parametros(params: dict) -> bool:
    """
    Valida que un dict de parámetros tenga todas las claves requeridas.

    Args:
        params: dict — debe contener {T1, T2, pendiente, indice_NIR}
               Parámetros adicionales (Fmax, T_half, slope_ratio) son opcionales
               y pueden ser None.

    Returns:
        bool — True si válido, False en caso contrario
    """
    requeridas = {"T1", "T2", "pendiente", "indice_NIR"}
    if not all(k in params for k in requeridas):
        return False
    # Solo validar tipos de los 4 parámetros requeridos
    return all(
        isinstance(params[k], (int, float)) for k in requeridas
    )
