# ============================================================
#  BIOCONNECT — Configuración Central de Umbrales
#  Bioconnect | Universidad de Guadalajara
# ============================================================
#
# Fuente: Son et al. (2023) — Quantitative ICG fluorescence
# for anastomotic perfusion assessment
#
# IMPORTANTE: Umbrales canonicos — todos los modulos deben
# importar desde aqui para evitar inconsistencias.
# ============================================================

# Umbrales canonicos (Son et al., 2023)
UMBRALES_CANONICOS = {
    "T1":         {"valor": 10.0, "operador": "<=", "unidad": "s",    "descripcion": "Llegada del bolo (10% pico)"},
    "T2":         {"valor": 30.0, "operador": "<=", "unidad": "s",    "descripcion": "Tiempo al pico"},
    "pendiente":  {"valor": 5.0,  "operador": ">=", "unidad": "u/s",  "descripcion": "Pendiente de subida"},
    "indice_NIR": {"valor": 50.0, "operador": ">=", "unidad": "a.u.", "descripcion": "Indice de intensidad relativa"},
}

# Umbrales para parámetros adicionales (informativos, no afectan clasificación primaria)
UMBRALES_ADICIONALES = {
    "Fmax":        {"valor": 30.0,  "operador": ">=", "unidad": "a.u.",  "descripcion": "Fluorescencia maxima normalizada"},
    "T_half":      {"valor": 15.0,  "operador": "<=", "unidad": "s",     "descripcion": "Tiempo de semi-descenso"},
    "slope_ratio": {"valor": 0.5,   "operador": ">=", "unidad": "ratio", "descripcion": "Ratio pendiente subida/bajada"},
}

# Parametros de extraccion de curva
EXTRACTION_PARAMS = {
    "t1_threshold_percent": 0.10,       # T1 = momento en que intensidad >= 10% del pico
    "savgol_window": 21,                # Ventana Savitzky-Golay (debe ser impar)
    "savgol_polyorder": 3,              # Orden polinomial S-G
}

# Parametros de generacion sintetica
SYNTHETIC_PARAMS = {
    "tiempo_max": 60.0,                 # Duracion maxima de la curva (s)
    "tiempo_puntos": 600,               # Numero de puntos de muestreo
    "ruido_default": 0.15,              # Std dev ruido gaussiano (realista para camaras NIR)
    "seed_default": 42,                 # Semilla aleatoria por defecto
}

# Parametros de validacion
VALIDATION_PARAMS = {
    "n_sinteticas": 500,                # N total de curvas sinteticas
    "train_ratio": 0.80,                # 400 train, 100 test
    "test_ratio": 0.20,
    "auc_threshold": 0.80,              # Criterio de exito: AUC >= 0.80
    "sensitivity_threshold": 0.80,      # Criterio de exito: sens >= 0.80
    "specificity_threshold": 0.70,      # Criterio de exito: spec >= 0.70
    "cv_folds": 5,                      # K-fold cross-validation
}

def get_umbral(param_nombre: str) -> float:
    """Retorna umbral canonico para un parametro."""
    if param_nombre not in UMBRALES_CANONICOS:
        raise ValueError(f"Parametro desconocido: {param_nombre}")
    return UMBRALES_CANONICOS[param_nombre]["valor"]

def get_umbral_dict() -> dict[str, float]:
    """Retorna dict de umbrales para clasificacion."""
    return {k: v["valor"] for k, v in UMBRALES_CANONICOS.items()}

