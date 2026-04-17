# ============================================================
#  BIOCONNECT — Gestor de Fuentes Accesibles (FontManager)
# Universidad de Guadalajara
# ============================================================
#
#  Gestiona la carga y aplicación de tipografías accesibles
#  (especialmente OpenDyslexic para usuarios con dislexia).
#
#  Flujo:
#    1. Busca archivos TTF/OTF en la carpeta fonts/
#    2. Si los encuentra, los instala en el directorio de fuentes
#       del sistema del usuario (~/.fonts en Linux,
#       ~/Library/Fonts en macOS)
#    3. Si no hay fuentes disponibles, usa fallback al sistema
#
#  Uso:
#    from font_manager import FontManager
#    fm = FontManager(base_dir=Path(__file__).parent)
#    fuente = fm.obtener_fuente("bold", 11)   # → ("OpenDyslexic", 11, "bold")
#    widget.config(font=fuente)
# ============================================================

import os
import sys
import shutil
import platform
from pathlib import Path

try:
    import tkinter.font as tkFont
    _TKINTER_DISPONIBLE = True
except ImportError:
    _TKINTER_DISPONIBLE = False


# Variantes de nombre que tkinter puede usar para OpenDyslexic
_NOMBRES_FAMILIA = [
    "OpenDyslexic",
    "OpenDyslexic3",
    "Open-Dyslexic",
]

# Fuentes de fallback amigables con dislexia (disponibles en el sistema)
_FALLBACK_DISLEXIA = ["Verdana", "Comic Sans MS", "Tahoma", "Arial"]

# Fuente por defecto de la app
_FUENTE_NORMAL = "Arial"


