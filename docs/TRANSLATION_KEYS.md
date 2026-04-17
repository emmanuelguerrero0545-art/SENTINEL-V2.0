# SENTINEL / BioConnect — Guía de Traducciones (i18n)

**Versión:** 1.0 | **Fecha:** 2026-04-08 | **Bioconnect · Universidad de Guadalajara**

---

## Arquitectura del sistema i18n

```
V2/
├── i18n/
│   ├── __init__.py     ← Loader: t(), cargar_idioma(), init_desde_prefs()
│   ├── es.json         ← Español (MX)  — idioma base / fallback
│   ├── en.json         ← English
│   ├── fr.json         ← Français
│   └── pt.json         ← Português (BR)
```

### Cómo funciona

1. Al iniciar la app, `init_desde_prefs(prefs)` lee el idioma guardado en `~/.bioconnect_prefs.json`
2. Carga el JSON correspondiente en memoria como diccionario global
3. Toda la UI llama `t("seccion.clave")` para obtener la cadena traducida
4. Si un JSON no existe para el idioma pedido → fallback automático a `es.json`
5. Cambiar idioma requiere reinicio (subprocess.Popen); la preferencia se persiste

### Uso en código

```python
from i18n import t, cargar_idioma, init_desde_prefs

# Al iniciar la app
init_desde_prefs(prefs)          # Lee prefs y carga idioma correcto

# En cualquier widget
tk.Label(frame, text=t("menu.inicio"))           # → "Inicio" / "Home" / "Accueil"
tk.Button(card,  text=t("inicio.abrir"))          # → "Abrir" / "Open" / "Ouvrir"
messagebox.showwarning(t("avisos.aviso"), t("avisos.cargar_primero"))

# Cargar idioma manualmente (p.ej. para tests)
cargar_idioma("en")
t("score.bajo_riesgo")  # → "Low risk"
```

---

## Idiomas soportados

| Código | Nombre           | Archivo   | Estado    |
|--------|------------------|-----------|-----------|
| `es`   | Español (MX)     | es.json   | ✓ Completo (base) |
| `en`   | English          | en.json   | ✓ Completo |
| `fr`   | Français         | fr.json   | ✓ Completo |
| `pt`   | Português (BR)   | pt.json   | ✓ Completo |

Para agregar un idioma nuevo:
1. Copiar `es.json` como `xx.json` (código ISO 639-1)
2. Traducir todos los valores
3. Agregar `"xx"` a `IDIOMAS_SOPORTADOS` en `config.py`
4. Agregar la opción en el combo de `sentinel_settings.py → _tab_general()`
5. Agregar la entrada en `_map_lang` / `_map_lang_inv` de `sentinel_settings.py`

---

## Referencia completa de claves (104 claves)

### `app` — Identidad de la aplicación

| Clave | ES | EN |
|---|---|---|
| `app.nombre` | SENTINEL | SENTINEL |
| `app.tagline` | Intraoperative Perfusion Intelligence · Tecno-Sheep | Intraoperative Perfusion Intelligence · Tecno-Sheep |
| `app.version` | v2.0 | v2.0 |
| `app.referencia` | Ref: Son et al. (2023)… | Ref: Son et al. (2023)… |
| `app.score_leyenda` | Score: >=60 Bajo riesgo … | Score: >=60 Low risk … |

### `menu` — Botones del encabezado

| Clave | ES | EN | FR | PT |
|---|---|---|---|---|
| `menu.configuracion` | ⚙  Configuracion | ⚙  Settings | ⚙  Paramètres | ⚙  Configurações |
| `menu.inicio` | Inicio | Home | Accueil | Início |

### `inicio` — Pantalla de inicio

| Clave | ES | EN | FR | PT |
|---|---|---|---|---|
| `inicio.selecciona_modulo` | Selecciona un modulo… | Select a module… | Sélectionnez un module… | Selecione um módulo… |
| `inicio.abrir` | Abrir | Open | Ouvrir | Abrir |

### `modulos.*` — Tarjetas de módulos (título + descripción)

Cada módulo tiene dos claves: `.titulo` y `.desc`.

| Módulo | Clave base |
|---|---|
| Análisis en Tiempo Real | `modulos.tiempo_real` |
| Analizar Video | `modulos.analizar_video` |
| Mapa de Calor Espacial | `modulos.mapa_calor` |
| Simulador ICG | `modulos.simulador` |
| Historial de Sesiones | `modulos.historial` |
| Análisis MAX | `modulos.max` |
| Modo Quirófano | `modulos.quirofano` |
| Segmentación + Línea | `modulos.segmentacion` |

### `archivo` — Barra de archivo común

