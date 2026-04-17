# ============================================================
#  BIOCONNECT v2.0 — Motor de Cuantificación ICG + UI
# Universidad de Guadalajara
# ============================================================
#
# Módulos centralizados: importar desde config, parameter_extraction
# ============================================================

import numpy as np

# Importar configuración centralizada
from config import UMBRALES_CANONICOS, clasificar_perfusion, SYNTHETIC_PARAMS
from parameter_extraction import extraer_parametros

# Imports GUI se hacen solo cuando se ejecuta como script principal
# o cuando se invocan funciones que necesitan GUI.
# generar_senal_icg() es importable sin tkinter.
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import tkinter as tk
    from tkinter import ttk, font
    _GUI_AVAILABLE = True
except ImportError:
    _GUI_AVAILABLE = False

# ============================================================
# MÓDULO 1 — Generador de señal ICG sintética
# ============================================================

def generar_senal_icg(t1_real, t2_real, pendiente_real, indice_real,
                      ruido=None, seed=42):
    """
    Genera curva ICG sintética realista con modelo Gaussiano + exponencial.

    El modelo garantiza que los parámetros EXTRAÍDOS correspondan
    directamente a los parámetros clínicos de entrada:
      - T1_extraído ≈ t1_real  (llegada al 10% del pico)
      - T2_extraído ≈ t2_real  (tiempo al pico)
      - indice_NIR proporcional a la duración de la curva (T2 - T1)

    Modelo:
      t ≤ t2:  A · exp(−(t − t2)² / (2σ²))   [subida Gaussiana]
      t > t2:  A · exp(−(t − t2) / τ)          [caída exponencial]

    Donde σ = (t2 − t1) / 2.146  asegura que en t = t1, la señal
    sea exactamente el 10% del pico (∵ exp(−ln10) = 0.10).

    Args:
        t1_real:       Tiempo de llegada del bolo — T1 clínico (s)
        t2_real:       Tiempo al pico              — T2 clínico (s)
        pendiente_real: No usada directamente; la pendiente queda
                        determinada por indice_real / (t2 − t1)
        indice_real:   Amplitud del pico (a.u.)
        ruido:         Fracción de ruido Gaussiano (default SYNTHETIC_PARAMS)
        seed:          Semilla aleatoria

    Returns:
        (tiempo, senal)
    """
    if ruido is None:
        ruido = SYNTHETIC_PARAMS["ruido_default"]

    rng = np.random.default_rng(seed)
    tiempo = np.linspace(0, SYNTHETIC_PARAMS["tiempo_max"],
                         SYNTHETIC_PARAMS["tiempo_puntos"])

    dt_rise = max(float(t2_real - t1_real), 0.5)

    # σ calibrado: 10% del pico exactamente en t1_real
    # 0.10 = exp(−(t1−t2)²/(2σ²)) → σ = dt_rise / sqrt(2·ln10) = dt_rise / 2.1460
    sigma = dt_rise / 2.1460

    # τ de caída: relación clínica típica τ = 1.5 · σ
    tau_fall = max(sigma * 1.5, 1.0)

    # Construir señal
    rise = indice_real * np.exp(-(tiempo - t2_real) ** 2 / (2.0 * sigma ** 2))
    fall = indice_real * np.exp(-(tiempo - t2_real) / tau_fall)
    senal = np.where(tiempo <= t2_real, rise, fall)

    # Ruido Gaussiano (factor 0.03 mantiene SNR realista)
    senal = senal + rng.normal(0, ruido * indice_real * 0.03, len(tiempo))
    senal = np.clip(senal, 0.0, None)

    return tiempo, senal


# ============================================================
# MÓDULO 3 — Generador de figura matplotlib
# ============================================================