def calcular_score_riesgo(params: dict[str, float]) -> float:
    """
    Score de riesgo anastomotico (0=alto riesgo, 100=bajo riesgo).
    Basado en Son et al. (2023).

    Pesos: T1=0.25, T2=0.30, pendiente=0.20, indice_NIR=0.10
    Adicionales (si disponibles): Fmax=0.05, T_half=0.05, slope_ratio=0.05
    """
    score_t1  = max(0, min(1, (20 - params["T1"])  / 20))
    score_t2  = max(0, min(1, (60 - params["T2"])  / 60))
    score_pen = max(0, min(1,  params["pendiente"] / 20))
    score_nir = max(0, min(1, params["indice_NIR"] / 80))

    # Pesos base (suman 0.85 si hay adicionales, 1.0 si no)
    has_extras = all(
        params.get(k) is not None
        for k in ["Fmax", "T_half", "slope_ratio"]
    )

    if has_extras:
        score_fmax  = max(0, min(1, params["Fmax"] / 100))
        score_thalf = max(0, min(1, (30 - params["T_half"]) / 30)) if params["T_half"] is not None else 0.5
        score_slope = max(0, min(1, params["slope_ratio"] / 2.0)) if params["slope_ratio"] is not None else 0.5

        score = (score_t1*0.25 + score_t2*0.30 + score_pen*0.20 + score_nir*0.10
                 + score_fmax*0.05 + score_thalf*0.05 + score_slope*0.05) * 100
    else:
        score = (score_t1*0.30 + score_t2*0.35 + score_pen*0.20 + score_nir*0.15) * 100

    return round(score, 1)

def clasificar_parametro(nombre: str, valor: float) -> bool:
    """
    Clasifica un parametro individual contra su umbral.

    Args:
        nombre: str — nombre del parametro (T1, T2, pendiente, indice_NIR)
        valor: float — valor medido

    Returns:
        bool — True si cumple el criterio, False en caso contrario
    """
    if nombre not in UMBRALES_CANONICOS:
        raise ValueError(f"Parametro desconocido: {nombre}")

    u = UMBRALES_CANONICOS[nombre]
    if u["operador"] == "<=":
        return valor <= u["valor"]
    elif u["operador"] == ">=":
        return valor >= u["valor"]
    else:
        raise ValueError(f"Operador desconocido: {u['operador']}")

def clasificar_perfusion(params: dict[str, float]) -> tuple[str, str, int, dict[str, bool]]:
    """
    Clasifica el estado de perfusion basado en 4 parametros.

    Logica:
    - 4/4 parametros pasan → ADECUADA (verde)
    - 3/4 parametros pasan → BORDERLINE (amarillo)
    - <3/4 parametros pasan → COMPROMETIDA (rojo)

    Args:
        params: dict con claves {T1, T2, pendiente, indice_NIR}

    Returns:
        tuple: (veredicto, color_hex, n_aprobados, dict_detalle)
    """
    detalle = {}
    aprobados = 0

    for nombre in ["T1", "T2", "pendiente", "indice_NIR"]:
        ok = clasificar_parametro(nombre, params[nombre])
        detalle[nombre] = ok
        if ok:
            aprobados += 1

    if aprobados == 4:
        return "ADECUADA", "#2ecc71", aprobados, detalle
    elif aprobados == 3:
        return "BORDERLINE", "#f39c12", aprobados, detalle
    else:
        return "COMPROMETIDA", "#e74c3c", aprobados, detalle

# ============================================================
#  Preferencias de localización e interfaz
# ============================================================

# Idioma de la interfaz (código corto)
IDIOMA_DEFAULT     = "es"
IDIOMAS_SOPORTADOS = ["es", "en", "fr", "de", "it", "pt", "ja", "zh"]

# Tipografía accesible
TIPOGRAFIA_DEFAULT     = "normal"      # "normal" | "OpenDyslexic"
TIPOGRAFIAS_SOPORTADAS = ["normal", "OpenDyslexic"]

# Rutas de recursos (relativas a la raíz de la app)
RUTA_I18N  = "i18n"
RUTA_FONTS = "fonts"

# Metadata de documentacion
REFERENCES = {
    "umbral_T1": "Son et al. (2023) — timing of ICG arrival as perfusion proxy",
    "umbral_T2": "Son et al. (2023) — peak timing inversely correlated with leak risk",
    "umbral_pendiente": "Empirically selected; represents slope of rise phase",
    "umbral_indice_NIR": "Area-under-curve integral; fluorescence total burden",
}
