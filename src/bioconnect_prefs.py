# ============================================================
#  BIOCONNECT — Persistencia de Preferencias de Usuario
# Universidad de Guadalajara
# ============================================================
#
#  Guarda preferencias entre sesiones en:
#    ~/.bioconnect_prefs.json
#
#  Diseño defensivo: JSON corrupto, archivo ausente o
#  directorio inexistente nunca elevan excepcion al caller.
# ============================================================

import json
import os
from pathlib import Path

_PREFS_FILE = Path.home() / ".bioconnect_prefs.json"

_DEFAULTS = {
    "pdf_directory": "",   # Ultima carpeta usada para guardar PDFs
    "language": "es",      # Idioma de la interfaz
    "theme": "dark",       # Tema visual
}


class BioConnectPrefs:
    """Gestiona las preferencias persistentes de la aplicacion BioConnect."""

    def __init__(self, filepath: Path = _PREFS_FILE):
        self._path = filepath
        self._data: dict = {}
        self._load()

    # ----------------------------------------------------------
    # API publica — propiedades especializadas
    # ----------------------------------------------------------

    @property
    def pdf_directory(self) -> str:
        """Ultima carpeta seleccionada para guardar reportes PDF."""
        valor = self._data.get("pdf_directory", "")
        # Devolver solo si la carpeta todavia existe en disco
        if valor and os.path.isdir(valor):
            return valor
        return ""

    @pdf_directory.setter
    def pdf_directory(self, path: str) -> None:
        self._data["pdf_directory"] = str(path)
        self._save()

    @property
    def language(self) -> str:
        return self._data.get("language", _DEFAULTS["language"])

    @language.setter
    def language(self, lang: str) -> None:
        self._data["language"] = lang
        self._save()

    @property
    def theme(self) -> str:
        return self._data.get("theme", _DEFAULTS["theme"])

    @theme.setter
    def theme(self, theme: str) -> None:
        self._data["theme"] = theme
        self._save()

    # ----------------------------------------------------------
    # API generica
    # ----------------------------------------------------------

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._save()

    def reset(self) -> None:
        """Restablece todas las preferencias a valores por defecto."""
        self._data = dict(_DEFAULTS)
        self._save()

    # ----------------------------------------------------------
    # Persistencia interna
    # ----------------------------------------------------------

    def _load(self) -> None:
        """Carga desde disco. En caso de error usa valores por defecto."""
        self._data = dict(_DEFAULTS)
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self._data.update(loaded)
        except (json.JSONDecodeError, OSError, ValueError):
            # JSON corrupto o sin permisos — continuar con defaults
            self._data = dict(_DEFAULTS)

    def _save(self) -> None:
        """Persiste a disco. Error silencioso si no hay permisos."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass  # Sin permisos de escritura — no critico
