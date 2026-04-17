# ============================================================
#  SENTINEL — Modulo de Segmentacion y Mapa Pixel a Pixel
#  BCV1_segmentacion.py
#  Universidad de Guadalajara | Ingenieria Biomedica
# ============================================================

import cv2
import numpy as np
from scipy.signal import savgol_filter
import os
from i18n import t, init_desde_prefs
from config import get_umbral
from logger import get_logger

log = get_logger("segmentacion")

# ------------------------------------------------------------
# Configuracion (centralizada desde config.py)
# ------------------------------------------------------------

T1_ADECUADA   = get_umbral("T1")   # 10.0 s (Son et al., 2023)
T1_BORDERLINE = 15.0
ALPHA_OVERLAY = 0.55   # transparencia del mapa sobre el frame

# ------------------------------------------------------------
# PASO 1 — Segmentacion automatica de ROI
# ------------------------------------------------------------

def segmentar_roi(frame_gris, umbral_pct=0.35):
    """
    Detecta automaticamente la region de tejido intestinal
    usando la zona mas brillante del frame NIR.

    Retorna:
        mascara   : imagen binaria del mismo tamanio que frame
        bbox      : (x1, y1, x2, y2) bounding box del ROI
        contorno  : contorno del tejido detectado
    """
    h, w = frame_gris.shape

    # Suavizado para reducir ruido de sensor
    blur = cv2.GaussianBlur(frame_gris, (15, 15), 0)

    # Umbral adaptativo — zona mas brillante del frame
    umbral_val = int(blur.max() * umbral_pct)
    umbral_val = max(umbral_val, 10)
    _, binaria = cv2.threshold(blur, umbral_val, 255, cv2.THRESH_BINARY)

    # Operaciones morfologicas para limpiar la mascara
    kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    binaria  = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, kernel)
    binaria  = cv2.morphologyEx(binaria, cv2.MORPH_OPEN,  kernel)

    # Encontrar contornos
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        # Fallback: ROI fijo central
        x1 = int(w*0.20); x2 = int(w*0.80)
        y1 = int(h*0.20); y2 = int(h*0.80)
        mascara = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(mascara, (x1,y1), (x2,y2), 255, -1)
        return mascara, (x1,y1,x2,y2), None

    # Tomar el contorno mas grande (tejido principal)
    contorno  = max(contornos, key=cv2.contourArea)
    mascara   = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mascara, [contorno], -1, 255, -1)

    # Bounding box con margen
    bx, by, bw, bh = cv2.boundingRect(contorno)
    margen = 10
    x1 = max(0,   bx - margen)
    y1 = max(0,   by - margen)
    x2 = min(w-1, bx + bw + margen)
    y2 = min(h-1, by + bh + margen)

    return mascara, (x1, y1, x2, y2), contorno


# ------------------------------------------------------------
# PASO 2 — Mapa de calor pixel a pixel
# ------------------------------------------------------------

def calcular_mapa_pixel(video_frames, fps, mascara_roi):
    """
    Calcula T1 para cada pixel dentro del ROI.

    Parametros:
        video_frames : array (n_frames, alto, ancho) en escala de grises
        fps          : frames por segundo del video
        mascara_roi  : imagen binaria del ROI

    Retorna:
        mapa_t1   : array (alto, ancho) con T1 por pixel (-1 = fuera de ROI)
        tiempo    : array de tiempos en segundos
    """
    n_frames, alto, ancho = video_frames.shape
    tiempo   = np.linspace(0, n_frames/fps, n_frames)
    mapa_t1  = np.full((alto, ancho), -1.0, dtype=np.float32)

    # Indices de pixels dentro del ROI
    ys, xs = np.where(mascara_roi > 0)
    n_pix  = len(ys)

    log.info("Calculando T1 para %d pixels...", n_pix)

    # Vectorizacion: extraer todas las curvas de una vez
    # curvas shape: (n_pixels, n_frames)
    curvas = video_frames[:, ys, xs].T.astype(np.float32)

    # Suavizado vectorizado
    if n_frames > 21:
        from scipy.signal import savgol_filter as sgf
        curvas = sgf(curvas, window_length=21, polyorder=3, axis=1)
    curvas = np.clip(curvas, 0, None)

    # Calcular pico por pixel
    picos    = curvas.max(axis=1)
    umbrales = picos * 0.10

    # Calcular T1 vectorizado
    for i in range(n_pix):
        pv = picos[i]
        if pv < 3.0:          # pixel sin senal — ignorar
            continue
        idx = np.where(curvas[i] >= umbrales[i])[0]
        if len(idx) > 0:
            mapa_t1[ys[i], xs[i]] = tiempo[idx[0]]

    log.info("T1 calculado en %d pixels validos", np.sum(mapa_t1 >= 0))
    return mapa_t1, tiempo