def generar_figura(tiempo, intensidad, params, resultado,
                   color_resultado, detalle, aprobados, nombre_caso):
    """
    Genera figura matplotlib para visualización de análisis ICG.
    """
    fig = plt.figure(figsize=(11, 5), facecolor="#1a1a2e")
    gs  = fig.add_gridspec(2, 3, hspace=0.5, wspace=0.35,
                           left=0.06, right=0.97, top=0.88, bottom=0.10)

    # --- Curva ICG ---
    ax1 = fig.add_subplot(gs[:, :2])
    ax1.set_facecolor("#0f0f1a")
    ax1.plot(tiempo, intensidad, color="#00d4ff", linewidth=2.0)
    ax1.fill_between(tiempo, intensidad, alpha=0.15, color="#00d4ff")

    pico_idx = np.argmax(intensidad)
    t2_val   = tiempo[pico_idx]
    pico_val = intensidad[pico_idx]

    idx_t1 = np.where(intensidad >= 0.10 * pico_val)[0]
    if len(idx_t1) > 0:
        ax1.axvline(tiempo[idx_t1[0]], color="#f39c12", linestyle="--",
                    linewidth=1.4, label=f"T₁ = {params['T1']} s")

    ax1.axvline(t2_val, color="#9b59b6", linestyle="--",
                linewidth=1.4, label=f"T₂ = {params['T2']} s")
    ax1.scatter([t2_val], [pico_val], color="#ff6b6b", s=60, zorder=5)

    ax1.set_xlabel("Tiempo (s)", color="white", fontsize=10)
    ax1.set_ylabel("Intensidad (u.a.)", color="white", fontsize=10)
    ax1.set_title(f"Curva ICG — {nombre_caso}", color="white", fontsize=11)
    ax1.tick_params(colors="white")
    ax1.spines[:].set_color("#333355")
    ax1.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)
    ax1.grid(color="#222244", linestyle="--", linewidth=0.5)

    # --- Parámetros ---
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.set_facecolor("#0f0f1a")
    ax2.set_xlim(0, 1); ax2.set_ylim(0, 1); ax2.axis("off")
    ax2.set_title("Parámetros", color="white", fontsize=10)

    etiquetas = {
        "T1":         f"T₁ = {params['T1']} s  (≤10)",
        "T2":         f"T₂ = {params['T2']} s  (≤30)",
        "pendiente":  f"Pend. = {params['pendiente']}  (≥5)",
        "indice_NIR": f"NIR = {params['indice_NIR']}  (≥50)",
    }
    for i, (nombre, etiqueta) in enumerate(etiquetas.items()):
        y     = 0.80 - i * 0.22
        color = "#2ecc71" if detalle[nombre] else "#e74c3c"
        sim   = "✓" if detalle[nombre] else "✗"
        ax2.add_patch(mpatches.FancyBboxPatch(
            (0.02, y - 0.06), 0.96, 0.16,
            boxstyle="round,pad=0.01",
            facecolor="#1a1a2e", edgecolor=color, linewidth=1.3))
        ax2.text(0.10, y + 0.01, sim, color=color,
                 fontsize=12, fontweight="bold", va="center")
        ax2.text(0.24, y + 0.01, etiqueta, color="white",
                 fontsize=8, va="center")

    # --- Veredicto ---
    ax3 = fig.add_subplot(gs[1, 2])
    ax3.set_facecolor("#0f0f1a")
    ax3.set_xlim(0, 1); ax3.set_ylim(0, 1); ax3.axis("off")
    ax3.set_title("Resultado", color="white", fontsize=10)

    ax3.add_patch(mpatches.FancyBboxPatch(
        (0.05, 0.20), 0.90, 0.60,
        boxstyle="round,pad=0.02",
        facecolor=color_resultado + "33",
        edgecolor=color_resultado, linewidth=2.5))

    ax3.text(0.50, 0.65, "PERFUSIÓN", color="white",
             fontsize=9, ha="center", va="center")
    ax3.text(0.50, 0.48, resultado, color=color_resultado,
             fontsize=13, fontweight="bold", ha="center", va="center")
    ax3.text(0.50, 0.31, f"{aprobados}/4 OK",
             color="#aaaacc", fontsize=9, ha="center", va="center")

    return fig


# ============================================================
# MÓDULO 4 — Interfaz gráfica (Tkinter)
# ============================================================

