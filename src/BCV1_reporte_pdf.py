# ============================================================
#  SENTINEL — Generador de Reporte PDF Clinico
# Universidad de Guadalajara
# ============================================================

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Importar sistema i18n
try:
    _i18n_dir = os.path.join(os.path.dirname(__file__), "i18n")
    if _i18n_dir not in sys.path:
        sys.path.insert(0, os.path.dirname(__file__))
    from i18n import t as _t_reporte, init_desde_prefs as _init_reporte
except ImportError:
    def _t_reporte(k, d=""):  return d or k
    def _init_reporte(p=None): pass

try:
    from logger import get_logger
    log = get_logger("reporte_pdf")
except ImportError:
    import logging
    log = logging.getLogger("reporte_pdf")

# ------------------------------------------------------------
# Colores corporativos SENTINEL
# ------------------------------------------------------------

COLOR_FONDO    = colors.HexColor("#0F0F0F")
COLOR_ACENTO   = colors.HexColor("#EF4444")
COLOR_VERDE    = colors.HexColor("#22C55E")
COLOR_AMARILLO = colors.HexColor("#FF9900")
COLOR_ROJO     = colors.HexColor("#EF4444")
COLOR_TEXTO    = colors.HexColor("#2c3e50")
COLOR_GRIS     = colors.HexColor("#7f8c8d")

# ------------------------------------------------------------
# Generar figura de curva ICG para insertar en PDF
# ------------------------------------------------------------