def colorear_mapa(mapa_t1, mascara_roi):
    """
    Convierte el mapa T1 en imagen BGR coloreada.

    Verde  : T1 <= T1_ADECUADA
    Amarillo: T1 <= T1_BORDERLINE
    Rojo   : T1 > T1_BORDERLINE
    Gris   : fuera del ROI o sin senal
    """
    alto, ancho = mapa_t1.shape
    img = np.zeros((alto, ancho, 3), dtype=np.uint8)

    # Fuera del ROI — gris oscuro
    img[mascara_roi == 0] = (40, 40, 40)

    # Dentro del ROI sin senal — gris medio
    sin_senal = (mascara_roi > 0) & (mapa_t1 < 0)
    img[sin_senal] = (80, 80, 80)

    # Zona adecuada — verde
    zona_ok = mapa_t1 <= T1_ADECUADA
    img[zona_ok, 0] = 19   # B
    img[zona_ok, 1] = 172  # G
    img[zona_ok, 2] = 77   # R  → BGR = verde MATLAB

    # Zona borderline — amarillo
    zona_bl = (mapa_t1 > T1_ADECUADA) & (mapa_t1 <= T1_BORDERLINE)
    img[zona_bl, 0] = 32   # B
    img[zona_bl, 1] = 177  # G
    img[zona_bl, 2] = 237  # R  → BGR = amarillo MATLAB

    # Zona comprometida — rojo
    zona_mal = mapa_t1 > T1_BORDERLINE
    img[zona_mal, 0] = 60   # B
    img[zona_mal, 1] = 76   # G
    img[zona_mal, 2] = 231  # R  → BGR = rojo MATLAB

    return img


# ------------------------------------------------------------
# PASO 3 — Linea de seccion sugerida
# ------------------------------------------------------------

def calcular_linea_seccion(mapa_t1, mascara_roi):
    """
    Encuentra la linea de seccion optima: el punto mas distal
    (hacia la derecha en el frame) donde la perfusion
    sigue siendo adecuada (T1 <= T1_ADECUADA).

    Retorna:
        x_linea   : coordenada x de la linea de seccion (-1 si no hay)
        confianza : porcentaje de la columna en zona adecuada
    """
    alto, ancho = mapa_t1.shape

    # Mascara de zona adecuada dentro del ROI
    zona_ok = (mapa_t1 <= T1_ADECUADA) & (mapa_t1 >= 0)

    # Buscar desde la derecha la primera columna
    # donde al menos 40% de los pixels son zona adecuada
    for x in range(ancho-1, -1, -1):
        col_roi    = mascara_roi[:, x]
        col_ok     = zona_ok[:, x]
        n_roi      = np.sum(col_roi > 0)
        n_ok       = np.sum(col_ok)

        if n_roi == 0:
            continue

        pct = n_ok / n_roi
        if pct >= 0.40:
            return x, round(float(pct) * 100, 1)

    return -1, 0.0


