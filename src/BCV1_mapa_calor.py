# ============================================================
#  SENTINEL — Mapa de Calor Espacial de Perfusion ICG
# Universidad de Guadalajara
# ============================================================

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from scipy.signal import savgol_filter
import os

# Importar umbrales desde modulo central
from config import get_umbral
from i18n import t, init_desde_prefs
from logger import get_logger

log = get_logger("mapa_calor")

# ------------------------------------------------------------
# Configuracion de la cuadricula
# ------------------------------------------------------------

FILAS  = 8
COLS   = 8
T1_ADECUADA   = get_umbral("T1")   # 10.0 s (Son et al., 2023)
T1_BORDERLINE = 15.0               # umbral intermedio clinico

# ------------------------------------------------------------
# Colormap personalizado: rojo -> amarillo -> verde
# ------------------------------------------------------------

CMAP_ICG = LinearSegmentedColormap.from_list(
    "icg_perfusion",
    [(0.0, "#e74c3c"),
     (0.4, "#f39c12"),
     (0.7, "#f1c40f"),
     (1.0, "#2ecc71")]
)

# ------------------------------------------------------------
# Extraer T1 por celda desde el video
# ------------------------------------------------------------

def extraer_mapa_t1(ruta_video):
    cap = cv2.VideoCapture(ruta_video)

    if not cap.isOpened():
        log.error("No se pudo abrir %s", ruta_video)
        return None, None, None

    fps   = cap.get(cv2.CAP_PROP_FPS)
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    log.info("Video: %s", ruta_video)
    log.info("Resolucion: %dx%d  |  FPS: %s  |  Frames: %d", ancho, alto, fps, total)
    log.info("Cuadricula: %dx%d = %d celdas", FILAS, COLS, FILAS*COLS)

    # Inicializar matriz de curvas por celda
    curvas = np.zeros((FILAS, COLS, total), dtype=np.float32)

    # Zona de analisis (misma que el ROI)
    x1 = int(ancho * 0.15)
    x2 = int(ancho * 0.85)
    y1 = int(alto  * 0.15)
    y2 = int(alto  * 0.85)

    ancho_roi = x2 - x1
    alto_roi  = y2 - y1
    paso_x    = ancho_roi // COLS
    paso_y    = alto_roi  // FILAS

    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for fi in range(FILAS):
            for ci in range(COLS):
                cx1 = x1 + ci * paso_x
                cx2 = cx1 + paso_x
                cy1 = y1 + fi * paso_y
                cy2 = cy1 + paso_y
                celda = gris[cy1:cy2, cx1:cx2]
                curvas[fi, ci, frame_idx] = float(np.mean(celda))

        frame_idx += 1
        if frame_idx % (int(fps) * 15) == 0:
            log.info("... %ds procesados", frame_idx // int(fps))

    cap.release()

    log.info("Extraccion completa: %d frames", frame_idx)
    return curvas, fps, (x1, y1, x2, y2, paso_x, paso_y)


# ------------------------------------------------------------
# Calcular T1 por celda
# ------------------------------------------------------------

def calcular_mapa_t1(curvas, fps):
    tiempo  = np.linspace(0, curvas.shape[2] / fps, curvas.shape[2])
    mapa_t1 = np.zeros((FILAS, COLS), dtype=np.float32)

    for fi in range(FILAS):
        for ci in range(COLS):
            senal = curvas[fi, ci, :]

            # Suavizado
            if len(senal) > 21:
                senal = savgol_filter(senal, window_length=21, polyorder=3)
            senal = np.clip(senal, 0, None)

            pico_val  = np.max(senal)
            umbral_t1 = 0.10 * pico_val
            idx_t1    = np.where(senal >= umbral_t1)[0]

            if len(idx_t1) > 0 and pico_val > 1.0:
                mapa_t1[fi, ci] = tiempo[idx_t1[0]]
            else:
                mapa_t1[fi, ci] = 60.0  # sin senal = peor caso

    return mapa_t1


# ------------------------------------------------------------
# Visualizar mapa de calor
# ------------------------------------------------------------

def visualizar_mapa(mapa_t1, nombre_caso, ruta_video):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="#1a1a2e")
    fig.suptitle(f"{t('modulo_calor.fig_titulo')}\n{nombre_caso}",
                 color="white", fontsize=14, fontweight="bold")

    # --- Panel izquierdo: mapa de calor T1 ---
    ax1 = axes[0]
    ax1.set_facecolor("#0f0f1a")

    # Normalizar T1: 0s (verde) a 20s+ (rojo)
    t1_norm = 1.0 - np.clip(mapa_t1 / 20.0, 0, 1)
    im = ax1.imshow(t1_norm, cmap=CMAP_ICG, vmin=0, vmax=1,
                    interpolation="bicubic", aspect="auto")

    # Anotaciones por celda
    for fi in range(FILAS):
        for ci in range(COLS):
            t1_val = mapa_t1[fi, ci]
            color  = "white" if t1_val > 10 else "#1a1a2e"
            ax1.text(ci, fi, f"{t1_val:.0f}s",
                     ha="center", va="center",
                     fontsize=7, color=color, fontweight="bold")

    ax1.set_title(t("modulo_calor.ax1_titulo"),
                  color="white", fontsize=10, pad=8)
    ax1.set_xlabel(t("modulo_calor.eje_col"), color="white", fontsize=9)
    ax1.set_ylabel(t("modulo_calor.eje_fila"), color="white", fontsize=9)
    ax1.tick_params(colors="white")

    # Colorbar
    cbar = plt.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label(t("modulo_calor.cbar_label"),
                   color="white", fontsize=8)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=7)

    # --- Panel derecho: clasificacion por zona ---
    ax2 = axes[1]
    ax2.set_facecolor("#0f0f1a")

    mapa_clase = np.zeros((FILAS, COLS, 3), dtype=np.float32)
    conteos = {"ADECUADA": 0, "BORDERLINE": 0, "COMPROMETIDA": 0}

    for fi in range(FILAS):
        for ci in range(COLS):
            t1 = mapa_t1[fi, ci]
            if t1 <= T1_ADECUADA:
                mapa_clase[fi, ci] = [0.18, 0.80, 0.44]   # verde
                conteos["ADECUADA"] += 1
            elif t1 <= T1_BORDERLINE:
                mapa_clase[fi, ci] = [0.95, 0.61, 0.07]   # amarillo
                conteos["BORDERLINE"] += 1
            else:
                mapa_clase[fi, ci] = [0.91, 0.30, 0.24]   # rojo
                conteos["COMPROMETIDA"] += 1

    ax2.imshow(mapa_clase, interpolation="nearest", aspect="auto")

    total_celdas = FILAS * COLS
    for fi in range(FILAS):
        for ci in range(COLS):
            t1 = mapa_t1[fi, ci]
            simbolo = "+" if t1 <= T1_ADECUADA else "~" if t1 <= T1_BORDERLINE else "x"
            ax2.text(ci, fi, simbolo, ha="center", va="center",
                     fontsize=9, color="white", fontweight="bold")

    ax2.set_title(t("modulo_calor.ax2_titulo"),
                  color="white", fontsize=10, pad=8)
    ax2.set_xlabel(t("modulo_calor.eje_col"), color="white", fontsize=9)
    ax2.set_ylabel(t("modulo_calor.eje_fila"), color="white", fontsize=9)
    ax2.tick_params(colors="white")

    # Leyenda
    leyenda = [
        mpatches.Patch(color="#2ecc71",
                       label=t("modulo_calor.leyenda_adecuada").format(
                           n=conteos['ADECUADA'],
                           pct=100*conteos['ADECUADA']//total_celdas)),
        mpatches.Patch(color="#f39c12",
                       label=t("modulo_calor.leyenda_borderline").format(
                           n=conteos['BORDERLINE'],
                           pct=100*conteos['BORDERLINE']//total_celdas)),
        mpatches.Patch(color="#e74c3c",
                       label=t("modulo_calor.leyenda_comprometida").format(
                           n=conteos['COMPROMETIDA'],
                           pct=100*conteos['COMPROMETIDA']//total_celdas)),
    ]
    ax2.legend(handles=leyenda, loc="lower center",
               bbox_to_anchor=(0.5, -0.22), ncol=1,
               facecolor="#1a1a2e", labelcolor="white", fontsize=8)

    plt.tight_layout()
    nombre_archivo = nombre_caso.replace(" ", "_") + "_mapa_calor.png"
    plt.savefig(nombre_archivo, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.show()
    log.info("Mapa guardado: %s", nombre_archivo)
    return conteos


# ------------------------------------------------------------
# Ejecucion principal
# ------------------------------------------------------------

if __name__ == "__main__":

    init_desde_prefs()
    log.info("=" * 55)
    log.info("SENTINEL — Mapa de Calor Espacial ICG")
    log.info("Bioconnect | Universidad de Guadalajara")
    log.info("=" * 55)

    videos = [
        ("icg_adecuada.avi",     "Caso 1 Perfusion Adecuada"),
        ("icg_borderline.avi",   "Caso 3 Perfusion Borderline"),
        ("icg_comprometida.avi", "Caso 2 Perfusion Comprometida"),
    ]

    for ruta, nombre in videos:
        if not os.path.exists(ruta):
            log.warning("No se encontro %s", ruta)
            continue

        curvas, fps, dims = extraer_mapa_t1(ruta)
        if curvas is None:
            continue

        mapa_t1 = calcular_mapa_t1(curvas, fps)
        conteos = visualizar_mapa(mapa_t1, nombre, ruta)

        log.info("Distribucion espacial:")
        log.info("  Adecuada    : %d celdas", conteos['ADECUADA'])
        log.info("  Borderline  : %d celdas", conteos['BORDERLINE'])
        log.info("  Comprometida: %d celdas", conteos['COMPROMETIDA'])