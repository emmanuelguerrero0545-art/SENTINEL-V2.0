# ============================================================
#  SENTINEL v2.0 — Intraoperative Perfusion Intelligence
#  Tecno-Sheep | Universidad de Guadalajara | Bioconnect
# ============================================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import json
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.font_manager as _mpl_fm
from scipy.signal import savgol_filter
# gamma_dist eliminado — generador migrado a modelo Gaussiana+exponencial (BCV1.py)
import cv2

# Importar desde modulos centralizados
from config import (
    clasificar_perfusion as _clasificar_perfusion_config,
    calcular_score_riesgo, get_umbral
)
from parameter_extraction import extraer_parametros
from bioconnect_prefs   import BioConnectPrefs
from sentinel_splash    import SentinelSplash
from sentinel_settings  import abrir_settings

# Sistema de internacionalización
from i18n import t, t_list, init_desde_prefs, idioma_actual

# ---- Fuentes CJK para matplotlib ----------------------------------------
# Droid Sans Fallback incluye glifos chinos y japoneses y está disponible
# en las instalaciones Linux habituales.  Si no se encuentra, se usa el
# fallback genérico de matplotlib sin errores.
_CJK_LANGS = {"ja", "zh"}
_CJK_FONT_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
_CJK_FONT_PROP = None
try:
    _CJK_FONT_PROP = _mpl_fm.FontProperties(fname=_CJK_FONT_PATH)
except (OSError, RuntimeError):
    _CJK_FONT_PROP = None


def _mpl_cjk_ctx():
    """Devuelve un dict de rcParams para usar en rc_context() cuando el
    idioma activo es CJK (ja/zh).  En otros idiomas devuelve {}.
    """
    if idioma_actual() in _CJK_LANGS and _CJK_FONT_PROP is not None:
        fname = _CJK_FONT_PATH
        return {"font.family": "sans-serif",
                "font.sans-serif": ["Droid Sans Fallback", "DejaVu Sans"]}
    return {}


def _apply_cjk_to_figure(fig):
    """Post-proceso: aplica FontProperties CJK a todos los elementos de texto
    de una figura, cuando el idioma activo es CJK.
    """
    if idioma_actual() not in _CJK_LANGS or _CJK_FONT_PROP is None:
        return
    for ax in fig.get_axes():
        for item in (
            [ax.title, ax.xaxis.label, ax.yaxis.label]
            + ax.get_xticklabels()
            + ax.get_yticklabels()
        ):
            item.set_fontproperties(_CJK_FONT_PROP)
        try:
            legend = ax.get_legend()
            if legend:
                for txt in legend.get_texts():
                    txt.set_fontproperties(_CJK_FONT_PROP)
        except Exception:
            pass
        for txt in ax.texts:
            txt.set_fontproperties(_CJK_FONT_PROP)
# -------------------------------------------------------------------------

# Gestor de fuentes accesibles
from font_manager import FontManager, resetear_font_manager

# Base de datos de casos clínicos
from bioconnect_db import BioConnectDB

# Manual técnico PDF exportable
try:
    from bioconnect_manual_pdf import generar_manual_tecnico
    _MANUAL_PDF_DISPONIBLE = True
except ImportError:
    _MANUAL_PDF_DISPONIBLE = False

# ------------------------------------------------------------
# Paleta SENTINEL (Modo Quirofano — oscuro)
# ------------------------------------------------------------

BG_DARK    = "#0F0F0F"   # Negro profundo
BG_PANEL   = "#1F1F1F"   # Gris oscuro UI
BG_CARD    = "#2A2A2A"   # Tarjeta elevada
ACENTO     = "#EF4444"   # Rojo alerta — color primario SENTINEL
VERDE      = "#22C55E"   # Verde perfusion OK
AMARILLO   = "#FF9900"   # Naranja advertencia — color secundario SENTINEL
ROJO       = "#EF4444"   # Rojo critico (coincide con ACENTO)
MORADO     = "#A855F7"   # Purpura (simulador / modo avanzado)
CYAN       = "#22D3EE"   # Cyan (datos en vivo)
AZUL_SEG   = "#3B82F6"   # Azul (segmentacion)
TEXTO      = "#FFFFFF"   # Blanco limpio
GRIS       = "#666666"   # Gris neutral muted
BORDE      = "#333333"   # Gris borde oscuro

# Sistema de unidades activo: "metric" | "imperial" | "hybrid"
_UNITS_SYSTEM = "metric"


def fmt_unidad(valor, tipo: str = "longitud") -> str:
    """Formatea un valor numerico segun el sistema de unidades activo.

    Args:
        valor: Valor en unidad base (cm para longitud, kg para masa,
               C para temperatura).
        tipo:  "longitud" | "masa" | "temp"

    Returns:
        String formateado con simbolo de unidad.
    """
    s = _UNITS_SYSTEM
    if tipo == "longitud":
        if s == "imperial":
            return f"{valor / 2.54:.2f} in"
        return f"{valor:.1f} cm"
    elif tipo == "masa":
        if s == "imperial":
            return f"{valor * 2.20462:.2f} lb"
        elif s == "hybrid":
            return f"{valor:.1f} kg / {valor * 2.20462:.1f} lb"
        return f"{valor:.1f} kg"
    elif tipo == "temp":
        if s == "imperial":
            return f"{valor * 9/5 + 32:.1f} °F"
        return f"{valor:.1f} °C"
    return str(valor)

HISTORIAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bioconnect_historial.json")

plt.rcParams.update({
    "figure.facecolor":  BG_DARK,
    "axes.facecolor":    BG_PANEL,
    "axes.edgecolor":    BORDE,
    "axes.labelcolor":   TEXTO,
    "xtick.color":       TEXTO,
    "ytick.color":       TEXTO,
    "text.color":        TEXTO,
    "grid.color":        "#444444",
    "grid.linestyle":    "--",
    "grid.linewidth":    0.5,
    "legend.facecolor":  BG_DARK,
    "legend.labelcolor": TEXTO,
})

# ------------------------------------------------------------
# Configuracion mapa de calor
# ------------------------------------------------------------

FILAS          = 8
COLS           = 8
T1_ADECUADA    = get_umbral("T1")   # 10.0 s — fuente: config.py (Son et al., 2023)
T1_BORDERLINE  = 15.0
UMBRAL_TEJIDO  = 8.0
UMBRAL_VAR     = 2.0

CMAP_ICG = LinearSegmentedColormap.from_list(
    "icg_perfusion",
    [(0.0, ROJO), (0.4, AMARILLO), (0.7, AMARILLO), (1.0, VERDE)])

# ------------------------------------------------------------
# Motor de analisis (umbrales y extraccion desde modulos centralizados)
# ------------------------------------------------------------

def clasificar_perfusion(params):
    """Wrapper: usa config.py; color_map se evalua en cada llamada para respetar la paleta activa."""
    veredicto, _, aprobados, detalle = _clasificar_perfusion_config(params)
    color_map = {"ADECUADA": VERDE, "BORDERLINE": AMARILLO, "COMPROMETIDA": ACENTO}
    return veredicto, color_map[veredicto], aprobados, detalle

def calcular_score(params):
    return calcular_score_riesgo(params)

def color_score(score):
    if score >= 60:
        return VERDE
    elif score >= 40:
        return AMARILLO
    else:
        return ROJO

def etiqueta_score(score):
    if score >= 60:
        return t("score.bajo_riesgo")
    elif score >= 40:
        return t("score.riesgo_moderado")
    else:
        return t("score.alto_riesgo")

def leer_video(ruta, callback=None):
    cap   = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        return None, None
    fps   = cap.get(cv2.CAP_PROP_FPS)
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    x1=int(ancho*0.30); x2=int(ancho*0.70)
    y1=int(alto*0.30);  y2=int(alto*0.70)
    vals = []
    i    = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        vals.append(float(np.mean(gris[y1:y2, x1:x2])))
        i += 1
        if callback and total > 0:
            callback(int(i / total * 100))
    cap.release()
    tiempo_arr = np.linspace(0, len(vals)/fps, len(vals))
    s = np.array(vals, dtype=np.float32)
    if len(s) > 21:
        s = savgol_filter(s, 21, 3)
    return tiempo_arr, np.clip(s, 0, None)

def generar_senal_sintetica(t1, t2, ruido_pct, amp, seed=42):
    """
    Genera señal ICG sintética — modelo Gaussiana + exponencial.

    Garantías sobre los parámetros EXTRAÍDOS (consistente con módulos validados):
      - T1_extraído ≈ t1   (el 10% del pico ocurre en t1)
      - T2_extraído ≈ t2   (pico en t2)
      - pendiente  ≈ amp · 2.146 / ((t2 - t1) · 1.649)
      - indice_NIR ≈ 27.5 · (t2 - t1) / 2.146

    Args:
        t1:        Tiempo de llegada del bolo — T1 clínico (s)
        t2:        Tiempo al pico — T2 clínico (s)
        ruido_pct: Nivel de ruido Gaussiano (fracción, 0.0–0.30)
        amp:       Amplitud del pico (a.u.)
        seed:      Semilla aleatoria
    """
    np.random.seed(seed)
    tiempo = np.linspace(0, 60, 600)

    dt_rise = max(float(t2 - t1), 0.5)
    sigma   = dt_rise / 2.1460         # 10% del pico exactamente en t1
    tau_fall = max(sigma * 1.5, 1.0)   # caída exponencial realista

    rise  = amp * np.exp(-(tiempo - t2) ** 2 / (2.0 * sigma ** 2))
    fall  = amp * np.exp(-(tiempo - t2) / tau_fall)
    senal = np.where(tiempo <= t2, rise, fall)

    senal = senal + np.random.normal(0, ruido_pct * amp * 0.03, len(tiempo))
    return tiempo, np.clip(senal, 0, None)

def cargar_historial():
    if os.path.exists(HISTORIAL_PATH):
        with open(HISTORIAL_PATH, "r") as f:
            return json.load(f)
    return []

def guardar_historial(entrada):
    h = cargar_historial()
    h.insert(0, entrada)
    with open(HISTORIAL_PATH, "w") as f:
        json.dump(h[:50], f, indent=2)

# ------------------------------------------------------------
# Motor de mapa de calor v2
# ------------------------------------------------------------

def extraer_curvas_celda(ruta_video, callback=None):
    cap   = cv2.VideoCapture(ruta_video)
    if not cap.isOpened():
        return None, None
    fps   = cap.get(cv2.CAP_PROP_FPS)
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    x1 = int(ancho * 0.15); x2 = int(ancho * 0.85)
    y1 = int(alto  * 0.15); y2 = int(alto  * 0.85)
    pw = (x2 - x1) // COLS
    ph = (y2 - y1) // FILAS
    # Ajustar región ROI para que sea múltiplo exacto de celdas
    roi_w = pw * COLS
    roi_h = ph * FILAS

    curvas = np.zeros((FILAS, COLS, max(total, 1)), dtype=np.float32)
    idx    = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Vectorizado: reshape ROI en bloques (FILAS, ph, COLS, pw)
        # y calcular la media de cada bloque en una sola operación numpy
        roi = gris[y1:y1+roi_h, x1:x1+roi_w].astype(np.float32)
        bloques = roi.reshape(FILAS, ph, COLS, pw)
        curvas[:, :, idx] = bloques.mean(axis=(1, 3))

        idx += 1
        if callback and total > 0:
            callback(int(idx / total * 100))
    cap.release()
    fps_val = fps if fps > 0 else 15
    tiempo  = np.linspace(0, idx / fps_val, idx)
    return curvas[:, :, :idx], tiempo

def calcular_mascara(curvas):
    mascara = np.zeros((FILAS, COLS), dtype=bool)
    for fi in range(FILAS):
        for ci in range(COLS):
            s = curvas[fi,ci,:]
            if np.max(s) >= UMBRAL_TEJIDO and \
               (np.max(s) - np.min(s)) >= UMBRAL_VAR:
                mascara[fi,ci] = True
    return mascara

def calcular_mapa_t1(curvas, tiempo, mascara):
    mapa = np.full((FILAS, COLS), -1.0, dtype=np.float32)
    for fi in range(FILAS):
        for ci in range(COLS):
            if not mascara[fi,ci]:
                continue
            s = curvas[fi,ci,:].copy()
            if len(s) > 21:
                s = savgol_filter(s, 21, 3)
            s  = np.clip(s, 0, None)
            pv = np.max(s)
            ix = np.where(s >= 0.10*pv)[0]
            mapa[fi,ci] = tiempo[ix[0]] if len(ix) > 0 else 60.0
    return mapa

def figura_mapa_v2(mapa_t1, mascara, nombre):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=BG_DARK)
    fig.suptitle(t("figura_mapa.titulo").format(nombre=nombre),
                 fontsize=12, fontweight="bold")
    ax1 = axes[0]
    t1_validos = mapa_t1[mascara]
    if len(t1_validos) > 0:
        t1_min = max(0, t1_validos.min())
        t1_max = max(t1_validos.max(), t1_min + 1)
    else:
        t1_min, t1_max = 0, 60
    img = np.zeros((FILAS, COLS, 4), dtype=np.float32)
    for fi in range(FILAS):
        for ci in range(COLS):
            if not mascara[fi,ci]:
                img[fi,ci] = [0.20, 0.20, 0.20, 0.40]
            else:
                t1  = mapa_t1[fi,ci]
                val = 1.0 - np.clip((t1-t1_min)/(t1_max-t1_min), 0, 1)
                rgb = CMAP_ICG(val)
                img[fi,ci] = [rgb[0], rgb[1], rgb[2], 1.0]
    ax1.imshow(img, interpolation="nearest", aspect="auto")
    for fi in range(FILAS):
        for ci in range(COLS):
            if not mascara[fi,ci]:
                ax1.text(ci, fi, "—", ha="center", va="center",
                         fontsize=9, color="#555555", fontweight="bold")
            else:
                t1  = mapa_t1[fi,ci]
                col = "white" if t1 > (t1_min+t1_max)/2 else BG_DARK
                ax1.text(ci, fi, f"{t1:.0f}s",
                         ha="center", va="center",
                         fontsize=7, color=col, fontweight="bold")
    ax1.set_title(t("figura_mapa.ax1_titulo"), fontsize=10)
    ax1.tick_params(colors="white")
    norm = mcolors.Normalize(vmin=t1_min, vmax=t1_max)
    sm   = cm.ScalarMappable(cmap=CMAP_ICG, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label(t("figura_mapa.cbar_label"), fontsize=7)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=6)
    ax2  = axes[1]
    mapc = np.zeros((FILAS, COLS, 4), dtype=np.float32)
    cnt  = {"ADECUADA":0, "BORDERLINE":0, "COMPROMETIDA":0, "SIN_TEJIDO":0}
    for fi in range(FILAS):
        for ci in range(COLS):
            if not mascara[fi,ci]:
                mapc[fi,ci] = [0.20, 0.20, 0.20, 0.30]
                cnt["SIN_TEJIDO"] += 1
            else:
                t1 = mapa_t1[fi,ci]
                if t1 <= T1_ADECUADA:
                    mapc[fi,ci] = [0.47,0.67,0.19,1.0]; cnt["ADECUADA"]+=1
                elif t1 <= T1_BORDERLINE:
                    mapc[fi,ci] = [0.93,0.69,0.13,1.0]; cnt["BORDERLINE"]+=1
                else:
                    mapc[fi,ci] = [0.85,0.33,0.10,1.0]; cnt["COMPROMETIDA"]+=1
    ax2.imshow(mapc, interpolation="nearest", aspect="auto")
    for fi in range(FILAS):
        for ci in range(COLS):
            if not mascara[fi,ci]:
                ax2.text(ci, fi, "—", ha="center", va="center",
                         fontsize=9, color="#555555", fontweight="bold")
            else:
                t1 = mapa_t1[fi,ci]
                s  = "+" if t1<=T1_ADECUADA else "~" if t1<=T1_BORDERLINE else "x"
                ax2.text(ci, fi, s, ha="center", va="center",
                         fontsize=10, color="white", fontweight="bold")
    n_tej = cnt["ADECUADA"] + cnt["BORDERLINE"] + cnt["COMPROMETIDA"]
    pct   = lambda n: f"{100*n//n_tej}%" if n_tej > 0 else "0%"
    ax2.set_title(
        t("figura_mapa.ax2_titulo").format(n_tej=n_tej, total=FILAS*COLS),
        fontsize=10)
    ax2.tick_params(colors="white")
    leyenda = [
        mpatches.Patch(color=VERDE,
                       label=t("figura_mapa.leyenda_adecuada").format(
                           n=cnt["ADECUADA"], pct=pct(cnt["ADECUADA"]))),
        mpatches.Patch(color=AMARILLO,
                       label=t("figura_mapa.leyenda_borderline").format(
                           n=cnt["BORDERLINE"], pct=pct(cnt["BORDERLINE"]))),
        mpatches.Patch(color=ROJO,
                       label=t("figura_mapa.leyenda_comprometida").format(
                           n=cnt["COMPROMETIDA"], pct=pct(cnt["COMPROMETIDA"]))),
        mpatches.Patch(color="#444444",
                       label=t("figura_mapa.leyenda_sin_tejido").format(
                           n=cnt["SIN_TEJIDO"])),
    ]
    ax2.legend(handles=leyenda, loc="lower center",
               bbox_to_anchor=(0.5,-0.26), ncol=2, fontsize=8)
    plt.tight_layout()
    return fig, cnt

# ------------------------------------------------------------
# Motor de segmentacion pixel a pixel
# ------------------------------------------------------------

def seg_segmentar_roi(frame_gris, umbral_pct=0.35):
    h, w = frame_gris.shape
    blur = cv2.GaussianBlur(frame_gris, (15, 15), 0)
    umbral_val = max(int(blur.max() * umbral_pct), 10)
    _, binaria = cv2.threshold(blur, umbral_val, 255, cv2.THRESH_BINARY)
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, kernel)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN,  kernel)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        x1=int(w*0.20); x2=int(w*0.80)
        y1=int(h*0.20); y2=int(h*0.80)
        mascara = np.zeros((h,w), dtype=np.uint8)
        cv2.rectangle(mascara, (x1,y1), (x2,y2), 255, -1)
        return mascara, (x1,y1,x2,y2), None
    contorno = max(contornos, key=cv2.contourArea)
    mascara  = np.zeros((h,w), dtype=np.uint8)
    cv2.drawContours(mascara, [contorno], -1, 255, -1)
    bx,by,bw,bh = cv2.boundingRect(contorno)
    margen = 10
    x1=max(0,bx-margen); y1=max(0,by-margen)
    x2=min(w-1,bx+bw+margen); y2=min(h-1,by+bh+margen)
    return mascara, (x1,y1,x2,y2), contorno

def seg_calcular_mapa_pixel(frames_gris, fps, mascara):
    n_frames, alto, ancho = frames_gris.shape
    tiempo  = np.linspace(0, n_frames/fps, n_frames)
    mapa_t1 = np.full((alto, ancho), -1.0, dtype=np.float32)
    ys, xs  = np.where(mascara > 0)
    if len(ys) == 0:
        return mapa_t1, tiempo
    curvas = frames_gris[:, ys, xs].T.astype(np.float32)
    if n_frames > 21:
        curvas = savgol_filter(curvas, window_length=21,
                                polyorder=3, axis=1)
    curvas   = np.clip(curvas, 0, None)
    picos    = curvas.max(axis=1)
    umbrales = picos * 0.10
    for i in range(len(ys)):
        if picos[i] < 3.0:
            continue
        idx = np.where(curvas[i] >= umbrales[i])[0]
        if len(idx) > 0:
            mapa_t1[ys[i], xs[i]] = tiempo[idx[0]]
    return mapa_t1, tiempo

def seg_colorear_mapa(mapa_t1, mascara):
    alto, ancho = mapa_t1.shape
    img = np.zeros((alto, ancho, 3), dtype=np.uint8)

    # Fondo fuera del ROI
    img[mascara == 0] = (40, 40, 40)

    # Sin senal dentro del ROI
    sin_senal = (mascara > 0) & (mapa_t1 < 0)
    img[sin_senal] = (80, 80, 80)

    # Suavizado del mapa T1 para gradiente continuo
    validos = mapa_t1.copy()
    validos[mapa_t1 < 0] = 0
    validos_suav = cv2.GaussianBlur(
        validos.astype(np.float32), (15, 15), 0)

    # Rango de T1 para normalizar
    t1_vals = mapa_t1[(mascara > 0) & (mapa_t1 >= 0)]
    if len(t1_vals) == 0:
        return img
    t1_min = float(t1_vals.min())
    t1_max = float(max(t1_vals.max(), t1_min + 1))

    # Vectorizado — calcular toda la imagen de una vez
    norm_map = np.clip(
        (validos_suav - t1_min) / (t1_max - t1_min), 0, 1)

    mascara_valida = (mascara > 0) & (mapa_t1 >= 0)

    # Zona verde->amarillo (norm <= 0.5)
    zona1 = mascara_valida & (norm_map <= 0.5)
    f1    = norm_map * 2
    img[zona1, 2] = np.clip(f1[zona1] * 237,         0, 255).astype(np.uint8)
    img[zona1, 1] = np.clip(172 + f1[zona1] * 5,     0, 255).astype(np.uint8)
    img[zona1, 0] = np.clip(77  - f1[zona1] * 45,    0, 255).astype(np.uint8)

    # Zona amarillo->rojo (norm > 0.5)
    zona2 = mascara_valida & (norm_map > 0.5)
    f2    = (norm_map - 0.5) * 2
    img[zona2, 2] = np.clip(237 - f2[zona2] * 177,   0, 255).astype(np.uint8)
    img[zona2, 1] = np.clip(177 - f2[zona2] * 101,   0, 255).astype(np.uint8)
    img[zona2, 0] = np.clip(32  + f2[zona2] * 199,   0, 255).astype(np.uint8)

    return img

def seg_calcular_linea(mapa_t1, mascara):
    ancho = mapa_t1.shape[1]
    for x in range(ancho-1, -1, -1):
        col_roi = mascara[:, x]
        col_ok  = (mapa_t1[:, x] >= 0) & (mapa_t1[:, x] <= T1_ADECUADA)
        n_roi   = np.sum(col_roi > 0)
        n_ok    = np.sum(col_ok)
        if n_roi == 0:
            continue
        if n_ok / n_roi >= 0.40:
            return x, round(float(n_ok/n_roi)*100, 1)
    return -1, 0.0

