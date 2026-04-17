# ============================================================
#  SENTINEL — Analisis en Tiempo Real v2.0
#  Pipeline optimizado con 3 hilos y deteccion de fases
#  Universidad de Guadalajara | Ingenieria Biomedica
# ============================================================

import cv2
import numpy as np
from scipy.signal import savgol_filter
from collections import deque
import threading
import queue
import time
import os

# Importar desde modulos centralizados
from config import clasificar_perfusion, calcular_score_riesgo, get_umbral
from parameter_extraction import extraer_parametros
from i18n import t, init_desde_prefs
from logger import get_logger

log = get_logger("tiempo_real")

# Mapa de colores para overlay OpenCV.
# NOTA: Los valores se almacenan en orden RGB porque línea 396 invierte a BGR
# antes de pasarlos a cv2.rectangle / cv2.putText.
# ADECUADA:    verde   #22C55E → RGB(34, 197, 94)
# BORDERLINE:  amarillo #FF9900 → RGB(255, 153, 0)
# COMPROMETIDA:rojo    #EF4444 → RGB(239, 68,  68)
_COLOR_BGR = {
    "ADECUADA":     (34,  197, 94),   # RGB de #22C55E — verde
    "BORDERLINE":   (255, 153, 0),    # RGB de #FF9900 — amarillo/naranja
    "COMPROMETIDA": (239, 68,  68),   # RGB de #EF4444 — rojo
}

def calcular_score(params):
    return calcular_score_riesgo(params)

def etiqueta_score(score):
    if score >= 60:
        return t("score.bajo_riesgo")
    elif score >= 40:
        return t("score.riesgo_moderado")
    else:
        return t("score.alto_riesgo")

# ------------------------------------------------------------
# Extractor de parametros (ventana deslizante)
# ------------------------------------------------------------

def extraer_params_ventana(tiempo_arr, intens_arr):
    if len(intens_arr) < 30:
        return None
    return extraer_parametros(tiempo_arr, intens_arr, smooth=False)

# ------------------------------------------------------------
# Detector de fases del bolo ICG
# ------------------------------------------------------------

class DetectorFase:
    """
    Detecta la fase actual del bolo ICG:
    - ESPERANDO:    sin senal significativa aun
    - SUBIDA:       senal en ascenso activo
    - ESTABILIZADO: pico alcanzado, senal en descenso o plana
    """
    ESPERANDO    = "ESPERANDO"
    SUBIDA       = "SUBIDA"
    ESTABILIZADO = "ESTABILIZADO"

    def __init__(self, umbral_inicio=3.0, ventana_estab=15):
        self.fase           = self.ESPERANDO
        self.umbral_inicio  = umbral_inicio
        self.ventana_estab  = ventana_estab
        self.pico_val       = 0.0
        self.pico_tiempo    = 0.0
        self._ultimos       = deque(maxlen=ventana_estab)

    def actualizar(self, tiempo_actual, intensidad_actual, intensidad_max):
        self._ultimos.append(intensidad_actual)

        if self.fase == self.ESPERANDO:
            if intensidad_actual > self.umbral_inicio:
                self.fase = self.SUBIDA

        elif self.fase == self.SUBIDA:
            if intensidad_actual > self.pico_val:
                self.pico_val    = intensidad_actual
                self.pico_tiempo = tiempo_actual
            # Estabilizado si llevamos ventana_estab frames
            # y la intensidad no supera el 95% del pico
            if len(self._ultimos) == self.ventana_estab:
                if max(self._ultimos) < 0.95 * self.pico_val:
                    self.fase = self.ESTABILIZADO

        return self.fase

    def color_fase(self):
        if self.fase == self.ESPERANDO:
            return (150, 150, 180)
        elif self.fase == self.SUBIDA:
            return (237, 177, 32)
        else:
            return (119, 172, 48)

    def texto_fase(self):
        if self.fase == self.ESPERANDO:
            return t("modulo_tiempo_real.fase_esperando")
        elif self.fase == self.SUBIDA:
            return t("modulo_tiempo_real.fase_subida")
        else:
            return t("modulo_tiempo_real.fase_estabilizado")

# ------------------------------------------------------------
# Pipeline optimizado con 3 hilos
# ------------------------------------------------------------

