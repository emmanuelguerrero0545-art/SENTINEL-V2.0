# ============================================================
#  BIOCONNECT — Generador de Video ICG Sintético
# Universidad de Guadalajara
# ============================================================

import numpy as np
import cv2
from scipy.signal import savgol_filter
from scipy.stats import gamma as gamma_dist
from logger import get_logger

log = get_logger("gen_video")

FPS          = 15
DURACION     = 60
ANCHO        = 640
ALTO         = 480
TOTAL_FRAMES = FPS * DURACION

def generar_curva(t1, t2, pendiente, amplitud, n_frames, seed=42):
    rng     = np.random.default_rng(seed)
    tiempo  = np.linspace(0, 60, n_frames)
    t_shift = np.maximum(tiempo - t1, 0)
    k       = max((t2 - t1) * pendiente, 1.5)
    theta   = (t2 - t1) / k
    senal   = gamma_dist.pdf(t_shift, a=k, scale=theta)
    senal   = senal / senal.max() * amplitud
    senal  += rng.normal(0, amplitud * 0.02, n_frames)
    senal   = np.clip(senal, 0, None)
    senal   = savgol_filter(senal, window_length=21, polyorder=3)
    return np.clip(senal, 0, None)

def generar_frame(intensidad_global, ancho, alto, seed_frame):
    rng   = np.random.default_rng(seed_frame)
    frame = rng.normal(3, 1.5, (alto, ancho)).astype(np.float32)
    frame = np.clip(frame, 0, 255)

    mascara = np.zeros((alto, ancho), dtype=np.float32)
    cx, cy  = ancho // 2, alto // 2
    cv2.ellipse(mascara, (cx, cy), (220, 160), 0, 0, 360, 1.0, -1)

    for i in range(alto):
        for j in range(ancho):
            if mascara[i, j] > 0:
                dist = np.sqrt(((i - cy) / 160) ** 2 + ((j - cx) / 220) ** 2)
                mascara[i, j] = max(0, 1.0 - dist * 0.6)

    textura     = rng.normal(1.0, 0.12, (alto, ancho)).astype(np.float32)
    textura     = cv2.GaussianBlur(textura, (15, 15), 0)
    fluorescencia = mascara * textura * intensidad_global * 2.2
    frame      += fluorescencia

    desplaz = int(np.sin(seed_frame / 30) * 2)
    M       = np.float32([[1, 0, desplaz], [0, 1, 0]])
    frame   = cv2.warpAffine(frame, M, (ancho, alto))

    frame  += rng.poisson(frame * 0.05).astype(np.float32)
    frame   = np.clip(frame, 0, 255).astype(np.uint8)
    frame_verde = np.zeros((alto, ancho, 3), dtype=np.uint8)
    frame_verde[:, :, 1] = frame
    return frame_verde

def generar_video(nombre_archivo, t1, t2, pendiente, amplitud, seed=42, caso=""):
    log.info(f"Generando: {nombre_archivo}")
    curva  = generar_curva(t1, t2, pendiente, amplitud, TOTAL_FRAMES, seed)
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    nombre_avi = nombre_archivo.replace(".mp4", ".avi")
    writer = cv2.VideoWriter(nombre_avi, fourcc, FPS, (ANCHO, ALTO))

    for i in range(TOTAL_FRAMES):
        intensidad = float(curva[i])
        frame      = generar_frame(intensidad, ANCHO, ALTO, seed_frame=i + seed)
        tiempo_s   = i / FPS

        cv2.putText(frame, f"BIOCONNECT - {caso}",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (180, 180, 180), 1, cv2.LINE_AA)
        cv2.putText(frame, f"t = {tiempo_s:.1f} s",
                    (10, 48), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (100, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"NIR = {intensidad:.1f}",
                    (10, 72), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (100, 220, 255), 1, cv2.LINE_AA)

        writer.write(frame)

        if i % (FPS * 10) == 0:
            log.info(f"... {int(tiempo_s)}s / {DURACION}s")

    writer.release()
    log.info(f"Guardado: {nombre_avi}")

if __name__ == "__main__":
    log.info("=" * 55)
    log.info("  BIOCONNECT — Generador de Video ICG Sintético")
    log.info("  Bioconnect | Universidad de Guadalajara")
    log.info("=" * 55)

    casos = [
        ("icg_adecuada.mp4",     5,  20, 0.50, 100, 42, "Perfusion ADECUADA"),
        ("icg_borderline.mp4",   9,  28, 0.25,  60, 15, "Perfusion BORDERLINE"),
        ("icg_comprometida.mp4", 15, 40, 0.10,  25,  7, "Perfusion COMPROMETIDA"),
    ]

    for args in casos:
        generar_video(*args)

    log.info("Todos los videos generados.")