| Clave | ES | EN |
|---|---|---|
| `archivo.etiqueta` | Archivo: | File: |
| `archivo.ningun_archivo` | Ningun archivo seleccionado | No file selected |
| `archivo.cargar_video` | Cargar Video | Load Video |
| `archivo.analizar` | Analizar | Analyze |
| `archivo.seleccionar_video` | Seleccionar video NIR/ICG | Select NIR/ICG video |
| `archivo.guardar_reporte` | Guardar reporte PDF | Save PDF report |
| `archivo.guardar_reporte_max` | Guardar reporte PDF — Analisis MAX | Save PDF report — MAX Analysis |

### `simulador` — Módulo simulador

| Clave | ES | EN |
|---|---|---|
| `simulador.titulo` | Simulador ICG | ICG Simulator |
| `simulador.instruccion` | Ajusta parametros y presiona Analizar | Adjust parameters and press Analyze |
| `simulador.caso` | Caso predefinido | Preset case |
| `simulador.analizar` | Analizar | Analyze |
| `simulador.pdf` | Generar Reporte PDF | Generate PDF Report |
| `simulador.sliders.t1` | T1 — Llegada bolo (s) | T1 — Bolus arrival (s) |
| `simulador.sliders.t2` | T2 — Tiempo al pico | T2 — Time to peak |
| `simulador.sliders.ruido` | Ruido de senal (0–30%) | Signal noise (0–30%) |
| `simulador.sliders.amp` | Amplitud de senal | Signal amplitude |
| `simulador.casos.personalizado` | Personalizado | Custom |
| `simulador.casos.caso1` | Caso 1 — Adecuada | Case 1 — Adequate |
| `simulador.casos.caso2` | Caso 2 — Comprometida | Case 2 — Compromised |
| `simulador.casos.caso3` | Caso 3 — Borderline | Case 3 — Borderline |

### `historial` — Módulo historial

| Clave | ES | EN |
|---|---|---|
| `historial.titulo` | Historial de Sesiones | Session History |
| `historial.vacio` | No hay sesiones registradas aun. | No sessions recorded yet. |

### `mapa` — Módulo mapa de calor

| Clave | ES | EN |
|---|---|---|
| `mapa.titulo` | Mapa de Calor Espacial v2 | Spatial Heat Map v2 |
| `mapa.subtitulo` | Con enmascaramiento de zonas sin tejido | With masking of non-tissue zones |
| `mapa.extrayendo` | Extrayendo curvas por celda... | Extracting curves per cell... |
| `mapa.mascara` | Calculando mascara de tejido... | Computing tissue mask... |
| `mapa.calculando` | Calculando T1 en {n} celdas... | Computing T1 in {n} cells... |
| `mapa.completado` | Completado — {n_tej}/{total} celdas  \| | Completed — {n_tej}/{total} cells  \| |

### `max` — Módulo Análisis MAX

| Clave | ES | EN |
|---|---|---|
| `max.titulo` | Analisis MAX | MAX Analysis |
| `max.subtitulo` | Tiempo Real → Analisis → … | Real Time → Analysis → … |
| `max.iniciar` | INICIAR ANALISIS MAX | START MAX ANALYSIS |
| `max.esperando` | Esperando... | Waiting... |

### `quirofano` — Módulo Quirófano

| Clave | Descripción |
|---|---|
| `quirofano.titulo` | Título del módulo |
| `quirofano.subtitulo` | Subtítulo |
| `quirofano.aviso` | Aviso de hardware requerido |
| `quirofano.indice` | Etiqueta "Índice de cámara" |
| `quirofano.nota_indice` | Nota explicativa del índice |
| `quirofano.conectar` | Botón conectar |
| `quirofano.detener` | Botón detener |
| `quirofano.desconectada` | Estado inicial |
| `quirofano.feed` | Título del feed |
| `quirofano.sin_senal` | Estado sin señal |
| `quirofano.curva` | Título del gráfico en vivo |
| `quirofano.esperando` | Estado esperando señal |

### `segmentacion` — Módulo Segmentación

| Clave | ES | EN |
|---|---|---|
| `segmentacion.titulo` | Segmentacion + Mapa Pixel + Linea... | Segmentation + Pixel Map + ... |
| `segmentacion.procesando` | Procesando... puede tardar 1-2 minutos | Processing... may take 1–2 minutes |
| `segmentacion.completado` | Completado — {n_val} px  \| | Completed — {n_val} px  \| |
| `segmentacion.guardar` | Guardar imagen | Save image |

### `pdf` — Diálogos de generación PDF

| Clave | ES |
|---|---|
| `pdf.dialogo_titulo` | Generar Reporte PDF |
| `pdf.dialogo_cuerpo` | Resultado: PERFUSION {resultado}\nScore: {score}/100… |
| `pdf.generado_titulo` | PDF Generado |
| `pdf.generado_msg` | Reporte guardado:\n{ruta} |
| `pdf.cancelado_titulo` | Cancelado |
| `pdf.cancelado_msg` | No se generara el reporte PDF. |
| `pdf.sin_analisis` | Primero realice un analisis. |
| `pdf.instalar_lib` | Instale reportlab:\npip install reportlab |

