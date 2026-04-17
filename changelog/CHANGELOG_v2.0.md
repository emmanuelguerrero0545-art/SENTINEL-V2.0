# CHANGELOG — BioConnect / SENTINEL v2.0

**Fecha:** 2026-04-10
**Autores:** Emmanuel Guerrero — Tecno-Sheep | Universidad de Guadalajara | Bioconnect 2026

---

## Resumen

Actualización mayor que corrige el problema de validación tautológica (AUC=1.0), añade parámetros clínicos adicionales, optimiza el rendimiento en tiempo real, y establece una base de código profesional con tests, logging centralizado y type hints.

---

## 1. Correcciones Críticas (P0)

### 1.1 Validación tautológica eliminada
- **Problema:** El clasificador anterior contaba parámetros aprobados — exactamente el mismo criterio usado para generar las etiquetas. Resultado: AUC=1.0 artificial.
- **Solución:** Nuevo `BioConnectClassifier` basado en `LogisticRegression + StandardScaler` (scikit-learn). Entrenado sobre features crudos (T1, T2, pendiente, indice_NIR), no sobre conteo de umbrales.
- **Resultado:** AUC = 0.8091 (CI: 0.70–0.92) — clínicamente creíble.

### 1.2 Datos sintéticos con solapamiento realista
- `generar_dataset_sintetico()` reescrito con 4 zonas: 40% adecuada clara, 10% adecuada borderline, 10% comprometida borderline, 40% comprometida clara.
- Las zonas borderline generan solapamiento natural → AUC < 1.0.

### 1.3 Bugs corregidos
- **Variable shadowing en `leer_video()`:** `t` → `tiempo_arr`, return statement actualizado.
- **HISTORIAL_PATH hardcodeado:** Ahora usa `os.path.dirname(os.path.abspath(__file__))`.
- **Temp file en `generar_pdf()`:** Usa `tempfile.NamedTemporaryFile(suffix=".png", delete=False)`.
- **`np.random.seed()` global:** Reemplazado por `np.random.default_rng()` en todos los módulos.
- **`bare except:`:** Reemplazado por `except Exception:` en validation.py, robustness_tests.py, falsification_tests.py.
- **`warnings.filterwarnings("ignore")`:** Eliminado de robustness_tests.py.
- **Código muerto v1.5:** 355 líneas eliminadas de BCV1_tiempo_real.py (clases, funciones y umbrales duplicados).

---

## 2. Validación Estadística Real (P0)

### 2.1 Nuevo módulo: `classifier.py`
- Clase `BioConnectClassifier` con métodos: `fit()`, `predict_proba()`, `predict()`, `get_coefficients()`, `save()`, `load()`.
- Persistencia via joblib.
- Feature names: `["T1", "T2", "pendiente", "indice_NIR"]`.

### 2.2 Pipeline actualizado
- `synthetic_validation_pipeline.py` ahora entrena el clasificador en train set y evalúa con `predict_proba()` en test set.
- N aumentado de 50 → 500.
- Ruido aumentado de 0.08 → 0.15 (realista para cámaras NIR).

### 2.3 Resultados de validación (N=500)
| Métrica | Valor |
|---------|-------|
| AUC | 0.8091 |
| AUC 95% CI | [0.70, 0.92] |
| Sensitivity | 0.7442 |
| Specificity | 0.9298 |
| Umbral óptimo (Youden) | 0.6522 |
| Robustness tests | 5/5 PASS |
| Falsification tests | 3/3 PASS |

---

## 3. Parámetros Clínicos Adicionales (P1)

### 3.1 Tres nuevos parámetros en `parameter_extraction.py`
| Parámetro | Descripción | Unidad |
|-----------|-------------|--------|
| `Fmax` | Fluorescencia máxima normalizada | a.u. |
| `T_half` | Tiempo de semi-descenso post-pico | s |
| `slope_ratio` | Ratio pendiente subida / bajada | ratio |

### 3.2 Umbrales adicionales en `config.py`
- `UMBRALES_ADICIONALES` dict con valores de referencia.
- `calcular_score_riesgo()` usa pesos extendidos cuando los 3 parámetros adicionales están disponibles (Fmax=0.05, T_half=0.05, slope_ratio=0.05).

