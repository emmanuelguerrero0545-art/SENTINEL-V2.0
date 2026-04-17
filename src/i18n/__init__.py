# ============================================================
#  BIOCONNECT — Sistema de Internacionalización (i18n)
# Universidad de Guadalajara
# ============================================================
#
#  Uso:
#    from i18n import t, cargar_idioma
#    t("menu.inicio")         → "Inicio"
#    t("modulos.simulador")   → "Simulador ICG"
#
#  El idioma se lee automáticamente desde BioConnectPrefs.
#  Si el JSON del idioma no existe, carga es.json (fallback).
# ============================================================

import json
import os
from pathlib import Path

# --- Estado interno ---
_TRANSLATIONS: dict = {}
_CURRENT_LANG: str  = "es"

# Directorio donde viven los archivos JSON
_I18N_DIR = Path(__file__).parent


def cargar_idioma(codigo_idioma: str = "es") -> dict:
    """Carga diccionario de idioma desde JSON.

    Si el archivo no existe, hace fallback a es.json.

    Args:
        codigo_idioma: Código corto del idioma ("es", "en", "fr", "pt", "de", "it", "zh", "ja").

    Returns:
        Diccionario con todas las cadenas traducidas.
    """
    global _TRANSLATIONS, _CURRENT_LANG

    ruta_json = _I18N_DIR / f"{codigo_idioma}.json"

    if not ruta_json.exists():
        # Fallback a español si idioma no existe
        ruta_json = _I18N_DIR / "es.json"
        codigo_idioma = "es"

    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            _TRANSLATIONS = json.load(f)
        _CURRENT_LANG = codigo_idioma
    except (json.JSONDecodeError, OSError):
        # Si incluso es.json falla, usar diccionario vacío
        _TRANSLATIONS = {}
        _CURRENT_LANG = "es"

    return _TRANSLATIONS


def idioma_actual() -> str:
    """Retorna el código del idioma actualmente cargado."""
    return _CURRENT_LANG


def obtener_cadena(clave: str, default: str = "") -> str:
    """Obtiene cadena traducida por clave en notación de punto.

    Ejemplo:
        obtener_cadena("menu.inicio")       → "Inicio"
        obtener_cadena("analisis.ejecutar") → "Ejecutar análisis"
        obtener_cadena("clave.inexistente") → ""  (o default)

    Args:
        clave:   Ruta de punto separado dentro del JSON. Ej: "menu.inicio"
        default: Valor retornado si la clave no existe.

    Returns:
        Cadena traducida, o `default` si no se encuentra.
    """
    if not _TRANSLATIONS:
        return default or clave  # Sin traducciones cargadas, devolver la clave

    partes = clave.split(".")
    valor  = _TRANSLATIONS

    for parte in partes:
        if isinstance(valor, dict):
            valor = valor.get(parte, None)
            if valor is None:
                return default or clave
        else:
            return default or clave

    return valor if isinstance(valor, str) else (default or clave)


def obtener_lista(clave: str) -> list:
    """Obtiene un valor de tipo lista desde el JSON de traducciones.

    Ejemplo:
        obtener_lista("calibracion.pasos") → ["Paso 1...", "Paso 2...", ...]

    Args:
        clave: Ruta de punto separado dentro del JSON. Ej: "calibracion.pasos"

    Returns:
        Lista de strings, o lista vacía si la clave no existe o no es lista.
    """
    if not _TRANSLATIONS:
        return []

    partes = clave.split(".")
    valor  = _TRANSLATIONS

    for parte in partes:
        if isinstance(valor, dict):
            valor = valor.get(parte, None)
            if valor is None:
                return []
        else:
            return []

    return valor if isinstance(valor, list) else []


# Alias corto — uso principal en la UI
t      = obtener_cadena
t_list = obtener_lista


def init_desde_prefs(prefs=None) -> str:
    """Inicializa el sistema i18n leyendo el idioma desde BioConnectPrefs.

    Si `prefs` es None, intenta leer directamente ~/.bioconnect_prefs.json.

    Args:
        prefs: Instancia de BioConnectPrefs, o None para leer directo del JSON.

    Returns:
        Código del idioma que se cargó.
    """
    codigo = "es"  # Default

    if prefs is not None:
        codigo = prefs.get("language", "es")
    else:
        # Leer directo del archivo de prefs
        prefs_path = Path.home() / ".bioconnect_prefs.json"
        if prefs_path.exists():
            try:
                with open(prefs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                codigo = data.get("language", "es")
            except (json.JSONDecodeError, OSError):
                pass

    # Normalizar: "Español (MX)" → "es", "English" → "en", etc.
    _MAPA_DISPLAY = {
        "Español (MX)":       "es",
        "English":            "en",
        "Português (BR)":     "pt",
        "Français":           "fr",
        "Deutsch":            "de",
        "Italiano":           "it",
        "中文 (简体)":         "zh",
        "日本語":              "ja",
        "es": "es", "en": "en", "fr": "fr", "pt": "pt",
        "de": "de", "it": "it", "zh": "zh", "ja": "ja",
    }
    codigo = _MAPA_DISPLAY.get(codigo, "es")

    cargar_idioma(codigo)
    return codigo