> **Nota sobre interpolación:** Las cadenas con `{ruta}`, `{n}`, `{n_tej}`, `{total}`, `{resultado}`, `{score}`, `{etiqueta}` deben usarse con `.format()`:
> ```python
> t("pdf.generado_msg").format(ruta=ruta_pdf)
> t("mapa.calculando").format(n=n_val)
> ```

### `avisos` — Mensajes de error y estado

| Clave | ES | EN |
|---|---|---|
| `avisos.aviso` | Aviso | Warning |
| `avisos.error` | Error | Error |
| `avisos.cargar_primero` | Cargue un video primero. | Please load a video first. |
| `avisos.error_leer_video` | No se pudo leer el video. | Could not read the video. |
| `avisos.guardado` | Guardado | Saved |
| `avisos.imagen_guardada` | Imagen guardada:\n{nombre} | Image saved:\n{nombre} |

### `configuracion` — Diálogo de configuración

| Clave | ES | EN |
|---|---|---|
| `configuracion.titulo` | Configuracion | Settings |
| `configuracion.idioma` | Idioma | Language |
| `configuracion.tipografia` | Tipografia | Typography |
| `configuracion.guardar` | Guardar | Save |
| `configuracion.cancelar` | Cancelar | Cancel |
| `configuracion.requiere_reinicio` | Requiere reiniciar la aplicacion | Requires restarting the application |
| `configuracion.guardado` | Configuracion guardada | Settings saved |
| `configuracion.reiniciar_ahora` | Reinicio necesario | Restart required |
| `configuracion.reiniciar_msg` | {aviso}\n\n¿Reiniciar ahora? | {aviso}\n\nRestart now? |

### `score` — Etiquetas de nivel de riesgo

| Clave | ES | EN | FR | PT |
|---|---|---|---|---|
| `score.bajo_riesgo` | Bajo riesgo | Low risk | Faible risque | Baixo risco |
| `score.riesgo_moderado` | Riesgo moderado | Moderate risk | Risque modéré | Risco moderado |
| `score.alto_riesgo` | Alto riesgo | High risk | Risque élevé | Alto risco |

### `perfusion` — Veredictos de perfusión

| Clave | ES | EN | FR | PT |
|---|---|---|---|---|
| `perfusion.adecuada` | ADECUADA | ADEQUATE | ADÉQUATE | ADEQUADA |
| `perfusion.borderline` | BORDERLINE | BORDERLINE | BORDERLINE | BORDERLINE |
| `perfusion.comprometida` | COMPROMETIDA | COMPROMISED | COMPROMISE | COMPROMETIDA |

### `tiempo_real` — Módulo tiempo real

| Clave | ES | EN |
|---|---|---|
| `tiempo_real.analisis_curso` | Analisis en curso... | Analysis in progress... |
| `tiempo_real.analisis_finalizado` | Analisis finalizado. | Analysis complete. |

---

## Archivos del sistema de accesibilidad (FontManager)

```
V2/
├── font_manager.py          ← FontManager: carga OpenDyslexic o fallback
└── fonts/
    ├── INSTALAR_FUENTES.py  ← Instala OpenDyslexic en el sistema del usuario
    └── OpenDyslexic-Regular.otf  ← Fuente (si ya fue descargada)
```

### Instalar OpenDyslexic

```bash
cd fonts/
python INSTALAR_FUENTES.py
```

Luego activar en **Configuraciones → Accesibilidad → Tipografía OpenDyslexic** y reiniciar.

### FontManager API

```python
from font_manager import FontManager
from pathlib import Path

fm = FontManager(base_dir=Path(__file__).parent)

fm.disponible          # True si OpenDyslexic está lista
fm.familia             # "OpenDyslexic" | "Verdana" | "Arial"
fm.fallback            # True si se usa fuente de sustitución

fm.obtener_fuente("bold", 12)          # → ("OpenDyslexic", 12, "bold")
fm.aplicar_a_widget(widget, "normal", 11)
fm.aplicar_a_arbol(root, tamaño_base=11)
fm.info()              # dict de diagnóstico
```

---

## Flujo de reinicio de idioma/tipografía

```
Usuario cambia idioma o dyslexic_font en Configuraciones
    ↓
sentinel_settings._guardar() detecta cambio
    ↓
messagebox.askyesno("¿Reiniciar ahora?")
    ├── SÍ → self.destroy() → on_restart() → BioConnect_App.reiniciar_aplicacion()
    │              └── subprocess.Popen([python, BioConnect_App.py])
    │              └── sys.exit(0)
    └── NO → dialog cerrado, cambio guardado, aplica en próximo inicio
```

---

*Generado automáticamente — Bioconnect 2026 | Tecno-Sheep*
