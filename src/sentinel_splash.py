# ============================================================
#  SENTINEL — Splash Screen de carga
#  Tecno-Sheep | Universidad de Guadalajara | Bioconnect
# ============================================================
#
#  Uso:
#    splash = SentinelSplash(root)
#    splash.iniciar(on_done=lambda: root.deiconify())
# ============================================================

import tkinter as tk
from tkinter import ttk
import threading
import time
import pathlib

from i18n import t

# Paleta SENTINEL
_BG      = "#0F0F0F"
_ROJO    = "#EF4444"
_NARANJA = "#FF9900"
_TEXTO   = "#FFFFFF"
_GRIS    = "#666666"
_PANEL   = "#1F1F1F"


class SentinelSplash(tk.Toplevel):
    """
    Ventana de bienvenida SENTINEL.

    Muestra logo, barra de progreso animada y mensajes de estado.
    Llama `on_done()` cuando termina (en el hilo principal via after()).
    """

    _DURACION_MS = 3500   # Duracion total del splash

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self._parent = parent
        self._on_done = None
        # Mensajes traducidos al idioma activo en el momento de construccion
        self._MENSAJES = [
            t("splash.iniciando"),
            t("splash.cargando_motor"),
            t("splash.verificando"),
            t("splash.calibrando"),
            t("splash.conectando"),
            t("splash.listo"),
        ]

        # Ventana: sin bordes, centrada, siempre al frente
        self.overrideredirect(True)
        self.configure(bg=_BG)
        self.attributes("-topmost", True)

        ancho, alto = 480, 340
        self.geometry(self._centrar(ancho, alto))

        self._build_ui()

    # ----------------------------------------------------------
    # Geometría centrada
    # ----------------------------------------------------------
    def _centrar(self, w: int, h: int) -> str:
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        return f"{w}x{h}+{x}+{y}"

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------
    def _build_ui(self):
        # Borde exterior rojo (efecto "glow")
        self.config(highlightbackground=_ROJO, highlightthickness=2)

        contenedor = tk.Frame(self, bg=_BG)
        contenedor.pack(expand=True, fill="both", padx=20, pady=20)

        # --- Logo ---
        self._logo_lbl = tk.Label(contenedor, bg=_BG)
        self._logo_lbl.pack(pady=(10, 4))
        self._cargar_logo()

        # --- Nombre ---
        tk.Label(contenedor, text="SENTINEL",
                 font=("Arial", 28, "bold"),
                 fg=_ROJO, bg=_BG).pack()

        # --- Tagline ---
        tk.Label(contenedor,
                 text="Intraoperative Perfusion Intelligence",
                 font=("Arial", 10), fg=_NARANJA, bg=_BG).pack()

        tk.Label(contenedor,
                 text="From Tecno-Sheep  ·  Universidad de Guadalajara",
                 font=("Arial", 8), fg=_GRIS, bg=_BG).pack(pady=(2, 12))

        # --- Separador ---
        tk.Frame(contenedor, bg=_ROJO, height=1).pack(fill="x")

        # --- Barra de progreso ---
        prog_frame = tk.Frame(contenedor, bg=_BG)
        prog_frame.pack(fill="x", pady=(14, 4))

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Sentinel.Horizontal.TProgressbar",
                        troughcolor=_PANEL,
                        background=_ROJO,
                        bordercolor=_PANEL,
                        darkcolor=_ROJO,
                        lightcolor=_NARANJA,
                        thickness=6)

        self._progvar = tk.DoubleVar(value=0)
        self._barra = ttk.Progressbar(prog_frame,
                                       variable=self._progvar,
                                       style="Sentinel.Horizontal.TProgressbar",
                                       maximum=100)
        self._barra.pack(fill="x")

        # --- Mensaje de estado ---
        self._msg_var = tk.StringVar(value=self._MENSAJES[0])
        tk.Label(contenedor, textvariable=self._msg_var,
                 font=("Arial", 9), fg=_GRIS, bg=_BG).pack(pady=(6, 0))

        # --- Versión ---
        tk.Label(contenedor, text="v2.0  |  Bioconnect",
                 font=("Arial", 7), fg="#333333", bg=_BG).pack(side="bottom")

    def _cargar_logo(self):
        """Intenta cargar PNG 128px; si falla dibuja logo SVG sintético."""
        base = pathlib.Path(__file__).parent
        ruta = base / "assets" / "logos" / "sentinel-icon-minimalista-128.png"
        try:
            from PIL import Image, ImageTk
            img = Image.open(ruta).resize((96, 96), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self._logo_lbl.config(image=self._photo)
        except Exception:
            # Canvas de respaldo (ojo SENTINEL dibujado en Tkinter)
            c = tk.Canvas(self._logo_lbl, width=96, height=96,
                          bg=_BG, highlightthickness=0)
            c.pack()
            c.create_oval(8,  8,  88, 88, outline=_ROJO,   width=3)
            c.create_oval(18, 18, 78, 78, fill="#1F1F1F",  outline=_NARANJA, width=2)
            c.create_oval(28, 28, 68, 68, fill=_ROJO)
            c.create_oval(38, 38, 58, 58, fill=_NARANJA)
            c.create_oval(42, 42, 52, 52, fill=_TEXTO)

    # ----------------------------------------------------------
    # Animación
    # ----------------------------------------------------------
    def iniciar(self, on_done=None):
        """Arranca la animación; llama on_done() al terminar."""
        self._on_done = on_done
        threading.Thread(target=self._animar, daemon=True).start()

    def _animar(self):
        n   = len(self._MENSAJES)
        dur = self._DURACION_MS / 1000.0
        paso = dur / (n + 2)

        for i, msg in enumerate(self._MENSAJES):
            pct = (i + 1) / n * 100
            self.after(0, lambda m=msg, p=pct: self._actualizar(m, p))
            time.sleep(paso)

        # Llegar al 100%
        self.after(0, lambda: self._progvar.set(100))
        time.sleep(0.3)

        # Cerrar y notificar
        self.after(0, self._finalizar)

    def _actualizar(self, mensaje: str, progreso: float):
        self._msg_var.set(mensaje)
        self._progvar.set(progreso)

    def _finalizar(self):
        self.destroy()
        if self._on_done:
            self._on_done()