def dibujar_overlay(frame_original, mapa_coloreado, contorno,
                     x_linea, confianza, bbox):
    """
    Superpone el mapa de calor y la linea de seccion
    sobre el frame original.
    """
    resultado = frame_original.copy()
    x1, y1, x2, y2 = bbox

    # Overlay del mapa de calor (semitransparente)
    mascara_alpha = np.zeros_like(frame_original)
    mascara_alpha[y1:y2, x1:x2] = mapa_coloreado[y1:y2, x1:x2]

    resultado = cv2.addWeighted(resultado, 1 - ALPHA_OVERLAY,
                                 mascara_alpha, ALPHA_OVERLAY, 0)

    # Contorno del tejido detectado
    if contorno is not None:
        cv2.drawContours(resultado, [contorno], -1, (0, 255, 255), 2)

    # Linea de seccion sugerida
    if x_linea > 0:
        alto = frame_original.shape[0]
        # Linea principal
        cv2.line(resultado, (x_linea, y1), (x_linea, y2),
                 (255, 255, 255), 3)
        cv2.line(resultado, (x_linea, y1), (x_linea, y2),
                 (0, 255, 0), 1)

        # Flechas indicadoras
        cv2.arrowedLine(resultado,
                         (x_linea - 30, y1 + 20),
                         (x_linea - 5,  y1 + 20),
                         (0, 255, 0), 2, tipLength=0.4)
        cv2.arrowedLine(resultado,
                         (x_linea + 30, y1 + 20),
                         (x_linea + 5,  y1 + 20),
                         (0, 255, 0), 2, tipLength=0.4)

        # Etiqueta
        cv2.rectangle(resultado,
                       (x_linea - 80, y1 - 30),
                       (x_linea + 80, y1 - 5),
                       (0, 0, 0), -1)
        cv2.putText(resultado,
                    t("modulo_segmentacion.seccion_sugerida").format(conf=confianza),
                    (x_linea - 78, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38, (0, 255, 0), 1)

    # Leyenda
    h = frame_original.shape[0]
    leyenda = [
        ((19,172,77),  t("modulo_segmentacion.leyenda_adecuada")),
        ((32,177,237), t("modulo_segmentacion.leyenda_borderline")),
        ((60,76,231),  t("modulo_segmentacion.leyenda_comprometida")),
    ]
    for i, (color, texto) in enumerate(leyenda):
        y_ley = h - 60 + i*18
        cv2.rectangle(resultado,
                       (8, y_ley-10), (22, y_ley+2),
                       color, -1)
        cv2.putText(resultado, texto,
                    (28, y_ley),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.32, (220,220,220), 1)

    return resultado


# ------------------------------------------------------------
# Pipeline completo desde archivo de video
# ------------------------------------------------------------

def analizar_segmentacion(ruta_video, nombre_caso=None,
                           mostrar=True, guardar=True):
    """
    Pipeline completo: video -> segmentacion -> mapa pixel -> linea.
    """
    if nombre_caso is None:
        nombre_caso = os.path.splitext(os.path.basename(ruta_video))[0]

    log.info("=" * 55)
    log.info("SENTINEL — Segmentacion + Mapa Pixel + Linea")
    log.info("Caso: %s", nombre_caso)
    log.info("=" * 55)

    # Leer todos los frames
    cap    = cv2.VideoCapture(ruta_video)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 15
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ancho  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    log.info("%dx%d | %s FPS | %d frames", ancho, alto, fps, total)
    log.info("Cargando frames...")

    frames_gris = np.zeros((total, alto, ancho), dtype=np.uint8)
    frame_ref   = None
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames_gris[i] = gris
        if i == total // 2:   # frame del medio como referencia visual
            frame_ref = frame.copy()
        i += 1
    cap.release()
    frames_gris = frames_gris[:i]
    log.info("%d frames cargados.", i)

    # PASO 1 — Segmentacion en frame de mayor senal
    log.info("PASO 1: Segmentacion automatica de ROI...")
    frame_pico_idx = np.argmax(frames_gris.mean(axis=(1,2)))
    frame_pico     = frames_gris[frame_pico_idx]
    mascara, bbox, contorno = segmentar_roi(frame_pico)
    x1,y1,x2,y2 = bbox
    n_roi = int(np.sum(mascara > 0))
    log.info("ROI detectado: (%d,%d) -> (%d,%d)", x1, y1, x2, y2)
    log.info("Pixels en ROI: %d", n_roi)

    # PASO 2 — Mapa pixel a pixel
    log.info("PASO 2: Mapa de calor pixel a pixel...")
    mapa_t1, tiempo = calcular_mapa_pixel(frames_gris, fps, mascara)
    mapa_color      = colorear_mapa(mapa_t1, mascara)

    # Estadisticas
    validos      = mapa_t1[mapa_t1 >= 0]
    n_adec       = int(np.sum((mapa_t1 >= 0) & (mapa_t1 <= T1_ADECUADA)))
    n_border     = int(np.sum((mapa_t1 > T1_ADECUADA) & (mapa_t1 <= T1_BORDERLINE)))
    n_comp       = int(np.sum(mapa_t1 > T1_BORDERLINE))
    n_val        = len(validos)

    log.info("Pixels validos: %d", n_val)
    if n_val > 0:
        pct_a = 100*n_adec//n_val if n_val>0 else 0
        pct_b = 100*n_border//n_val if n_val>0 else 0
        pct_c = 100*n_comp//n_val if n_val>0 else 0
        log.info("Adecuada    : %d px (%d%%)", n_adec, pct_a)
        log.info("Borderline  : %d px (%d%%)", n_border, pct_b)
        log.info("Comprometida: %d px (%d%%)", n_comp, pct_c)

    # PASO 3 — Linea de seccion
    log.info("PASO 3: Calculando linea de seccion sugerida...")
    x_linea, confianza = calcular_linea_seccion(mapa_t1, mascara)
    if x_linea > 0:
        log.info("Linea de seccion: x=%d px (confianza: %d%%)", x_linea, confianza)
    else:
        log.info("No se encontro zona adecuada para seccion")

    # Overlay final
    if frame_ref is None:
        frame_ref = cv2.cvtColor(frames_gris[total//2], cv2.COLOR_GRAY2BGR)

    resultado = dibujar_overlay(frame_ref, mapa_color, contorno,
                                 x_linea, confianza, bbox)

    # Encabezado
    cv2.rectangle(resultado, (0,0), (ancho, 28), (0,0,0), -1)
    cv2.putText(resultado,
                f"SENTINEL — Mapa Pixel + Linea Seccion  |  {nombre_caso}",
                (8, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,212,255), 1)

    # Guardar
    if guardar:
        nombre_out = nombre_caso.replace(" ","_") + "_segmentacion.png"
        cv2.imwrite(nombre_out, resultado)
        log.info("Imagen guardada: %s", nombre_out)

    # Mostrar
    if mostrar:
        cv2.imshow(f"SENTINEL — {nombre_caso}", resultado)
        log.info("Presiona cualquier tecla para continuar...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return {
        "mapa_t1":    mapa_t1,
        "mapa_color": mapa_color,
        "mascara":    mascara,
        "bbox":       bbox,
        "x_linea":    x_linea,
        "confianza":  confianza,
        "n_adecuada": n_adec,
        "n_borderline": n_border,
        "n_comprometida": n_comp,
        "n_validos":  n_val,
    }


# ------------------------------------------------------------
# Ejecucion principal
# ------------------------------------------------------------

if __name__ == "__main__":
    init_desde_prefs()
    log.info("=" * 55)
    log.info("SENTINEL — Segmentacion + Mapa Pixel + Linea")
    log.info("Universidad de Guadalajara | Ingenieria Biomedica")
    log.info("=" * 55)

    videos = [
        ("icg_adecuada.avi",     "Caso 1 Perfusion Adecuada"),
        ("icg_borderline.avi",   "Caso 3 Perfusion Borderline"),
        ("icg_comprometida.avi", "Caso 2 Perfusion Comprometida"),
    ]

    for ruta, nombre in videos:
        if os.path.exists(ruta):
            analizar_segmentacion(ruta, nombre)
        else:
            log.warning("No se encontro %s", ruta)