class BioConnectApp:

    def __init__(self, root):
        self.root = root
        self.root.title("BIOCONNECT v2.0 — Motor de Cuantificación ICG")
        self.root.configure(bg="#1a1a2e")
        self.root.geometry("1200x780")
        self.root.resizable(True, True)

        self._build_ui()
        self._analizar()   # corre el análisis con valores por defecto al abrir

    def _build_ui(self):
        # ── Encabezado ──────────────────────────────────────
        header = tk.Frame(self.root, bg="#0f0f1a", pady=8)
        header.pack(fill="x")

        tk.Label(header, text="BIOCONNECT",
                 font=("Arial", 20, "bold"),
                 fg="#00d4ff", bg="#0f0f1a").pack()
        tk.Label(header, text="Motor de Cuantificación ICG  ·  Bioconnect 2026  ·  Universidad de Guadalajara",
                 font=("Arial", 9), fg="#7777aa", bg="#0f0f1a").pack()

        # ── Contenedor principal ─────────────────────────────
        main = tk.Frame(self.root, bg="#1a1a2e")
        main.pack(fill="both", expand=True, padx=12, pady=8)

        # Panel izquierdo — controles
        left = tk.Frame(main, bg="#0f0f1a", width=260, bd=0,
                        highlightbackground="#333355", highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="Parámetros de entrada",
                 font=("Arial", 11, "bold"),
                 fg="white", bg="#0f0f1a").pack(pady=(14, 4))

        tk.Label(left, text="Ajusta los valores y presiona Analizar",
                 font=("Arial", 8), fg="#7777aa", bg="#0f0f1a",
                 wraplength=220).pack(pady=(0, 12))

        # Sliders
        self.vars = {}
        sliders_config = [
            ("T₁  —  Llegada del bolo (s)",  "t1",  1,  20, 6),
            ("T₂  —  Tiempo al pico (s)",     "t2",  5,  55, 20),
            ("Pendiente de subida",            "pen", 0.05, 1.0, 0.5),
            ("Amplitud de señal (índice)",     "amp", 10, 150, 100),
        ]

        for label, key, mn, mx, default in sliders_config:
            frame = tk.Frame(left, bg="#0f0f1a")
            frame.pack(fill="x", padx=14, pady=6)

            tk.Label(frame, text=label, font=("Arial", 8, "bold"),
                     fg="#aaaacc", bg="#0f0f1a", anchor="w").pack(fill="x")

            row = tk.Frame(frame, bg="#0f0f1a")
            row.pack(fill="x")

            var = tk.DoubleVar(value=default)
            self.vars[key] = var

            val_label = tk.Label(row, text=f"{default:.2f}",
                                 font=("Arial", 9, "bold"),
                                 fg="#00d4ff", bg="#0f0f1a", width=6)
            val_label.pack(side="right")

            slider = ttk.Scale(row, from_=mn, to=mx, variable=var,
                               orient="horizontal",
                               command=lambda v, l=val_label, vr=var:
                                   l.config(text=f"{vr.get():.2f}"))
            slider.pack(side="left", fill="x", expand=True)

        # Selector de caso
        tk.Label(left, text="Caso clínico",
                 font=("Arial", 9, "bold"),
                 fg="#aaaacc", bg="#0f0f1a").pack(pady=(16, 4))

        self.caso_var = tk.StringVar(value="Personalizado")
        casos = ["Personalizado", "Caso 1 — Adecuada",
                 "Caso 2 — Comprometida", "Caso 3 — Borderline"]
        combo = ttk.Combobox(left, textvariable=self.caso_var,
                             values=casos, state="readonly", width=24)
        combo.pack(padx=14)
        combo.bind("<<ComboboxSelected>>", self._cargar_caso)

        # Botones
        btn_frame = tk.Frame(left, bg="#0f0f1a")
        btn_frame.pack(pady=20, padx=14, fill="x")

        tk.Button(btn_frame, text="▶  Analizar",
                  font=("Arial", 11, "bold"),
                  bg="#00d4ff", fg="#0f0f1a", relief="flat",
                  padx=10, pady=8, cursor="hand2",
                  command=self._analizar).pack(fill="x", pady=(0, 6))

        tk.Button(btn_frame, text="💾  Guardar reporte",
                  font=("Arial", 9),
                  bg="#333355", fg="white", relief="flat",
                  padx=10, pady=6, cursor="hand2",
                  command=self._guardar).pack(fill="x")

        # Panel derecho — gráfica
        self.right = tk.Frame(main, bg="#1a1a2e")
        self.right.pack(side="left", fill="both", expand=True)

        self.canvas_widget = None
        self.fig_actual    = None

    def _cargar_caso(self, event=None):
        caso = self.caso_var.get()
        presets = {
            "Caso 1 — Adecuada":      (5,  20, 0.50, 100),
            "Caso 2 — Comprometida":  (15, 40, 0.10,  25),
            "Caso 3 — Borderline":    (9,  28, 0.25,  60),
        }
        if caso in presets:
            t1, t2, pen, amp = presets[caso]
            self.vars["t1"].set(t1)
            self.vars["t2"].set(t2)
            self.vars["pen"].set(pen)
            self.vars["amp"].set(amp)
        self._analizar()

    def _analizar(self):
        t1  = self.vars["t1"].get()
        t2  = self.vars["t2"].get()
        pen = self.vars["pen"].get()
        amp = self.vars["amp"].get()

        nombre = self.caso_var.get()

        tiempo, senal        = generar_senal_icg(t1, t2, pen, amp)
        params               = extraer_parametros(tiempo, senal)
        resultado, color, ap, detalle = clasificar_perfusion(params)

        self.ultimo_resultado = (tiempo, senal, params, resultado,
                                 color, detalle, ap, nombre)

        fig = generar_figura(tiempo, senal, params, resultado,
                             color, detalle, ap, nombre)
        self.fig_actual = fig

        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()

        canvas = FigureCanvasTkAgg(fig, master=self.right)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas_widget = canvas
        plt.close(fig)

    def _guardar(self):
        if self.fig_actual is None:
            return
        _, _, _, resultado, _, _, _, nombre = self.ultimo_resultado
        nombre_archivo = nombre.replace(" ", "_").replace("—", "").strip("_") + ".png"

        tiempo, senal, params, resultado, color, detalle, ap, nombre = self.ultimo_resultado
        fig = generar_figura(tiempo, senal, params, resultado,
                             color, detalle, ap, nombre)
        fig.savefig(nombre_archivo, dpi=170, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close(fig)
        print(f"✓ Reporte guardado como: {nombre_archivo}")


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = BioConnectApp(root)
    root.mainloop()