def generar_figura_curva(tiempo, intensidad, params, resultado,
                          color_hex, nombre_caso, nombre_archivo):
    fig, ax = plt.subplots(figsize=(8, 3.5), facecolor="#1a1a2e")
    ax.set_facecolor("#0f0f1a")

    ax.plot(tiempo, intensidad, color="#00d4ff", linewidth=2.0)
    ax.fill_between(tiempo, intensidad, alpha=0.15, color="#00d4ff")

    pico_idx = np.argmax(intensidad)
    t2_val   = tiempo[pico_idx]
    pico_val = intensidad[pico_idx]

    idx_t1 = np.where(intensidad >= 0.10 * pico_val)[0]
    if len(idx_t1) > 0:
        ax.axvline(tiempo[idx_t1[0]], color="#f39c12", linestyle="--",
                   linewidth=1.5, label=_t_reporte("reporte_pdf.t1_label","T1 = {t1} s").format(t1=params['T1']))
    ax.axvline(t2_val, color="#9b59b6", linestyle="--",
               linewidth=1.5, label=_t_reporte("reporte_pdf.t2_label","T2 = {t2} s").format(t2=params['T2']))
    ax.scatter([t2_val], [pico_val], color="#ff6b6b", s=60, zorder=5)

    ax.set_xlabel(_t_reporte("reporte_pdf.fig_xlabel", "Tiempo (s)"), color="white", fontsize=9)
    ax.set_ylabel(_t_reporte("reporte_pdf.fig_ylabel", "Intensidad NIR (u.a.)"), color="white", fontsize=9)
    ax.set_title(_t_reporte("reporte_pdf.fig_titulo", "Curva ICG — {nombre}").format(nombre=nombre_caso),
                 color="white", fontsize=10)
    ax.tick_params(colors="white")
    ax.spines[:].set_color("#333355")
    ax.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)
    ax.grid(color="#222244", linestyle="--", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(nombre_archivo, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)

# ------------------------------------------------------------
# Generador principal de PDF
# ------------------------------------------------------------

def generar_reporte_pdf(tiempo, intensidad, params, resultado,
                         color_hex, detalle, aprobados, score, nombre_caso,
                         nombre_pdf=None):

    # Cargar idioma activo desde preferencias
    _init_reporte()

    if nombre_pdf is None:
        nombre_pdf = nombre_caso.replace(" ", "_") + "_reporte.pdf"

    # Generar figura temporal
    fig_path = "_temp_curva_icg.png"
    generar_figura_curva(tiempo, intensidad, params, resultado,
                          color_hex, nombre_caso, fig_path)

    # Configurar documento
    doc = SimpleDocTemplate(
        nombre_pdf,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    styles = getSampleStyleSheet()
    story  = []

    # --- Estilos personalizados ---
    estilo_titulo = ParagraphStyle(
        "titulo",
        parent=styles["Title"],
        fontSize=22,
        textColor=COLOR_ACENTO,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold"
    )
    estilo_subtitulo = ParagraphStyle(
        "subtitulo",
        parent=styles["Normal"],
        fontSize=10,
        textColor=COLOR_GRIS,
        spaceAfter=2,
        alignment=TA_CENTER
    )
    estilo_seccion = ParagraphStyle(
        "seccion",
        parent=styles["Heading1"],
        fontSize=12,
        textColor=COLOR_TEXTO,
        spaceBefore=14,
        spaceAfter=6,
        fontName="Helvetica-Bold",
        borderPad=4
    )
    estilo_normal = ParagraphStyle(
        "normal",
        parent=styles["Normal"],
        fontSize=9,
        textColor=COLOR_TEXTO,
        spaceAfter=4,
        leading=14
    )
    estilo_pie = ParagraphStyle(
        "pie",
        parent=styles["Normal"],
        fontSize=7.5,
        textColor=COLOR_GRIS,
        alignment=TA_CENTER
    )

    # ── ENCABEZADO ──────────────────────────────────────────
    story.append(Paragraph("SENTINEL", estilo_titulo))
    story.append(Paragraph(
        _t_reporte("reporte_pdf.subtitulo",
                   "Intraoperative Perfusion Intelligence — Reporte Clinico"),
        estilo_subtitulo))
    story.append(Paragraph(
        _t_reporte("reporte_pdf.institucion",
                   "Bioconnect 2026  |  Universidad de Guadalajara  |  Ingenieria Biomedica"),
        estilo_subtitulo))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=COLOR_ACENTO, spaceAfter=10))

    # ── DATOS DEL CASO ───────────────────────────────────────
    fecha = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
    story.append(Paragraph(_t_reporte("reporte_pdf.sec_info_caso", "Informacion del caso"), estilo_seccion))

    datos_caso = [
        [_t_reporte("reporte_pdf.campo_caso",      "Caso clinico:"),    nombre_caso],
        [_t_reporte("reporte_pdf.campo_fecha",     "Fecha y hora:"),    fecha],
        [_t_reporte("reporte_pdf.campo_sistema",   "Sistema:"),         "SENTINEL v2.0 — Intraoperative Perfusion Intelligence"],
        [_t_reporte("reporte_pdf.campo_referencia","Referencia:"),      "Son et al. (2023). Biomedicines 11(7):2029"],
    ]
    tabla_caso = Table(datos_caso, colWidths=[1.8*inch, 5.2*inch])
    tabla_caso.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 0), (0, -1), COLOR_TEXTO),
        ("TEXTCOLOR",   (1, 0), (1, -1), COLOR_GRIS),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
    ]))
    story.append(tabla_caso)
    story.append(Spacer(1, 8))

    # ── CURVA ICG ────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=COLOR_GRIS, spaceAfter=8))
    story.append(Paragraph(_t_reporte("reporte_pdf.sec_curva", "Curva de perfusion ICG"), estilo_seccion))
    story.append(Image(fig_path, width=6.5*inch, height=2.8*inch))
    story.append(Spacer(1, 6))

    # ── PARAMETROS ───────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=COLOR_GRIS, spaceAfter=8))
    story.append(Paragraph(_t_reporte("reporte_pdf.sec_parametros", "Parametros cuantitativos ICG"), estilo_seccion))

    encabezado = [
        Paragraph(f"<b>{_t_reporte('reporte_pdf.col_parametro','Parametro')}</b>",  estilo_normal),
        Paragraph(f"<b>{_t_reporte('reporte_pdf.col_valor','Valor medido')}</b>",   estilo_normal),
        Paragraph(f"<b>{_t_reporte('reporte_pdf.col_umbral','Umbral')}</b>",        estilo_normal),
        Paragraph(f"<b>{_t_reporte('reporte_pdf.col_estado','Estado')}</b>",        estilo_normal),
    ]

    color_estado = {True: COLOR_VERDE, False: COLOR_ROJO}
    texto_estado = {
        True:  _t_reporte("reporte_pdf.dentro_umbral", "DENTRO DEL UMBRAL"),
        False: _t_reporte("reporte_pdf.fuera_umbral",  "FUERA DEL UMBRAL"),
    }

    filas_params = [encabezado]
    definiciones = {
        "T1":         ("T1 — Tiempo de llegada del bolo",  f"{params['T1']} s",  "<= 10 s"),
        "T2":         ("T2 — Tiempo al pico maximo",       f"{params['T2']} s",  "<= 30 s"),
        "pendiente":  ("Pendiente de subida",               f"{params['pendiente']}",  ">= 5.0"),
        "indice_NIR": ("Indice NIR (area normalizada)",     f"{params['indice_NIR']}", ">= 50"),
    }

    for key, (nombre_p, valor_p, umbral_p) in definiciones.items():
        ok    = detalle[key]
        color = color_estado[ok]
        fila  = [
            Paragraph(nombre_p, estilo_normal),
            Paragraph(valor_p,  estilo_normal),
            Paragraph(umbral_p, estilo_normal),
            Paragraph(f"<b>{texto_estado[ok]}</b>",
                      ParagraphStyle("est", parent=estilo_normal,
                                     textColor=color, fontName="Helvetica-Bold")),
        ]
        filas_params.append(fila)

    # Parámetros adicionales (informativos)
    from config import UMBRALES_ADICIONALES
    params_adicionales = {
        "Fmax":        ("Fmax — Fluorescencia maxima",
                        f"{params.get('Fmax', '—')} a.u." if params.get('Fmax') is not None else "—",
                        f">= {UMBRALES_ADICIONALES['Fmax']['valor']}"),
        "T_half":      ("T_half — Semi-descenso",
                        f"{params.get('T_half', '—')} s" if params.get('T_half') is not None else "—",
                        f"<= {UMBRALES_ADICIONALES['T_half']['valor']}"),
        "slope_ratio": ("Slope ratio — Subida/bajada",
                        f"{params.get('slope_ratio', '—')}" if params.get('slope_ratio') is not None else "—",
                        f">= {UMBRALES_ADICIONALES['slope_ratio']['valor']}"),
    }

    # Separator row
    filas_params.append([
        Paragraph('<i>Parámetros adicionales (informativos)</i>',
                  ParagraphStyle("info_header", parent=estilo_normal, textColor=colors.HexColor("#7f8c8d"))),
        Paragraph("", estilo_normal),
        Paragraph("", estilo_normal),
        Paragraph("", estilo_normal),
    ])

    for key_a, (nombre_a, valor_a, umbral_a) in params_adicionales.items():
        fila = [
            Paragraph(nombre_a, estilo_normal),
            Paragraph(valor_a, estilo_normal),
            Paragraph(umbral_a, estilo_normal),
            Paragraph('<i>INFORMATIVO</i>',
                      ParagraphStyle("info", parent=estilo_normal,
                                     textColor=colors.HexColor("#7f8c8d"), fontName="Helvetica-Oblique")),
        ]
        filas_params.append(fila)

    tabla_params = Table(filas_params,
                          colWidths=[2.5*inch, 1.3*inch, 1.2*inch, 2.0*inch])
    tabla_params.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#ecf0f1")),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("GRID",        (0, 0), (-1, -1), 0.4, COLOR_GRIS),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8f9fa")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla_params)
    story.append(Spacer(1, 10))

    # ── RESULTADO FINAL ──────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=COLOR_GRIS, spaceAfter=8))
    story.append(Paragraph(_t_reporte("reporte_pdf.sec_resultado", "Evaluacion global de perfusion"), estilo_seccion))

    color_res = COLOR_VERDE if resultado == "ADECUADA" else \
                COLOR_AMARILLO if resultado == "BORDERLINE" else COLOR_ROJO

    color_score = COLOR_VERDE if score >= 75 else \
                  COLOR_AMARILLO if score >= 50 else COLOR_ROJO

    datos_resultado = [
        [
            Paragraph(f"<b>{_t_reporte('reporte_pdf.campo_clasif','Clasificacion de perfusion:')}</b>", estilo_normal),
            Paragraph(f"<b>{resultado}</b>",
                      ParagraphStyle("res", parent=estilo_normal,
                                     textColor=color_res,
                                     fontSize=13,
                                     fontName="Helvetica-Bold")),
        ],
        [
            Paragraph(f"<b>{_t_reporte('reporte_pdf.campo_aprobados','Parametros dentro del umbral:')}</b>", estilo_normal),
            Paragraph(f"<b>{aprobados} / 4</b>", estilo_normal),
        ],
        [
            Paragraph(f"<b>{_t_reporte('reporte_pdf.campo_score','Score SENTINEL (0-100):')}</b>", estilo_normal),
            Paragraph(f"<b>{score} / 100</b>",
                      ParagraphStyle("sc", parent=estilo_normal,
                                     textColor=color_score,
                                     fontSize=12,
                                     fontName="Helvetica-Bold")),
        ],
    ]

    tabla_resultado = Table(datos_resultado, colWidths=[3.0*inch, 4.0*inch])
    tabla_resultado.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ("BOX",           (0, 0), (-1, -1), 1.0, COLOR_ACENTO),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, COLOR_GRIS),
    ]))
    story.append(tabla_resultado)
    story.append(Spacer(1, 10))

    # ── INTERPRETACION CLINICA ───────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=COLOR_GRIS, spaceAfter=8))
    story.append(Paragraph(_t_reporte("reporte_pdf.sec_clinica", "Interpretacion clinica"), estilo_seccion))

    interpretaciones = {
        "ADECUADA":     _t_reporte("reporte_pdf.interp_adecuada",
                            "Los 4 parametros cuantitativos se encuentran dentro de los umbrales "
                            "validados. El tejido analizado presenta perfusion tisular adecuada para "
                            "sostener una anastomosis segura. Se recomienda proceder con la "
                            "anastomosis en el sitio evaluado."),
        "BORDERLINE":   _t_reporte("reporte_pdf.interp_borderline",
                            "3 de 4 parametros se encuentran dentro del umbral. El tejido presenta "
                            "perfusion limitrofe. Se recomienda precaucion: considerar la evaluacion "
                            "de un sitio anastomotico alternativo o repetir la medicion antes de "
                            "proceder."),
        "COMPROMETIDA": _t_reporte("reporte_pdf.interp_comprometida",
                            "2 o menos parametros se encuentran dentro del umbral. El tejido presenta "
                            "perfusion comprometida con riesgo elevado de complicacion anastomotica. "
                            "Se recomienda NO proceder con la anastomosis en este sitio y reevaluar "
                            "un segmento con mejor vascularizacion."),
    }

    story.append(Paragraph(interpretaciones[resultado], estilo_normal))
    story.append(Spacer(1, 8))

    # ── PIE DE PAGINA ────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1.0,
                             color=COLOR_ACENTO, spaceBefore=10, spaceAfter=6))
    story.append(Paragraph(
        _t_reporte("reporte_pdf.pie_1",
            "SENTINEL v2.0 — Tecno-Sheep  |  Bioconnect 2026  |  Universidad de Guadalajara  |  "
            "Este reporte es una herramienta de apoyo a la decision clinica. "
            "No sustituye el juicio del cirujano."),
        estilo_pie))
    story.append(Paragraph(
        _t_reporte("reporte_pdf.pie_2",
            "Referencia: Son et al. (2023). Biomedicines 11(7):2029. "
            "doi:10.3390/biomedicines11072029"),
        estilo_pie))

    # ── CONSTRUIR PDF ────────────────────────────────────────
    doc.build(story)

    # Limpiar figura temporal
    if os.path.exists(fig_path):
        os.remove(fig_path)

    log.info("Reporte PDF guardado: %s", nombre_pdf)
    return nombre_pdf