class FontManager:
    """Gestiona tipografías accesibles para SENTINEL/BioConnect.

    Atributos:
        disponible (bool): True si OpenDyslexic está lista para usar.
        familia    (str):  Nombre de familia de fuente activa.
        fallback   (bool): True si se está usando fuente de fallback.
    """

    def __init__(self, base_dir: Path = None):
        """
        Args:
            base_dir: Directorio raíz de la app (donde existe la carpeta fonts/).
                      Si None, usa el directorio del archivo font_manager.py.
        """
        self._base_dir   = base_dir or Path(__file__).parent
        self._fonts_dir  = self._base_dir / "fonts"
        self.disponible  = False
        self.fallback    = False
        self.familia     = _FUENTE_NORMAL
        self._intentar_cargar()

    # ----------------------------------------------------------
    # API pública
    # ----------------------------------------------------------

    def obtener_fuente(self, estilo: str = "normal", tamaño: int = 11) -> tuple:
        """Retorna una tupla de fuente compatible con Tkinter.

        Args:
            estilo:  "normal" | "bold" | "italic" | "bold italic"
            tamaño:  Tamaño en puntos (entero).

        Returns:
            Tupla (familia, tamaño) o (familia, tamaño, estilo).
        """
        if estilo in ("normal", ""):
            return (self.familia, tamaño)
        else:
            return (self.familia, tamaño, estilo)

    def aplicar_a_widget(self, widget, estilo: str = "normal", tamaño: int = 11):
        """Aplica la fuente activa a un widget Tkinter.

        Args:
            widget: Widget Tkinter con .config(font=...).
            estilo: "normal" | "bold" | "italic".
            tamaño: Tamaño en puntos.
        """
        try:
            widget.config(font=self.obtener_fuente(estilo, tamaño))
        except Exception:
            pass

    def aplicar_a_arbol(self, widget_raiz, tamaño_base: int = 11):
        """Aplica la fuente a todos los widgets descendientes.

        Args:
            widget_raiz: Widget raíz (p.ej. tk.Tk() o un Frame).
            tamaño_base: Tamaño base en puntos.
        """
        self._recorrer(widget_raiz, tamaño_base)

    def info(self) -> dict:
        """Retorna información de diagnóstico sobre el estado de la fuente."""
        return {
            "familia":     self.familia,
            "disponible":  self.disponible,
            "fallback":    self.fallback,
            "fonts_dir":   str(self._fonts_dir),
            "archivos":    self._listar_archivos_fuente(),
        }

    # ----------------------------------------------------------
    # Carga e instalación
    # ----------------------------------------------------------

    def _intentar_cargar(self):
        """Intenta cargar OpenDyslexic en el siguiente orden:
        1. Ya instalada en el sistema (tkFont.families())
        2. Presente en fonts/ → instalar en usuario → recargar
        3. Fallback a fuente amigable con dislexia disponible en sistema
        4. Fallback a Arial (siempre disponible)
        """
        # Paso 1: ¿ya está en el sistema?
        if _TKINTER_DISPONIBLE and self._en_sistema():
            return  # self.familia ya actualizado

        # Paso 2: ¿hay archivos en fonts/?
        archivos = self._listar_archivos_fuente()
        if archivos:
            exito = self._instalar_fuentes(archivos)
            if exito and _TKINTER_DISPONIBLE and self._en_sistema():
                return

        # Paso 3: fallback a fuente del sistema amigable con dislexia
        self.fallback = True
        if _TKINTER_DISPONIBLE:
            disponibles = set(tkFont.families())
            for f in _FALLBACK_DISLEXIA:
                if f in disponibles:
                    self.familia    = f
                    self.disponible = False
                    return

        # Paso 4: Arial siempre funciona en Tkinter
        self.familia    = _FUENTE_NORMAL
        self.disponible = False

    def _en_sistema(self) -> bool:
        """Verifica si OpenDyslexic está en las familias de tkFont."""
        try:
            familias = set(tkFont.families())
            for nombre in _NOMBRES_FAMILIA:
                if nombre in familias:
                    self.familia    = nombre
                    self.disponible = True
                    self.fallback   = False
                    return True
        except Exception:
            pass
        return False

    def _listar_archivos_fuente(self) -> list:
        """Lista archivos TTF/OTF disponibles en fonts/."""
        if not self._fonts_dir.exists():
            return []
        return [
            f for f in self._fonts_dir.iterdir()
            if f.suffix.lower() in (".ttf", ".otf")
               and "dyslexic" in f.name.lower()
        ]

    def _instalar_fuentes(self, archivos: list) -> bool:
        """Copia los archivos de fuente al directorio de usuario del sistema.

        Returns:
            True si al menos un archivo se copió correctamente.
        """
        destino = self._directorio_fuentes_usuario()
        if destino is None:
            return False

        destino.mkdir(parents=True, exist_ok=True)
        instalados = 0

        for archivo in archivos:
            dst = destino / archivo.name
            try:
                if not dst.exists():
                    shutil.copy2(archivo, dst)
                instalados += 1
            except OSError:
                pass

        if instalados > 0:
            self._actualizar_cache_fuentes()
            return True
        return False

    def _directorio_fuentes_usuario(self) -> Path | None:
        """Retorna el directorio de fuentes del usuario según el SO."""
        sistema = platform.system()
        if sistema == "Linux":
            return Path.home() / ".local" / "share" / "fonts"
        elif sistema == "Darwin":       # macOS
            return Path.home() / "Library" / "Fonts"
        elif sistema == "Windows":
            # En Windows se necesitaría ctypes/AddFontResourceEx
            # Por ahora solo soportamos Linux/macOS
            return None
        return None

    def _actualizar_cache_fuentes(self):
        """Ejecuta fc-cache en Linux para que el sistema reconozca la fuente."""
        if platform.system() == "Linux":
            try:
                # -f fuerza rescan; omitir -q (no disponible en todas las versiones)
                os.system("fc-cache -f 2>/dev/null")
            except Exception:
                pass

    # ----------------------------------------------------------
    # Recorrido de árbol de widgets
    # ----------------------------------------------------------

    def _recorrer(self, widget, tamaño_base: int):
        """Recorre el árbol de widgets y aplica la fuente activa."""
        try:
            import tkinter as tk
            tipos = (tk.Label, tk.Button, tk.Entry,
                     tk.Checkbutton, tk.Radiobutton, tk.Text)
            if isinstance(widget, tipos):
                try:
                    cfg = str(widget.cget("font"))
                    # Preservar bold/italic si ya los tiene
                    bold   = "bold"   in cfg
                    italic = "italic" in cfg
                    if bold and italic:
                        estilo = "bold italic"
                    elif bold:
                        estilo = "bold"
                    elif italic:
                        estilo = "italic"
                    else:
                        estilo = "normal"
                    widget.config(font=self.obtener_fuente(estilo, tamaño_base))
                except Exception:
                    pass
        except Exception:
            pass

        for child in widget.winfo_children():
            self._recorrer(child, tamaño_base)


# ----------------------------------------------------------
# Función de conveniencia — instancia global
# ----------------------------------------------------------

_instancia_global: FontManager | None = None


def obtener_font_manager(base_dir: Path = None) -> FontManager:
    """Retorna (y crea si es necesario) la instancia global de FontManager."""
    global _instancia_global
    if _instancia_global is None:
        _instancia_global = FontManager(base_dir)
    return _instancia_global


def resetear_font_manager():
    """Destruye la instancia global para forzar recarga (p.ej. tras cambio de prefs)."""
    global _instancia_global
    _instancia_global = None