def seg_dibujar_overlay(frame, mapa_color, contorno,
                         x_linea, confianza, bbox,
                         n_adec=0, n_bord=0, n_comp=0, n_val=0):
    resultado = frame.copy()
    x1,y1,x2,y2 = bbox
    alto, ancho  = frame.shape[:2]

    # Overlay semitransparente del mapa
    overlay = resultado.copy()
    overlay[y1:y2, x1:x2] = cv2.addWeighted(
        overlay[y1:y2, x1:x2], 0.40,
        mapa_color[y1:y2, x1:x2], 0.60, 0)
    resultado[y1:y2, x1:x2] = overlay[y1:y2, x1:x2]

    # Contorno del tejido
    if contorno is not None:
        cv2.drawContours(resultado, [contorno], -1, (0,255,255), 2)

    # Linea de seccion
    if x_linea > 0:
        cv2.line(resultado, (x_linea, y1), (x_linea, y2),
                 (255,255,255), 3)
        cv2.line(resultado, (x_linea, y1), (x_linea, y2),
                 (0,255,0), 1)
        cv2.arrowedLine(resultado,
                         (x_linea-30, y1+20), (x_linea-5, y1+20),
                         (0,255,0), 2, tipLength=0.4)
        cv2.arrowedLine(resultado,
                         (x_linea+30, y1+20), (x_linea+5, y1+20),
                         (0,255,0), 2, tipLength=0.4)
        cv2.rectangle(resultado,
                       (x_linea-90, y1-34),
                       (x_linea+90, y1-6),
                       (0,0,0), -1)
        cv2.putText(resultado,
                    t("overlay_seg.seccion_sugerida").format(conf=confianza),
                    (x_linea-88, y1-12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,255,0), 1)

    # Panel de estadisticas integrado
    if n_val > 0:
        pct_a = int(100*n_adec/n_val)
        pct_b = int(100*n_bord/n_val)
        pct_c = int(100*n_comp/n_val)
        px, py = ancho-162, 28
        pw, ph = 150, 92

        panel = resultado.copy()
        cv2.rectangle(panel, (px, py), (px+pw, py+ph), (0,0,0), -1)
        resultado = cv2.addWeighted(resultado, 0.35, panel, 0.65, 0)

        cv2.putText(resultado, t("overlay_seg.perfusion_icg"),
                    (px+6, py+14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0,212,255), 1)
        cv2.line(resultado,
                  (px+4, py+18), (px+pw-4, py+18), (0,212,255), 1)

        stats = [
            ((19,172,77),  t("overlay_seg.adecuada").format(pct=pct_a),     pct_a),
            ((32,177,237), t("overlay_seg.borderline").format(pct=pct_b),   pct_b),
            ((60,76,231),  t("overlay_seg.comprometida").format(pct=pct_c), pct_c),
        ]
        for i, (col, txt, pval) in enumerate(stats):
            y_s   = py + 36 + i*20
            bar_w = int((pw-20) * pval / 100)
            cv2.rectangle(resultado,
                           (px+8, y_s-8),
                           (px+8+max(bar_w,1), y_s-2),
                           col, -1)
            cv2.putText(resultado, txt,
                        (px+8, y_s+7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.29,
                        (220,220,220), 1)

    # Leyenda inferior izquierda
    leyenda = [
        ((19,172,77),  t("overlay_seg.leyenda_adecuada")),
        ((32,177,237), t("overlay_seg.leyenda_borderline")),
        ((60,76,231),  t("overlay_seg.leyenda_comprometida")),
    ]
    for i, (color, texto) in enumerate(leyenda):
        y_ley = alto - 52 + i*16
        cv2.rectangle(resultado,
                       (8, y_ley-8), (20, y_ley+2), color, -1)
        cv2.putText(resultado, texto,
                    (26, y_ley),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (200,200,200), 1)

    # Encabezado
    cv2.rectangle(resultado, (0,0), (ancho, 24), (0,0,0), -1)
    cv2.putText(resultado,
                t("overlay_seg.header"),
                (8, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,212,255), 1)

    return resultado

def seg_procesar_video(ruta_video, callback_prog=None):
    # ── Límites de recursos ────────────────────────────────────
    # Cap de resolución: reducir frames grandes evita picos de RAM
    # de varios GB. 320×240 es suficiente para un mapa T1 clínico.
    SEG_MAX_W   = 320
    SEG_MAX_H   = 240
    # Cap de frames: ICG útil en ≤120 s; subsampling si video es más largo
    SEG_MAX_FPS = 15   # fps de procesamiento efectivo

    cap   = cv2.VideoCapture(ruta_video)
    fps   = cap.get(cv2.CAP_PROP_FPS) or 15
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Factor de escala para resolución
    escala  = min(SEG_MAX_W / max(ancho, 1), SEG_MAX_H / max(alto, 1), 1.0)
    proc_w  = max(int(ancho * escala), 1)
    proc_h  = max(int(alto  * escala), 1)

    # Factor de subsampling temporal (tomar 1 de cada N frames)
    step = max(1, int(round(fps / SEG_MAX_FPS)))

    # ── PASADA ÚNICA ──────────────────────────────────────────
    # Objetivos simultáneos:
    #   1. Detectar frame de pico y frame de referencia visual
    #   2. Acumular frames (ya reducidos) para mapa T1
    frame_ref_bgr = None
    pico_frame    = None
    pico_val      = -1.0
    frames_proc   = []        # frames reducidos, uint8
    i_total       = 0         # contador total de frames leídos
    i_proc        = 0         # contador de frames procesados

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Frame de referencia visual (mitad del video, resolución original)
        if i_total == total // 2:
            frame_ref_bgr = frame.copy()

        # Reducir resolución para procesamiento
        if escala < 1.0:
            gris_small = cv2.resize(gris, (proc_w, proc_h),
                                    interpolation=cv2.INTER_AREA)
        else:
            gris_small = gris

        # Detectar frame de pico (a resolución reducida)
        m = float(gris_small.mean())
        if m > pico_val:
            pico_val   = m
            pico_frame = gris_small.copy()

        # Subsampling temporal
        if i_total % step == 0:
            frames_proc.append(gris_small)
            i_proc += 1

        i_total += 1
        if callback_prog and total > 0:
            callback_prog(int(i_total / total * 70))  # 0-70%

    cap.release()

    if not frames_proc:
        # Video vacío o ilegible
        return {"imagen": None, "x_linea": -1, "confianza": 0,
                "n_val": 0, "n_adec": 0, "n_bord": 0, "n_comp": 0}

    # fps efectivo después del subsampling
    fps_proc = fps / step

    # Convertir lista → array numpy (resolución reducida)
    frames_gris = np.array(frames_proc, dtype=np.uint8)
    del frames_proc

    if callback_prog:
        callback_prog(75)

    # ── Segmentar ROI usando frame de pico ────────────────────
    mascara, bbox, contorno = seg_segmentar_roi(pico_frame)

    # ── Calcular mapa T1 pixel a pixel ───────────────────────
    mapa_t1, _ = seg_calcular_mapa_pixel(frames_gris, fps_proc, mascara)
    del frames_gris

    if callback_prog:
        callback_prog(90)

    mapa_color  = seg_colorear_mapa(mapa_t1, mascara)
    x_linea, confianza = seg_calcular_linea(mapa_t1, mascara)

    n_val  = int(np.sum(mapa_t1 >= 0))
    n_adec = int(np.sum((mapa_t1 >= 0) & (mapa_t1 <= T1_ADECUADA)))
    n_bord = int(np.sum(
        (mapa_t1 > T1_ADECUADA) & (mapa_t1 <= T1_BORDERLINE)))
    n_comp = int(np.sum(mapa_t1 > T1_BORDERLINE))

    # Frame de referencia visual: escalar al tamaño de procesamiento si no se capturó
    if frame_ref_bgr is None and i_total > 0:
        frame_ref_bgr = cv2.cvtColor(pico_frame, cv2.COLOR_GRAY2BGR)
    elif frame_ref_bgr is not None and escala < 1.0:
        frame_ref_bgr = cv2.resize(frame_ref_bgr, (proc_w, proc_h),
                                   interpolation=cv2.INTER_AREA)

    if callback_prog:
        callback_prog(95)

    img_overlay = seg_dibujar_overlay(
        frame_ref_bgr, mapa_color, contorno,
        x_linea, confianza, bbox,
        n_adec, n_bord, n_comp, n_val)

    if callback_prog:
        callback_prog(100)

    return {
        "imagen":    img_overlay,
        "x_linea":  x_linea,
        "confianza": confianza,
        "n_val":    n_val,
        "n_adec":   n_adec,
        "n_bord":   n_bord,
        "n_comp":   n_comp,
    }

# ------------------------------------------------------------
# Generador de PDF
# ------------------------------------------------------------

def generar_pdf(tiempo, intensidad, params, resultado,
                color_hex, detalle, aprobados, score,
                nombre_caso, fig_extra=None, seg_extra=None,
                ruta_guardado=None):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, Image, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        if ruta_guardado:
            nombre_pdf = ruta_guardado
        else:
            nombre_pdf = nombre_caso.replace(" ","_") + "_reporte.pdf"
        import tempfile
        fig_path   = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name

        fig, ax = plt.subplots(figsize=(8,3), facecolor=BG_DARK)
        ax.plot(tiempo, intensidad, color=ACENTO, linewidth=1.8)
        ax.fill_between(tiempo, intensidad, alpha=0.15, color=ACENTO)
        pico_idx = np.argmax(intensidad)
        t2v      = tiempo[pico_idx]
        pv       = intensidad[pico_idx]
        idx_t1   = np.where(intensidad >= 0.10*pv)[0]
        if len(idx_t1) > 0:
            ax.axvline(tiempo[idx_t1[0]], color=AMARILLO,
                       linestyle="--", linewidth=1.2,
                       label=f"T1={params['T1']}s")
        ax.axvline(t2v, color=MORADO, linestyle="--",
                   linewidth=1.2, label=f"T2={params['T2']}s")
        ax.set_xlabel("Tiempo (s)", fontsize=8)
        ax.set_ylabel("Intensidad NIR", fontsize=8)
        ax.set_title(f"Curva ICG — {nombre_caso}", fontsize=9)
        ax.legend(fontsize=7)
        plt.tight_layout()
        plt.savefig(fig_path, dpi=130, bbox_inches="tight", facecolor=BG_DARK)
        plt.close(fig)

        doc    = SimpleDocTemplate(nombre_pdf, pagesize=letter,
                                   rightMargin=0.75*inch, leftMargin=0.75*inch,
                                   topMargin=0.75*inch,   bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        CA = colors.HexColor(ACENTO)
        CG = colors.HexColor(GRIS)
        CT = colors.HexColor("#2c3e50")

        sT = ParagraphStyle("t", parent=styles["Title"], fontSize=20,
                             textColor=CA, alignment=TA_CENTER,
                             fontName="Helvetica-Bold")
        sS = ParagraphStyle("s", parent=styles["Normal"], fontSize=9,
                             textColor=CG, alignment=TA_CENTER)
        sH = ParagraphStyle("h", parent=styles["Heading1"], fontSize=11,
                             textColor=CT, fontName="Helvetica-Bold",
                             spaceBefore=10, spaceAfter=5)
        sN = ParagraphStyle("n", parent=styles["Normal"], fontSize=9,
                             textColor=CT, leading=13)
        sP = ParagraphStyle("p", parent=styles["Normal"], fontSize=7,
                             textColor=CG, alignment=TA_CENTER)

        story = []
        story.append(Paragraph("SENTINEL", sT))
        story.append(Paragraph("Motor de Cuantificacion ICG — Reporte Clinico", sS))
        story.append(Paragraph("Universidad de Guadalajara  |  Ingenieria Biomedica", sS))
        story.append(HRFlowable(width="100%", thickness=1.5,
                                 color=CA, spaceAfter=10))
        fecha = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        story.append(Paragraph("Informacion del caso", sH))
        tc = Table([
            ["Caso:",    nombre_caso],
            ["Fecha:",   fecha],
            ["Sistema:", "SENTINEL v2.0 — Tecno-Sheep"],
            ["Ref:",     "Son et al. (2023). Biomedicines 11(7):2029"],
        ], colWidths=[1.5*inch, 5.5*inch])
        tc.setStyle(TableStyle([
            ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
            ("TEXTCOLOR",     (0,0),(0,-1), CT),
            ("TEXTCOLOR",     (1,0),(1,-1), CG),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ]))
        story.append(tc)
        story.append(Spacer(1,8))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=CG, spaceAfter=6))
        story.append(Paragraph("Curva de perfusion ICG", sH))
        story.append(Image(fig_path, width=6.5*inch, height=2.5*inch))
        story.append(Spacer(1,6))

        if fig_extra and os.path.exists(fig_extra):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                     color=CG, spaceAfter=6))
            story.append(Paragraph("Mapa de calor espacial (cuadricula)", sH))
            story.append(Image(fig_extra, width=6.5*inch, height=3.0*inch))
            story.append(Spacer(1,6))

        if seg_extra and os.path.exists(seg_extra):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                     color=CG, spaceAfter=6))
            story.append(Paragraph(
                "Mapa de perfusion pixel a pixel + Linea de seccion", sH))
            story.append(Image(seg_extra, width=6.5*inch, height=3.2*inch))
            story.append(Spacer(1,6))

        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=CG, spaceAfter=6))
        story.append(Paragraph("Parametros cuantitativos", sH))
        enc  = [Paragraph(f"<b>{x}</b>", sN) for x in
                ["Parametro","Valor","Umbral","Estado"]]
        defs = {
            "T1":         ("T1 — Llegada del bolo",   f"{params['T1']} s",    "<= 10 s"),
            "T2":         ("T2 — Tiempo al pico",      f"{params['T2']} s",    "<= 30 s"),
            "pendiente":  ("Pendiente de subida",       f"{params['pendiente']}", ">= 5.0"),
            "indice_NIR": ("Indice NIR",                f"{params['indice_NIR']}", ">= 50"),
        }
        filas = [enc]
        for key, (np_, vp, up) in defs.items():
            ok  = detalle[key]
            col = colors.HexColor(VERDE if ok else ROJO)
            filas.append([
                Paragraph(np_, sN), Paragraph(vp, sN), Paragraph(up, sN),
                Paragraph(f"<b>{'OK' if ok else 'FUERA'}</b>",
                          ParagraphStyle("e", parent=sN,
                                         textColor=col,
                                         fontName="Helvetica-Bold")),
            ])
        tp = Table(filas, colWidths=[2.4*inch,1.2*inch,1.2*inch,2.2*inch])
        tp.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), colors.HexColor("#ecf0f1")),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
            ("GRID",          (0,0),(-1,-1), 0.3, CG),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),
             [colors.white, colors.HexColor("#f8f9fa")]),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ]))
        story.append(tp)

        # ── Parámetros adicionales (informativos) ──────────────────
        fmax_val  = params.get("Fmax")
        thalf_val = params.get("T_half")
        sr_val    = params.get("slope_ratio")
        if any(v is not None for v in [fmax_val, thalf_val, sr_val]):
            sGray = ParagraphStyle("gray", parent=sN,
                                   textColor=colors.HexColor("#7f8c8d"),
                                   fontName="Helvetica-Oblique", fontSize=8)
            filas_add = [
                [Paragraph(f"<b>{x}</b>", sN) for x in
                 ["Parametro adicional", "Valor", "Referencia", "Nota"]],
                # fila separadora con etiqueta
                [Paragraph("<i>Parametros informativos (v2.0)</i>", sGray),
                 Paragraph("", sN), Paragraph("", sN), Paragraph("", sN)],
                [Paragraph("Fmax — Fluorescencia maxima", sN),
                 Paragraph(f"{fmax_val} a.u." if fmax_val is not None else "—", sN),
                 Paragraph(">= 30.0 a.u.", sN),
                 Paragraph("<i>INFORMATIVO</i>", sGray)],
                [Paragraph("T_half — Semi-descenso post-pico", sN),
                 Paragraph(f"{thalf_val} s" if thalf_val is not None else "—", sN),
                 Paragraph("<= 15.0 s", sN),
                 Paragraph("<i>INFORMATIVO</i>", sGray)],
                [Paragraph("Slope ratio — Subida / bajada", sN),
                 Paragraph(f"{sr_val}" if sr_val is not None else "—", sN),
                 Paragraph(">= 0.5", sN),
                 Paragraph("<i>INFORMATIVO</i>", sGray)],
            ]
            ta = Table(filas_add, colWidths=[2.4*inch, 1.2*inch, 1.2*inch, 2.2*inch])
            ta.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#ecf0f1")),
                ("FONTSIZE",      (0, 0), (-1, -1), 9),
                ("GRID",          (0, 0), (-1, -1), 0.3, CG),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f8f9fa")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ]))
            story.append(Spacer(1, 4))
            story.append(ta)

        story.append(Spacer(1,8))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=CG, spaceAfter=6))
        story.append(Paragraph("Resultado global", sH))
        cr  = colors.HexColor(color_hex)
        csc = colors.HexColor(color_score(score))
        tr  = Table([
            [Paragraph("<b>Clasificacion:</b>", sN),
             Paragraph(f"<b>{resultado}</b>",
                       ParagraphStyle("r", parent=sN, textColor=cr,
                                      fontSize=13, fontName="Helvetica-Bold"))],
            [Paragraph("<b>Parametros OK:</b>", sN),
             Paragraph(f"<b>{aprobados} / 4</b>", sN)],
            [Paragraph("<b>Score SENTINEL:</b>", sN),
             Paragraph(f"<b>{score} / 100  ({etiqueta_score(score)})</b>",
                       ParagraphStyle("sc", parent=sN,
                                      textColor=csc, fontSize=11,
                                      fontName="Helvetica-Bold"))],
        ], colWidths=[2.8*inch, 4.2*inch])
        tr.setStyle(TableStyle([
            ("FONTSIZE",      (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#f8f9fa")),
            ("BOX",           (0,0),(-1,-1), 1.0, CA),
            ("LINEBELOW",     (0,0),(-1,-2), 0.3, CG),
        ]))
        story.append(tr)
        story.append(Spacer(1,8))
        interp = {
            "ADECUADA":     "Perfusion tisular adecuada. Se recomienda proceder con la anastomosis.",
            "BORDERLINE":   "Perfusion limitrofe. Considere evaluar un sitio alternativo.",
            "COMPROMETIDA": "Perfusion comprometida. No se recomienda anastomosis en este sitio.",
        }
        story.append(HRFlowable(width="100%", thickness=1.0,
                                 color=CA, spaceBefore=8, spaceAfter=6))
        story.append(Paragraph(interp[resultado], sN))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=CG, spaceBefore=10, spaceAfter=4))
        story.append(Paragraph(
            "SENTINEL v2.0 | Tecno-Sheep | Universidad de Guadalajara | "
            "Herramienta de apoyo clinico. No sustituye el juicio del cirujano.", sP))
        doc.build(story)
        if os.path.exists(fig_path):
            os.remove(fig_path)
        return nombre_pdf
    except ImportError:
        return None

# ------------------------------------------------------------
# Aplicacion principal
# ------------------------------------------------------------

class BioConnectApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.prefs = BioConnectPrefs()          # Preferencias persistentes
        init_desde_prefs(self.prefs)            # Cargar idioma desde preferencias
        self._font_mgr = self._init_fuente()   # Fuente accesible (OpenDyslexic o fallback)
        self._db = BioConnectDB()              # Base de datos de casos clínicos

        # ── Aplicar unidades guardadas ────────────────────────────
        global _UNITS_SYSTEM
        _units_stored = self.prefs.get("units", "Metrico (cm, kg)")
        _UNITS_SYSTEM = {
            "Metrico (cm, kg)": "metric", "Metric (cm, kg)": "metric",
            "Imperial (in, lb)": "imperial",
            "Hibrido": "hybrid", "Hybrid": "hybrid",
        }.get(_units_stored, "metric")

        # ── Aplicar paleta de color guardada (antes de construir la UI) ──
        _paleta_inicial = self.prefs.get("color_palette", "normal")
        if _paleta_inicial and _paleta_inicial != "normal":
            global ACENTO, AMARILLO, BG_CARD, ROJO
            _p = self._PALETAS.get(_paleta_inicial)
            if _p:
                ACENTO   = _p[0]
                ROJO     = _p[0]
                AMARILLO = _p[1]
                BG_CARD  = _p[2]
        self.title("SENTINEL v2.0 — Intraoperative Perfusion Intelligence")
        self.geometry("1100x720")
        self.configure(bg=BG_DARK)
        self.resizable(True, True)
        self._logo_img = self._cargar_logo()    # Logo Tkinter PhotoImage
        self.iconphoto(True, self._logo_img) if self._logo_img else None
        self._build_encabezado()
        self._contenedor = tk.Frame(self, bg=BG_DARK)
        self._contenedor.pack(fill="both", expand=True)
        self._mostrar_inicio()

        # ── Aplicar line_spacing guardado (post-UI) ───────────────
        _spacing_inicial = self.prefs.get("line_spacing", "1.0x (normal)")
        if _spacing_inicial and _spacing_inicial != "1.0x (normal)":
            sp1, sp2, sp3 = self._SPACING_MAP.get(_spacing_inicial, (0, 0, 0))
            self._aplicar_spacing_texto(self, sp1, sp2, sp3)

    # ----------------------------------------------------------
    # Carga del logo como PhotoImage (PNG → Tkinter)
    # ----------------------------------------------------------
    def _init_fuente(self) -> FontManager:
        """Inicializa el gestor de fuentes según la preferencia dyslexic_font."""
        import pathlib
        base = pathlib.Path(__file__).parent
        fm   = FontManager(base_dir=base)

        usar_dyslexic = self.prefs.get("dyslexic_font", False)
        if usar_dyslexic and not fm.disponible:
            # Fuente no instalada aún — intentar instalar desde fonts/
            fm._intentar_cargar()

        # Si dyslexic_font está OFF, forzar fuente normal
        if not usar_dyslexic:
            fm.familia    = "Arial"
            fm.disponible = False

        return fm

    def _cargar_logo(self):
        """Devuelve PhotoImage del icono SENTINEL o None si falla."""
        import pathlib
        base = pathlib.Path(__file__).parent
        ruta = base / "assets" / "logos" / "sentinel-icon-minimalista-64.png"
        try:
            from PIL import Image, ImageTk
            img = Image.open(ruta).resize((64, 64), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _build_encabezado(self):
        enc = tk.Frame(self, bg=BG_PANEL, pady=8)
        enc.pack(fill="x")
        fila = tk.Frame(enc, bg=BG_PANEL)
        fila.pack(fill="x", padx=16)

        # Logo (izquierda)
        if self._logo_img:
            lbl_logo = tk.Label(fila, image=self._logo_img,
                                bg=BG_PANEL, cursor="hand2")
            lbl_logo.pack(side="left", padx=(0, 10))

        # Nombre + tagline
        txt_frame = tk.Frame(fila, bg=BG_PANEL)
        txt_frame.pack(side="left")
        tk.Label(txt_frame, text=t("app.nombre"),
                 font=("Arial", 20, "bold"),
                 fg=ACENTO, bg=BG_PANEL).pack(anchor="w")
        tk.Label(txt_frame, text=t("app.tagline"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(anchor="w")

        # Botones (derecha)
        btn_frame = tk.Frame(fila, bg=BG_PANEL)
        btn_frame.pack(side="right")
        tk.Button(btn_frame, text=t("menu.configuracion"),
                  font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self._abrir_settings).pack(side="right", padx=(6,0))
        self.btn_regresar = tk.Button(
            btn_frame, text=t("menu.inicio"),
            font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._mostrar_inicio)
        self.btn_regresar.pack(side="right")

        # Línea roja SENTINEL
        tk.Frame(enc, bg=ACENTO, height=2).pack(fill="x", pady=(8,0))

    def _limpiar(self):
        for w in self._contenedor.winfo_children():
            w.destroy()

    def _abrir_settings(self):
        """Abre el panel de configuracion SENTINEL."""
        abrir_settings(self, self.prefs,
                       on_change=self._apply_settings_live,
                       on_restart=self.reiniciar_aplicacion)

    def reiniciar_aplicacion(self):
        """Reinicia BioConnect lanzando una nueva instancia y cerrando la actual.

        Estrategia: subprocess.Popen([sys.executable, __file__]) + sys.exit()
        Esto garantiza un inicio limpio (nueva memoria, nueva carga de prefs y i18n).
        """
        import sys
        import subprocess
        try:
            # Lanzar nueva instancia antes de cerrar la actual
            subprocess.Popen([sys.executable, __file__])
        except Exception as e:
            tk.messagebox.showerror(
                "Error al reiniciar",
                f"No se pudo reiniciar automáticamente:\n{e}\n\n"
                "Por favor cierra y vuelve a abrir BioConnect manualmente."
            )
            return
        # Cerrar la instancia actual
        try:
            self.quit()
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    # ----------------------------------------------------------
    # Aplicacion de settings EN VIVO
    # ----------------------------------------------------------

    # Paletas para daltonismo  {codigo_canonico → (primario, secundario, card)}
    # Los codigos son independientes del idioma de la UI
    _PALETAS = {
        "normal":        ("#EF4444", "#FF9900", "#2A2A2A"),
        "protanopia":    ("#2563EB", "#FBBF24", "#1E2A3A"),
        "deuteranopia":  ("#2563EB", "#EF4444", "#1E2A3A"),
        "tritanopia":    ("#EF4444", "#22D3EE", "#1A2A2A"),
        "acromatopsia":  ("#FFFFFF", "#AAAAAA", "#333333"),
    }

    def _apply_settings_live(self, changed: dict):
        """
        Aplica inmediatamente los settings que no requieren reinicio.

        En vivo:
          font_size       → reconfigura fuente de todos los widgets
          units           → actualiza sistema de unidades global
          line_spacing    → actualiza espaciado en widgets Text
          contrast_mode   → ajusta fondos
          high_contrast_max → fondo maximo negro

        Requiere reinicio (aviso ya dado en settings):
          language, dyslexic_font, color_palette
        """
        if "font_size" in changed:
            self._live_font_size(int(changed["font_size"]))
        if "color_palette" in changed:
            # Actualizar globales antes del reinicio (pre-calentamiento visual)
            self._live_color_palette(changed["color_palette"])
        if "units" in changed:
            self._live_units(changed["units"])
        if "line_spacing" in changed:
            self._live_line_spacing(changed["line_spacing"])
        if "contrast_mode" in changed or "high_contrast_max" in changed:
            modo   = self.prefs.get("contrast_mode", "Normal")
            max_hc = self.prefs.get("high_contrast_max", False)
            self._live_contrast(modo, max_hc)
        if "dyslexic_font" in changed:
            self._live_dyslexic_font(changed["dyslexic_font"])

    def _live_dyslexic_font(self, activar: bool):
        """Activa o desactiva la tipografía OpenDyslexic en toda la app.

        Si activar=True y la fuente no está instalada, muestra aviso con
        instrucciones de instalación. Si activar=False, restaura Arial.
        """
        import pathlib
        resetear_font_manager()
        base = pathlib.Path(__file__).parent
        self._font_mgr = FontManager(base_dir=base)

        if activar:
            if self._font_mgr.disponible:
                tamaño = self.prefs.get("font_size", 11)
                self._font_mgr.aplicar_a_arbol(self, tamaño)
            else:
                # Fuente no disponible — mostrar aviso con instrucciones
                tk.messagebox.showwarning(
                    "Tipografia OpenDyslexic",
                    "OpenDyslexic no está instalada en tu sistema.\n\n"
                    "Para instalarla, ejecuta:\n"
                    "  python fonts/INSTALAR_FUENTES.py\n\n"
                    "Luego reinicia BioConnect para aplicar el cambio.\n"
                    f"Fuente actual: {self._font_mgr.familia}"
                )
        else:
            # Restaurar Arial en todo el árbol
            self._font_mgr.familia = "Arial"
            tamaño = self.prefs.get("font_size", 11)
            fuente      = ("Arial", tamaño)
            fuente_bold = ("Arial", tamaño, "bold")
            self._recorrer_widgets_font(self, fuente, fuente_bold)

    def _live_font_size(self, size: int):
        """Actualiza la fuente base de todos los widgets de la app."""
        familia     = self._font_mgr.familia if hasattr(self, "_font_mgr") else "Arial"
        fuente      = (familia, size)
        fuente_bold = (familia, size, "bold")
        self.option_add("*Font", fuente)
        self._recorrer_widgets_font(self, fuente, fuente_bold)

    def _recorrer_widgets_font(self, widget, fuente, fuente_bold):
        tipos = (tk.Label, tk.Button, tk.Entry,
                 tk.Checkbutton, tk.Radiobutton)
        try:
            if isinstance(widget, tipos):
                cfg = str(widget.cget("font"))
                if "Arial" in cfg or cfg in ("TkDefaultFont", ""):
                    bold = "bold" in cfg
                    widget.config(font=fuente_bold if bold else fuente)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._recorrer_widgets_font(child, fuente, fuente_bold)

    def _live_color_palette(self, codigo_paleta: str):
        """Aplica paleta de daltonismo: actualiza globales y recolorea widgets de acento."""
        global ACENTO, AMARILLO, BG_CARD, ROJO
        primario, secundario, card = self._PALETAS.get(
            codigo_paleta, ("#EF4444", "#FF9900", "#2A2A2A"))
        ACENTO   = primario
        ROJO     = primario   # ROJO y ACENTO representan el mismo color de alerta
        AMARILLO = secundario
        BG_CARD  = card
        # Recolorear todos los widgets que usan el color de acento
        self._recolorear_acento(self, primario, secundario)

    def _recolorear_acento(self, widget, primario: str, secundario: str):
        """Recorre el arbol de widgets actualizando colores de acento/alerta."""
        _tipos_coloreables = (tk.Label, tk.Button, tk.Frame,
                              tk.Checkbutton, tk.Radiobutton, tk.Entry)
        _colores_acento = {
            "#EF4444", "#2563EB", "#FFFFFF",          # Primarios conocidos
        }
        _colores_secundario = {
            "#FF9900", "#FBBF24", "#22D3EE", "#AAAAAA",  # Secundarios conocidos
        }
        try:
            if isinstance(widget, _tipos_coloreables):
                cfg_fg = str(widget.cget("fg"))
                cfg_bg = str(widget.cget("bg"))
                if cfg_fg.upper() in {c.upper() for c in _colores_acento}:
                    widget.config(fg=primario)
                elif cfg_fg.upper() in {c.upper() for c in _colores_secundario}:
                    widget.config(fg=secundario)
                if cfg_bg.upper() in {c.upper() for c in _colores_acento}:
                    widget.config(bg=primario)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._recolorear_acento(child, primario, secundario)

    def _refresh_acento_bar(self, color: str):
        """Actualiza la linea roja del encabezado con el nuevo color primario."""
        for child in self.winfo_children():
            if isinstance(child, tk.Frame) and child.cget("bg") == BG_PANEL:
                for sub in child.winfo_children():
                    try:
                        if int(sub.cget("height")) == 2:
                            sub.config(bg=color)
                            return
                    except Exception:
                        pass

    def _live_contrast(self, modo: str, max_hc: bool):
        """Ajusta el nivel de negro del fondo segun contraste."""
        global BG_DARK, BG_PANEL
        if max_hc:
            BG_DARK  = "#000000"
            BG_PANEL = "#0A0A0A"
        elif modo == "Alto contraste":
            BG_DARK  = "#080808"
            BG_PANEL = "#141414"
        else:
            BG_DARK  = "#0F0F0F"
            BG_PANEL = "#1F1F1F"
        self.configure(bg=BG_DARK)

    # ----------------------------------------------------------
    # Sistema de unidades
    # ----------------------------------------------------------
    # Mapa de texto UI → codigo canonico de unidades
    _UNITS_MAP = {
        "Metrico (cm, kg)":   "metric",
        "Metric (cm, kg)":    "metric",
        "Metrisch (cm, kg)":  "metric",
        "Métrique (cm, kg)":  "metric",
        "Métrico (cm, kg)":   "metric",
        "Metrico (cm, kg)":   "metric",
        "公制（cm, kg）":       "metric",
        "メートル法（cm, kg）": "metric",
        "Imperial (in, lb)":  "imperial",
        "Imperiale (in, lb)": "imperial",
        "Impérial (in, lb)":  "imperial",
        "英制（in, lb）":       "imperial",
        "ヤード・ポンド法（in, lb）": "imperial",
        "Hibrido":   "hybrid",
        "Hybrid":    "hybrid",
        "Hybride":   "hybrid",
        "Ibrido":    "hybrid",
        "混合":      "hybrid",
        "ハイブリッド": "hybrid",
    }

    def _live_units(self, modo_display: str):
        """Actualiza el sistema de unidades global y refresca etiquetas de medida."""
        global _UNITS_SYSTEM
        _UNITS_SYSTEM = self._UNITS_MAP.get(modo_display, "metric")

        # Actualizar variables Tkinter vinculadas a unidades (si existen)
        self._actualizar_labels_unidades()

        # Toast de confirmacion
        if _UNITS_SYSTEM == "imperial":
            msg = "Unidades → Imperial (in, lb, oz)"
            emoji_color = AMARILLO
        elif _UNITS_SYSTEM == "hybrid":
            msg = "Unidades → Hibrido (cm + lb)"
            emoji_color = CYAN
        else:
            msg = "Unidades → Metrico (cm, kg)"
            emoji_color = VERDE
        self._mostrar_toast(msg, color=emoji_color)

    def _actualizar_labels_unidades(self):
        """Recorre widgets Label buscando los que muestran medidas con unidad
        y los actualiza segun _UNITS_SYSTEM."""
        self._actualizar_labels_rec(self)

    def _actualizar_labels_rec(self, widget):
        """Recorre el arbol buscando labels con datos de medida registrados."""
        if hasattr(widget, "_unidad_valor") and isinstance(widget, tk.Label):
            # El label tiene metadatos de conversion registrados por la app
            valor_base = widget._unidad_valor   # valor en unidad base (cm o kg)
            tipo       = widget._unidad_tipo    # "longitud" | "masa" | "temp"
            widget.config(text=fmt_unidad(valor_base, tipo))
        for child in widget.winfo_children():
            self._actualizar_labels_rec(child)

    # ----------------------------------------------------------
    # Espaciado de linea
    # ----------------------------------------------------------
    # Mapa de texto UI → tupla (spacing1, spacing2, spacing3) en pixels
    _SPACING_MAP = {
        "1.0x (normal)":     (0,  0, 0),
        "1.4x (comodo)":     (5,  2, 3),
        "1.8x (amplio)":     (10, 4, 6),
        "2.2x (baja vision)":(15, 6, 9),
    }

    def _live_line_spacing(self, modo: str):
        """Aplica espaciado de linea a todos los widgets Text de la app."""
        sp1, sp2, sp3 = self._SPACING_MAP.get(modo, (0, 0, 0))
        self._aplicar_spacing_texto(self, sp1, sp2, sp3)
        self._mostrar_toast(f"Espaciado de linea: {modo}", color=CYAN)

    def _aplicar_spacing_texto(self, widget, sp1: int, sp2: int, sp3: int):
        """Recorre recursivamente el arbol y configura spacing en tk.Text."""
        if isinstance(widget, tk.Text):
            try:
                widget.configure(spacing1=sp1, spacing2=sp2, spacing3=sp3)
                # Actualizar tambien los tags de cuerpo/body si existen
                for tag in ("body", "li", "normal"):
                    try:
                        widget.tag_configure(tag,
                                             spacing1=max(sp1, 2),
                                             spacing3=max(sp3, 1))
                    except Exception:
                        pass
            except Exception:
                pass
        for child in widget.winfo_children():
            self._aplicar_spacing_texto(child, sp1, sp2, sp3)

    # ----------------------------------------------------------
    # Toast de notificacion en vivo
    # ----------------------------------------------------------
    def _mostrar_toast(self, mensaje: str, color: str = "#FF9900",
                       duracion_ms: int = 2800):
        """Muestra un mensaje emergente no bloqueante en la esquina inferior."""
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)        # Sin bordes de ventana
        toast.attributes("-topmost", True)
        toast.configure(bg="#1F1F1F")

        lbl = tk.Label(toast, text=f"  {mensaje}  ",
                       font=("Arial", 9, "bold"),
                       fg=color, bg="#1F1F1F",
                       relief="flat", padx=10, pady=6)
        lbl.pack()

        # Borde de acento
        toast.config(highlightbackground=color,
                     highlightthickness=1)

        # Posicionar en esquina inferior derecha de la ventana principal
        self.update_idletasks()
        rx = self.winfo_rootx()
        ry = self.winfo_rooty()
        rw = self.winfo_width()
        rh = self.winfo_height()
        toast.geometry(f"+{rx + rw - 320}+{ry + rh - 60}")

        # Auto-destruir despues de duracion_ms
        toast.after(duracion_ms, toast.destroy)

    def _mostrar_inicio(self):
        self._limpiar()
        self.btn_regresar.pack_forget()

        # ── Wrapper principal ──────────────────────────────────────
        wrapper = tk.Frame(self._contenedor, bg=BG_DARK)
        wrapper.pack(fill="both", expand=True)

        # ── Encabezado compacto ───────────────────────────────────
        hdr = tk.Frame(wrapper, bg=BG_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text="SENTINEL",
                 font=("Arial", 15, "bold"),
                 fg=ACENTO, bg=BG_PANEL).pack(side="left", padx=(18, 6), pady=8)
        tk.Label(hdr, text=t("inicio.selecciona_modulo"),
                 font=("Arial", 9), fg=GRIS, bg=BG_PANEL).pack(side="left", pady=8)
        tk.Label(hdr,
                 text=f"{t('app.version')}  |  {t('app.referencia')}",
                 font=("Arial", 7), fg="#555555", bg=BG_PANEL).pack(
                     side="right", padx=14, pady=8)

        # ── Canvas scrollable para el grid de módulos ─────────────
        canvas = tk.Canvas(wrapper, bg=BG_DARK, highlightthickness=0)
        sb = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG_DARK)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        # Scroll con rueda del mouse
        def _on_wheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        # ── Definición de categorías ───────────────────────────────
        categorias = [
            {
                "titulo": t("inicio.cat_icg"),
                "color":  ACENTO,
                "modulos": [
                    (t("modulos.tiempo_real.titulo"),
                     t("modulos.tiempo_real.desc"),
                     VERDE,    self._mostrar_tiempo_real),
                    (t("modulos.analizar_video.titulo"),
                     t("modulos.analizar_video.desc"),
                     ACENTO,   self._mostrar_video),
                    (t("modulos.mapa_calor.titulo"),
                     t("modulos.mapa_calor.desc"),
                     AMARILLO, self._mostrar_mapa),
                    (t("modulos.max.titulo"),
                     t("modulos.max.desc"),
                     ROJO,     self._mostrar_max),
                    (t("modulos.quirofano.titulo"),
                     t("modulos.quirofano.desc"),
                     CYAN,     self._mostrar_quirofano),
                    (t("modulos.segmentacion.titulo"),
                     t("modulos.segmentacion.desc"),
                     AZUL_SEG, self._mostrar_segmentacion),
                ],
            },
            {
                "titulo": t("inicio.cat_datos"),
                "color":  CYAN,
                "modulos": [
                    (t("modulos.casos.titulo"),
                     t("modulos.casos.desc"),
                     CYAN,     self._mostrar_casos),
                    (t("modulos.dashboard.titulo"),
                     t("modulos.dashboard.desc"),
                     MORADO,   self._mostrar_dashboard),
                    (t("modulos.historial.titulo"),
                     t("modulos.historial.desc"),
                     GRIS,     self._mostrar_historial),
                    (t("modulos.simulador.titulo"),
                     t("modulos.simulador.desc"),
                     MORADO,   self._mostrar_simulador),
                ],
            },
            {
                "titulo": t("inicio.cat_formacion"),
                "color":  VERDE,
                "modulos": [
                    (t("modulos.ayuda.titulo"),
                     t("modulos.ayuda.desc"),
                     VERDE,    self._mostrar_ayuda),
                    (t("modulos.educacion.titulo"),
                     t("modulos.educacion.desc"),
                     AMARILLO, self._mostrar_educacion),
                    (t("modulos.gen_video.titulo"),
                     t("modulos.gen_video.desc"),
                     VERDE,    self._mostrar_gen_video),
                    (t("modulos.exportacion.titulo"),
                     t("modulos.exportacion.desc"),
                     AMARILLO, self._mostrar_exportacion),
                    (t("modulos.calibracion.titulo"),
                     t("modulos.calibracion.desc"),
                     GRIS,     self._mostrar_calibracion),
                ],
            },
        ]

        COLS = 4          # columnas del grid de tarjetas
        CARD_W = 210      # ancho fijo de tarjeta
        CARD_H = 110      # alto fijo de tarjeta

        for cat in categorias:
            # ── Cabecera de categoría ─────────────────────────────
            cat_hdr = tk.Frame(inner, bg=BG_DARK)
            cat_hdr.pack(fill="x", padx=16, pady=(14, 4))
            tk.Frame(cat_hdr, bg=cat["color"], width=3,
                     height=20).pack(side="left")
            tk.Label(cat_hdr, text=cat["titulo"],
                     font=("Arial", 10, "bold"),
                     fg=cat["color"], bg=BG_DARK).pack(side="left", padx=8)
            tk.Frame(cat_hdr, bg=BORDE, height=1).pack(
                side="left", fill="x", expand=True)

            # ── Grid de tarjetas ──────────────────────────────────
            grid = tk.Frame(inner, bg=BG_DARK)
            grid.pack(fill="x", padx=16, pady=(0, 6))

            for i, (titulo, desc, color, cmd) in enumerate(cat["modulos"]):
                col = i % COLS
                row = i // COLS
                card = tk.Frame(grid, bg=BG_CARD,
                                width=CARD_W, height=CARD_H,
                                highlightbackground=color,
                                highlightthickness=2,
                                cursor="hand2")
                card.grid(row=row, column=col, padx=6, pady=5)
                card.pack_propagate(False)
                card.bind("<Button-1>", lambda e, c=cmd: c())

                tk.Label(card, text=titulo,
                         font=("Arial", 10, "bold"),
                         fg=color, bg=BG_CARD,
                         justify="center").pack(pady=(10, 2))
                tk.Label(card, text=desc,
                         font=("Arial", 7), fg=GRIS, bg=BG_CARD,
                         justify="center", wraplength=CARD_W - 16).pack()
                tk.Button(card, text=t("inicio.abrir"),
                          font=("Arial", 8, "bold"),
                          bg=color,
                          fg=BG_DARK if color in (VERDE, AMARILLO, CYAN) else TEXTO,
                          relief="flat", padx=10, pady=2,
                          cursor="hand2",
                          command=cmd).pack(pady=(5, 0))

        # ── Pie de página ─────────────────────────────────────────
        tk.Label(inner,
                 text=f"{t('app.score_leyenda')}  ·  Bioconnect  ·  UdeG Ingeniería Biomédica",
                 font=("Arial", 7), fg="#444444", bg=BG_DARK).pack(pady=(12, 10))

    def _nav(self, func):
        self._limpiar()
        self.btn_regresar.pack(side="right")
        func()

    # ----------------------------------------------------------
    # Helper centralizado para abrir un video de forma segura
    # en Linux/Wayland/X11 sin congelar el event loop.
    # ----------------------------------------------------------
    def _dialogo_video(self, callback):
        """
        Abre filedialog.askopenfilename en un Toplevel transitorio para
        evitar que la ventana principal congele el event loop en Linux.

        Args:
            callback: función que recibe la ruta seleccionada (o "" si cancela)
        """
        def _abrir():
            # Forzar foco en la ventana principal antes de abrir el diálogo
            self.lift()
            self.focus_force()
            self.update_idletasks()

            ruta = filedialog.askopenfilename(
                parent=self,
                title=t("archivo.seleccionar_video"),
                filetypes=[("Video", "*.avi *.mp4 *.mov"), ("Todos", "*.*")],
                initialdir=os.path.expanduser("~"),
            )
            # Devolver foco a la ventana principal
            self.lift()
            self.focus_force()
            if ruta:
                callback(ruta)

        # Diferir 50 ms para que Tkinter termine de procesar el clic del botón
        self.after(50, _abrir)

    def _dialogo_guardar(self, callback, titulo, ext, filetypes, nombre_inicial, directorio=None):
        """Helper para asksaveasfilename con el mismo patrón seguro."""
        def _abrir():
            self.lift()
            self.focus_force()
            self.update_idletasks()
            ruta = filedialog.asksaveasfilename(
                parent=self,
                title=titulo,
                defaultextension=ext,
                filetypes=filetypes,
                initialfile=nombre_inicial,
                initialdir=directorio or os.path.expanduser("~"),
            )
            self.lift()
            self.focus_force()
            if ruta:
                callback(ruta)

        self.after(50, _abrir)

    def _barra_archivo(self, parent, cmd_cargar,
                        texto_btn="Analizar", cmd_analizar=None):
        barra = tk.Frame(parent, bg=BG_CARD,
                         highlightbackground=BORDE, highlightthickness=1)
        barra.pack(fill="x", pady=(0,8))
        tk.Label(barra, text=t("archivo.etiqueta"), font=("Arial",9),
                 fg=GRIS, bg=BG_CARD).pack(side="left", padx=10, pady=8)
        lbl = tk.Label(barra, text=t("archivo.ningun_archivo"),
                        font=("Arial",9), fg="#aaaaaa", bg=BG_CARD)
        lbl.pack(side="left", padx=4)
        tk.Button(barra, text=t("archivo.cargar_video"),
                  font=("Arial",9,"bold"),
                  bg=ACENTO, fg=BG_DARK, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=cmd_cargar).pack(side="right", padx=10, pady=6)
        if cmd_analizar:
            tk.Button(barra, text=texto_btn,
                      font=("Arial",9,"bold"),
                      bg=VERDE, fg="white", relief="flat",
                      padx=10, pady=4, cursor="hand2",
                      command=cmd_analizar).pack(side="right", padx=4, pady=6)
        return lbl

    def _barra_progreso(self, parent):
        var = tk.IntVar()
        ttk.Progressbar(parent, variable=var,
                         maximum=100).pack(fill="x", pady=(0,6))
        return var

    def _figura_analisis(self, tiempo, intensidad, params,
                          resultado, color, detalle, aprobados, score):
        fig = plt.figure(figsize=(11, 5.2), facecolor=BG_DARK)
        gs  = fig.add_gridspec(2, 3, hspace=0.5, wspace=0.35,
                               left=0.07, right=0.97,
                               top=0.88, bottom=0.10)
        ax1 = fig.add_subplot(gs[:, :2])
        ax1.plot(tiempo, intensidad, color=ACENTO, linewidth=2.0)
        ax1.fill_between(tiempo, intensidad, alpha=0.15, color=ACENTO)
        pico_idx = np.argmax(intensidad)
        t2v      = tiempo[pico_idx]
        pv       = intensidad[pico_idx]
        idx_t1   = np.where(intensidad >= 0.10*pv)[0]
        if len(idx_t1) > 0:
            ax1.axvline(tiempo[idx_t1[0]], color=AMARILLO,
                        linestyle="--", linewidth=1.4,
                        label=f"T1={params['T1']}s")
        ax1.axvline(t2v, color=MORADO, linestyle="--",
                    linewidth=1.4, label=f"T2={params['T2']}s")
        ax1.scatter([t2v], [pv], color=ROJO, s=60, zorder=5)
        ax1.set_xlabel(t("figura_video.eje_tiempo"), fontsize=10)
        ax1.set_ylabel(t("figura_video.eje_intensidad"), fontsize=10)
        ax1.set_title(t("figura_video.titulo_curva"), fontsize=11)
        ax1.legend(fontsize=8)
        ax1.grid(True)
        ax2 = fig.add_subplot(gs[0, 2])
        ax2.set_xlim(0,1); ax2.set_ylim(0,1); ax2.axis("off")
        ax2.set_title(t("figura_video.titulo_params"), fontsize=10)
        etiquetas = {
            "T1":         f"T1={params['T1']}s  (<=10)",
            "T2":         f"T2={params['T2']}s  (<=30)",
            "pendiente":  f"Pend={params['pendiente']}  (>=5)",
            "indice_NIR": f"NIR={params['indice_NIR']}  (>=50)",
        }
        for i, (k, e) in enumerate(etiquetas.items()):
            y  = 0.80 - i*0.16
            c  = VERDE if detalle[k] else ROJO
            s  = "OK" if detalle[k] else "X"
            ax2.add_patch(mpatches.FancyBboxPatch(
                (0.02,y-0.06), 0.96, 0.16,
                boxstyle="round,pad=0.01",
                facecolor=BG_CARD, edgecolor=c, linewidth=1.3))
            ax2.text(0.10, y+0.01, s, color=c,
                     fontsize=11, fontweight="bold", va="center")
            ax2.text(0.24, y+0.01, e, color=TEXTO,
                     fontsize=8, va="center")
        # Parámetros informativos (3 nuevos)
        info_y = 0.12
        ax2.text(0.02, info_y+0.05, "Informativos:", color=CYAN,
                 fontsize=7, va="top", fontweight="bold")
        fmax_val = params.get('Fmax', '—')
        t_half_val = params.get('T_half', '—')
        sr_val = params.get('slope_ratio', '—')
        ax2.text(0.02, info_y-0.02, f"Fmax={fmax_val}  T½={t_half_val}s  SR={sr_val}",
                 color=CYAN, fontsize=7, va="top")
        ax3 = fig.add_subplot(gs[1, 2])
        ax3.set_xlim(0,1); ax3.set_ylim(0,1); ax3.axis("off")
        ax3.set_title(t("figura_video.titulo_resultado"), fontsize=10)
        ax3.add_patch(mpatches.FancyBboxPatch(
            (0.05,0.10), 0.90, 0.82,
            boxstyle="round,pad=0.02",
            facecolor=color+"33", edgecolor=color, linewidth=2.5))
        resultado_txt = {
            "ADECUADA":     t("perfusion.adecuada"),
            "BORDERLINE":   t("perfusion.borderline"),
            "COMPROMETIDA": t("perfusion.comprometida"),
        }.get(resultado, resultado)
        ax3.text(0.50, 0.78, t("figura_video.perfusion"), color=TEXTO,
                 fontsize=9, ha="center", va="center")
        ax3.text(0.50, 0.62, resultado_txt, color=color,
                 fontsize=12, fontweight="bold", ha="center", va="center")
        ax3.text(0.50, 0.48, t("figura_video.params_ok").format(aprobados=aprobados),
                 color=GRIS, fontsize=9, ha="center", va="center")
        csc = color_score(score)
        ax3.text(0.50, 0.34, t("figura_video.score_label"),
                 color=GRIS, fontsize=8, ha="center", va="center")
        ax3.text(0.50, 0.20, f"{score}/100",
                 color=csc, fontsize=12, fontweight="bold",
                 ha="center", va="center")
        ax3.text(0.50, 0.10, etiqueta_score(score),
                 color=csc, fontsize=8, ha="center", va="center")
        _apply_cjk_to_figure(fig)
        return fig

    def _embed_figura(self, parent, fig):
        _apply_cjk_to_figure(fig)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)
        return canvas

    def _preguntar_pdf(self, tiempo, intensidad, params, resultado,
                        color, detalle, aprobados, score, nombre,
                        fig_extra=None, seg_extra=None):
        if not messagebox.askyesno(
            t("pdf.dialogo_titulo"),
            f"{t('perfusion.adecuada') if resultado == 'ADECUADA' else resultado}\n"
            f"Score: {score}/100 — {etiqueta_score(score)}\n\n"
            f"Resultado: PERFUSION {resultado}\n"
            "Desea generar el reporte PDF clinico?"):
            return

        nombre_defecto = nombre.replace(" ", "_") + "_reporte.pdf"
        self.update()
        ruta_pdf = filedialog.asksaveasfilename(
            parent=self,
            title=t("archivo.guardar_reporte"),
            defaultextension=".pdf",
            filetypes=[("Archivo PDF", "*.pdf"), ("Todos los archivos", "*.*")],
            initialfile=nombre_defecto,
            initialdir=self.prefs.pdf_directory or os.path.expanduser("~"),
        )
        if not ruta_pdf:
            return

        self.prefs.pdf_directory = os.path.dirname(ruta_pdf)

        # Pre-capturar strings i18n antes de entrar al hilo
        _titulo_ok   = t("pdf.generado_titulo")
        _msg_ok      = t("pdf.generado_msg")
        _aviso       = t("avisos.aviso")
        _sin_lib     = t("pdf.instalar_lib")
        _generando   = t("pdf.generando") if t("pdf.generando") != "pdf.generando" else "Generando PDF..."
        _error_pdf   = t("pdf.error")    if t("pdf.error")    != "pdf.error"    else "Error al generar PDF"

        # Indicador visual mientras se genera
        _dlg = tk.Toplevel(self)
        _dlg.title(_generando)
        _dlg.resizable(False, False)
        _dlg.grab_set()
        _dlg.configure(bg=BG_DARK)
        sw = _dlg.winfo_screenwidth(); sh = _dlg.winfo_screenheight()
        _dlg.geometry(f"340x90+{(sw-340)//2}+{(sh-90)//2}")
        tk.Label(_dlg, text=_generando, font=("Arial", 11),
                 fg=TEXTO, bg=BG_DARK).pack(pady=(18, 4))
        _bar_var = tk.IntVar(value=0)
        ttk.Progressbar(_dlg, variable=_bar_var, maximum=100,
                        mode="indeterminate").pack(fill="x", padx=20, pady=6)
        _bar_var.set(0)
        _prog_bar = _dlg.children[list(_dlg.children)[-1]]
        _prog_bar.start(12)
        _dlg.update()

        def _generar():
            try:
                pdf = generar_pdf(tiempo, intensidad, params, resultado,
                                  color, detalle, aprobados, score,
                                  nombre, fig_extra, seg_extra,
                                  ruta_guardado=ruta_pdf)
            except Exception as exc:
                pdf = None
                self.after(0, lambda e=str(exc): (
                    _prog_bar.stop(), _dlg.destroy(),
                    messagebox.showerror(_aviso, f"{_error_pdf}\n{e}")
                ))
                return

            def _mostrar():
                _prog_bar.stop()
                _dlg.destroy()
                if pdf:
                    messagebox.showinfo(_titulo_ok, _msg_ok.format(ruta=pdf))
                else:
                    messagebox.showwarning(_aviso, _sin_lib)

            self.after(0, _mostrar)

        threading.Thread(target=_generar, daemon=True).start()

    # ----------------------------------------------------------
    # Simulador
    # ----------------------------------------------------------

    def _mostrar_simulador(self):
        self._nav(self._build_simulador)

    def _build_simulador(self):
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        left = tk.Frame(frame, bg=BG_PANEL, width=270,
                        highlightbackground=BORDE, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0,10))
        left.pack_propagate(False)
        tk.Label(left, text=t("simulador.titulo"),
                 font=("Arial",12,"bold"),
                 fg=MORADO, bg=BG_PANEL).pack(pady=(14,2))
        tk.Label(left, text=t("simulador.instruccion"),
                 font=("Arial",8), fg=GRIS, bg=BG_PANEL,
                 wraplength=230).pack(pady=(0,10))
        self._sim_vars = {}
        sliders = [
            ("T1 — Llegada bolo (s)", "t1",  1,    20,  5),
            ("T2 — Tiempo al pico",   "t2",  5,    55, 20),
            ("Ruido de senal (0–30%)", "pen", 0.0, 0.30, 0.05),
            ("Amplitud de senal",     "amp", 10,  150, 100),
        ]
        for label, key, mn, mx, default in sliders:
            f = tk.Frame(left, bg=BG_PANEL)
            f.pack(fill="x", padx=12, pady=5)
            tk.Label(f, text=label, font=("Arial",8,"bold"),
                     fg="#aaaacc", bg=BG_PANEL, anchor="w").pack(fill="x")
            row = tk.Frame(f, bg=BG_PANEL)
            row.pack(fill="x")
            var = tk.DoubleVar(value=default)
            self._sim_vars[key] = var
            lbl = tk.Label(row, text=f"{default:.2f}",
                           font=("Arial",9,"bold"),
                           fg=ACENTO, bg=BG_PANEL, width=6)
            lbl.pack(side="right")
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient="horizontal",
                      command=lambda v, l=lbl, vr=var:
                          l.config(text=f"{vr.get():.2f}")).pack(
                              side="left", fill="x", expand=True)
        tk.Label(left, text=t("simulador.caso"),
                 font=("Arial",9,"bold"),
                 fg="#aaaacc", bg=BG_PANEL).pack(pady=(12,4))
        self._sim_caso = tk.StringVar(value=t("simulador.casos.personalizado"))
        combo = ttk.Combobox(left, textvariable=self._sim_caso,
                             values=[t("simulador.casos.personalizado"),
                                     t("simulador.casos.caso1"),
                                     t("simulador.casos.caso2"),
                                     t("simulador.casos.caso3")],
                             state="readonly", width=26)
        combo.pack(padx=12)
        combo.bind("<<ComboboxSelected>>", self._sim_cargar_caso)
        btn_f = tk.Frame(left, bg=BG_PANEL)
        btn_f.pack(pady=14, padx=12, fill="x")
        tk.Button(btn_f, text=t("simulador.btn_analizar"),
                  font=("Arial",11,"bold"),
                  bg=MORADO, fg="white", relief="flat",
                  padx=8, pady=7, cursor="hand2",
                  command=self._sim_analizar).pack(fill="x", pady=(0,6))
        tk.Button(btn_f, text=t("simulador.btn_pdf"),
                  font=("Arial",9),
                  bg=BG_CARD, fg=TEXTO, relief="flat",
                  padx=8, pady=5, cursor="hand2",
                  command=self._sim_pdf).pack(fill="x")
        self._sim_right  = tk.Frame(frame, bg=BG_DARK)
        self._sim_right.pack(side="left", fill="both", expand=True)
        self._sim_canvas = None
        self._sim_ultimo = None
        self._sim_analizar()

    def _sim_cargar_caso(self, e=None):
        # Presets calibrados con el modelo Gaussiana+exponencial validado
        # (T1, T2, ruido_pct, amp) — clasificaciones verificadas numéricamente
        presets = {
            "Caso 1 — Adecuada":     (5,  20, 0.05, 100),   # 4/4 ADECUADA
            "Caso 2 — Comprometida": (15, 40, 0.05, 100),   # T1>10 + T2>30 → COMPROMETIDA
            "Caso 3 — Borderline":   (9,  28, 0.05,  60),   # pend≈4.1<5 → BORDERLINE
        }
        c = self._sim_caso.get()
        if c in presets:
            t1,t2,pen,amp = presets[c]
            self._sim_vars["t1"].set(t1)
            self._sim_vars["t2"].set(t2)
            self._sim_vars["pen"].set(pen)
            self._sim_vars["amp"].set(amp)
        self._sim_analizar()

    def _sim_analizar(self):
        t1  = self._sim_vars["t1"].get()
        t2  = self._sim_vars["t2"].get()
        pen = self._sim_vars["pen"].get()
        amp = self._sim_vars["amp"].get()
        tiempo, senal = generar_senal_sintetica(t1, t2, pen, amp)
        params        = extraer_parametros(tiempo, senal)
        resultado, color, aprobados, detalle = clasificar_perfusion(params)
        score         = calcular_score(params)
        self._sim_ultimo = (tiempo, senal, params, resultado,
                             color, detalle, aprobados, score,
                             self._sim_caso.get())
        fig = self._figura_analisis(tiempo, senal, params, resultado,
                                     color, detalle, aprobados, score)
        if self._sim_canvas:
            self._sim_canvas.get_tk_widget().destroy()
        self._sim_canvas = self._embed_figura(self._sim_right, fig)

    def _sim_pdf(self):
        if self._sim_ultimo:
            t,s,p,r,c,d,a,sc,n = self._sim_ultimo
            self._preguntar_pdf(t,s,p,r,c,d,a,sc,n)
        else:
            messagebox.showwarning(t("avisos.aviso"), t("pdf.sin_analisis"))

    # ----------------------------------------------------------
    # Analizar Video
    # ----------------------------------------------------------

    def _mostrar_video(self):
        self._nav(self._build_video)

    def _build_video(self):
        self._vid_ruta   = None
        self._vid_ultimo = None
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        self._vid_lbl  = self._barra_archivo(
            frame, self._vid_cargar, t("modulo_video.btn_analizar"), self._vid_analizar)
        self._vid_prog = self._barra_progreso(frame)
        self._vid_area   = tk.Frame(frame, bg=BG_DARK)
        self._vid_area.pack(fill="both", expand=True)
        self._vid_canvas = None
        bot = tk.Frame(frame, bg=BG_DARK)
        bot.pack(fill="x", pady=(6,0))
        tk.Button(bot, text=t("modulo_video.btn_pdf"),
                  font=("Arial",9),
                  bg=BG_CARD, fg=TEXTO, relief="flat",
                  padx=10, pady=5, cursor="hand2",
                  command=self._vid_pdf).pack(side="right", padx=4)

    def _vid_cargar(self):
        def _set(ruta):
            self._vid_ruta = ruta
            self._vid_lbl.config(text=os.path.basename(ruta))
        self._dialogo_video(_set)

    def _vid_analizar(self):
        if not self._vid_ruta:
            messagebox.showwarning(t("avisos.aviso"), t("avisos.cargar_primero"))
            return
        self._vid_prog.set(0)
        def proceso():
            tiempo, senal = leer_video(self._vid_ruta,
                                        callback=lambda p: self._vid_prog.set(p))
            if tiempo is None:
                self.after(0, lambda: messagebox.showerror(
                    t("avisos.error"), t("avisos.error_leer_video")))
                return
            params    = extraer_parametros(tiempo, senal)
            resultado, color, aprobados, detalle = clasificar_perfusion(params)
            score     = calcular_score(params)
            nombre    = os.path.splitext(os.path.basename(self._vid_ruta))[0]
            self._vid_ultimo = (tiempo, senal, params, resultado,
                                color, detalle, aprobados, score, nombre)
            guardar_historial({
                "fecha":     datetime.now().strftime("%d/%m/%Y %H:%M"),
                "caso":      nombre,
                "resultado": resultado,
                "score":     score,
                "modulo":    "Analizar Video"
            })
            self._db.guardar_caso(
                caso_id=nombre, modulo="Analizar Video",
                resultado=resultado, score=score,
                aprobados=aprobados, params=params,
                ruta_video=getattr(self, "_vid_ruta", ""))
            self.after(0, lambda: self._vid_mostrar(
                tiempo, senal, params, resultado, color, detalle, aprobados, score, nombre))
        threading.Thread(target=proceso, daemon=True).start()

    def _vid_mostrar(self, tiempo, senal, params, resultado,
                      color, detalle, aprobados, score, nombre):
        fig = self._figura_analisis(tiempo, senal, params, resultado,
                                    color, detalle, aprobados, score)
        if self._vid_canvas:
            self._vid_canvas.get_tk_widget().destroy()
        self._vid_canvas = self._embed_figura(self._vid_area, fig)
        self._vid_prog.set(100)
        self._preguntar_pdf(tiempo, senal, params, resultado,
                            color, detalle, aprobados, score, nombre)

    def _vid_pdf(self):
        if self._vid_ultimo:
            self._preguntar_pdf(*self._vid_ultimo)
        else:
            messagebox.showwarning(t("avisos.aviso"), t("pdf.sin_analisis"))

    # ----------------------------------------------------------
    # Mapa de Calor v2
    # ----------------------------------------------------------

    def _mostrar_mapa(self):
        self._nav(self._build_mapa)

    def _build_mapa(self):
        self._mapa_ruta = None
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        enc = tk.Frame(frame, bg=BG_CARD,
                        highlightbackground=AMARILLO, highlightthickness=1)
        enc.pack(fill="x", pady=(0,8))
        tk.Label(enc, text=t("mapa.titulo"),
                 font=("Arial",11,"bold"),
                 fg=AMARILLO, bg=BG_CARD).pack(side="left", padx=12, pady=6)
        tk.Label(enc, text=t("mapa.subtitulo"),
                 font=("Arial",8), fg=GRIS, bg=BG_CARD).pack(
                     side="left", padx=4)
        self._mapa_lbl  = self._barra_archivo(
            frame, self._mapa_cargar, t("figura_mapa.btn_generar"), self._mapa_analizar)
        self._mapa_prog = self._barra_progreso(frame)
        self._mapa_estado = tk.Label(frame, text="",
                                      font=("Arial",9), fg=GRIS, bg=BG_DARK)
        self._mapa_estado.pack()
        self._mapa_area   = tk.Frame(frame, bg=BG_DARK)
        self._mapa_area.pack(fill="both", expand=True)
        self._mapa_canvas = None

    def _mapa_cargar(self):
        def _set(ruta):
            self._mapa_ruta = ruta
            self._mapa_lbl.config(text=os.path.basename(ruta))
        self._dialogo_video(_set)

    def _mapa_analizar(self):
        if not self._mapa_ruta:
            messagebox.showwarning(t("avisos.aviso"), t("avisos.cargar_primero"))
            return
        self._mapa_prog.set(0)
        self._mapa_estado.config(text=t("mapa.extrayendo"), fg=GRIS)
        def proceso():
            curvas, tiempo = extraer_curvas_celda(
                self._mapa_ruta,
                callback=lambda p: self._mapa_prog.set(p))
            if curvas is None:
                messagebox.showerror(t("avisos.error"), t("avisos.error_leer_video"))
                return
            self.after(0, lambda: self._mapa_estado.config(
                text=t("mapa.mascara"), fg=AMARILLO))
            mascara = calcular_mascara(curvas)
            n_val   = int(np.sum(mascara))
            self.after(0, lambda nv=n_val: self._mapa_estado.config(
                text=t("mapa.calculando").format(n=nv), fg=AMARILLO))
            mapa_t1 = calcular_mapa_t1(curvas, tiempo, mascara)
            nombre  = os.path.splitext(os.path.basename(self._mapa_ruta))[0]
            self.after(0, lambda: self._mapa_mostrar(mapa_t1, mascara, nombre))
        threading.Thread(target=proceso, daemon=True).start()

    def _mapa_mostrar(self, mapa_t1, mascara, nombre):
        fig, cnt = figura_mapa_v2(mapa_t1, mascara, nombre)
        if self._mapa_canvas:
            self._mapa_canvas.get_tk_widget().destroy()
        self._mapa_canvas = self._embed_figura(self._mapa_area, fig)
        self._mapa_prog.set(100)
        n_tej = cnt["ADECUADA"] + cnt["BORDERLINE"] + cnt["COMPROMETIDA"]
        self._mapa_estado.config(
            text=t("figura_mapa.estado").format(
                n_tej=n_tej, total=FILAS*COLS,
                adecuada=cnt["ADECUADA"],
                borderline=cnt["BORDERLINE"],
                comprometida=cnt["COMPROMETIDA"]),
            fg=VERDE)

    # ----------------------------------------------------------
    # Tiempo Real
    # ----------------------------------------------------------

    def _mostrar_tiempo_real(self):
        self._nav(self._build_tiempo_real)

    def _build_tiempo_real(self):
        self._tr_ruta = None
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        self._tr_lbl = self._barra_archivo(
            frame, self._tr_cargar, t("tiempo_real.btn_iniciar"), self._tr_iniciar)
        tk.Label(frame,
                 text=t("tiempo_real.instruccion"),
                 font=("Arial",9), fg=GRIS, bg=BG_DARK).pack(pady=6)
        self._tr_estado = tk.Label(frame, text="",
                                    font=("Arial",12,"bold"),
                                    fg=ACENTO, bg=BG_DARK)
        self._tr_estado.pack(pady=10)

    def _tr_cargar(self):
        def _set(ruta):
            self._tr_ruta = ruta
            self._tr_lbl.config(text=os.path.basename(ruta))
        self._dialogo_video(_set)

    def _tr_iniciar(self):
        if not self._tr_ruta:
            messagebox.showwarning(t("avisos.aviso"), t("avisos.cargar_primero"))
            return
        self._tr_estado.config(text=t("tiempo_real.estado_curso"))
        def proceso():
            from BCV1_tiempo_real import analizar_tiempo_real
            nombre = os.path.splitext(os.path.basename(self._tr_ruta))[0]
            analizar_tiempo_real(self._tr_ruta, nombre)
            self.after(0, lambda: self._tr_estado.config(
                text=t("tiempo_real.estado_finalizado")))
        threading.Thread(target=proceso, daemon=True).start()

    # ----------------------------------------------------------
    # Historial
    # ----------------------------------------------------------

    def _mostrar_historial(self):
        self._nav(self._build_historial)

    def _build_historial(self):
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        tk.Label(frame, text=t("historial.titulo"),
                 font=("Arial",12,"bold"),
                 fg=ACENTO, bg=BG_DARK).pack(pady=(0,8))
        cols = ("Fecha","Caso","Resultado","Score","Modulo")
        tree = ttk.Treeview(frame, columns=cols,
                             show="headings", height=20)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=160, anchor="center")
        historial = cargar_historial()
        for h in historial:
            tree.insert("", "end", values=(
                h.get("fecha",""),
                h.get("caso",""),
                h.get("resultado",""),
                f"{h.get('score','')} / 100",
                h.get("modulo",""),
            ))
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        if not historial:
            tk.Label(frame, text=t("historial.vacio"),
                     font=("Arial",11), fg=GRIS, bg=BG_DARK).pack(pady=40)

    # ----------------------------------------------------------
    # Analisis MAX
    # ----------------------------------------------------------

    def _mostrar_max(self):
        self._nav(self._build_max)

    def _build_max(self):
        self._max_ruta = None
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        enc = tk.Frame(frame, bg=BG_CARD,
                        highlightbackground=ROJO, highlightthickness=2)
        enc.pack(fill="x", pady=(0,8))
        tk.Label(enc, text=t("max.titulo"),
                 font=("Arial",13,"bold"),
                 fg=ROJO, bg=BG_CARD).pack(side="left", padx=14, pady=8)
        tk.Label(enc, text=t("max.subtitulo"),
                 font=("Arial",8), fg=GRIS, bg=BG_CARD).pack(
                     side="left", padx=4)
        barra = tk.Frame(frame, bg=BG_CARD,
                          highlightbackground=BORDE, highlightthickness=1)
        barra.pack(fill="x", pady=(0,8))
        tk.Label(barra, text=t("archivo.etiqueta"), font=("Arial",9),
                 fg=GRIS, bg=BG_CARD).pack(side="left", padx=10, pady=8)
        self._max_lbl = tk.Label(barra, text=t("archivo.ningun_archivo"),
                                  font=("Arial",9), fg="#aaaaaa", bg=BG_CARD)
        self._max_lbl.pack(side="left", padx=4)
        tk.Button(barra, text=t("archivo.cargar_video"),
                  font=("Arial",9,"bold"),
                  bg=ACENTO, fg=BG_DARK, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=self._max_cargar).pack(side="right", padx=10, pady=6)
        tk.Button(barra, text=t("max.iniciar"),
                  font=("Arial",10,"bold"),
                  bg=ROJO, fg="white", relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  command=self._max_iniciar).pack(side="right", padx=4, pady=6)
        etapas_frame = tk.Frame(frame, bg=BG_DARK)
        etapas_frame.pack(fill="x", pady=(0,8))
        self._max_progs = {}
        self._max_lbls  = {}
        etapas = [
            ("tr",    t("max.etapa_tr"),    VERDE),
            ("video", t("max.etapa_video"), ACENTO),
            ("mapa",  t("max.etapa_mapa"),  AMARILLO),
            ("seg",   t("max.etapa_seg"),   AZUL_SEG),
            ("pdf",   t("max.etapa_pdf"),   MORADO),
        ]
        for key, nombre, color in etapas:
            f = tk.Frame(etapas_frame, bg=BG_DARK)
            f.pack(fill="x", pady=2, padx=4)
            tk.Label(f, text=f"  {nombre}",
                     font=("Arial",9,"bold"),
                     fg=color, bg=BG_DARK, width=34, anchor="w").pack(side="left")
            var = tk.IntVar()
            ttk.Progressbar(f, variable=var, maximum=100,
                             length=380).pack(side="left", padx=8)
            est = tk.Label(f, text=t("max.esperando"),
                           font=("Arial",8), fg=GRIS, bg=BG_DARK, width=14)
            est.pack(side="left")
            self._max_progs[key] = var
            self._max_lbls[key]  = est
        self._max_nb = ttk.Notebook(frame)
        self._max_nb.pack(fill="both", expand=True)
        self._max_tabs   = {}
        self._max_canvas = {}
        for key, nombre in [("analisis", t("max.tab_analisis")),
                             ("mapa",     t("max.tab_mapa")),
                             ("seg",      t("max.tab_seg"))]:
            tab = tk.Frame(self._max_nb, bg=BG_DARK)
            self._max_nb.add(tab, text=nombre)
            self._max_tabs[key] = tab

    def _max_cargar(self):
        def _set(ruta):
            self._max_ruta = ruta
            self._max_lbl.config(text=os.path.basename(ruta))
        self._dialogo_video(_set)

    def _max_set(self, key, texto, color=GRIS):
        self._max_lbls[key].config(text=texto, fg=color)

    def _max_iniciar(self):
        if not self._max_ruta:
            messagebox.showwarning(t("avisos.aviso"), t("avisos.cargar_primero"))
            return

        # Pedir ubicacion de guardado ANTES de iniciar el hilo
        # (filedialog solo puede usarse desde el hilo principal de Tkinter)
        nombre_base = os.path.splitext(os.path.basename(self._max_ruta))[0]
        nombre_defecto = nombre_base + "_MAX_reporte.pdf"
        ruta_pdf = filedialog.asksaveasfilename(
            parent=self,
            title=t("max.guardar_titulo"),
            defaultextension=".pdf",
            filetypes=[("Archivo PDF", "*.pdf"), ("Todos los archivos", "*.*")],
            initialfile=nombre_defecto,
            initialdir=self.prefs.pdf_directory or None,
        )
        if not ruta_pdf:
            messagebox.showinfo(t("pdf.cancelado_titulo"), t("pdf.cancelado_msg"))
            return
        self.prefs.pdf_directory = os.path.dirname(ruta_pdf)

        for key in self._max_progs:
            self._max_progs[key].set(0)
            self._max_set(key, t("max.esperando"))

        def proceso():
            nombre = nombre_base
            # Pre-capturar strings i18n ANTES de que la variable local _t
            # pueda interferir con la función t() del módulo i18n
            _s_en_curso   = t("max.en_curso")
            _s_completado = t("max.completado")
            _s_error      = t("max.error")
            _s_sin_rl     = t("max.sin_reportlab")
            _s_titulo_ok  = t("max.completado_titulo")
            _s_no_disp    = t("avisos.no_disponible") if t("avisos.no_disponible") != "avisos.no_disponible" else "N/A"

            # Etapa 1 — Tiempo Real
            self.after(0, lambda s=_s_en_curso:   self._max_set("tr", s, VERDE))
            try:
                from BCV1_tiempo_real import analizar_tiempo_real
                analizar_tiempo_real(self._max_ruta, nombre)
            except Exception:
                pass
            self._max_progs["tr"].set(100)
            self.after(0, lambda s=_s_completado: self._max_set("tr", s, VERDE))

            # Etapa 2 — Analisis General
            self.after(0, lambda s=_s_en_curso:   self._max_set("video", s, ACENTO))
            _t, _s = leer_video(self._max_ruta,
                                 callback=lambda p: self._max_progs["video"].set(p))
            if _t is None:
                self.after(0, lambda s=_s_error:  self._max_set("video", s, ROJO))
                return
            params    = extraer_parametros(_t, _s)
            resultado, color, aprobados, detalle = clasificar_perfusion(params)
            score     = calcular_score(params)
            self.after(0, lambda s=_s_completado: self._max_set("video", s, ACENTO))
            fig_a = self._figura_analisis(_t,_s,params,resultado,
                                           color,detalle,aprobados,score)
            self.after(0, lambda f=fig_a: self._max_embed("analisis", f))

            # Etapa 3 — Mapa v2
            self.after(0, lambda s=_s_en_curso:   self._max_set("mapa", s, AMARILLO))
            curvas, tiempo_m = extraer_curvas_celda(
                self._max_ruta,
                callback=lambda p: self._max_progs["mapa"].set(p))
            mapa_path = None
            if curvas is not None:
                mascara = calcular_mascara(curvas)
                mapa_t1 = calcular_mapa_t1(curvas, tiempo_m, mascara)
                fig_m, _ = figura_mapa_v2(mapa_t1, mascara, nombre)
                self.after(0, lambda f=fig_m: self._max_embed("mapa", f))
                mapa_path = "_temp_max_mapa.png"
                fig_m2, _ = figura_mapa_v2(mapa_t1, mascara, nombre)
                fig_m2.savefig(mapa_path, dpi=120, bbox_inches="tight",
                                facecolor=BG_DARK)
                plt.close(fig_m2)
            self.after(0, lambda s=_s_completado: self._max_set("mapa", s, AMARILLO))

            # Etapa 3b — Segmentacion + Linea
            self.after(0, lambda s=_s_en_curso:   self._max_set("seg", s, AZUL_SEG))
            seg_res  = seg_procesar_video(
                self._max_ruta,
                callback_prog=lambda p: self._max_progs["seg"].set(p))
            seg_path = "_temp_max_seg.png"
            cv2.imwrite(seg_path, seg_res["imagen"])
            x_lin    = seg_res["x_linea"]
            conf     = seg_res["confianza"]
            n_val_s  = seg_res["n_val"]
            n_adec_s = seg_res["n_adec"]
            pct_a    = round(100*n_adec_s/n_val_s, 1) if n_val_s > 0 else 0
            self.after(0, lambda i=seg_res["imagen"], x=x_lin,
                        c=conf, p=pct_a:
                self._max_embed_seg(i, x, c, p))
            self.after(0, lambda s=_s_completado: self._max_set("seg", s, AZUL_SEG))

            # Etapa 4 — PDF
            self.after(0, lambda s=_s_en_curso:   self._max_set("pdf", s, MORADO))
            guardar_historial({
                "fecha":     datetime.now().strftime("%d/%m/%Y %H:%M"),
                "caso":      nombre,
                "resultado": resultado,
                "score":     score,
                "modulo":    t("max.titulo"),
            })
            self._db.guardar_caso(
                caso_id=nombre, modulo=t("max.titulo"),
                resultado=resultado, score=score,
                aprobados=aprobados, params=params,
                ruta_video=getattr(self, "_max_ruta", ""))
            self._max_progs["pdf"].set(50)
            pdf = generar_pdf(_t, _s, params, resultado,
                               color, detalle, aprobados, score,
                               nombre + "_MAX", mapa_path, seg_path,
                               ruta_guardado=ruta_pdf)
            self._max_progs["pdf"].set(100)
            for tmp in [mapa_path, seg_path]:
                if tmp and os.path.exists(tmp):
                    os.remove(tmp)

            linea_txt = (f"x={x_lin} px ({conf}%)" if x_lin > 0 else _s_no_disp)
            _msg_resultado = t("max.resultado_lbl").format(resultado=resultado)
            _msg_score     = t("max.score_lbl").format(score=score, etiqueta=etiqueta_score(score))
            _msg_linea     = t("max.linea_lbl").format(linea=linea_txt)
            if pdf:
                self.after(0, lambda s=_s_completado: self._max_set("pdf", s, MORADO))
                _msg_pdf = t("max.reporte_lbl").format(ruta=pdf)
                self.after(0, lambda ti=_s_titulo_ok,
                            m=f"{_msg_resultado}\n{_msg_score}\n{_msg_linea}\n\n{_msg_pdf}":
                    messagebox.showinfo(ti, m))
            else:
                self.after(0, lambda s=_s_sin_rl:  self._max_set("pdf", s, AMARILLO))
                self.after(0, lambda ti=_s_titulo_ok,
                            m=f"{_msg_resultado}\n{_msg_score}\n{_msg_linea}":
                    messagebox.showinfo(ti, m))

        threading.Thread(target=proceso, daemon=True).start()

    def _max_embed(self, key, fig):
        tab = self._max_tabs[key]
        if key in self._max_canvas and self._max_canvas[key]:
            self._max_canvas[key].get_tk_widget().destroy()
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._max_canvas[key] = canvas
        plt.close(fig)

    def _max_embed_seg(self, img_bgr, x_linea, confianza, pct_adec):
        tab = self._max_tabs["seg"]
        if "seg" in self._max_canvas and self._max_canvas["seg"]:
            self._max_canvas["seg"].get_tk_widget().destroy()
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), facecolor=BG_DARK)
        fig.suptitle(t("figura_seg.suptitle_max"),
                     fontsize=11, fontweight="bold")
        axes[0].imshow(img_rgb)
        axes[0].set_title(t("figura_seg.overlay_titulo"), fontsize=10)
        axes[0].axis("off")
        axes[1].set_facecolor(BG_PANEL)
        axes[1].set_xlim(0,1); axes[1].set_ylim(0,1)
        axes[1].axis("off")
        axes[1].set_title(t("figura_seg.linea_titulo"), fontsize=10)
        if x_linea > 0:
            axes[1].add_patch(mpatches.FancyBboxPatch(
                (0.05,0.50), 0.90, 0.30,
                boxstyle="round,pad=0.02",
                facecolor="#003300", edgecolor=VERDE, linewidth=2))
            axes[1].text(0.50, 0.70,
                         t("figura_seg.linea_sugerida").format(x=x_linea),
                         color=VERDE, fontsize=11,
                         ha="center", va="center", fontweight="bold")
            axes[1].text(0.50, 0.58,
                         t("figura_seg.info_confianza").format(
                             conf=confianza, pct=pct_adec),
                         color=VERDE, fontsize=9,
                         ha="center", va="center")
        else:
            axes[1].add_patch(mpatches.FancyBboxPatch(
                (0.05,0.50), 0.90, 0.30,
                boxstyle="round,pad=0.02",
                facecolor="#330000", edgecolor=ROJO, linewidth=2))
            axes[1].text(0.50, 0.65,
                         t("figura_seg.sin_zona_max"),
                         color=ROJO, fontsize=10,
                         ha="center", va="center", fontweight="bold")
        axes[1].text(0.50, 0.35,
                     t("figura_seg.leyenda_colores"),
                     color=GRIS, fontsize=7,
                     ha="center", va="center")
        axes[1].text(0.50, 0.12,
                     t("figura_seg.referencia"),
                     color=GRIS, fontsize=7,
                     ha="center", va="center")
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._max_canvas["seg"] = canvas
        plt.close(fig)

    # ----------------------------------------------------------
    # Modo Quirofano (Beta)
    # ----------------------------------------------------------

    def _mostrar_quirofano(self):
        self._nav(self._build_quirofano)

    def _build_quirofano(self):
        self._q_activo       = False
        self._q_cap          = None
        self._q_intensidades = []
        self._q_canvas_fig   = None
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        enc = tk.Frame(frame, bg=BG_CARD,
                        highlightbackground=CYAN, highlightthickness=2)
        enc.pack(fill="x", pady=(0,8))
        tk.Label(enc, text=t("quirofano.titulo"),
                 font=("Arial",13,"bold"),
                 fg=CYAN, bg=BG_CARD).pack(side="left", padx=14, pady=8)
        tk.Label(enc, text=t("quirofano.subtitulo"),
                 font=("Arial",8), fg=GRIS, bg=BG_CARD).pack(
                     side="left", padx=4)
        aviso = tk.Frame(frame, bg="#1a1a00",
                          highlightbackground=AMARILLO, highlightthickness=1)
        aviso.pack(fill="x", pady=(0,8))
        tk.Label(aviso,
                 text=t("quirofano.aviso"),
                 font=("Arial",8), fg=AMARILLO, bg="#1a1a00",
                 justify="left").pack(padx=12, pady=8)
        ctrl = tk.Frame(frame, bg=BG_CARD,
                         highlightbackground=BORDE, highlightthickness=1)
        ctrl.pack(fill="x", pady=(0,8))
        tk.Label(ctrl, text=t("quirofano.indice"),
                 font=("Arial",9), fg=GRIS, bg=BG_CARD).pack(
                     side="left", padx=10, pady=8)
        self._q_idx = tk.IntVar(value=0)
        ttk.Spinbox(ctrl, from_=0, to=10,
                    textvariable=self._q_idx,
                    width=5).pack(side="left", padx=4)
        tk.Label(ctrl, text=t("quirofano.nota_indice"),
                 font=("Arial",8), fg=GRIS, bg=BG_CARD).pack(
                     side="left", padx=8)
        tk.Button(ctrl, text=t("quirofano.conectar"),
                  font=("Arial",10,"bold"),
                  bg=CYAN, fg=BG_DARK, relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  command=self._q_iniciar).pack(side="right", padx=10, pady=6)
        tk.Button(ctrl, text=t("quirofano.detener"),
                  font=("Arial",10,"bold"),
                  bg=ROJO, fg="white", relief="flat",
                  padx=14, pady=5, cursor="hand2",
                  command=self._q_detener).pack(side="right", padx=4, pady=6)
        self._q_estado = tk.Label(frame, text=t("quirofano.desconectada"),
                                   font=("Arial",10,"bold"),
                                   fg=GRIS, bg=BG_DARK)
        self._q_estado.pack(pady=4)
        area = tk.Frame(frame, bg=BG_DARK)
        area.pack(fill="both", expand=True)
        self._q_left = tk.Frame(area, bg=BG_PANEL,
                                 highlightbackground=BORDE,
                                 highlightthickness=1)
        self._q_left.pack(side="left", fill="both",
                           expand=True, padx=(0,6))
        tk.Label(self._q_left, text=t("quirofano.feed"),
                 font=("Arial",9,"bold"),
                 fg=CYAN, bg=BG_PANEL).pack(pady=4)
        self._q_feed = tk.Label(self._q_left, bg=BG_PANEL,
                                 text=t("quirofano.sin_senal"),
                                 font=("Arial",12), fg=GRIS)
        self._q_feed.pack(fill="both", expand=True)
        self._q_right = tk.Frame(area, bg=BG_PANEL,
                                  highlightbackground=BORDE,
                                  highlightthickness=1)
        self._q_right.pack(side="left", fill="both",
                            expand=True, padx=(6,0))
        tk.Label(self._q_right, text="Curva ICG en tiempo real",
                 font=("Arial",9,"bold"),
                 fg=CYAN, bg=BG_PANEL).pack(pady=4)
        self._q_fig_frame = tk.Frame(self._q_right, bg=BG_PANEL)
        self._q_fig_frame.pack(fill="both", expand=True)
        self._q_resultado = tk.Label(self._q_right,
                                      text="Esperando senal...",
                                      font=("Arial",11,"bold"),
                                      fg=GRIS, bg=BG_PANEL)
        self._q_resultado.pack(pady=6)

    def _q_iniciar(self):
        if self._q_activo:
            return
        idx = self._q_idx.get()
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            messagebox.showerror(
                "Error de camara",
                f"No se pudo conectar a la camara {idx}.\n\n"
                "Verifique que:\n"
                "  - La camara este conectada\n"
                "  - El indice sea correcto\n"
                "  - Ningun otro programa la este usando")
            return
        self._q_cap          = cap
        self._q_activo       = True
        self._q_intensidades = []
        self._q_estado.config(
            text=f"Camara {idx} conectada — Analizando...", fg=VERDE)
        threading.Thread(target=self._q_loop, daemon=True).start()

    def _q_detener(self):
        self._q_activo = False
        if self._q_cap:
            self._q_cap.release()
            self._q_cap = None
        self._q_estado.config(text="Camara desconectada", fg=GRIS)
        self._q_resultado.config(text="Esperando senal...", fg=GRIS)

    def _q_loop(self):
        import time
        fps_cam   = self._q_cap.get(cv2.CAP_PROP_FPS) or 15
        ancho     = int(self._q_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto      = int(self._q_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        x1=int(ancho*0.30); x2=int(ancho*0.70)
        y1=int(alto*0.30);  y2=int(alto*0.70)
        frame_idx = 0
        while self._q_activo:
            ret, frame = self._q_cap.read()
            if not ret:
                break
            gris       = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            intensidad = float(np.mean(gris[y1:y2, x1:x2]))
            self._q_intensidades.append(intensidad)
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,255), 2)
            cv2.putText(frame, f"ROI: {intensidad:.1f}",
                        (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (0,255,255), 1)
            cv2.putText(frame, "SENTINEL — Modo Quirofano",
                        (10,24), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (77,172,48), 1)
            if frame_idx % max(1, int(fps_cam)) == 0 and \
               len(self._q_intensidades) > 30:
                tiempo_arr = np.linspace(0,
                    len(self._q_intensidades)/fps_cam,
                    len(self._q_intensidades))
                intens_arr = np.array(self._q_intensidades, dtype=np.float32)
                if len(intens_arr) > 21:
                    intens_arr = savgol_filter(intens_arr, 21, 3)
                intens_arr = np.clip(intens_arr, 0, None)
                params     = extraer_parametros(tiempo_arr, intens_arr)
                resultado, color_res, aprobados, detalle = \
                    clasificar_perfusion(params)
                score = calcular_score(params)
                self.after(0, lambda t=tiempo_arr, s=intens_arr,
                            p=params, r=resultado, c=color_res,
                            a=aprobados, sc=score:
                    self._q_actualizar_curva(t,s,p,r,c,a,sc))
            try:
                from PIL import Image, ImageTk
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img       = Image.fromarray(frame_rgb)
                img       = img.resize((460, 320))
                imgtk     = ImageTk.PhotoImage(image=img)
                self.after(0, lambda i=imgtk: self._q_set_feed(i))
            except ImportError:
                pass
            frame_idx += 1
            time.sleep(1.0 / max(fps_cam, 1))
        self.after(0, lambda: self._q_estado.config(
            text="Camara desconectada", fg=GRIS))

    def _q_set_feed(self, imgtk):
        self._q_feed.config(image=imgtk, text="")
        self._q_feed.image = imgtk

    def _q_actualizar_curva(self, tiempo, intensidad, params,
                              resultado, color, aprobados, score):
        n   = min(len(tiempo), 300)
        fig = plt.figure(figsize=(5.5, 3.2), facecolor=BG_DARK)
        ax  = fig.add_subplot(111)
        ax.plot(tiempo[-n:], intensidad[-n:], color=ACENTO, linewidth=1.8)
        ax.fill_between(tiempo[-n:], intensidad[-n:],
                         alpha=0.15, color=ACENTO)
        ax.set_xlabel("Tiempo (s)", fontsize=8)
        ax.set_ylabel("Intensidad NIR", fontsize=8)
        ax.set_title(f"T1={params['T1']}s  T2={params['T2']}s  "
                     f"NIR={params['indice_NIR']}", fontsize=8)
        ax.grid(True)
        plt.tight_layout()
        if self._q_canvas_fig:
            self._q_canvas_fig.get_tk_widget().destroy()
        canvas = FigureCanvasTkAgg(fig, master=self._q_fig_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._q_canvas_fig = canvas
        plt.close(fig)
        csc = color_score(score)
        self._q_resultado.config(
            text=f"PERFUSION {resultado}  |  "
                 f"Score: {score}/100  |  {etiqueta_score(score)}",
            fg=color)

    # ----------------------------------------------------------
    # Segmentacion + Mapa Pixel + Linea de Seccion
    # ----------------------------------------------------------

    def _mostrar_segmentacion(self):
        self._nav(self._build_segmentacion)

    def _build_segmentacion(self):
        self._seg_ruta   = None
        self._seg_ultimo = None
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        enc = tk.Frame(frame, bg=BG_CARD,
                        highlightbackground=AZUL_SEG, highlightthickness=2)
        enc.pack(fill="x", pady=(0,8))
        tk.Label(enc, text=t("build_seg.titulo"),
                 font=("Arial",12,"bold"),
                 fg=AZUL_SEG, bg=BG_CARD).pack(side="left", padx=14, pady=8)
        info = tk.Frame(frame, bg="#001a1a",
                         highlightbackground=AZUL_SEG, highlightthickness=1)
        info.pack(fill="x", pady=(0,8))
        tk.Label(info,
                 text=t("build_seg.descripcion"),
                 font=("Arial",8), fg=AZUL_SEG, bg="#001a1a",
                 justify="left").pack(padx=12, pady=8)
        self._seg_lbl  = self._barra_archivo(
            frame, self._seg_cargar, t("build_seg.btn_analizar"), self._seg_analizar)
        self._seg_prog = self._barra_progreso(frame)
        self._seg_estado = tk.Label(frame, text="",
                                     font=("Arial",9,"bold"),
                                     fg=GRIS, bg=BG_DARK)
        self._seg_estado.pack(pady=4)
        self._seg_area   = tk.Frame(frame, bg=BG_DARK)
        self._seg_area.pack(fill="both", expand=True)
        self._seg_canvas = None
        bot = tk.Frame(frame, bg=BG_DARK)
        bot.pack(fill="x", pady=(6,0))
        tk.Button(bot, text=t("segmentacion.guardar"),
                  font=("Arial",9),
                  bg=BG_CARD, fg=TEXTO, relief="flat",
                  padx=10, pady=5, cursor="hand2",
                  command=self._seg_guardar).pack(side="right", padx=4)

    def _seg_cargar(self):
        def _set(ruta):
            self._seg_ruta = ruta
            self._seg_lbl.config(text=os.path.basename(ruta))
        self._dialogo_video(_set)

    def _seg_analizar(self):
        if not self._seg_ruta:
            messagebox.showwarning(t("avisos.aviso"), t("avisos.cargar_primero"))
            return
        self._seg_prog.set(0)
        self._seg_estado.config(
            text=t("segmentacion.procesando"), fg=AMARILLO)

        def proceso():
            res = seg_procesar_video(
                self._seg_ruta,
                callback_prog=lambda p: self._seg_prog.set(int(p*0.95)))
            nombre = os.path.splitext(
                os.path.basename(self._seg_ruta))[0]
            self._seg_ultimo = {**res, "nombre": nombre}
            _seg_score = round(100*res["n_adec"]/res["n_val"], 1) if res["n_val"] > 0 else 0
            guardar_historial({
                "fecha":     datetime.now().strftime("%d/%m/%Y %H:%M"),
                "caso":      nombre,
                "resultado": "SEGMENTACION",
                "score":     _seg_score,
                "modulo":    "Segmentacion+Linea"
            })
            self._db.guardar_caso(
                caso_id=nombre, modulo="Segmentacion+Linea",
                resultado="SEGMENTACION", score=_seg_score,
                aprobados=0, params={},
                ruta_video=getattr(self, "_seg_ruta", ""))
            self._seg_prog.set(100)
            self.after(0, self._seg_mostrar)

        threading.Thread(target=proceso, daemon=True).start()

    def _seg_mostrar(self):
        if not self._seg_ultimo:
            return
        d       = self._seg_ultimo
        img_rgb = cv2.cvtColor(d["imagen"], cv2.COLOR_BGR2RGB)
        nombre  = d["nombre"]

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.8),
                                  facecolor=BG_DARK)
        fig.suptitle(
            t("figura_seg.titulo_fig").format(nombre=nombre),
            fontsize=11, fontweight="bold")

        axes[0].imshow(img_rgb)
        axes[0].set_title(t("figura_seg.ax0_titulo"), fontsize=10)
        axes[0].axis("off")

        axes[1].set_facecolor(BG_PANEL)
        axes[1].set_xlim(0,1); axes[1].set_ylim(0,1)
        axes[1].axis("off")
        axes[1].set_title(t("figura_seg.ax1_titulo"), fontsize=10)

        n_val  = d["n_val"]
        n_adec = d["n_adec"]
        n_bord = d["n_bord"]
        n_comp = d["n_comp"]
        pct_a  = 100*n_adec//n_val if n_val>0 else 0
        pct_b  = 100*n_bord//n_val if n_val>0 else 0
        pct_c  = 100*n_comp//n_val if n_val>0 else 0

        datos = [
            (VERDE,    f"{t('figura_seg.adecuada')}     {n_adec:>7} px  ({pct_a}%)"),
            (AMARILLO, f"{t('figura_seg.borderline')}   {n_bord:>7} px  ({pct_b}%)"),
            (ROJO,     f"{t('figura_seg.comprometida')} {n_comp:>7} px  ({pct_c}%)"),
        ]
        for i, (color, texto) in enumerate(datos):
            y = 0.78 - i*0.16
            axes[1].add_patch(mpatches.FancyBboxPatch(
                (0.02, y-0.06), 0.96, 0.13,
                boxstyle="round,pad=0.01",
                facecolor=BG_CARD, edgecolor=color, linewidth=1.5))
            axes[1].text(0.08, y+0.01, texto,
                         color=TEXTO, fontsize=9,
                         va="center", fontfamily="monospace")

        if d["x_linea"] > 0:
            axes[1].add_patch(mpatches.FancyBboxPatch(
                (0.02, 0.22), 0.96, 0.16,
                boxstyle="round,pad=0.01",
                facecolor="#003300", edgecolor=VERDE, linewidth=2))
            axes[1].text(0.50, 0.32,
                         t("figura_seg.linea_x").format(x=d["x_linea"]),
                         color=VERDE, fontsize=9,
                         ha="center", va="center", fontweight="bold")
            axes[1].text(0.50, 0.24,
                         t("figura_seg.confianza").format(pct=d["confianza"]),
                         color=VERDE, fontsize=8,
                         ha="center", va="center")
        else:
            axes[1].add_patch(mpatches.FancyBboxPatch(
                (0.02, 0.22), 0.96, 0.16,
                boxstyle="round,pad=0.01",
                facecolor="#330000", edgecolor=ROJO, linewidth=2))
            axes[1].text(0.50, 0.30,
                         t("figura_seg.sin_zona"),
                         color=ROJO, fontsize=9,
                         ha="center", va="center", fontweight="bold")

        axes[1].text(0.50, 0.10,
                     "Ref: Son et al. (2023)",
                     color=GRIS, fontsize=7,
                     ha="center", va="center")

        plt.tight_layout()

        if self._seg_canvas:
            self._seg_canvas.get_tk_widget().destroy()
        self._seg_canvas = self._embed_figura(self._seg_area, fig)

        linea_txt = (t("figura_seg.linea_ok").format(x=d["x_linea"], conf=d["confianza"])
                     if d["x_linea"] > 0 else t("figura_seg.sin_zona_corta"))
        self._seg_estado.config(
            text=t("figura_seg.estado").format(
                n_val=n_val, pct_a=pct_a, pct_b=pct_b,
                pct_c=pct_c, linea=linea_txt),
            fg=VERDE)

    def _seg_guardar(self):
        if not self._seg_ultimo:
            messagebox.showwarning(t("avisos.aviso"), t("pdf.sin_analisis"))
            return
        nombre = self._seg_ultimo["nombre"].replace(" ","_") + \
                 "_segmentacion.png"
        cv2.imwrite(nombre, self._seg_ultimo["imagen"])
        messagebox.showinfo(t("avisos.guardado"), t("avisos.imagen_guardada").format(nombre=nombre))


    # ===========================================================
    # CASOS CLÍNICOS — Base de datos con anotaciones
    # ===========================================================

    def _mostrar_casos(self):
        self._nav(self._build_casos)

    def _build_casos(self):
        self._casos_id_seleccionado = None      # ID SQLite del caso seleccionado

        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        # ---------- Encabezado + barra de herramientas ----------
        hdr = tk.Frame(frame, bg=BG_DARK)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text=t("casos.titulo"),
                 font=("Arial", 12, "bold"),
                 fg=CYAN, bg=BG_DARK).pack(side="left")
        tk.Label(hdr, text=t("casos.subtitulo"),
                 font=("Arial", 8), fg=GRIS, bg=BG_DARK).pack(side="left", padx=8)

        # Botones derecha
        btn_bar = tk.Frame(hdr, bg=BG_DARK)
        btn_bar.pack(side="right")

        def _exportar():
            ruta = filedialog.asksaveasfilename(
                parent=self,
                title=t("casos.exportar_csv"),
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
                initialfile="bioconnect_casos.csv")
            if ruta:
                casos_act = self._db.cargar_casos()
                n = self._db.exportar_csv(ruta, casos_act)
                messagebox.showinfo(t("avisos.guardado"),
                                    t("casos.exportar_ok").format(n=n, ruta=ruta))

        tk.Button(btn_bar, text=t("casos.exportar_csv"),
                  font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=_exportar).pack(side="right", padx=(4, 0))

        self._casos_btn_comparar = tk.Button(
                  btn_bar, text=t("casos.comparar"),
                  font=("Arial", 9), bg=BG_CARD, fg=GRIS,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  state="disabled",
                  command=self._casos_comparar)
        self._casos_btn_comparar.pack(side="right", padx=4)

        # Contador de selección + hint para multi-select
        hint_frame = tk.Frame(frame, bg=BG_DARK)
        hint_frame.pack(fill="x", padx=6, pady=(0, 2))
        tk.Label(hint_frame, text=t("casos.comparar_hint"),
                 font=("Arial", 7), fg=GRIS, bg=BG_DARK).pack(side="left")
        self._casos_sel_lbl = tk.Label(
            hint_frame, text=t("casos.sel_count").format(n=0),
            font=("Arial", 7, "bold"), fg=GRIS, bg=BG_DARK)
        self._casos_sel_lbl.pack(side="right")

        # ---------- Barra de filtros ----------
        filtros = tk.Frame(frame, bg=BG_PANEL,
                           highlightbackground=BORDE, highlightthickness=1)
        filtros.pack(fill="x", pady=(0, 6))

        tk.Label(filtros, text=t("casos.filtro_modulo"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(
            side="left", padx=(10, 2), pady=6)
        self._casos_var_mod = tk.StringVar(value=t("casos.filtro_todos"))
        modulos_lista = [t("casos.filtro_todos")] + self._db.modulos_disponibles()
        self._casos_combo_mod = ttk.Combobox(
            filtros, textvariable=self._casos_var_mod,
            values=modulos_lista, state="readonly", width=18)
        self._casos_combo_mod.pack(side="left", padx=(0, 10), pady=6)

        tk.Label(filtros, text=t("casos.filtro_resultado"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(side="left", padx=(0, 2))
        self._casos_var_res = tk.StringVar(value=t("casos.filtro_todos"))
        ttk.Combobox(filtros, textvariable=self._casos_var_res,
                     values=[t("casos.filtro_todos"),
                             "ADECUADA", "BORDERLINE", "COMPROMETIDA", "SEGMENTACION"],
                     state="readonly", width=16).pack(side="left", padx=(0, 10), pady=6)

        tk.Label(filtros, text=t("casos.buscar"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(side="left", padx=(0, 2))
        self._casos_var_busq = tk.StringVar()
        ent = tk.Entry(filtros, textvariable=self._casos_var_busq,
                       font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                       relief="flat", insertbackground=TEXTO, width=20)
        ent.pack(side="left", pady=6)

        tk.Button(filtros, text="🔍",
                  font=("Arial", 9), bg=CYAN, fg=BG_DARK,
                  relief="flat", padx=6, cursor="hand2",
                  command=self._casos_recargar).pack(side="left", padx=4)

        self._casos_var_mod.trace_add("write",  lambda *_: self._casos_recargar())
        self._casos_var_res.trace_add("write",  lambda *_: self._casos_recargar())

        # ---------- Layout principal: tabla + panel detalle ----------
        main = tk.Frame(frame, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        # Tabla izquierda
        tabla_frame = tk.Frame(main, bg=BG_DARK)
        tabla_frame.pack(side="left", fill="both", expand=True)

        cols = (t("casos.col_fecha"), t("casos.col_caso"), t("casos.col_resultado"),
                t("casos.col_score"), t("casos.col_aprobados"),
                t("casos.col_modulo"), t("casos.col_dx_cir"))
        self._casos_tree = ttk.Treeview(
            tabla_frame, columns=cols, show="headings",
            height=18, selectmode="extended")
        anchos = [120, 160, 110, 70, 60, 130, 110]
        for c, w in zip(cols, anchos):
            self._casos_tree.heading(c, text=c,
                command=lambda col=c: self._casos_ordenar(col))
            self._casos_tree.column(c, width=w, anchor="center")

        sb_v = ttk.Scrollbar(tabla_frame, orient="vertical",
                             command=self._casos_tree.yview)
        sb_h = ttk.Scrollbar(tabla_frame, orient="horizontal",
                             command=self._casos_tree.xview)
        self._casos_tree.configure(yscrollcommand=sb_v.set,
                                   xscrollcommand=sb_h.set)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self._casos_tree.pack(fill="both", expand=True)
        self._casos_tree.bind("<<TreeviewSelect>>", self._casos_on_select)

        # Tags de color para filas
        self._casos_tree.tag_configure("ADECUADA",     foreground=VERDE)
        self._casos_tree.tag_configure("BORDERLINE",   foreground=AMARILLO)
        self._casos_tree.tag_configure("COMPROMETIDA", foreground=ACENTO)

        # Panel derecho: detalle + anotación
        detalle = tk.Frame(main, bg=BG_PANEL, width=270,
                           highlightbackground=BORDE, highlightthickness=1)
        detalle.pack(side="right", fill="y", padx=(8, 0))
        detalle.pack_propagate(False)

        tk.Label(detalle, text=t("casos.detalle_titulo"),
                 font=("Arial", 10, "bold"),
                 fg=CYAN, bg=BG_PANEL).pack(pady=(12, 4), padx=10, anchor="w")
        tk.Frame(detalle, bg=BORDE, height=1).pack(fill="x", padx=8)

        # Parámetros del caso seleccionado
        self._casos_lbl_info = tk.Label(
            detalle, text="—\nSelecciona un caso",
            font=("Arial", 9), fg=GRIS, bg=BG_PANEL,
            justify="left", wraplength=240)
        self._casos_lbl_info.pack(padx=10, pady=8, anchor="w")

        tk.Frame(detalle, bg=BORDE, height=1).pack(fill="x", padx=8)

        # Anotación clínica
        tk.Label(detalle, text=t("casos.anotacion_titulo"),
                 font=("Arial", 9, "bold"),
                 fg=AMARILLO, bg=BG_PANEL).pack(pady=(10, 4), padx=10, anchor="w")

        tk.Label(detalle, text=t("casos.dx_cirujano"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(padx=10, anchor="w")
        self._casos_dx_var = tk.StringVar()
        ttk.Combobox(detalle, textvariable=self._casos_dx_var,
                     values=["", "ADECUADA", "BORDERLINE", "COMPROMETIDA",
                             "NO EVALUADO"],
                     width=22).pack(padx=10, pady=(2, 6))

        tk.Label(detalle, text=t("casos.etiquetas"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(padx=10, anchor="w")
        self._casos_etiq_var = tk.StringVar()
        tk.Entry(detalle, textvariable=self._casos_etiq_var,
                 font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                 relief="flat", insertbackground=TEXTO,
                 width=25).pack(padx=10, pady=(2, 6))

        tk.Label(detalle, text=t("casos.notas"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL).pack(padx=10, anchor="w")
        self._casos_txt_notas = tk.Text(
            detalle, height=5, font=("Arial", 9),
            bg=BG_CARD, fg=TEXTO, relief="flat",
            insertbackground=TEXTO, wrap="word",
            padx=4, pady=4)
        self._casos_txt_notas.pack(padx=10, pady=(2, 6), fill="x")

        tk.Button(detalle, text=t("casos.guardar_anotacion"),
                  font=("Arial", 9, "bold"),
                  bg=AMARILLO, fg=BG_DARK, relief="flat",
                  padx=8, pady=5, cursor="hand2",
                  command=self._casos_guardar_anotacion).pack(
            fill="x", padx=10, pady=4)

        tk.Frame(detalle, bg=BORDE, height=1).pack(fill="x", padx=8, pady=4)

        tk.Button(detalle, text=t("casos.eliminar"),
                  font=("Arial", 8), bg=BG_CARD, fg=ACENTO,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._casos_eliminar).pack(fill="x", padx=10)

        # Cargar datos iniciales
        self._casos_recargar()

    # ---------- Helpers de la tabla ----------

    def _casos_recargar(self):
        """Recarga la tabla aplicando filtros actuales."""
        mod_sel = self._casos_var_mod.get()
        res_sel = self._casos_var_res.get()
        busq    = self._casos_var_busq.get().strip()
        todos   = t("casos.filtro_todos")

        casos = self._db.cargar_casos(
            modulo   = None if mod_sel == todos else mod_sel,
            resultado= None if res_sel == todos else res_sel,
            busqueda = busq or None,
        )

        # Actualizar opciones del combo de módulos
        mods_nuevos = [todos] + self._db.modulos_disponibles()
        self._casos_combo_mod["values"] = mods_nuevos

        for row in self._casos_tree.get_children():
            self._casos_tree.delete(row)

        if not casos:
            self._casos_tree.insert("", "end", values=(
                t("casos.sin_casos").split("\n")[0], "", "", "", "", "", ""))
            return

        for c in casos:
            tag = c.get("resultado", "")
            self._casos_tree.insert("", "end", iid=str(c["id"]),
                values=(
                    c.get("fecha", ""),
                    c.get("caso_id", ""),
                    c.get("resultado", ""),
                    f"{c.get('score', 0):.0f}",
                    f"{c.get('aprobados', 0)}/4",
                    c.get("modulo", ""),
                    c.get("diagnostico_cirujano", "") or "—",
                ),
                tags=(tag,))

    def _casos_on_select(self, event=None):
        sel = self._casos_tree.selection()
        # --- Actualizar contador y estado del botón Comparar ---
        n = len(sel)
        try:
            self._casos_sel_lbl.config(
                text=t("casos.sel_count").format(n=n),
                fg=VERDE if n == 2 else GRIS)
            if n == 2:
                self._casos_btn_comparar.config(state="normal", fg=TEXTO, bg=CYAN)
            else:
                self._casos_btn_comparar.config(state="disabled", fg=GRIS, bg=BG_CARD)
        except AttributeError:
            pass  # Widgets aún no creados
        if not sel:
            return
        iid = sel[0]
        try:
            caso_id_db = int(iid)
        except ValueError:
            return
        caso = self._db.cargar_caso_por_id(caso_id_db)
        if not caso:
            return
        self._casos_id_seleccionado = caso_id_db

        # Mostrar info
        res_color = {
            "ADECUADA": VERDE, "BORDERLINE": AMARILLO,
            "COMPROMETIDA": ACENTO
        }.get(caso.get("resultado", ""), GRIS)
        info = (
            f"Caso: {caso.get('caso_id','—')}\n"
            f"Fecha: {caso.get('fecha','—')}\n"
            f"Módulo: {caso.get('modulo','—')}\n"
            f"────────────────\n"
            f"SENTINEL: {caso.get('resultado','—')} | Score: {caso.get('score',0):.0f}\n"
            f"T1={caso.get('t1',0) or 0:.1f}s   T2={caso.get('t2',0) or 0:.1f}s\n"
            f"Pend={caso.get('pendiente',0) or 0:.1f}   NIR={caso.get('indice_nir',0) or 0:.0f}"
        )
        self._casos_lbl_info.config(text=info, fg=res_color)

        # Cargar anotación existente
        self._casos_dx_var.set(caso.get("diagnostico_cirujano", "") or "")
        self._casos_etiq_var.set(caso.get("etiquetas", "") or "")
        self._casos_txt_notas.delete("1.0", "end")
        self._casos_txt_notas.insert("1.0", caso.get("notas", "") or "")

    def _casos_guardar_anotacion(self):
        if self._casos_id_seleccionado is None:
            return
        self._db.actualizar_anotacion(
            self._casos_id_seleccionado,
            diagnostico_cirujano=self._casos_dx_var.get(),
            notas=self._casos_txt_notas.get("1.0", "end").strip(),
            etiquetas=self._casos_etiq_var.get(),
        )
        messagebox.showinfo(t("avisos.aviso"), t("casos.anotacion_guardada"))
        self._casos_recargar()

    def _casos_eliminar(self):
        if self._casos_id_seleccionado is None:
            return
        caso = self._db.cargar_caso_por_id(self._casos_id_seleccionado)
        nombre = caso.get("caso_id", "?") if caso else "?"
        if messagebox.askyesno(
                t("casos.eliminar_titulo"),
                t("casos.eliminar_confirm").format(caso=nombre)):
            self._db.eliminar_caso(self._casos_id_seleccionado)
            self._casos_id_seleccionado = None
            self._casos_lbl_info.config(text="—\nSelecciona un caso", fg=GRIS)
            self._casos_recargar()

    def _casos_ordenar(self, col):
        """Ordena la tabla por columna clicada (toggle asc/desc)."""
        pass  # Implementación futura: sort en memoria

    def _casos_comparar(self):
        sel = self._casos_tree.selection()
        if len(sel) != 2:
            messagebox.showwarning(t("avisos.aviso"), t("casos.comparar_error"))
            return
        try:
            ids = [int(s) for s in sel]
        except (ValueError, TypeError):
            messagebox.showwarning(t("avisos.aviso"), t("casos.comparar_error"))
            return
        if len(ids) != 2:
            messagebox.showwarning(t("avisos.aviso"), t("casos.comparar_error"))
            return
        c1 = self._db.cargar_caso_por_id(ids[0])
        c2 = self._db.cargar_caso_por_id(ids[1])
        if not c1 or not c2:
            return
        self._casos_ventana_comparacion(c1, c2)

    def _casos_ventana_comparacion(self, c1, c2):
        """Abre ventana Toplevel con comparación lado a lado."""
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title(t("casos.comparar_titulo"))
        win.geometry("700x420")

        tk.Label(win, text=t("casos.comparar_titulo"),
                 font=("Arial", 12, "bold"),
                 fg=CYAN, bg=BG_DARK).pack(pady=(12, 8))

        tabla = tk.Frame(win, bg=BG_DARK)
        tabla.pack(fill="both", expand=True, padx=20)

        headers = ["Campo",
                   c1.get("caso_id", "Caso 1")[:22],
                   c2.get("caso_id", "Caso 2")[:22]]
        cols_color = [GRIS, CYAN, MORADO]
        for i, (h, col) in enumerate(zip(headers, cols_color)):
            tk.Label(tabla, text=h, font=("Arial", 10, "bold"),
                     fg=col, bg=BG_DARK, width=22, anchor="center").grid(
                row=0, column=i, padx=4, pady=4)

        def _color(val1, val2, key, higher_better=False):
            if val1 is None or val2 is None:
                return GRIS, GRIS
            try:
                v1, v2 = float(val1), float(val2)
            except (TypeError, ValueError):
                return TEXTO, TEXTO
            if higher_better:
                return (VERDE if v1 >= v2 else AMARILLO,
                        VERDE if v2 >= v1 else AMARILLO)
            else:
                return (VERDE if v1 <= v2 else AMARILLO,
                        VERDE if v2 <= v1 else AMARILLO)

        filas = [
            ("Fecha",        c1.get("fecha",""), c2.get("fecha",""), False),
            ("Módulo",       c1.get("modulo",""), c2.get("modulo",""), False),
            ("Resultado SENTINEL", c1.get("resultado",""), c2.get("resultado",""), False),
            ("Score",        c1.get("score",0), c2.get("score",0), True),
            ("Aprobados",    c1.get("aprobados",0), c2.get("aprobados",0), True),
            ("T1 (s)",       c1.get("t1",0), c2.get("t1",0), False),
            ("T2 (s)",       c1.get("t2",0), c2.get("t2",0), False),
            ("Pendiente",    c1.get("pendiente",0), c2.get("pendiente",0), True),
            ("NIR",          c1.get("indice_nir",0), c2.get("indice_nir",0), True),
            ("Dx Cirujano",  c1.get("diagnostico_cirujano","—"),
                             c2.get("diagnostico_cirujano","—"), False),
        ]
        for r, (campo, v1, v2, hb) in enumerate(filas, 1):
            bg_ = BG_PANEL if r % 2 == 0 else BG_CARD
            tk.Label(tabla, text=campo, font=("Arial", 9),
                     fg=GRIS, bg=bg_, width=18, anchor="w").grid(
                row=r, column=0, padx=4, pady=3, sticky="ew")

            if isinstance(v1, float) and campo != "Fecha":
                c_1, c_2 = _color(v1, v2, campo, hb)
                txt1 = f"{v1:.2f}" if isinstance(v1, float) else str(v1)
                txt2 = f"{v2:.2f}" if isinstance(v2, float) else str(v2)
            else:
                c_1 = c_2 = TEXTO
                txt1, txt2 = str(v1), str(v2)

            tk.Label(tabla, text=txt1, font=("Arial", 9, "bold"),
                     fg=c_1, bg=bg_, width=22, anchor="center").grid(
                row=r, column=1, padx=4, pady=3)
            tk.Label(tabla, text=txt2, font=("Arial", 9, "bold"),
                     fg=c_2, bg=bg_, width=22, anchor="center").grid(
                row=r, column=2, padx=4, pady=3)

        tk.Button(win, text="Cerrar", font=("Arial", 9),
                  bg=BG_CARD, fg=TEXTO, relief="flat",
                  padx=12, pady=5, cursor="hand2",
                  command=win.destroy).pack(pady=12)

    # ===========================================================
    # DASHBOARD — Estadísticas clínicas agregadas
    # ===========================================================

    def _mostrar_dashboard(self):
        self._nav(self._build_dashboard)

    def _build_dashboard(self):
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        # Encabezado
        hdr = tk.Frame(frame, bg=BG_DARK)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text=t("dashboard.titulo"),
                 font=("Arial", 12, "bold"),
                 fg=MORADO, bg=BG_DARK).pack(side="left")
        tk.Button(hdr, text=t("dashboard.refrescar"),
                  font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=lambda: self._dash_refrescar(frame)).pack(side="right")

        stats = self._db.estadisticas()

        if stats.get("total", 0) == 0:
            tk.Label(frame, text=t("dashboard.sin_datos"),
                     font=("Arial", 12), fg=GRIS, bg=BG_DARK,
                     justify="center").pack(expand=True)
            return

        # Tarjetas KPI
        self._dash_kpis(frame, stats)
        # Gráficas
        self._dash_graficas(frame, stats)

    def _dash_kpis(self, parent, stats):
        """Fila de KPI cards en la parte superior."""
        kpi_frame = tk.Frame(parent, bg=BG_DARK)
        kpi_frame.pack(fill="x", pady=(0, 8))

        dist  = stats.get("distribucion", {})
        total = stats.get("total", 0)
        conc  = stats.get("concordancia", {})
        score_m = stats.get("scores", {}).get("media", 0)
        acuerdo  = conc.get("acuerdo", 0)
        con_dx   = acuerdo + conc.get("desacuerdo", 0)
        pct_conc = round(acuerdo / con_dx * 100, 1) if con_dx > 0 else None

        kpis = [
            (t("dashboard.total"),       str(total),           CYAN),
            (t("dashboard.adecuada"),
             f"{dist.get('ADECUADA',0)} ({round(dist.get('ADECUADA',0)/total*100)}%)",
             VERDE),
            (t("dashboard.borderline"),
             f"{dist.get('BORDERLINE',0)} ({round(dist.get('BORDERLINE',0)/total*100)}%)",
             AMARILLO),
            (t("dashboard.comprometida"),
             f"{dist.get('COMPROMETIDA',0)} ({round(dist.get('COMPROMETIDA',0)/total*100)}%)",
             ACENTO),
            (t("dashboard.score_prom"),   f"{score_m:.1f}/100",  MORADO),
            (t("dashboard.concordancia"),
             f"{pct_conc}%" if pct_conc is not None else "N/A",
             VERDE if (pct_conc or 0) >= 80 else AMARILLO),
        ]
        for titulo, valor, color in kpis:
            card = tk.Frame(kpi_frame, bg=BG_CARD,
                            highlightbackground=color, highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=4)
            tk.Label(card, text=valor, font=("Arial", 16, "bold"),
                     fg=color, bg=BG_CARD).pack(pady=(10, 2))
            tk.Label(card, text=titulo, font=("Arial", 8),
                     fg=GRIS, bg=BG_CARD).pack(pady=(0, 8))

    def _dash_graficas(self, parent, stats):
        """2×2 grid de gráficas clínicas."""
        raw   = stats.get("raw", {})
        dist  = stats.get("distribucion", {})
        total = stats.get("total", 1)

        fig, axes = plt.subplots(2, 2, figsize=(11, 6.5), tight_layout=True)
        fig.patch.set_facecolor(BG_DARK)

        # ---------- 1. Distribución diagnósticos (Pie) ----------
        ax1 = axes[0][0]
        labels_pie, sizes_pie, colores_pie = [], [], []
        for lbl, col in [("ADECUADA", VERDE), ("BORDERLINE", AMARILLO),
                          ("COMPROMETIDA", ACENTO)]:
            n = dist.get(lbl, 0)
            if n > 0:
                labels_pie.append(f"{lbl}\n({n})")
                sizes_pie.append(n)
                colores_pie.append(col)
        if sizes_pie:
            ax1.pie(sizes_pie, labels=labels_pie, colors=colores_pie,
                    autopct="%1.1f%%", startangle=90,
                    textprops={"color": TEXTO, "fontsize": 8},
                    pctdistance=0.75, labeldistance=1.15)
        ax1.set_title(t("dashboard.fig_titulo_distribucion"), color=TEXTO, fontsize=10)
        ax1.set_facecolor(BG_DARK)

        # ---------- 2. Boxplots de parámetros ----------
        ax2 = axes[0][1]
        ax2.set_facecolor(BG_PANEL)
        param_data = []
        param_labels = []
        param_cols   = []
        for key, col, label in [
            ("t1s",   CYAN,    t("dashboard.fig_param_t1")),
            ("t2s",   VERDE,   t("dashboard.fig_param_t2")),
            ("pends", AMARILLO,t("dashboard.fig_param_pend")),
            ("nirs",  MORADO,  t("dashboard.fig_param_nir")),
        ]:
            vals = raw.get(key, [])
            if vals:
                # Normalizar NIR para que quepa en escala visual
                param_data.append([v/10 if key=="nirs" else v for v in vals])
                param_labels.append(label)
                param_cols.append(col)

        if param_data:
            bp = ax2.boxplot(param_data, patch_artist=True,
                             medianprops={"color": TEXTO, "linewidth": 2})
            for patch, col in zip(bp["boxes"], param_cols):
                patch.set_facecolor(col + "55")
                patch.set_edgecolor(col)
            for element in ["whiskers","caps","fliers"]:
                for ln in bp[element]:
                    ln.set_color(GRIS)
            ax2.set_xticklabels(param_labels, color=TEXTO, fontsize=8)
        ax2.set_title(t("dashboard.fig_titulo_parametros"), color=TEXTO, fontsize=10)
        ax2.set_ylabel(t("dashboard.fig_ylabel_valor"), color=TEXTO, fontsize=8)
        ax2.tick_params(colors=TEXTO)
        ax2.spines[:].set_color(BORDE)

        # ---------- 3. Histograma de scores ----------
        ax3 = axes[1][0]
        ax3.set_facecolor(BG_PANEL)
        scores = raw.get("scores", [])
        if scores:
            ax3.hist(scores, bins=min(20, max(5, len(scores)//2)),
                     color=MORADO, alpha=0.8, edgecolor=BG_DARK)
            ax3.axvline(60, color=VERDE,   linestyle="--",
                        alpha=0.8, label=t("dashboard.fig_label_bajo_riesgo"))
            ax3.axvline(40, color=AMARILLO, linestyle="--",
                        alpha=0.8, label=t("dashboard.fig_label_moderado"))
            ax3.legend(fontsize=7, loc="upper left")
        ax3.set_title(t("dashboard.fig_titulo_scores"), color=TEXTO, fontsize=10)
        ax3.set_xlabel(t("dashboard.fig_xlabel_score"), color=TEXTO, fontsize=8)
        ax3.set_ylabel(t("dashboard.fig_ylabel_frecuencia"), color=TEXTO, fontsize=8)
        ax3.tick_params(colors=TEXTO)
        ax3.spines[:].set_color(BORDE)

        # ---------- 4. Concordancia SENTINEL vs Cirujano ----------
        ax4 = axes[1][1]
        ax4.set_facecolor(BG_PANEL)
        concord = stats.get("concordancia", {})
        acuerdo    = concord.get("acuerdo", 0)
        desacuerdo = concord.get("desacuerdo", 0)
        sin_dx     = concord.get("sin_dx", 0)

        if acuerdo + desacuerdo > 0:
            bars = ax4.bar([t("dashboard.fig_label_acuerdo"), t("dashboard.fig_label_desacuerdo")],
                           [acuerdo, desacuerdo],
                           color=[VERDE, ACENTO], alpha=0.85,
                           edgecolor=BG_DARK)
            for bar, val in zip(bars, [acuerdo, desacuerdo]):
                ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                         str(val), ha="center", va="bottom",
                         color=TEXTO, fontsize=9, fontweight="bold")
            ax4.set_title(t("casos.concordancia"), color=TEXTO, fontsize=10)
            ax4.set_ylabel("Casos", color=TEXTO, fontsize=8)
        else:
            ax4.text(0.5, 0.5,
                     t("dashboard.fig_sin_diagnostico").format(n=sin_dx),
                     ha="center", va="center",
                     transform=ax4.transAxes,
                     color=GRIS, fontsize=10)
            ax4.set_title(t("casos.concordancia"), color=TEXTO, fontsize=10)

        ax4.tick_params(colors=TEXTO)
        ax4.spines[:].set_color(BORDE)

        # Embeber en Tkinter
        canvas_widget = FigureCanvasTkAgg(fig, master=parent)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill="both", expand=True)

    def _dash_refrescar(self, frame):
        """Destruye y reconstruye el dashboard con datos actualizados."""
        for w in frame.winfo_children():
            w.destroy()
        # Reconstruir
        hdr2 = tk.Frame(frame, bg=BG_DARK)
        hdr2.pack(fill="x", pady=(0, 6))
        tk.Label(hdr2, text=t("dashboard.titulo"),
                 font=("Arial", 12, "bold"),
                 fg=MORADO, bg=BG_DARK).pack(side="left")
        tk.Button(hdr2, text=t("dashboard.refrescar"),
                  font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=lambda: self._dash_refrescar(frame)).pack(side="right")
        stats = self._db.estadisticas()
        if stats.get("total", 0) == 0:
            tk.Label(frame, text=t("dashboard.sin_datos"),
                     font=("Arial", 12), fg=GRIS, bg=BG_DARK,
                     justify="center").pack(expand=True)
            return
        self._dash_kpis(frame, stats)
        self._dash_graficas(frame, stats)

    # ===========================================================
    # CENTRO DE AYUDA — Manual de Usuario integrado
    # ===========================================================

    def _mostrar_ayuda(self):
        self._nav(self._build_ayuda)

    def _build_ayuda(self):
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        tk.Label(frame, text=t("ayuda.titulo"),
                 font=("Arial", 12, "bold"),
                 fg=VERDE, bg=BG_DARK).pack(pady=(0, 8))

        content_frame = tk.Frame(frame, bg=BG_DARK)
        content_frame.pack(fill="both", expand=True)

        # Sidebar izquierdo con secciones
        sidebar = tk.Frame(content_frame, bg=BG_PANEL, width=190,
                           highlightbackground=BORDE, highlightthickness=1)
        sidebar.pack(side="left", fill="y", padx=(0, 8))
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="Secciones",
                 font=("Arial", 9, "bold"),
                 fg=VERDE, bg=BG_PANEL).pack(pady=(12, 6), padx=10, anchor="w")
        tk.Frame(sidebar, bg=BORDE, height=1).pack(fill="x", padx=8)

        # Panel derecho con texto enriquecido
        right = tk.Frame(content_frame, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        txt = tk.Text(right, bg=BG_PANEL, fg=TEXTO,
                      font=("Arial", 10), relief="flat",
                      padx=18, pady=14, wrap="word",
                      state="disabled", cursor="arrow",
                      selectbackground=BG_CARD)
        sb = ttk.Scrollbar(right, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        # Tags de formato
        txt.tag_configure("h1",   font=("Arial", 14, "bold"), foreground=ACENTO,
                          spacing1=14, spacing3=6)
        txt.tag_configure("h2",   font=("Arial", 11, "bold"), foreground=VERDE,
                          spacing1=10, spacing3=4)
        txt.tag_configure("body", font=("Arial", 10), foreground=TEXTO,
                          spacing1=3, lmargin1=8, lmargin2=8)
        txt.tag_configure("li",   font=("Arial", 10), foreground=TEXTO,
                          spacing1=3, lmargin1=20, lmargin2=28)
        txt.tag_configure("code", font=("Courier", 9), foreground=AMARILLO,
                          background=BG_CARD, lmargin1=20, lmargin2=20)
        txt.tag_configure("param",font=("Arial", 10, "bold"), foreground=CYAN)
        txt.tag_configure("ok",   font=("Arial", 10, "bold"), foreground=VERDE)
        txt.tag_configure("warn", font=("Arial", 10, "bold"), foreground=AMARILLO)
        txt.tag_configure("bad",  font=("Arial", 10, "bold"), foreground=ACENTO)
        txt.tag_configure("sep",  font=("Arial", 5), spacing1=4, spacing3=4)

        # Botones de sección activos
        self._ayuda_btns = {}
        secciones = [
            ("inicio",          t("ayuda.sec_inicio")),
            ("modulos",         t("ayuda.sec_modulos")),
            ("parametros",      t("ayuda.sec_parametros")),
            ("interpretacion",  t("ayuda.sec_interpretacion")),
            ("tecnico",         t("ayuda.sec_tecnico")),
            ("acerca",          t("ayuda.sec_acerca")),
        ]

        def mostrar_seccion(key):
            # Resaltar botón activo
            for k, b in self._ayuda_btns.items():
                b.config(bg=BG_PANEL, fg=TEXTO)
            self._ayuda_btns[key].config(bg=VERDE, fg=BG_DARK)
            # Renderizar contenido
            txt.config(state="normal")
            txt.delete("1.0", "end")
            self._ayuda_render(txt, key)
            txt.config(state="disabled")
            txt.see("1.0")

        for key, label in secciones:
            btn = tk.Button(sidebar, text=label,
                            font=("Arial", 9),
                            bg=BG_PANEL, fg=TEXTO,
                            relief="flat", padx=10, pady=7,
                            cursor="hand2", anchor="w",
                            wraplength=170, justify="left",
                            command=lambda k=key: mostrar_seccion(k))
            btn.pack(fill="x", padx=4, pady=1)
            self._ayuda_btns[key] = btn

        mostrar_seccion("inicio")

    def _ayuda_render(self, txt, seccion):
        """Escribe contenido formateado en el widget Text según la sección."""

        def w(texto, tag="body"):
            txt.insert("end", texto + "\n", tag)

        def sep():
            txt.insert("end", "\n", "sep")

        if seccion == "inicio":
            w(t("ayuda.inicio_titulo"), "h1")
            sep()
            w(t("ayuda.paso_1_titulo"), "h2")
            w(t("ayuda.paso_1_desc"), "body")
            sep()
            w(t("ayuda.paso_2_titulo"), "h2")
            w(t("ayuda.paso_2_desc"), "body")
            sep()
            w(t("ayuda.paso_3_titulo"), "h2")
            w(t("ayuda.paso_3_desc"), "body")
            sep()
            w(t("ayuda.paso_4_titulo"), "h2")
            w(t("ayuda.paso_4_intro"), "body")
            w(t("ayuda.paso_4_adecuada"), "li")
            w(t("ayuda.paso_4_borderline"), "li")
            w(t("ayuda.paso_4_comprometida"), "li")
            sep()
            w(t("ayuda.paso_5_titulo"), "h2")
            w(t("ayuda.paso_5_desc"), "body")
            sep()
            w(t("ayuda.requisitos_titulo"), "h2")
            w(t("ayuda.req_python"), "li")
            w(t("ayuda.req_video"), "li")
            w(t("ayuda.req_quirofano"), "li")
            w(t("ayuda.req_ram"), "li")

        elif seccion == "modulos":
            w(t("ayuda.modulos_titulo"), "h1")
            sep()
            modulos_info = [
                (t("ayuda.modulo_tr"),          CYAN,     t("ayuda.modulo_tr_desc")),
                (t("ayuda.modulo_video"),        ACENTO,   t("ayuda.modulo_video_desc")),
                (t("ayuda.modulo_mapa"),         AMARILLO, t("ayuda.modulo_mapa_desc")),
                (t("ayuda.modulo_simulador"),    MORADO,   t("ayuda.modulo_simulador_desc")),
                (t("ayuda.modulo_historial"),    GRIS,     t("ayuda.modulo_historial_desc")),
                (t("ayuda.modulo_max"),          ROJO,     t("ayuda.modulo_max_desc")),
                (t("ayuda.modulo_quirofano"),    CYAN,     t("ayuda.modulo_quirofano_desc")),
                (t("ayuda.modulo_segmentacion"), AZUL_SEG, t("ayuda.modulo_segmentacion_desc")),
                (t("ayuda.modulo_ayuda"),        VERDE,    t("ayuda.modulo_ayuda_desc")),
                (t("ayuda.modulo_educacion"),    AMARILLO, t("ayuda.modulo_educacion_desc")),
                (t("ayuda.modulo_casos"),        CYAN,     t("ayuda.modulo_casos_desc")),
                (t("ayuda.modulo_dashboard"),    MORADO,   t("ayuda.modulo_dashboard_desc")),
                (t("ayuda.modulo_exportacion"),  AMARILLO, t("ayuda.modulo_exportacion_desc")),
                (t("ayuda.modulo_calibracion"),  GRIS,     t("ayuda.modulo_calibracion_desc")),
            ]
            for nombre, color, desc in modulos_info:
                txt.insert("end", f"\u25b6  {nombre}\n", "h2")
                w(desc, "body")
                sep()

        elif seccion == "parametros":
            w(t("ayuda.parametros_titulo"), "h1")
            sep()
            w(t("ayuda.parametros_intro"), "body")
            sep()

            params = [
                (t("ayuda.param_t1_nombre"),   t("ayuda.param_t1_umbral"),
                 t("ayuda.param_t1_desc"),     t("ayuda.param_t1_fallo")),
                (t("ayuda.param_t2_nombre"),   t("ayuda.param_t2_umbral"),
                 t("ayuda.param_t2_desc"),     t("ayuda.param_t2_fallo")),
                (t("ayuda.param_pend_nombre"), t("ayuda.param_pend_umbral"),
                 t("ayuda.param_pend_desc"),   t("ayuda.param_pend_fallo")),
                (t("ayuda.param_nir_nombre"),  t("ayuda.param_nir_umbral"),
                 t("ayuda.param_nir_desc"),    t("ayuda.param_nir_fallo")),
            ]
            for nombre, umbral, desc, fallo in params:
                txt.insert("end", f"{nombre}\n", "h2")
                txt.insert("end", "  ", "body")
                txt.insert("end", f"{umbral}\n", "param")
                w(desc, "body")
                txt.insert("end", f"  \u26a0  {fallo}\n", "warn")
                sep()

            w("Parámetros adicionales (informativos)", "h2")
            w("Estos parámetros complementan el análisis pero no afectan la clasificación primaria.", "body")
            sep()
            additional_params = [
                ("Fmax — Fluorescencia máxima", "≥ 30.0 a.u.",
                 "Valor pico de fluorescencia normalizada. Indica la intensidad máxima de perfusión alcanzada."),
                ("T_half — Tiempo de semi-descenso", "≤ 15.0 s",
                 "Tiempo desde el pico hasta el 50% de descenso. Refleja la velocidad de lavado del ICG."),
                ("slope_ratio — Ratio de pendientes", "≥ 0.5",
                 "Cociente entre pendiente de subida y bajada. Valores cercanos a 1.0 indican cinética simétrica."),
            ]
            for nombre_a, umbral_a, desc_a in additional_params:
                txt.insert("end", f"{nombre_a}\n", "h2")
                txt.insert("end", "  ", "body")
                txt.insert("end", f"Referencia: {umbral_a}\n", "param")
                w(desc_a, "body")
                sep()

            w(t("ayuda.clasif_titulo"), "h2")
            w(t("ayuda.clasif_4de4"), "li")
            w(t("ayuda.clasif_2de4"), "li")
            w(t("ayuda.clasif_0de4"), "li")
            sep()
            w(t("ayuda.score_titulo"), "h2")
            w(t("ayuda.score_desc"), "body")

        elif seccion == "interpretacion":
            w(t("ayuda.sec_interpretacion"), "h1")
            sep()
            txt.insert("end", t("ayuda.interp_adecuada_titulo") + "\n", "ok")
            w(t("ayuda.interp_adecuada_desc"), "body")
            w(t("ayuda.interp_adecuada_impl"), "body")
            sep()
            txt.insert("end", t("ayuda.interp_borderline_titulo") + "\n", "warn")
            w(t("ayuda.interp_borderline_desc"), "body")
            w(t("ayuda.interp_borderline_impl"), "body")
            sep()
            txt.insert("end", t("ayuda.interp_comprometida_titulo") + "\n", "bad")
            w(t("ayuda.interp_comprometida_desc"), "body")
            w(t("ayuda.interp_comprometida_impl"), "body")
            sep()
            w(t("ayuda.interp_limites_titulo"), "h2")
            w(f"  \u2022  {t('ayuda.interp_limite_1')}", "li")
            w(f"  \u2022  {t('ayuda.interp_limite_2')}", "li")
            w(f"  \u2022  {t('ayuda.interp_limite_3')}", "li")
            w(f"  \u2022  {t('ayuda.interp_limite_4')}", "li")
            sep()
            w("Parámetros complementarios v2.0", "h2")
            w("A partir de v2.0, SENTINEL calcula 3 parámetros adicionales (Fmax, T_half, slope_ratio) "
              "que complementan el análisis cinético. Estos se reportan en el PDF pero no modifican la "
              "clasificación primaria basada en los 4 parámetros canónicos.", "body")

        elif seccion == "tecnico":
            w(t("ayuda.tecnico_titulo"), "h1")
            sep()
            w(t("ayuda.tecnico_pipeline_titulo"), "h2")
            for i in range(1, 8):
                w(t(f"ayuda.tecnico_pipe_{i}"), "li")
            sep()
            w(t("ayuda.tecnico_modulos_titulo"), "h2")
            archivos = [
                ("BioConnect_App.py",       t("ayuda.tecnico_app_desc")),
                ("config.py",               t("ayuda.tecnico_config_desc")),
                ("parameter_extraction.py", t("ayuda.tecnico_params_desc")),
                ("BCV1.py",                 t("ayuda.tecnico_bcv1_desc")),
                ("BCV1_tiempo_real.py",     t("ayuda.tecnico_tr_desc")),
                ("BCV1_lector_video.py",    t("ayuda.tecnico_lector_desc")),
                ("BCV1_mapa_calor.py",      t("ayuda.tecnico_mapa_desc")),
                ("BCV1_segmentacion.py",    t("ayuda.tecnico_seg_desc")),
                ("BCV1_reporte_pdf.py",     t("ayuda.tecnico_pdf_desc")),
                ("bioconnect_db.py",        t("ayuda.tecnico_db_desc")),
                ("bioconnect_manual_pdf.py",t("ayuda.tecnico_manual_desc")),
                ("bioconnect_prefs.py",     t("ayuda.tecnico_prefs_desc")),
                ("sentinel_settings.py",    t("ayuda.tecnico_settings_desc")),
                ("sentinel_splash.py",      t("ayuda.tecnico_splash_desc")),
                ("data_persistence.py",     t("ayuda.tecnico_persist_desc")),
                ("classifier.py",           "Clasificador LogisticRegression para predicción de fuga"),
                ("logger.py",               "Logging centralizado con rotación de archivos"),
                ("font_manager.py",         t("ayuda.tecnico_font_desc")),
                ("i18n/",                   t("ayuda.tecnico_i18n_desc")),
            ]
            for archivo, desc in archivos:
                txt.insert("end", f"  {archivo}\n", "code")
                txt.insert("end", f"     {desc}\n", "body")
            sep()
            w(t("ayuda.tecnico_savgol_titulo"), "h2")
            w(t("ayuda.tecnico_savgol_desc"), "body")
            sep()
            w(t("ayuda.tecnico_valid_titulo"), "h2")
            w(t("ayuda.tecnico_valid_desc"), "body")
            sep()
            w(t("ayuda.tecnico_deps_titulo"), "h2")
            deps = ["numpy", "scipy", "opencv-python (cv2)",
                    "matplotlib", "reportlab", "Pillow (PIL)",
                    "tkinter (stdlib)"]
            for d in deps:
                w(f"  pip install {d}", "code")
            sep()
            # ── Botón exportar manual técnico PDF ──────────────────────
            btn_frame = tk.Frame(txt.master, bg=BG_PANEL)
            txt.window_create("end", window=btn_frame)
            txt.insert("end", "\n")
            tk.Button(
                btn_frame,
                text=t("exportacion.manual_btn"),
                bg=MORADO, fg=TEXTO,
                font=("Helvetica", 11, "bold"),
                relief="flat", cursor="hand2",
                command=self._exportar_manual_desde_ayuda,
            ).pack(pady=6, padx=10, fill="x")

        elif seccion == "acerca":
            w(t("ayuda.acerca_titulo"), "h1")
            sep()
            w(t("ayuda.acerca_subtitulo"), "h2")
            w(t("ayuda.acerca_desc"), "body")
            sep()
            w(t("ayuda.acerca_inst_titulo"), "h2")
            w(t("ayuda.acerca_inst_1"), "li")
            w(t("ayuda.acerca_inst_2"), "li")
            w(t("ayuda.acerca_inst_3"), "li")
            sep()
            w(t("ayuda.acerca_ciencia_titulo"), "h2")
            txt.insert("end", t("ayuda.acerca_referencia") + "\n", "param")
            w(t("ayuda.acerca_ref_texto"), "body")
            sep()
            w(t("ayuda.acerca_tech_titulo"), "h2")
            w(t("ayuda.acerca_tech_1"), "li")
            w(t("ayuda.acerca_tech_2"), "li")
            sep()
            w(t("ayuda.acerca_version"), "body")
            w(t("ayuda.acerca_soporte"), "body")

    # ===========================================================
    # MÓDULO DE ENSEÑANZA ICG — Práctica + Quiz + Explorador
    # ===========================================================

    def _mostrar_educacion(self):
        self._nav(self._build_educacion)

    def _build_educacion(self):
        frame = tk.Frame(self._contenedor, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        tk.Label(frame, text=t("educacion.titulo"),
                 font=("Arial", 12, "bold"),
                 fg=AMARILLO, bg=BG_DARK).pack(pady=(0, 6))

        # Notebook con estilo oscuro
        style = ttk.Style()
        style.configure("Edu.TNotebook",         background=BG_DARK,  borderwidth=0)
        style.configure("Edu.TNotebook.Tab",     background=BG_CARD,  foreground=TEXTO,
                        padding=[12, 6],         font=("Arial", 9, "bold"))
        style.map("Edu.TNotebook.Tab",
                  background=[("selected", AMARILLO)],
                  foreground=[("selected", BG_DARK)])

        nb = ttk.Notebook(frame, style="Edu.TNotebook")
        nb.pack(fill="both", expand=True, pady=4)

        tab_p = tk.Frame(nb, bg=BG_DARK)
        tab_q = tk.Frame(nb, bg=BG_DARK)
        tab_e = tk.Frame(nb, bg=BG_DARK)

        nb.add(tab_p, text=t("educacion.tab_practica"))
        nb.add(tab_q, text=t("educacion.tab_quiz"))
        nb.add(tab_e, text=t("educacion.tab_explorador"))

        self._edu_build_practica(tab_p)
        self._edu_build_quiz(tab_q)
        self._edu_build_explorador(tab_e)

    # ----------------------------------------------------------
    # Tab 1: Práctica Libre
    # ----------------------------------------------------------

    def _edu_build_practica(self, parent):
        self._edu_practica_n = 0
        self._edu_practica_ultimo = None
        self._edu_practica_mostrar = False

        # Layout: panel izquierdo + canvas derecho
        left = tk.Frame(parent, bg=BG_PANEL, width=230,
                        highlightbackground=BORDE, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 8), pady=4)
        left.pack_propagate(False)
        right = tk.Frame(parent, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True, pady=4)

        tk.Label(left, text=t("educacion.gen_titulo"),
                 font=("Arial", 10, "bold"),
                 fg=AMARILLO, bg=BG_PANEL).pack(pady=(12, 4), padx=10, anchor="w")
        tk.Label(left, text=t("educacion.gen_instruccion"),
                 font=("Arial", 8), fg=GRIS, bg=BG_PANEL,
                 wraplength=200, justify="left").pack(padx=10, anchor="w")

        tk.Frame(left, bg=BORDE, height=1).pack(fill="x", padx=8, pady=8)

        tk.Label(left, text=t("educacion.practica_tipo"),
                 font=("Arial", 9, "bold"), fg="#aaaacc", bg=BG_PANEL).pack(
            padx=10, anchor="w")
        self._edu_tipo = tk.StringVar(value=t("educacion.practica_aleatorio"))
        tipos = [t("educacion.practica_aleatorio"),
                 t("educacion.practica_adecuada"),
                 t("educacion.practica_borderline"),
                 t("educacion.practica_comprometida")]
        ttk.Combobox(left, textvariable=self._edu_tipo,
                     values=tipos, state="readonly",
                     width=22).pack(padx=10, pady=(2, 10))

        tk.Button(left, text=t("educacion.practica_generar"),
                  font=("Arial", 10, "bold"),
                  bg=AMARILLO, fg=BG_DARK, relief="flat",
                  padx=8, pady=7, cursor="hand2",
                  command=lambda: self._edu_practica_generar(right)).pack(
            fill="x", padx=10, pady=(0, 6))

        self._edu_practica_btn_reveal = tk.Button(
            left, text=t("educacion.practica_mostrar"),
            font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
            relief="flat", padx=8, pady=5, cursor="hand2",
            command=self._edu_practica_toggle_reveal)
        self._edu_practica_btn_reveal.pack(fill="x", padx=10)

        tk.Frame(left, bg=BORDE, height=1).pack(fill="x", padx=8, pady=10)
        self._edu_practica_lbl_prog = tk.Label(
            left, text=t("educacion.practica_progreso").format(n=0),
            font=("Arial", 8), fg=GRIS, bg=BG_PANEL)
        self._edu_practica_lbl_prog.pack(padx=10, anchor="w")

        # Panel de revelación
        self._edu_practica_reveal_frame = tk.Frame(left, bg=BG_PANEL)
        self._edu_practica_reveal_frame.pack(fill="x", padx=10, pady=6)
        self._edu_practica_lbl_result = tk.Label(
            self._edu_practica_reveal_frame,
            text="", font=("Arial", 11, "bold"),
            bg=BG_PANEL, wraplength=200)
        self._edu_practica_lbl_result.pack(anchor="w")
        self._edu_practica_lbl_params = tk.Label(
            self._edu_practica_reveal_frame,
            text="", font=("Arial", 8),
            fg="#aaaacc", bg=BG_PANEL, justify="left", wraplength=200)
        self._edu_practica_lbl_params.pack(anchor="w")

        self._edu_practica_canvas_frame = right
        # Generar caso inicial
        self._edu_practica_generar(right)

    def _edu_practica_generar(self, canvas_parent):
        import random
        tipo_str = self._edu_tipo.get()
        label_a  = t("educacion.practica_adecuada")
        label_b  = t("educacion.practica_borderline")
        label_c  = t("educacion.practica_comprometida")
        label_r  = t("educacion.practica_aleatorio")

        # Parámetros de generación según tipo
        if tipo_str == label_a or (tipo_str == label_r and random.random() < 0.33):
            t1_ = random.uniform(3, 9.5)
            t2_ = random.uniform(12, 28)
            ruido_ = random.uniform(0.02, 0.10)
            amp_ = random.uniform(80, 130)
        elif tipo_str == label_c or (tipo_str == label_r and random.random() < 0.5):
            t1_ = random.uniform(11, 18)
            t2_ = random.uniform(32, 50)
            ruido_ = random.uniform(0.05, 0.15)
            amp_ = random.uniform(50, 100)
        else:  # borderline
            t1_ = random.uniform(8, 12)
            t2_ = random.uniform(25, 35)
            ruido_ = random.uniform(0.03, 0.08)
            amp_ = random.uniform(55, 75)

        tiempo, senal = generar_senal_sintetica(t1_, t2_, ruido_, amp_,
                                                seed=random.randint(0, 9999))
        params    = extraer_parametros(tiempo, senal)
        resultado, color, aprobados, detalle = clasificar_perfusion(params)
        score     = calcular_score(params)

        self._edu_practica_ultimo = (tiempo, senal, params, resultado,
                                     color, aprobados, score)
        self._edu_practica_n += 1
        self._edu_practica_mostrar = False
        self._edu_practica_lbl_prog.config(
            text=t("educacion.practica_progreso").format(n=self._edu_practica_n))
        self._edu_practica_btn_reveal.config(
            text=t("educacion.practica_mostrar"),
            bg=BG_CARD, fg=TEXTO)
        self._edu_practica_lbl_result.config(text="", fg=TEXTO)
        self._edu_practica_lbl_params.config(text="")

        # Figura con clasificación oculta
        fig = self._edu_practica_figura(tiempo, senal, ocultar=True)
        for w in canvas_parent.winfo_children():
            w.destroy()
        self._edu_practica_cv = self._embed_figura(canvas_parent, fig)

    def _edu_practica_toggle_reveal(self):
        if not self._edu_practica_ultimo:
            return
        self._edu_practica_mostrar = not self._edu_practica_mostrar
        tiempo, senal, params, resultado, color, aprobados, score = \
            self._edu_practica_ultimo

        if self._edu_practica_mostrar:
            self._edu_practica_btn_reveal.config(
                text=t("educacion.practica_ocultar"),
                bg=VERDE, fg=BG_DARK)
            resultado_txt = {
                "ADECUADA":     t("perfusion.adecuada"),
                "BORDERLINE":   t("perfusion.borderline"),
                "COMPROMETIDA": t("perfusion.comprometida"),
            }.get(resultado, resultado)
            self._edu_practica_lbl_result.config(
                text=t("educacion.perfusion_label").format(resultado=resultado_txt),
                fg=color)
            p = params
            resumen = (f"T1={p['T1']:.1f}s  T2={p['T2']:.1f}s\n"
                       f"Pend={p['pendiente']:.1f}u/s  NIR={p['indice_NIR']:.0f}\n"
                       f"Fmax={p.get('Fmax','—')}  T½={p.get('T_half','—')}s\n"
                       f"Slope ratio={p.get('slope_ratio','—')}\n"
                       f"Score: {score}/100  |  {aprobados}/4 OK")
            self._edu_practica_lbl_params.config(text=resumen)
            fig = self._edu_practica_figura(tiempo, senal, ocultar=False,
                                            resultado=resultado, color=color,
                                            params=params, score=score)
        else:
            self._edu_practica_btn_reveal.config(
                text=t("educacion.practica_mostrar"),
                bg=BG_CARD, fg=TEXTO)
            self._edu_practica_lbl_result.config(text="")
            self._edu_practica_lbl_params.config(text="")
            fig = self._edu_practica_figura(tiempo, senal, ocultar=True)

        for w in self._edu_practica_canvas_frame.winfo_children():
            w.destroy()
        self._embed_figura(self._edu_practica_canvas_frame, fig)

    def _edu_practica_figura(self, tiempo, senal, ocultar=True,
                              resultado=None, color=None, params=None, score=None):
        fig, ax = plt.subplots(figsize=(7, 4), tight_layout=True)
        ax.plot(tiempo, senal, color=CYAN, linewidth=2, label="ICG")
        ax.set_xlabel(t("educacion.fig_eje_tiempo"))
        ax.set_ylabel(t("educacion.fig_eje_intensidad"))
        ax.grid(True, alpha=0.3)
        if ocultar:
            ax.set_title(t("educacion.fig_titulo_pregunta"),
                         color=TEXTO, fontsize=11)
            ax.text(0.5, 0.05, t("educacion.fig_clasificacion_oculta"),
                    transform=ax.transAxes, ha="center",
                    color=GRIS, fontsize=9, style="italic")
        else:
            resultado_txt = {
                "ADECUADA":     t("perfusion.adecuada"),
                "BORDERLINE":   t("perfusion.borderline"),
                "COMPROMETIDA": t("perfusion.comprometida"),
            }.get(resultado, resultado)
            titulo = t("educacion.fig_titulo_revelado")
            ax.set_title(titulo, color=color, fontsize=12, fontweight="bold")
            if params:
                ax.axvline(params["T1"], color=AMARILLO, linestyle="--",
                           alpha=0.7, label=f"T1={params['T1']:.1f}s")
                ax.axvline(params["T2"], color=VERDE,   linestyle="--",
                           alpha=0.7, label=f"T2={params['T2']:.1f}s")
                ax.legend(fontsize=8)
        _apply_cjk_to_figure(fig)
        return fig

    # ----------------------------------------------------------
    # Tab 2: Quiz Clínico
    # ----------------------------------------------------------

    def _edu_build_quiz(self, parent):
        self._quiz_correctas = 0
        self._quiz_total     = 0
        self._quiz_max       = 10
        self._quiz_respondido = False
        self._quiz_ultimo    = None

        # Layout
        top = tk.Frame(parent, bg=BG_DARK)
        top.pack(fill="x", padx=8, pady=(8, 4))

        self._quiz_lbl_score = tk.Label(
            top, text=t("educacion.quiz_score").format(c=0, t=0, pct=0),
            font=("Arial", 10, "bold"), fg=CYAN, bg=BG_DARK)
        self._quiz_lbl_score.pack(side="left")

        tk.Button(top, text=t("educacion.quiz_nuevo"),
                  font=("Arial", 9), bg=BG_CARD, fg=TEXTO,
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  command=self._quiz_reiniciar).pack(side="right")

        # Canvas
        mid = tk.Frame(parent, bg=BG_DARK)
        mid.pack(fill="both", expand=True, padx=8)
        self._quiz_canvas_frame = mid

        # Pregunta + botones
        bot = tk.Frame(parent, bg=BG_DARK)
        bot.pack(fill="x", padx=8, pady=6)

        tk.Label(bot, text=t("educacion.quiz_pregunta"),
                 font=("Arial", 10, "bold"), fg=TEXTO, bg=BG_DARK).pack(pady=(0, 4))

        btn_frame = tk.Frame(bot, bg=BG_DARK)
        btn_frame.pack()

        colores_btn = [VERDE, AMARILLO, ACENTO]
        labels_btn  = [t("educacion.quiz_btn_adecuada"),
                       t("educacion.quiz_btn_borderline"),
                       t("educacion.quiz_btn_comprometida")]
        self._quiz_btns = []
        for i, (lbl, col) in enumerate(zip(labels_btn, colores_btn)):
            b = tk.Button(btn_frame, text=lbl,
                          font=("Arial", 10, "bold"),
                          bg=col, fg=BG_DARK, relief="flat",
                          padx=14, pady=8, cursor="hand2",
                          command=lambda r=lbl: self._quiz_responder(r))
            b.pack(side="left", padx=6)
            self._quiz_btns.append(b)

        self._quiz_lbl_feedback = tk.Label(
            bot, text="", font=("Arial", 10, "bold"), bg=BG_DARK)
        self._quiz_lbl_feedback.pack(pady=(6, 0))

        self._quiz_btn_siguiente = tk.Button(
            bot, text=t("educacion.quiz_siguiente"),
            font=("Arial", 9), bg=MORADO, fg=TEXTO,
            relief="flat", padx=12, pady=5, cursor="hand2",
            command=self._quiz_siguiente, state="disabled")
        self._quiz_btn_siguiente.pack(pady=(4, 0))

        self._quiz_nuevo_caso()

    def _quiz_nuevo_caso(self):
        import random
        if self._quiz_total >= self._quiz_max:
            return
        t1_ = random.uniform(2, 18)
        t2_ = random.uniform(10, 50)
        ruido_ = random.uniform(0.02, 0.12)
        amp_   = random.uniform(50, 130)
        seed_  = random.randint(0, 9999)

        tiempo, senal = generar_senal_sintetica(t1_, t2_, ruido_, amp_, seed=seed_)
        params    = extraer_parametros(tiempo, senal)
        resultado, color, aprobados, _ = clasificar_perfusion(params)
        score     = calcular_score(params)

        self._quiz_ultimo = (tiempo, senal, params, resultado, color, score)
        self._quiz_respondido = False

        # Habilitar botones
        for b in self._quiz_btns:
            b.config(state="normal", relief="flat")
        self._quiz_btn_siguiente.config(state="disabled")
        self._quiz_lbl_feedback.config(text="")

        # Figura nueva (oculta)
        fig = self._edu_practica_figura(tiempo, senal, ocultar=True)
        for w in self._quiz_canvas_frame.winfo_children():
            w.destroy()
        self._embed_figura(self._quiz_canvas_frame, fig)

    def _quiz_responder(self, respuesta_usuario):
        if self._quiz_respondido or not self._quiz_ultimo:
            return
        self._quiz_respondido = True
        _, senal, params, resultado, color, score = (
            self._quiz_ultimo[0], self._quiz_ultimo[1], self._quiz_ultimo[2],
            self._quiz_ultimo[3], self._quiz_ultimo[4], self._quiz_ultimo[5])
        tiempo = self._quiz_ultimo[0]
        senal  = self._quiz_ultimo[1]

        # Mapear respuesta i18n → clave interna
        mapa = {
            t("educacion.quiz_btn_adecuada"):     "ADECUADA",
            t("educacion.quiz_btn_borderline"):   "BORDERLINE",
            t("educacion.quiz_btn_comprometida"): "COMPROMETIDA",
        }
        resp_norm = mapa.get(respuesta_usuario, respuesta_usuario)
        correcto  = resp_norm == resultado

        self._quiz_total += 1
        if correcto:
            self._quiz_correctas += 1
            self._quiz_lbl_feedback.config(
                text=f"✓  {t('educacion.quiz_correcto')}  —  {resultado}",
                fg=VERDE)
        else:
            self._quiz_lbl_feedback.config(
                text=(f"✗  {t('educacion.quiz_incorrecto')}  —  "
                      + t("educacion.quiz_respuesta").format(r=resultado)),
                fg=ACENTO)

        pct = int(self._quiz_correctas / self._quiz_total * 100) if self._quiz_total else 0
        self._quiz_lbl_score.config(
            text=t("educacion.quiz_score").format(
                c=self._quiz_correctas, t=self._quiz_total, pct=pct))

        # Deshabilitar botones, revelar figura
        for b in self._quiz_btns:
            b.config(state="disabled")

        fig_rev = self._edu_practica_figura(tiempo, senal, ocultar=False,
                                            resultado=resultado, color=color,
                                            params=params, score=score)
        for w in self._quiz_canvas_frame.winfo_children():
            w.destroy()
        self._embed_figura(self._quiz_canvas_frame, fig_rev)

        if self._quiz_total < self._quiz_max:
            self._quiz_btn_siguiente.config(state="normal")
        else:
            # Quiz terminado
            pct_f = int(self._quiz_correctas / self._quiz_max * 100)
            tk.messagebox.showinfo(
                t("educacion.quiz_listo"),
                t("educacion.quiz_listo_msg").format(
                    c=self._quiz_correctas, t=self._quiz_max, pct=pct_f))
            self._quiz_btn_siguiente.config(state="disabled")

    def _quiz_siguiente(self):
        self._quiz_nuevo_caso()

    def _quiz_reiniciar(self):
        self._quiz_correctas = 0
        self._quiz_total     = 0
        self._quiz_respondido = False
        self._quiz_lbl_score.config(
            text=t("educacion.quiz_score").format(c=0, t=0, pct=0))
        self._quiz_lbl_feedback.config(text="")
        self._quiz_nuevo_caso()

    # ----------------------------------------------------------
    # Tab 3: Explorador de Umbrales
    # ----------------------------------------------------------

    def _edu_build_explorador(self, parent):
        # Umbrales locales (NO modifican config.py)
        from config import get_umbral
        self._exp_umbrales = {
            "T1":         get_umbral("T1"),
            "T2":         get_umbral("T2"),
            "pendiente":  get_umbral("pendiente"),
            "indice_NIR": get_umbral("indice_NIR"),
        }

        main = tk.Frame(parent, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # Sidebar de controles
        left = tk.Frame(main, bg=BG_PANEL, width=240,
                        highlightbackground=BORDE, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        tk.Label(left, text="Ajustar Umbrales",
                 font=("Arial", 10, "bold"),
                 fg=AMARILLO, bg=BG_PANEL).pack(pady=(12, 4), padx=10, anchor="w")
        tk.Label(left,
                 text=t("educacion.explorador_nota"),
                 font=("Arial", 7), fg=ACENTO, bg=BG_PANEL,
                 wraplength=215, justify="left").pack(padx=10, pady=(0, 8))
        tk.Frame(left, bg=BORDE, height=1).pack(fill="x", padx=8, pady=4)

        self._exp_vars = {}
        defs = [
            ("T1",         t("educacion.explorador_t1"),         1.0,  25.0,  True),
            ("T2",         t("educacion.explorador_t2"),         5.0,  60.0,  True),
            ("pendiente",  t("educacion.explorador_pend"),       0.5,  20.0,  False),
            ("indice_NIR", t("educacion.explorador_nir"),        5.0, 150.0,  False),
        ]
        for key, label, mn, mx, leq in defs:
            f = tk.Frame(left, bg=BG_PANEL)
            f.pack(fill="x", padx=10, pady=5)
            tk.Label(f, text=label, font=("Arial", 8, "bold"),
                     fg="#aaaacc", bg=BG_PANEL, anchor="w").pack(fill="x")
            row = tk.Frame(f, bg=BG_PANEL)
            row.pack(fill="x")
            val = self._exp_umbrales[key]
            var = tk.DoubleVar(value=val)
            self._exp_vars[key] = var
            lbl_v = tk.Label(row, text=f"{val:.1f}",
                             font=("Arial", 9, "bold"),
                             fg=AMARILLO, bg=BG_PANEL, width=6)
            lbl_v.pack(side="right")
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient="horizontal",
                      command=lambda v, l=lbl_v, vr=var, k=key:
                          self._exp_slider_moved(l, vr, k)).pack(
                side="left", fill="x", expand=True)

        tk.Button(left, text=t("educacion.explorador_restaurar"),
                  font=("Arial", 8), bg=BG_CARD, fg=TEXTO,
                  relief="flat", padx=8, pady=5, cursor="hand2",
                  command=self._exp_restaurar).pack(fill="x", padx=10, pady=8)

        tk.Frame(left, bg=BORDE, height=1).pack(fill="x", padx=8)

        # Clasificación en vivo
        self._exp_lbl_clase = tk.Label(
            left, text="—", font=("Arial", 12, "bold"),
            bg=BG_PANEL)
        self._exp_lbl_clase.pack(pady=(10, 2))
        self._exp_lbl_params = tk.Label(
            left, text="", font=("Arial", 8),
            fg="#aaaacc", bg=BG_PANEL, justify="left")
        self._exp_lbl_params.pack(padx=10, anchor="w")

        # Canvas derecho
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._exp_canvas_frame = right

        # Caso de prueba fijo para explorar
        self._exp_t, self._exp_s = generar_senal_sintetica(8, 25, 0.05, 90, seed=42)
        self._exp_params_raw = extraer_parametros(self._exp_t, self._exp_s)
        self._exp_actualizar()

    def _exp_slider_moved(self, lbl, var, key):
        lbl.config(text=f"{var.get():.1f}")
        self._exp_umbrales[key] = var.get()
        self._exp_actualizar()

    def _exp_restaurar(self):
        from config import get_umbral
        defaults = {
            "T1":        get_umbral("T1"),
            "T2":        get_umbral("T2"),
            "pendiente": get_umbral("pendiente"),
            "indice_NIR":get_umbral("indice_NIR"),
        }
        for k, v in defaults.items():
            self._exp_vars[k].set(v)
            self._exp_umbrales[k] = v
        self._exp_actualizar()

    def _exp_actualizar(self):
        """Reclasifica con umbrales locales y actualiza figura."""
        u = self._exp_umbrales
        p = self._exp_params_raw

        # Clasificación manual con umbrales explorador
        ok_t1   = p["T1"]         <= u["T1"]
        ok_t2   = p["T2"]         <= u["T2"]
        ok_pend = p["pendiente"]  >= u["pendiente"]
        ok_nir  = p["indice_NIR"] >= u["indice_NIR"]
        aprobados = sum([ok_t1, ok_t2, ok_pend, ok_nir])

        if aprobados == 4:
            resultado = "ADECUADA";    color = VERDE
        elif aprobados >= 2:
            resultado = "BORDERLINE";  color = AMARILLO
        else:
            resultado = "COMPROMETIDA"; color = ACENTO

        resultado_txt = {
            "ADECUADA":     t("perfusion.adecuada"),
            "BORDERLINE":   t("perfusion.borderline"),
            "COMPROMETIDA": t("perfusion.comprometida"),
        }.get(resultado, resultado)
        self._exp_lbl_clase.config(
            text=t("educacion.explorador_perfusion_lbl").format(
                resultado=resultado_txt, aprobados=aprobados),
            fg=color)
        resumen = (
            f"T1={p['T1']:.1f}s  {'✓' if ok_t1 else '✗'}  (umbral ≤{u['T1']:.1f})\n"
            f"T2={p['T2']:.1f}s  {'✓' if ok_t2 else '✗'}  (umbral ≤{u['T2']:.1f})\n"
            f"Pend={p['pendiente']:.1f}  {'✓' if ok_pend else '✗'}  (umbral ≥{u['pendiente']:.1f})\n"
            f"NIR={p['indice_NIR']:.0f}  {'✓' if ok_nir else '✗'}  (umbral ≥{u['indice_NIR']:.0f})\n"
            f"─── Informativos ───\n"
            f"Fmax={p.get('Fmax', '—')}  T½={p.get('T_half', '—')}s  SR={p.get('slope_ratio', '—')}"
        )
        self._exp_lbl_params.config(text=resumen)

        # Figura
        fig, ax = plt.subplots(figsize=(7, 4), tight_layout=True)
        ax.plot(self._exp_t, self._exp_s, color=CYAN, linewidth=2,
                label=t("educacion.explorador_fig_signal"))
        ax.axvline(p["T1"], color=AMARILLO, linestyle="--", alpha=0.8,
                   label=f"T1={p['T1']:.1f}s")
        ax.axvline(p["T2"], color=VERDE,   linestyle="--", alpha=0.8,
                   label=f"T2={p['T2']:.1f}s")

        # Sombrear umbrales
        ylim = ax.get_ylim()
        ax.axvspan(0, u["T1"], alpha=0.06, color=VERDE,
                   label=f"Zona OK T1 (\u2264{u['T1']:.1f}s)")
        ax.axvspan(0, u["T2"], alpha=0.04, color=AMARILLO,
                   label=f"Zona OK T2 (\u2264{u['T2']:.1f}s)")

        titulo = t("educacion.explorador_fig_titulo").format(
            resultado=resultado_txt, aprobados=aprobados)
        ax.set_title(titulo, color=color, fontsize=11, fontweight="bold")
        ax.set_xlabel(t("educacion.fig_eje_tiempo"))
        ax.set_ylabel(t("educacion.fig_eje_intensidad"))
        ax.legend(fontsize=7, ncol=2)
        ax.grid(True, alpha=0.3)

        for w in self._exp_canvas_frame.winfo_children():
            w.destroy()
        self._embed_figura(self._exp_canvas_frame, fig)


    # ==============================================================
    #  MÓDULO EXPORTACIÓN AVANZADA
    # ==============================================================

    def _mostrar_exportacion(self):
        self._nav(self._build_exportacion)

    def _build_exportacion(self):
        self._limpiar()
        # ── Encabezado ────────────────────────────────────────────
        hdr = tk.Frame(self._contenedor, bg=BG_PANEL)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text=t("exportacion.titulo"),
                 bg=BG_PANEL, fg=AMARILLO,
                 font=("Helvetica", 18, "bold")).pack(anchor="w", padx=20, pady=(12, 2))
        tk.Label(hdr, text=t("exportacion.subtitulo"),
                 bg=BG_PANEL, fg=GRIS,
                 font=("Helvetica", 10)).pack(anchor="w", padx=20, pady=(0, 10))
        ttk.Separator(self._contenedor, orient="horizontal").pack(fill="x")

        body = tk.Frame(self._contenedor, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=30, pady=20)

        self._exp_status_var = tk.StringVar(value="")

        # ── Tarjeta 1 — Manual Técnico PDF ───────────────────────
        self._exp_card(
            body,
            title=t("exportacion.manual_btn"),
            desc=t("exportacion.manual_desc"),
            color=MORADO,
            command=self._exp_generar_manual,
            row=0,
        )
        # ── Tarjeta 2 — Reporte de sesión PDF ────────────────────
        self._exp_card(
            body,
            title=t("exportacion.sesion_btn"),
            desc=t("exportacion.sesion_desc"),
            color=VERDE,
            command=self._exp_generar_sesion,
            row=1,
        )
        # ── Tarjeta 3 — CSV ──────────────────────────────────────
        self._exp_card(
            body,
            title=t("exportacion.csv_btn"),
            desc="",
            color=CYAN,
            command=self._exp_exportar_csv,
            row=2,
        )
        # ── Barra de estado ───────────────────────────────────────
        tk.Label(body, textvariable=self._exp_status_var,
                 bg=BG_DARK, fg=VERDE,
                 font=("Helvetica", 10), wraplength=520,
                 justify="left").grid(row=6, column=0, sticky="w", pady=(10, 0))

    def _exp_card(self, parent, title, desc, color, command, row):
        """Tarjeta de acción reutilizable para el módulo de exportación."""
        card = tk.Frame(parent, bg=BG_CARD,
                        highlightbackground=color, highlightthickness=1)
        card.grid(row=row*2, column=0, sticky="ew", pady=(0, 4))
        parent.columnconfigure(0, weight=1)

        inner = tk.Frame(card, bg=BG_CARD)
        inner.pack(fill="x", padx=14, pady=10)

        tk.Button(
            inner, text=title,
            bg=color, fg=BG_DARK if color in (AMARILLO, CYAN, VERDE) else TEXTO,
            font=("Helvetica", 11, "bold"),
            relief="flat", cursor="hand2",
            command=command,
        ).pack(side="left", padx=(0, 16))

        if desc:
            tk.Label(inner, text=desc,
                     bg=BG_CARD, fg=GRIS,
                     font=("Helvetica", 9),
                     justify="left", wraplength=380,
                     anchor="w").pack(side="left", fill="x", expand=True)

    # ── Acciones de exportación ────────────────────────────────────

    def _exp_generar_manual(self):
        if not _MANUAL_PDF_DISPONIBLE:
            messagebox.showerror(t("avisos.error"),
                                 t("pdf.instalar_lib"))
            return
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title=t("exportacion.manual_btn"),
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="SENTINEL_Manual_Tecnico.pdf",
        )
        if not ruta:
            return
        self._exp_status_var.set(t("exportacion.manual_gen"))
        self._contenedor.update_idletasks()
        try:
            generar_manual_tecnico(ruta, db=self._db)
            self._exp_status_var.set(t("exportacion.manual_ok").format(ruta=ruta))
        except Exception as e:
            self._exp_status_var.set(t("exportacion.error").format(e=e))

    def _exp_generar_sesion(self):
        """Genera PDF multi-caso con tabla de todos los casos registrados."""
        casos = self._db.cargar_casos()
        if not casos:
            messagebox.showwarning(t("avisos.aviso"),
                                   t("exportacion.sesion_vacio"))
            return
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title=t("exportacion.sesion_btn"),
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="SENTINEL_Reporte_Sesion.pdf",
        )
        if not ruta:
            return
        self._exp_status_var.set(t("exportacion.sesion_gen"))
        self._contenedor.update_idletasks()
        try:
            self._exp_pdf_sesion(ruta, casos)
            n = len(casos)
            self._exp_status_var.set(
                t("exportacion.sesion_ok").format(ruta=ruta, n=n))
        except Exception as e:
            self._exp_status_var.set(t("exportacion.error").format(e=e))

    def _exp_pdf_sesion(self, ruta: str, casos: list):
        """Construye el PDF de sesión usando ReportLab."""
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from datetime import datetime

        doc = SimpleDocTemplate(ruta, pagesize=letter,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        H1 = ParagraphStyle("H1", fontSize=16, textColor=colors.HexColor("#A855F7"),
                             fontName="Helvetica-Bold", spaceAfter=6)
        NORM = ParagraphStyle("NORM", fontSize=9, textColor=colors.HexColor("#CCCCCC"),
                              fontName="Helvetica", spaceAfter=4)
        story = []
        story.append(Paragraph("SENTINEL — Reporte de Sesión", H1))
        story.append(Paragraph(
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  "
            f"Casos: {len(casos)}", NORM))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#A855F7"),
                                spaceAfter=10))

        # Tabla
        cols = ["Fecha", "Caso", "Módulo", "Resultado", "Score", "Params"]
        data = [cols]
        for c in casos:
            data.append([
                c.get("fecha", "")[:16],
                str(c.get("caso_id", ""))[:24],
                str(c.get("modulo", "")),
                str(c.get("resultado", "")),
                str(c.get("score", "")),
                str(c.get("aprobados", "")),
            ])
        col_w = [3*cm, 5*cm, 3.5*cm, 3.5*cm, 2*cm, 2*cm]
        tbl = Table(data, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2A2A2A")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.HexColor("#A855F7")),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("TEXTCOLOR",   (0, 1), (-1, -1), colors.HexColor("#CCCCCC")),
            ("BACKGROUND",  (0, 1), (-1, -1), colors.HexColor("#1F1F1F")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#1F1F1F"), colors.HexColor("#252525")]),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#444444")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)

        # Stats
        stats = self._db.estadisticas()
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#444444")))
        story.append(Spacer(1, 6))
        dist = stats.get("distribucion", {})
        conc = stats.get("concordancia", {})
        resumen = (
            f"Adecuada: {dist.get('ADECUADA', 0)}   "
            f"Borderline: {dist.get('BORDERLINE', 0)}   "
            f"Comprometida: {dist.get('COMPROMETIDA', 0)}   |   "
            f"Concordancia SENTINEL-Cirujano: "
            f"{conc.get('acuerdo', 0)} acuerdos / "
            f"{conc.get('desacuerdo', 0)} desacuerdos"
        )
        story.append(Paragraph(resumen, NORM))
        doc.build(story)

    def _exp_exportar_csv(self):
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title=t("exportacion.csv_btn"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="bioconnect_casos.csv",
        )
        if not ruta:
            return
        try:
            n = self._db.exportar_csv(ruta)
            self._exp_status_var.set(
                t("exportacion.csv_ok").format(n=n, ruta=ruta))
        except Exception as e:
            self._exp_status_var.set(t("exportacion.error").format(e=e))

    def _exportar_manual_desde_ayuda(self):
        """Wrapper invocado desde el botón en el Centro de Ayuda."""
        self._mostrar_exportacion()
        # Pequeño delay para que cargue la UI y luego dispara la exportación
        self._contenedor.after(100, self._exp_generar_manual)

    # ==============================================================
    #  MÓDULO CALIBRACIÓN DEL SISTEMA
    # ==============================================================

    def _mostrar_calibracion(self):
        self._nav(self._build_calibracion)

    def _build_calibracion(self):
        self._limpiar()
        # ── Encabezado ────────────────────────────────────────────
        hdr = tk.Frame(self._contenedor, bg=BG_PANEL)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text=t("calibracion.titulo"),
                 bg=BG_PANEL, fg=GRIS,
                 font=("Helvetica", 18, "bold")).pack(anchor="w", padx=20, pady=(12, 2))
        tk.Label(hdr, text=t("calibracion.subtitulo"),
                 bg=BG_PANEL, fg=GRIS,
                 font=("Helvetica", 10)).pack(anchor="w", padx=20, pady=(0, 10))
        ttk.Separator(self._contenedor, orient="horizontal").pack(fill="x")

        # ── Contenedor scrollable ─────────────────────────────────
        canvas = tk.Canvas(self._contenedor, bg=BG_DARK, highlightthickness=0)
        sb = ttk.Scrollbar(self._contenedor, orient="vertical",
                           command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=BG_DARK)
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")

        def _resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(body_win, width=e.width)
        canvas.bind("<Configure>", _resize)

        # ── Cargar perfil guardado ────────────────────────────────
        import json as _json
        perfil_path = "sentinel_calibracion.json"
        try:
            with open(perfil_path, "r", encoding="utf-8") as fp:
                perfil = _json.load(fp)
        except (FileNotFoundError, ValueError):
            perfil = {}

        pad_x = 30
        pad_y = 8

        # ── Sección: Perfil del Equipo ────────────────────────────
        tk.Label(body, text=t("calibracion.perfil_titulo"),
                 bg=BG_DARK, fg=GRIS,
                 font=("Helvetica", 14, "bold")).pack(
                     anchor="w", padx=pad_x, pady=(16, 4))

        campos_cfg = [
            ("campo_camara",     "camara",       perfil.get("camara", "")),
            ("campo_hospital",   "hospital",     perfil.get("hospital", "")),
            ("campo_fps_nominal","fps_nominal",   perfil.get("fps_nominal", "")),
            ("campo_fps_real",   "fps_real",      perfil.get("fps_real", "")),
            ("campo_operador",   "operador",      perfil.get("operador", "")),
        ]
        self._cal_vars = {}
        for llave, key, val in campos_cfg:
            fila = tk.Frame(body, bg=BG_DARK)
            fila.pack(fill="x", padx=pad_x, pady=2)
            tk.Label(fila, text=t(f"calibracion.{llave}"),
                     bg=BG_DARK, fg=TEXTO,
                     font=("Helvetica", 10), width=32, anchor="w").pack(side="left")
            var = tk.StringVar(value=val)
            self._cal_vars[key] = var
            tk.Entry(fila, textvariable=var,
                     bg=BG_CARD, fg=TEXTO, insertbackground=TEXTO,
                     font=("Helvetica", 10), relief="flat",
                     width=28).pack(side="left", padx=(6, 0))

        # Notas
        nota_frame = tk.Frame(body, bg=BG_DARK)
        nota_frame.pack(fill="x", padx=pad_x, pady=4)
        tk.Label(nota_frame, text=t("calibracion.campo_notas"),
                 bg=BG_DARK, fg=TEXTO,
                 font=("Helvetica", 10)).pack(anchor="w")
        self._cal_notas = tk.Text(nota_frame, height=3,
                                   bg=BG_CARD, fg=TEXTO,
                                   insertbackground=TEXTO,
                                   font=("Helvetica", 10),
                                   relief="flat", wrap="word")
        self._cal_notas.insert("1.0", perfil.get("notas", ""))
        self._cal_notas.pack(fill="x", pady=2)

        # Botón guardar perfil
        def _guardar_perfil():
            datos = {k: v.get() for k, v in self._cal_vars.items()}
            datos["notas"] = self._cal_notas.get("1.0", "end-1c")
            from datetime import datetime as _dt
            datos["fecha_calibracion"] = _dt.now().strftime("%d/%m/%Y %H:%M")
            with open(perfil_path, "w", encoding="utf-8") as fp:
                _json.dump(datos, fp, ensure_ascii=False, indent=2)
            self._cal_status_var.set(t("calibracion.perfil_guardado"))
            # Refrescar estado
            self._cal_refresh_estado(estado_frame, datos)

        tk.Button(body, text=t("calibracion.guardar_perfil"),
                  bg=VERDE, fg=BG_DARK,
                  font=("Helvetica", 11, "bold"),
                  relief="flat", cursor="hand2",
                  command=_guardar_perfil,
                  ).pack(anchor="w", padx=pad_x, pady=(6, 0))

        self._cal_status_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self._cal_status_var,
                 bg=BG_DARK, fg=VERDE,
                 font=("Helvetica", 9)).pack(anchor="w", padx=pad_x)

        # ── Separador ─────────────────────────────────────────────
        ttk.Separator(body, orient="horizontal").pack(fill="x",
                                                       padx=pad_x, pady=12)

        # ── Sección: Asistente de Calibración ─────────────────────
        tk.Label(body, text=t("calibracion.asistente_titulo"),
                 bg=BG_DARK, fg=GRIS,
                 font=("Helvetica", 14, "bold")).pack(
                     anchor="w", padx=pad_x, pady=(0, 6))

        pasos_txt = t_list("calibracion.pasos")  # lista de strings
        n_pasos   = len(pasos_txt)
        pasos_estado = perfil.get("pasos_completados", [False] * n_pasos)
        # Normalizar longitud
        while len(pasos_estado) < n_pasos:
            pasos_estado.append(False)
        self._cal_pasos_vars = []

        for i, texto_paso in enumerate(pasos_txt):
            var_chk = tk.BooleanVar(value=bool(pasos_estado[i]))
            self._cal_pasos_vars.append(var_chk)

            paso_frame = tk.Frame(body, bg=BG_CARD,
                                   highlightbackground=GRIS,
                                   highlightthickness=1)
            paso_frame.pack(fill="x", padx=pad_x, pady=3)

            hd = tk.Frame(paso_frame, bg=BG_CARD)
            hd.pack(fill="x", padx=10, pady=6)

            num_lbl = tk.Label(
                hd, text=t("calibracion.asistente_paso").format(
                    n=i+1, total=n_pasos),
                bg=BG_CARD, fg=AMARILLO,
                font=("Helvetica", 9, "bold"))
            num_lbl.pack(side="left")

            estado_lbl_var = tk.StringVar(
                value=t("calibracion.paso_ok") if var_chk.get()
                else t("calibracion.paso_pendiente"))
            estado_col = VERDE if var_chk.get() else ROJO
            estado_lbl = tk.Label(hd, textvariable=estado_lbl_var,
                                   bg=BG_CARD, fg=estado_col,
                                   font=("Helvetica", 9, "bold"))
            estado_lbl.pack(side="right")

            tk.Label(paso_frame, text=texto_paso,
                     bg=BG_CARD, fg=TEXTO,
                     font=("Helvetica", 9),
                     justify="left", wraplength=520, anchor="w",
                     ).pack(anchor="w", padx=10, pady=(0, 4))

            def _make_toggle(v=var_chk, lv=estado_lbl_var, ll=estado_lbl):
                def _toggle():
                    v.set(not v.get())
                    lv.set(t("calibracion.paso_ok") if v.get()
                           else t("calibracion.paso_pendiente"))
                    ll.config(fg=VERDE if v.get() else ROJO)
                    self._cal_guardar_pasos(perfil_path, perfil)
                return _toggle

            tk.Button(paso_frame,
                      text=t("calibracion.completar"),
                      bg=AMARILLO, fg=BG_DARK,
                      font=("Helvetica", 9),
                      relief="flat", cursor="hand2",
                      command=_make_toggle(),
                      ).pack(anchor="e", padx=10, pady=(0, 6))

        # ── Estado de calibración ─────────────────────────────────
        ttk.Separator(body, orient="horizontal").pack(fill="x",
                                                       padx=pad_x, pady=12)
        estado_frame = tk.Frame(body, bg=BG_DARK)
        estado_frame.pack(fill="x", padx=pad_x, pady=(0, 20))
        self._cal_refresh_estado(estado_frame, perfil)

    def _cal_guardar_pasos(self, ruta_perfil: str, perfil_base: dict):
        """Persiste el estado de cada paso del asistente."""
        import json as _json
        estados = [v.get() for v in self._cal_pasos_vars]
        perfil_base["pasos_completados"] = estados
        try:
            with open(ruta_perfil, "r", encoding="utf-8") as fp:
                datos = _json.load(fp)
        except (FileNotFoundError, ValueError):
            datos = {}
        datos["pasos_completados"] = estados
        with open(ruta_perfil, "w", encoding="utf-8") as fp:
            _json.dump(datos, fp, ensure_ascii=False, indent=2)

    def _cal_refresh_estado(self, frame: tk.Frame, perfil: dict):
        """Actualiza el widget de estado de calibración."""
        for w in frame.winfo_children():
            w.destroy()
        tk.Label(frame, text=t("calibracion.estado_titulo"),
                 bg=BG_DARK, fg=GRIS,
                 font=("Helvetica", 12, "bold")).pack(anchor="w")

        fecha = perfil.get("fecha_calibracion", "")
        if fecha:
            msg = t("calibracion.estado_ok").format(fecha=fecha)
            color = VERDE
        else:
            msg = t("calibracion.estado_nok")
            color = ROJO
        tk.Label(frame, text=msg, bg=BG_DARK, fg=color,
                 font=("Helvetica", 11, "bold")).pack(anchor="w", pady=2)

        if not fecha:
            tk.Label(frame, text=t("calibracion.advertencia"),
                     bg=BG_DARK, fg=AMARILLO,
                     font=("Helvetica", 9),
                     justify="left", wraplength=520).pack(anchor="w", pady=4)
        else:
            tk.Label(frame,
                     text=f"{t('calibracion.fecha_ultima')} {fecha}",
                     bg=BG_DARK, fg=GRIS,
                     font=("Helvetica", 9)).pack(anchor="w")


    # ==============================================================
    #  MÓDULO GENERADOR DE VIDEOS ICG SINTÉTICOS
    # ==============================================================

    # ── Catálogo de presets ─────────────────────────────────────
    # (nombre, clasificacion_esperada, t1, t2, forma, amplitud, ruido, seed)
    _GVID_PRESETS = [
        ("ADECUADA — Caso estándar",          "ADECUADA",      5.0, 20.0, 0.50, 100, 0.04, 42),
        ("ADECUADA — Perfusión excelente",    "ADECUADA",      3.0, 15.0, 0.65, 130, 0.03,  7),
        ("ADECUADA — Pico tardío OK",         "ADECUADA",      8.5, 27.0, 0.40,  90, 0.05, 99),
        ("ADECUADA — Anastomosis colorrectal","ADECUADA",      6.2, 22.5, 0.48, 105, 0.04, 13),
        ("BORDERLINE — T1 en límite",         "BORDERLINE",    9.8, 25.0, 0.35,  75, 0.05, 15),
        ("BORDERLINE — T2 en límite",         "BORDERLINE",    7.0, 29.5, 0.22,  65, 0.06, 31),
        ("BORDERLINE — Amplitud baja",        "BORDERLINE",    6.0, 22.0, 0.15,  55, 0.07, 55),
        ("BORDERLINE — Rise lento",           "BORDERLINE",    7.5, 26.0, 0.12,  70, 0.06, 88),
        ("COMPROMETIDA — Clásica",            "COMPROMETIDA", 14.0, 38.0, 0.10,  35, 0.08, 21),
        ("COMPROMETIDA — Severa",             "COMPROMETIDA", 18.0, 52.0, 0.06,  20, 0.10,  8),
        ("COMPROMETIDA — Solo T1 alto",       "COMPROMETIDA", 12.0, 25.0, 0.08,  45, 0.07, 63),
        ("COMPROMETIDA — Bajo índice NIR",    "COMPROMETIDA", 11.0, 33.0, 0.09,  18, 0.09, 37),
        ("Alta variabilidad (test ruido)",    "ADECUADA",      5.0, 20.0, 0.45,  95, 0.25, 77),
        ("Caso límite extremo",               "BORDERLINE",    9.9, 29.9, 0.20,  52, 0.08, 44),
    ]

    def _mostrar_gen_video(self):
        self._nav(self._build_gen_video)

    def _build_gen_video(self):
        self._gvid_cancelar = False   # flag para cancelar generación

        # ── Encabezado ─────────────────────────────────────────
        hdr = tk.Frame(self._contenedor, bg=BG_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("gen_video.titulo"),
                 bg=BG_PANEL, fg=VERDE,
                 font=("Arial", 14, "bold")).pack(side="left", padx=18, pady=10)
        tk.Label(hdr, text=t("gen_video.subtitulo"),
                 bg=BG_PANEL, fg=GRIS,
                 font=("Arial", 8)).pack(side="left")
        ttk.Separator(self._contenedor, orient="horizontal").pack(fill="x")

        # ── Cuerpo principal: izquierda + derecha ───────────────
        body = tk.Frame(self._contenedor, bg=BG_DARK)
        body.pack(fill="both", expand=True)

        # Columna izquierda — presets
        left = tk.Frame(body, bg=BG_PANEL, width=270,
                        highlightbackground=BORDE, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(10, 0), pady=10)
        left.pack_propagate(False)
        self._gvid_build_presets(left)

        # Columna derecha — parámetros + preview + botón
        right = tk.Frame(body, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self._gvid_build_params(right)

    # ── Panel de presets ────────────────────────────────────────

    def _gvid_build_presets(self, parent):
        tk.Label(parent, text=t("gen_video.sec_presets"),
                 bg=BG_PANEL, fg=GRIS,
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(parent,
                 text=t("gen_video.label_clasificacion"),
                 bg=BG_PANEL, fg="#555555",
                 font=("Arial", 7), justify="left").pack(anchor="w", padx=12)
        tk.Frame(parent, bg=BORDE, height=1).pack(fill="x", padx=8, pady=(4, 0))

        sb = ttk.Scrollbar(parent, orient="vertical")
        lb = tk.Listbox(parent, yscrollcommand=sb.set,
                        bg=BG_CARD, fg=TEXTO,
                        selectbackground=VERDE, selectforeground=BG_DARK,
                        font=("Arial", 9),
                        activestyle="none",
                        relief="flat", bd=0,
                        highlightthickness=0)
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.pack(fill="both", expand=True, padx=(8, 0), pady=4)

        color_map = {"ADECUADA": VERDE, "BORDERLINE": AMARILLO,
                     "COMPROMETIDA": ACENTO}
        for nombre, clasif, *_ in self._GVID_PRESETS:
            lb.insert("end", f"  {nombre}")
            lb.itemconfig("end", foreground=color_map.get(clasif, GRIS))

        def _on_select(e):
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            preset = self._GVID_PRESETS[idx]
            self._gvid_cargar_preset(preset)

        lb.bind("<<ListboxSelect>>", _on_select)
        self._gvid_listbox = lb

    # ── Panel de parámetros ─────────────────────────────────────

    def _gvid_build_params(self, parent):
        """Construye los sliders, preview y botón de generación."""
        # Variables de control
        self._gvid_t1      = tk.DoubleVar(value=5.0)
        self._gvid_t2      = tk.DoubleVar(value=20.0)
        self._gvid_amp     = tk.DoubleVar(value=100.0)
        self._gvid_forma   = tk.DoubleVar(value=0.50)
        self._gvid_ruido   = tk.DoubleVar(value=0.04)
        self._gvid_fps     = tk.IntVar(value=15)
        self._gvid_dur     = tk.IntVar(value=60)
        self._gvid_seed    = tk.IntVar(value=42)
        self._gvid_nombre  = tk.StringVar(value=t("gen_video.nombre_default"))
        self._gvid_status  = tk.StringVar(value=t("gen_video.selecciona_preset"))
        self._gvid_pct     = tk.IntVar(value=0)

        # ── Sección parámetros (2 columnas) ──────────────────────
        tk.Label(parent, text=t("gen_video.params_titulo"),
                 bg=BG_DARK, fg=GRIS,
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 4))

        params_frame = tk.Frame(parent, bg=BG_DARK)
        params_frame.pack(fill="x")

        def _slider(row_parent, label_key, var, from_, to, resolution,
                    fmt="{:.2f}", col_offset=0):
            """Helper: label + scale + value label en una fila."""
            fila = tk.Frame(row_parent, bg=BG_DARK)
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text=t(f"gen_video.{label_key}"),
                     bg=BG_DARK, fg=TEXTO,
                     font=("Arial", 8), width=36, anchor="w").pack(side="left")
            val_lbl = tk.Label(fila, text=fmt.format(var.get()),
                               bg=BG_DARK, fg=VERDE,
                               font=("Arial", 8, "bold"), width=7)
            val_lbl.pack(side="right")
            sc = ttk.Scale(fila, from_=from_, to=to, variable=var,
                           orient="horizontal", length=260)
            sc.pack(side="left", fill="x", expand=True, padx=(4, 4))

            def _upd(*_):
                # Snap to resolution
                v = round(var.get() / resolution) * resolution
                var.set(v)
                val_lbl.config(text=fmt.format(v))
                self._gvid_actualizar_preview()
            var.trace_add("write", _upd)
            return sc

        _slider(params_frame, "param_t1",   self._gvid_t1,   1.0, 20.0, 0.1)
        _slider(params_frame, "param_t2",   self._gvid_t2,   2.0, 55.0, 0.1)
        _slider(params_frame, "param_amp",  self._gvid_amp,  10.0, 200.0, 1.0,
                fmt="{:.0f}")
        _slider(params_frame, "param_forma",self._gvid_forma, 0.05, 0.80, 0.01)
        _slider(params_frame, "param_ruido",self._gvid_ruido, 0.01, 0.30, 0.01)

        # FPS + Duración + Seed en una fila
        meta_frame = tk.Frame(parent, bg=BG_DARK)
        meta_frame.pack(fill="x", pady=(4, 0))

        for lbl_key, var, options in [
            ("param_fps", self._gvid_fps, [10, 15, 25, 30]),
            ("param_dur", self._gvid_dur, [30, 45, 60, 90]),
        ]:
            col = tk.Frame(meta_frame, bg=BG_DARK)
            col.pack(side="left", padx=(0, 20))
            tk.Label(col, text=t(f"gen_video.{lbl_key}"),
                     bg=BG_DARK, fg=TEXTO,
                     font=("Arial", 8)).pack(anchor="w")
            om = ttk.Combobox(col, textvariable=var,
                              values=options, state="readonly", width=8)
            om.pack()
            om.bind("<<ComboboxSelected>>",
                    lambda e: self._gvid_actualizar_preview())

        seed_col = tk.Frame(meta_frame, bg=BG_DARK)
        seed_col.pack(side="left", padx=(0, 20))
        tk.Label(seed_col, text=t("gen_video.param_seed"),
                 bg=BG_DARK, fg=TEXTO, font=("Arial", 8)).pack(anchor="w")
        tk.Spinbox(seed_col, from_=0, to=999, textvariable=self._gvid_seed,
                   bg=BG_CARD, fg=TEXTO, font=("Arial", 9),
                   relief="flat", width=8,
                   command=self._gvid_actualizar_preview).pack()

        # Nombre del archivo
        nombre_row = tk.Frame(parent, bg=BG_DARK)
        nombre_row.pack(fill="x", pady=(4, 0))
        tk.Label(nombre_row, text=t("gen_video.param_nombre"),
                 bg=BG_DARK, fg=TEXTO, font=("Arial", 8)).pack(side="left")
        tk.Entry(nombre_row, textvariable=self._gvid_nombre,
                 bg=BG_CARD, fg=TEXTO, font=("Arial", 9),
                 insertbackground=TEXTO, relief="flat", width=26).pack(
                     side="left", padx=6)
        tk.Label(nombre_row, text=".avi",
                 bg=BG_DARK, fg=GRIS, font=("Arial", 8)).pack(side="left")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(8, 6))

        # ── Preview ───────────────────────────────────────────────
        preview_hdr = tk.Frame(parent, bg=BG_DARK)
        preview_hdr.pack(fill="x")
        tk.Label(preview_hdr, text=t("gen_video.sec_preview"),
                 bg=BG_DARK, fg=GRIS,
                 font=("Arial", 10, "bold")).pack(side="left")
        # Labels de parámetros extraídos y clasificación
        self._gvid_lbl_params = tk.Label(
            preview_hdr, text="", bg=BG_DARK, fg=GRIS,
            font=("Arial", 8), justify="left")
        self._gvid_lbl_params.pack(side="left", padx=20)
        self._gvid_lbl_clasif = tk.Label(
            preview_hdr, text="", bg=BG_DARK, fg=VERDE,
            font=("Arial", 10, "bold"))
        self._gvid_lbl_clasif.pack(side="right", padx=10)

        # Canvas de la figura
        self._gvid_fig_frame = tk.Frame(parent, bg=BG_DARK)
        self._gvid_fig_frame.pack(fill="x")

        # ── Botón Generar + barra de progreso ────────────────────
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(6, 6))

        btn_row = tk.Frame(parent, bg=BG_DARK)
        btn_row.pack(fill="x")
        self._gvid_btn = tk.Button(
            btn_row, text=t("gen_video.btn_generar"),
            bg=VERDE, fg=BG_DARK,
            font=("Arial", 11, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=6,
            command=self._gvid_generar)
        self._gvid_btn.pack(side="left")

        self._gvid_btn_cancel = tk.Button(
            btn_row, text=t("gen_video.btn_cancelar"),
            bg=ROJO, fg=TEXTO,
            font=("Arial", 9),
            relief="flat", cursor="hand2", padx=10, pady=6,
            command=self._gvid_cancelar_gen,
            state="disabled")
        self._gvid_btn_cancel.pack(side="left", padx=8)

        self._gvid_progress = ttk.Progressbar(
            btn_row, variable=self._gvid_pct,
            maximum=100, length=200, mode="determinate")
        self._gvid_progress.pack(side="left", padx=10)

        tk.Label(parent, textvariable=self._gvid_status,
                 bg=BG_DARK, fg=AMARILLO,
                 font=("Arial", 9), wraplength=520, justify="left").pack(
                     anchor="w", pady=(4, 0))

        # Preview inicial
        self._gvid_actualizar_preview()

    # ── Lógica de presets y preview ─────────────────────────────

    def _gvid_cargar_preset(self, preset):
        nombre, clasif, t1, t2, forma, amp, ruido, seed = preset
        # Suspender callbacks temporalmente con trace_info vacío
        self._gvid_t1.set(t1)
        self._gvid_t2.set(t2)
        self._gvid_amp.set(amp)
        self._gvid_forma.set(forma)
        self._gvid_ruido.set(ruido)
        self._gvid_seed.set(seed)
        # Nombre sugerido para el archivo
        slug = nombre.lower().replace(" ", "_").replace("—", "").replace("  ", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")[:28]
        self._gvid_nombre.set(f"icg_{slug}")
        self._gvid_status.set(t("gen_video.preset_cargado").format(nombre=nombre))
        self._gvid_actualizar_preview()

    def _gvid_actualizar_preview(self, *_):
        """Genera la curva con los parámetros actuales y actualiza la figura."""
        try:
            from BCV1_gen_video import generar_curva
            from parameter_extraction import extraer_parametros
            from config import clasificar_perfusion

            t1    = self._gvid_t1.get()
            t2    = self._gvid_t2.get()
            amp   = self._gvid_amp.get()
            forma = self._gvid_forma.get()
            ruido = self._gvid_ruido.get()
            dur   = self._gvid_dur.get()
            fps   = self._gvid_fps.get()
            seed  = self._gvid_seed.get()

            n_frames = fps * dur
            curva = generar_curva(t1, t2, forma, amp, n_frames, seed)
            tiempo = np.linspace(0, dur, n_frames)

            # Extracción de parámetros clínicos
            params = extraer_parametros(tiempo, curva, smooth=True)
            resultado, color_hex, aprobados, _ = clasificar_perfusion(params)

            # Actualizar labels
            color_map = {"ADECUADA": VERDE, "BORDERLINE": AMARILLO,
                         "COMPROMETIDA": ACENTO}
            col = color_map.get(resultado, GRIS)
            self._gvid_lbl_clasif.config(
                text=f"{resultado}  ({aprobados}/4)",
                fg=col)
            self._gvid_lbl_params.config(
                text=(f"T1={params['T1']:.1f}s  "
                      f"T2={params['T2']:.1f}s  "
                      f"Pend={params['pendiente']:.2f}  "
                      f"NIR={params['indice_NIR']:.1f}"),
                fg=GRIS)

            # Figura matplotlib
            fig, ax = plt.subplots(figsize=(7, 2.4),
                                   facecolor="#0F0F0F")
            ax.set_facecolor("#1A1A1A")
            ax.plot(tiempo, curva, color=col, linewidth=1.6, alpha=0.9)
            ax.axvline(params["T1"], color=AMARILLO, lw=1, ls="--",
                       alpha=0.8, label=f"T1={params['T1']:.1f}s")
            ax.axvline(params["T2"], color=MORADO, lw=1, ls="--",
                       alpha=0.8, label=f"T2={params['T2']:.1f}s")

            # Umbrales de color de fondo
            ax.axvspan(0,   10, alpha=0.04, color=VERDE)
            ax.axvspan(10, dur, alpha=0.04, color=ACENTO)

            ax.set_xlabel(t("gen_video.fig_eje_tiempo"), color="#888", fontsize=7)
            ax.set_ylabel(t("gen_video.fig_eje_intensidad"), color="#888", fontsize=7)
            ax.tick_params(colors="#666", labelsize=6)
            ax.spines[:].set_color("#333")
            leg = ax.legend(fontsize=6, framealpha=0.2,
                            labelcolor="white", loc="upper right")
            leg.get_frame().set_facecolor("#222")
            resultado_txt = {
                "ADECUADA":     t("perfusion.adecuada"),
                "BORDERLINE":   t("perfusion.borderline"),
                "COMPROMETIDA": t("perfusion.comprometida"),
            }.get(resultado, resultado)
            ax.set_title(t("gen_video.fig_curva_perfusion").format(resultado=resultado_txt),
                         color=col, fontsize=8, fontweight="bold")
            fig.tight_layout(pad=0.5)
            _apply_cjk_to_figure(fig)

            # Limpiar y redibujar en el frame
            for w in self._gvid_fig_frame.winfo_children():
                w.destroy()
            canvas = FigureCanvasTkAgg(fig, master=self._gvid_fig_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="x")
            plt.close(fig)

        except Exception:
            pass   # Silenciar errores durante ajuste de sliders

    # ── Generación del video ─────────────────────────────────────

    def _gvid_generar(self):
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title=t("gen_video.btn_generar"),
            defaultextension=".avi",
            filetypes=[("AVI Video", "*.avi"), ("Todos", "*.*")],
            initialfile=f"{self._gvid_nombre.get()}.avi",
        )
        if not ruta:
            return
        if not ruta.endswith(".avi"):
            ruta += ".avi"

        self._gvid_cancelar = False
        self._gvid_btn.config(state="disabled")
        self._gvid_btn_cancel.config(state="normal")
        self._gvid_pct.set(0)

        params = {
            "t1":    self._gvid_t1.get(),
            "t2":    self._gvid_t2.get(),
            "amp":   self._gvid_amp.get(),
            "forma": self._gvid_forma.get(),
            "ruido": self._gvid_ruido.get(),
            "fps":   self._gvid_fps.get(),
            "dur":   self._gvid_dur.get(),
            "seed":  self._gvid_seed.get(),
            "nombre_caso": self._gvid_nombre.get(),
        }
        threading.Thread(
            target=self._gvid_worker,
            args=(params, ruta),
            daemon=True,
        ).start()

    def _gvid_cancelar_gen(self):
        self._gvid_cancelar = True
        self._gvid_status.set(t("gen_video.cancelado"))

    def _gvid_worker(self, p, ruta):
        """Worker en hilo secundario: genera el video frame a frame."""
        try:
            from BCV1_gen_video import generar_curva, generar_frame

            fps      = int(p["fps"])
            dur      = int(p["dur"])
            n_frames = fps * dur
            curva    = generar_curva(
                p["t1"], p["t2"], p["forma"], p["amp"],
                n_frames, int(p["seed"]))

            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            writer = cv2.VideoWriter(ruta, fourcc, fps, (640, 480))

            for i in range(n_frames):
                if self._gvid_cancelar:
                    writer.release()
                    try:
                        import os; os.unlink(ruta)
                    except Exception:
                        pass
                    self._contenedor.after(
                        0, lambda: self._gvid_btn.config(state="normal"))
                    self._contenedor.after(
                        0, lambda: self._gvid_btn_cancel.config(state="disabled"))
                    return

                intensidad = float(curva[i])
                frame = generar_frame(intensidad, 640, 480,
                                      seed_frame=i + int(p["seed"]))
                t_s = i / fps

                caso_label = p["nombre_caso"].upper()
                cv2.putText(frame, f"SENTINEL — {caso_label}",
                            (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                            0.50, (180, 180, 180), 1, cv2.LINE_AA)
                cv2.putText(frame, f"t = {t_s:.1f} s",
                            (10, 44), cv2.FONT_HERSHEY_SIMPLEX,
                            0.48, (100, 220, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"NIR = {intensidad:.1f}",
                            (10, 64), cv2.FONT_HERSHEY_SIMPLEX,
                            0.48, (100, 220, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"FPS={fps}  DUR={dur}s  SEED={int(p['seed'])}",
                            (10, 472), cv2.FONT_HERSHEY_SIMPLEX,
                            0.36, (80, 80, 80), 1, cv2.LINE_AA)
                writer.write(frame)

                pct = int((i + 1) / n_frames * 100)
                if i % max(fps, 1) == 0:   # actualiza UI aprox. 1×/s
                    msg = t("gen_video.generando").format(
                        pct=pct, frame=i+1, total=n_frames)
                    self._contenedor.after(0, lambda m=msg, v=pct: (
                        self._gvid_status.set(m),
                        self._gvid_pct.set(v),
                    ))

            writer.release()
            msg_ok = t("gen_video.guardado").format(ruta=ruta)
            self._contenedor.after(0, lambda: (
                self._gvid_status.set(msg_ok),
                self._gvid_pct.set(100),
                self._gvid_btn.config(state="normal"),
                self._gvid_btn_cancel.config(state="disabled"),
            ))

        except Exception as e:
            msg_err = t("gen_video.error").format(e=e)
            self._contenedor.after(0, lambda: (
                self._gvid_status.set(msg_err),
                self._gvid_btn.config(state="normal"),
                self._gvid_btn_cancel.config(state="disabled"),
            ))


# ------------------------------------------------------------
# Ejecucion
# ------------------------------------------------------------

if __name__ == "__main__":
    app = BioConnectApp()
    # Ocultar ventana principal durante el splash
    app.withdraw()
    splash = SentinelSplash(app)
    splash.iniciar(on_done=lambda: app.deiconify())
    app.mainloop()