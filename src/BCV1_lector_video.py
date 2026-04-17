# ============================================================
#  SENTINEL — Modulo B: Lector de Video NIR/ICG
# Universidad de Guadalajara
# ============================================================

import cv2
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Importar desde modulos centralizados
from config import clasificar_perfusion, calcular_score_riesgo
from parameter_extraction import extraer_parametros
from i18n import t, init_desde_prefs
from logger import get_logger

log = get_logger("lector_video")

# ------------------------------------------------------------
# Lector de video
# ------------------------------------------------------------

def leer_curva_desde_video(ruta_video, mostrar_preview=True):
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

    x1 = int(ancho * 0.30)
    x2 = int(ancho * 0.70)
    y1 = int(alto  * 0.30)
    y2 = int(alto  * 0.70)

    intensidades = []
    frame_idx    = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gris       = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        roi        = gris[y1:y2, x1:x2]
        intensidad = float(np.mean(roi))
        intensidades.append(intensidad)

        if mostrar_preview and frame_idx % 10 == 0:
            preview = frame.copy()
            cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(preview, f"ROI: {intensidad:.1f}",
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 255, 255), 1)
            cv2.imshow("SENTINEL - Lectura de Video NIR", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        frame_idx += 1
        if frame_idx % (int(fps) * 10) == 0:
            log.info("... %ds procesados", frame_idx // int(fps))

    cap.release()
    cv2.destroyAllWindows()

    tiempo     = np.linspace(0, len(intensidades) / fps, len(intensidades))
    intensidad = np.array(intensidades, dtype=np.float32)

    if len(intensidad) > 21:
        intensidad = savgol_filter(intensidad, window_length=21, polyorder=3)
    intensidad = np.clip(intensidad, 0, None)

    log.info("Extraccion completa: %d frames", len(intensidades))
    return tiempo, intensidad, fps

# ------------------------------------------------------------
# Reporte visual
# ------------------------------------------------------------

def visualizar_reporte(tiempo, intensidad, params, resultado,
                       color_resultado, detalle, aprobados, nombre_caso, score):

    fig = plt.figure(figsize=(14, 8), facecolor="#1a1a2e")
    fig.suptitle(t("modulo_video.fig_titulo"),
                 color="white", fontsize=16, fontweight="bold", y=0.98)

    gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.35,
                          left=0.06, right=0.97, top=0.91, bottom=0.08)

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
                    linewidth=1.5, label=f"T1 = {params['T1']} s")
    ax1.axvline(t2_val, color="#9b59b6", linestyle="--",
                linewidth=1.5, label=f"T2 = {params['T2']} s")
    ax1.scatter([t2_val], [pico_val], color="#ff6b6b", s=80, zorder=5)

    ax1.set_xlabel(t("modulo_video.eje_tiempo"), color="white", fontsize=11)
    ax1.set_ylabel(t("modulo_video.eje_intensidad"), color="white", fontsize=11)
    ax1.set_title(t("modulo_video.titulo_curva").format(nombre_caso=nombre_caso),
                  color="white", fontsize=12)
    ax1.tick_params(colors="white")
    ax1.spines[:].set_color("#333355")
    ax1.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=9)
    ax1.grid(color="#222244", linestyle="--", linewidth=0.5)

    ax2 = fig.add_subplot(gs[0, 2])
    ax2.set_facecolor("#0f0f1a")
    ax2.set_xlim(0, 1); ax2.set_ylim(0, 1); ax2.axis("off")
    ax2.set_title(t("modulo_video.titulo_params"), color="white", fontsize=11)

    etiquetas = {
        "T1":         f"T1 = {params['T1']} s  (<=10)",
        "T2":         f"T2 = {params['T2']} s  (<=30)",
        "pendiente":  f"Pend. = {params['pendiente']}  (>=5)",
        "indice_NIR": f"NIR = {params['indice_NIR']}  (>=50)",
    }
    for i, (nombre, etiqueta) in enumerate(etiquetas.items()):
        y     = 0.80 - i * 0.16
        color = "#2ecc71" if detalle[nombre] else "#e74c3c"
        sim   = "OK" if detalle[nombre] else "X"
        ax2.add_patch(mpatches.FancyBboxPatch(
            (0.02, y - 0.05), 0.96, 0.12,
            boxstyle="round,pad=0.01",
            facecolor="#1a1a2e", edgecolor=color, linewidth=1.5))
        ax2.text(0.10, y + 0.01, sim, color=color,
                 fontsize=9, fontweight="bold", va="center")
        ax2.text(0.28, y + 0.01, etiqueta, color="white",
                 fontsize=8, va="center")

    # Parámetros adicionales (informativos)
    y_info = 0.80 - 4 * 0.16 - 0.06
    info_txt = (f"Fmax={params.get('Fmax', '—')}  "
                f"T½={params.get('T_half', '—')}s  "
                f"SR={params.get('slope_ratio', '—')}")
    ax2.text(0.50, y_info, info_txt, color="#00bcd4",
             fontsize=7, ha="center", va="center", style="italic")

    ax3 = fig.add_subplot(gs[1, 2])
    ax3.set_facecolor("#0f0f1a")
    ax3.set_xlim(0, 1); ax3.set_ylim(0, 1); ax3.axis("off")
    ax3.set_title(t("modulo_video.titulo_resultado"), color="white", fontsize=11)

    ax3.add_patch(mpatches.FancyBboxPatch(
        (0.05, 0.15), 0.90, 0.75,
        boxstyle="round,pad=0.02",
        facecolor=color_resultado + "33",
        edgecolor=color_resultado, linewidth=2.5))
    ax3.text(0.50, 0.74, t("modulo_video.perfusion"), color="white",
             fontsize=10, ha="center", va="center")
    ax3.text(0.50, 0.58, resultado, color=color_resultado,
             fontsize=12, fontweight="bold", ha="center", va="center")
    ax3.text(0.50, 0.44, t("modulo_video.params_ok").format(aprobados=aprobados),
             color="#aaaacc", fontsize=9, ha="center", va="center")

    # Score de riesgo
    color_score = "#2ecc71" if score >= 75 else "#f39c12" if score >= 50 else "#e74c3c"
    ax3.text(0.50, 0.31, t("modulo_video.score_label"),
             color="#aaaacc", fontsize=8, ha="center", va="center")
    ax3.text(0.50, 0.20, f"{score} / 100", color=color_score,
             fontsize=13, fontweight="bold", ha="center", va="center")

    ax3.text(0.50, 0.08,
             "Ref: Son et al. (2023)",
             color="#666688", fontsize=7.5, ha="center", va="center")

    nombre_archivo = nombre_caso.replace(" ", "_") + "_video.png"
    plt.savefig(nombre_archivo, dpi=170, bbox_inches="tight", facecolor="#1a1a2e")
    plt.show()
    log.info("Reporte guardado: %s", nombre_archivo)