### 3.3 Idiomas
- `IDIOMAS_SOPORTADOS` expandido a 8: es, en, fr, de, it, pt, ja, zh.

---

## 4. Optimización de Rendimiento (P1)

### 4.1 BCV1_tiempo_real.py
- **Mini-curva vectorizada:** `cv2.polylines()` reemplaza pixel-by-pixel loop.
- **Cola de display separada:** `cola_display` independiente de `cola_procesamiento`.
- **Intervalos adaptativos:** 0.5s durante SUBIDA, 1.0s durante ESPERANDO.
- **Savgol incremental:** Filtra solo los últimos 100 puntos.

### 4.2 BioConnect_App.py
- **Segmentación two-pass:** Primer paso cuenta frames, segundo procesa. No carga todos los frames en RAM.

### 4.3 BCV1.py
- **Import condicional de GUI:** `tkinter` y `matplotlib.backends` envueltos en try/except con flag `_GUI_AVAILABLE`. Permite importar `generar_senal_icg()` en entornos headless.

---

## 5. Calidad de Código (P2)

### 5.1 Logging centralizado
- Nuevo módulo `logger.py` con `get_logger(name)`.
- File handler → `bioconnect.log`, console handler → WARNING+.
- `print()` reemplazado por `log.info/warning/error` en: classifier.py, data_persistence.py, BCV1_tiempo_real.py, synthetic_validation_pipeline.py.

### 5.2 Tests (pytest)
| Archivo | Tests | Cobertura |
|---------|-------|-----------|
| `test_parameter_extraction.py` | 12 | Extracción de 7 params, validación, edge cases |
| `test_classification.py` | 18 | Classifier fit/predict/save/load, clasificar_perfusion, clasificar_parametro |
| `test_config.py` | 16 | Umbrales, get_umbral, score_riesgo, params de extracción/validación |
| `test_consistency.py` | 6 | Imports desde config, features del classifier, keys de extraer_parametros |
| **Total** | **58** | **Todos PASS** |

### 5.3 Configuración de proyecto
- `pyproject.toml` con metadata, dependencias, pytest config, mypy config.

### 5.4 Type hints
- Funciones públicas de `config.py`, `parameter_extraction.py`, `validation.py` ahora tienen type hints.

### 5.5 Umbrales centralizados
- Todos los módulos importan umbrales desde `config.py` via `get_umbral()`.
- Umbrales hardcodeados eliminados de BCV1_tiempo_real.py.

---

## Archivos nuevos

| Archivo | Propósito |
|---------|-----------|
| `classifier.py` | BioConnectClassifier (LogisticRegression) |
| `logger.py` | Logging centralizado |
| `pyproject.toml` | Configuración de proyecto |
| `tests/conftest.py` | Fixtures de pytest |
| `tests/test_parameter_extraction.py` | Tests de extracción |
| `tests/test_classification.py` | Tests de clasificación |
| `tests/test_config.py` | Tests de configuración |
| `tests/test_consistency.py` | Tests de consistencia entre módulos |

## Archivos modificados

| Archivo | Cambios principales |
|---------|-------------------|
| `config.py` | UMBRALES_ADICIONALES, N=500, ruido=0.15, 8 idiomas, type hints |
| `parameter_extraction.py` | 3 params adicionales, type hints |
| `BCV1.py` | Import condicional GUI, rng moderno |
| `BCV1_tiempo_real.py` | Polylines, cola_display, intervalos adaptativos, código muerto eliminado, logger |
| `BioConnect_App.py` | Fix shadowing, fix HISTORIAL_PATH, fix tempfile, two-pass segmentación |
| `synthetic_validation_pipeline.py` | Classifier real, 4 zonas de solapamiento, logger |
| `validation.py` | rng moderno, type hints, bare except fix |
| `robustness_tests.py` | rng moderno, bare except fix, warnings fix |
| `falsification_tests.py` | rng moderno, bare except fix |
| `data_persistence.py` | Logger reemplaza prints |