# ------------------------------------------------------------
# Integracion con el pipeline de video
# ------------------------------------------------------------

if __name__ == "__main__":
    # Importar pipeline de video
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    from BCV1_lector_video import leer_curva_desde_video
    from config import clasificar_perfusion, calcular_score_riesgo
    from parameter_extraction import extraer_parametros

    log.info("=" * 55)
    log.info("SENTINEL — Generador de Reportes PDF")
    log.info("Bioconnect | Universidad de Guadalajara")
    log.info("=" * 55)

    videos = [
        ("icg_adecuada.avi",     "Caso 1 Perfusion Adecuada"),
        ("icg_borderline.avi",   "Caso 3 Perfusion Borderline"),
        ("icg_comprometida.avi", "Caso 2 Perfusion Comprometida"),
    ]

    for ruta, nombre in videos:
        if not os.path.exists(ruta):
            log.warning("No se encontro %s — omitiendo.", ruta)
            continue

        log.info("Procesando: %s", nombre)
        tiempo, intensidad, fps = leer_curva_desde_video(ruta, mostrar_preview=False)
        if tiempo is None:
            continue

        params    = extraer_parametros(tiempo, intensidad)
        score     = calcular_score_riesgo(params)
        resultado, color_hex, aprobados, detalle = clasificar_perfusion(params)

        log.info("Resultado: PERFUSION %s  |  Score: %d/100", resultado, score)

        generar_reporte_pdf(
            tiempo, intensidad, params, resultado,
            color_hex, detalle, aprobados, score, nombre
        )

    log.info("Todos los reportes PDF generados.")