def analizar_tiempo_real(ruta_video, nombre_caso=""):
    cap = cv2.VideoCapture(ruta_video)
    if not cap.isOpened():
        log.error("No se pudo abrir %s", ruta_video)
        return

    fps   = cap.get(cv2.CAP_PROP_FPS) or 15
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    delay = max(1, int(1000 / fps))

    log.info("Iniciando analisis: %s", nombre_caso)
    log.info("Resolucion: %dx%d  FPS: %s", ancho, alto, fps)
    log.info("Presiona Q para salir")

    # ROI central
    x1=int(ancho*0.30); x2=int(ancho*0.70)
    y1=int(alto*0.30);  y2=int(alto*0.70)

    # Colas de comunicacion entre hilos
    cola_frames    = queue.Queue(maxsize=5)   # captura -> procesamiento
    cola_display   = queue.Queue(maxsize=3)   # procesamiento -> UI (separada)
    cola_resultado = queue.Queue(maxsize=2)   # procesamiento -> UI (resultados)

    # Estado compartido (thread-safe con lock)
    estado = {
        "activo":       True,
        "intensidades": deque(maxlen=600),
        "tiempos":      deque(maxlen=600),
        "params":       None,
        "resultado":    None,
        "color":        (150, 150, 180),
        "aprobados":    0,
        "score":        0.0,
        "fase":         DetectorFase.ESPERANDO,
        "fase_color":   (150, 150, 180),
        "fase_texto":   t("modulo_tiempo_real.fase_esperando"),
        "params_fijos": False,   # True cuando la fase es ESTABILIZADO
    }
    lock    = threading.Lock()
    detector = DetectorFase(umbral_inicio=3.0)

    # ── HILO 1: Captura ──────────────────────────────────────
    def hilo_captura():
        frame_idx = 0
        while estado["activo"]:
            ret, frame = cap.read()
            if not ret:
                estado["activo"] = False
                break
            try:
                cola_frames.put_nowait((frame_idx, frame))
            except queue.Full:
                pass  # descarta frame si la cola esta llena
            frame_idx += 1
            time.sleep(1.0 / fps)
        cap.release()

    # ── HILO 2: Procesamiento ────────────────────────────────
    def hilo_procesamiento():
        ultimo_calculo = 0
        # Actualizar cada 0.5s en SUBIDA, cada 1s en ESPERANDO
        intervalo_rapido = max(1, int(fps * 0.5))
        intervalo_lento  = max(1, int(fps))

        while estado["activo"]:
            try:
                frame_idx, frame = cola_frames.get(timeout=0.1)
            except queue.Empty:
                continue

            # Extraer intensidad ROI
            gris       = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            intensidad = float(np.mean(gris[y1:y2, x1:x2]))
            tiempo_act = frame_idx / fps

            with lock:
                estado["intensidades"].append(intensidad)
                estado["tiempos"].append(tiempo_act)

                # Actualizar detector de fase
                intens_max = max(estado["intensidades"]) if estado["intensidades"] else 1
                fase = detector.actualizar(tiempo_act, intensidad, intens_max)
                estado["fase"]       = fase
                estado["fase_color"] = detector.color_fase()
                estado["fase_texto"] = detector.texto_fase()

            # Enviar frame a cola de display (sin bloquear)
            try:
                cola_display.put_nowait((frame_idx, frame))
            except queue.Full:
                pass

            # Intervalo adaptativo: más rápido en SUBIDA
            intervalo = intervalo_rapido if fase == DetectorFase.SUBIDA else intervalo_lento

            # Recalcular parametros
            # EXCEPTO si ya estamos estabilizados (parametros fijos)
            if frame_idx - ultimo_calculo >= intervalo:
                ultimo_calculo = frame_idx
                with lock:
                    ya_fijo = estado["params_fijos"]
                    n       = len(estado["intensidades"])

                if not ya_fijo and n > 30:
                    intens_arr = np.array(list(estado["intensidades"]),
                                          dtype=np.float32)
                    tiempo_arr = np.array(list(estado["tiempos"]),
                                          dtype=np.float32)
                    # Filtrado: solo los últimos 100 puntos para O(1) constante
                    if len(intens_arr) > 100:
                        intens_filt = intens_arr.copy()
                        intens_filt[-100:] = savgol_filter(intens_arr[-100:], 21, 3)
                    elif len(intens_arr) > 21:
                        intens_filt = savgol_filter(intens_arr, 21, 3)
                    else:
                        intens_filt = intens_arr
                    intens_filt = np.clip(intens_filt, 0, None)

                    params = extraer_params_ventana(tiempo_arr, intens_filt)
                    if params:
                        resultado, _, aprobados, _ = \
                            clasificar_perfusion(params)
                        color = _COLOR_BGR.get(resultado, (150, 150, 180))
                        score = calcular_score(params)

                        with lock:
                            estado["params"]    = params
                            estado["resultado"] = resultado
                            estado["color"]     = color
                            estado["aprobados"] = aprobados
                            estado["score"]     = score
                            # Congelar parametros si estabilizado
                            if fase == DetectorFase.ESTABILIZADO:
                                estado["params_fijos"] = True

    # ── HILO 3: UI (OpenCV) ──────────────────────────────────
    def hilo_ui():
        # Crear figura una sola vez
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.figure as mplfig

        PANEL_W = 420
        PANEL_H = alto

        while estado["activo"]:
            # Obtener frame mas reciente de la cola de display
            frame_disp = None
            try:
                _, frame_disp = cola_display.get_nowait()
            except queue.Empty:
                time.sleep(0.03)
                continue

            # Construir canvas
            canvas = np.zeros((PANEL_H, ancho + PANEL_W, 3), dtype=np.uint8)

            # Frame con ROI
            frame_anotado = frame_disp.copy()
            cv2.rectangle(frame_anotado, (x1,y1), (x2,y2), (0,255,255), 2)
            cv2.putText(frame_anotado, t("modulo_tiempo_real.roi_label"),
                        (x1+4, y1-6), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, (0,255,255), 1)

            with lock:
                fase_color  = estado["fase_color"]
                fase_texto  = estado["fase_texto"]
                params      = estado["params"]
                resultado   = estado["resultado"]
                color_res   = estado["color"]
                aprobados   = estado["aprobados"]
                score       = estado["score"]
                params_fijo = estado["params_fijos"]
                n_intens    = len(estado["intensidades"])
                intens_list = list(estado["intensidades"])[-300:]
                tiempo_list = list(estado["tiempos"])[-300:]

            cv2.putText(frame_anotado,
                        f"SENTINEL  |  {nombre_caso}",
                        (10,22), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0,212,255), 1)
            cv2.putText(frame_anotado, fase_texto,
                        (10,44), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, fase_color, 1)

            h_frame = min(frame_anotado.shape[0], PANEL_H)
            w_frame = min(frame_anotado.shape[1], ancho)
            canvas[:h_frame, :w_frame] = frame_anotado[:h_frame, :w_frame]

            # Panel derecho
            panel = canvas[:, ancho:]
            panel[:] = (26, 26, 46)

            # Titulo panel
            cv2.putText(canvas, t("modulo_tiempo_real.motor_titulo"),
                        (ancho+10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,212,255), 2)
            cv2.line(canvas,
                     (ancho+5, 38),
                     (ancho+PANEL_W-5, 38), (0,212,255), 1)

            # Mini curva ICG (dibujada directamente en OpenCV)
            GRAF_X = ancho + 10
            GRAF_Y = 48
            GRAF_W = PANEL_W - 20
            GRAF_H = 90

            cv2.rectangle(canvas,
                           (GRAF_X, GRAF_Y),
                           (GRAF_X+GRAF_W, GRAF_Y+GRAF_H),
                           (20,20,40), -1)
            cv2.rectangle(canvas,
                           (GRAF_X, GRAF_Y),
                           (GRAF_X+GRAF_W, GRAF_Y+GRAF_H),
                           (50,50,100), 1)

            if len(intens_list) > 2:
                vals = np.array(intens_list)
                vmax = max(vals.max(), 1)
                n    = len(vals)
                # Vectorizado: construir array de puntos y dibujar con polylines
                ix = (np.arange(n) / n * GRAF_W + GRAF_X).astype(np.int32)
                iy = (GRAF_Y + GRAF_H - (vals / vmax) * (GRAF_H - 8) - 4).astype(np.int32)
                pts_array = np.column_stack((ix, iy)).reshape((-1, 1, 2))
                cv2.polylines(canvas, [pts_array], False, (0, 212, 255), 1)

            cv2.putText(canvas,
                        t("modulo_tiempo_real.curva_label").format(n=n_intens),
                        (GRAF_X, GRAF_Y+GRAF_H+14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, (150,150,180), 1)

            # Separador
            y_sep = GRAF_Y + GRAF_H + 24
            cv2.line(canvas,
                     (ancho+5, y_sep),
                     (ancho+PANEL_W-5, y_sep), (50,50,100), 1)

            # Parametros
            Y_PAR = y_sep + 16
            if params:
                param_lista = [
                    (f"T1  = {params['T1']} s",
                     params['T1'] <= get_umbral("T1")),
                    (f"T2  = {params['T2']} s",
                     params['T2'] <= get_umbral("T2")),
                    (f"Pend= {params['pendiente']}",
                     params['pendiente'] >= get_umbral("pendiente")),
                    (f"NIR = {params['indice_NIR']}",
                     params['indice_NIR'] >= get_umbral("indice_NIR")),
                ]
                for i, (texto, ok) in enumerate(param_lista):
                    # cv2 usa BGR directo: verde(34,197,94) | rojo(68,68,239)
                    c   = (34, 197, 94) if ok else (68, 68, 239)
                    sym = "OK" if ok else "X "
                    cv2.putText(canvas,
                                f"{sym}  {texto}",
                                (ancho+15, Y_PAR + i*22),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.40, c, 1)
                if params_fijo:
                    cv2.putText(canvas, t("modulo_tiempo_real.params_fijos"),
                                (ancho+15, Y_PAR + 4*22),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.35, (119,172,48), 1)
            else:
                cv2.putText(canvas, t("modulo_tiempo_real.calculando"),
                            (ancho+15, Y_PAR+10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.40, (150,150,180), 1)

            # Resultado / semaforo
            Y_RES = alto - 145
            cv2.line(canvas,
                     (ancho+5, Y_RES-10),
                     (ancho+PANEL_W-5, Y_RES-10), (50,50,100), 1)

            if resultado and params:
                bgr = (color_res[2], color_res[1], color_res[0])
                cv2.rectangle(canvas,
                               (ancho+10, Y_RES),
                               (ancho+PANEL_W-10, Y_RES+60),
                               bgr, -1)
                cv2.putText(canvas, t("modulo_tiempo_real.perfusion"),
                            (ancho+20, Y_RES+18),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45, (255,255,255), 1)
                cv2.putText(canvas, resultado,
                            (ancho+20, Y_RES+44),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (255,255,255), 2)

                # Score — cv2 BGR directo: verde(34,197,94) | amarillo(0,153,255) | rojo(68,68,239)
                csc = (34, 197, 94)  if score >= 60 else \
                      (0,  153, 255) if score >= 40 else (68, 68, 239)
                cv2.putText(canvas,
                            f"Score: {score}/100  {etiqueta_score(score)}",
                            (ancho+15, Y_RES+80),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.38, csc, 1)
                cv2.putText(canvas,
                            f"{aprobados}/4 parametros OK",
                            (ancho+15, Y_RES+98),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.38, (170,170,200), 1)
            else:
                cv2.putText(canvas, t("modulo_tiempo_real.analizando"),
                            (ancho+20, Y_RES+30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (150,150,180), 1)

            # Fase actual
            cv2.putText(canvas, fase_texto,
                        (ancho+10, alto-50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.38, fase_color, 1)

            # Pie
            cv2.putText(canvas,
                        "Son et al. (2023)  |  Q para salir",
                        (ancho+10, alto-15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.28, (60,60,100), 1)

            cv2.imshow(f"SENTINEL — {nombre_caso}", canvas)
            if cv2.waitKey(delay) & 0xFF == ord("q"):
                estado["activo"] = False
                break

        cv2.destroyAllWindows()

    # ── Arrancar los 3 hilos ─────────────────────────────────
    t1 = threading.Thread(target=hilo_captura,      daemon=True)
    t2 = threading.Thread(target=hilo_procesamiento, daemon=True)

    t1.start()
    t2.start()

    # La UI corre en el hilo principal (requerido por OpenCV en Windows)
    hilo_ui()

    estado["activo"] = False
    t1.join(timeout=2)
    t2.join(timeout=2)
    log.info("Analisis finalizado: %s", nombre_caso)


# ------------------------------------------------------------
# Ejecucion principal
# ------------------------------------------------------------

if __name__ == "__main__":
    init_desde_prefs()
    log.info("=" * 55)
    log.info("  SENTINEL — Analisis en Tiempo Real v2.0")
    log.info("  Pipeline optimizado | 3 hilos")
    log.info("=" * 55)

    analizar_tiempo_real("icg_adecuada.avi", "Caso 1 Perfusion Adecuada")