# ------------------------------------------------------------
# Pipeline completo
# ------------------------------------------------------------

def analizar_video_completo(ruta_video, nombre_caso):
    tiempo, intensidad, fps = leer_curva_desde_video(ruta_video)
    if tiempo is None:
        return
    params   = extraer_parametros(tiempo, intensidad)
    score    = calcular_score_riesgo(params)
    resultado, color, aprobados, detalle = clasificar_perfusion(params)

    log.info("T1 = %s s  |  T2 = %s s  |  Pendiente = %s  |  Indice NIR = %s",
             params['T1'], params['T2'], params['pendiente'], params['indice_NIR'])
    log.info("Fmax = %s  |  T_half = %s s  |  slope_ratio = %s",
             params.get('Fmax', '—'), params.get('T_half', '—'), params.get('slope_ratio', '—'))
    log.info("Score SENTINEL: %d / 100", score)
    log.info("PERFUSION %s  (%d/4 parametros OK)", resultado, aprobados)

    visualizar_reporte(tiempo, intensidad, params, resultado,
                       color, detalle, aprobados, nombre_caso, score)

# ------------------------------------------------------------
# Ejecucion principal
# ------------------------------------------------------------

if __name__ == "__main__":

    init_desde_prefs()
    log.info("=" * 55)
    log.info("SENTINEL - Modulo B: Analisis de Video NIR/ICG")
    log.info("Bioconnect | Universidad de Guadalajara")
    log.info("=" * 55)

    videos = [
        ("icg_adecuada.avi",     "Caso 1 Perfusion Adecuada"),
        ("icg_borderline.avi",   "Caso 3 Perfusion Borderline"),
        ("icg_comprometida.avi", "Caso 2 Perfusion Comprometida"),
    ]

    for ruta, nombre in videos:
        if os.path.exists(ruta):
            analizar_video_completo(ruta, nombre)
        else:
            log.warning("No se encontro %s — omitiendo.", ruta)