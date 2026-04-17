# 📋 ANÁLISIS DEL PROYECTO BIOCONNECT V2

**Fecha de análisis:** 2026-04-07  
**Versión analizada:** V2  
**Universidad:** Universidad de Guadalajara | Ingeniería Biomédica  
**Institución:** Bioconnect — Universidad de Guadalajara

---

## 1️⃣ RESUMEN EJECUTIVO

BioConnect es una **aplicación de análisis de perfusión tisular mediante video NIR/ICG** (Indocianina Verde) en tiempo real para cirugía intraoperatoria. El sistema analiza curvas de intensidad fluorescente y genera reportes clínicos en PDF basados en parámetros validados (Son et al., 2023).

**Estado actual:** Funcional con 5 módulos independientes + aplicación GUI Tkinter  
**Error reportado:** El PDF en la función MAX no se guarda en una ubicación controlada

---

## 2️⃣ ARQUITECTURA DEL PROYECTO

### Estructura de archivos:
```
V2/
├── BioConnect_App.py             ← APLICACIÓN PRINCIPAL (GUI Tkinter)
├── config.py                      ← CONFIGURACIÓN CENTRALIZADA (umbrales)
├── parameter_extraction.py        ← EXTRACCIÓN DE PARÁMETROS
│
├── [MÓDULOS FUNCIONALES]
├── BCV1.py                        ← Motor de análisis genérico
├── BCV1_lector_video.py           ← Lectura de video y extracción de curva ICG
├── BCV1_tiempo_real.py            ← Análisis en tiempo real
├── BCV1_mapa_calor.py             ← Generación de mapa de calor (8x8 celdas)
├── BCV1_reporte_pdf.py            ← GENERADOR DE PDF (módulo separado)
├── BCV1_segmentacion.py           ← Segmentación de tejido
├── BCV1_gen_video.py              ← Generación de video procesado
│
└── [VALIDACIÓN - Opcional]
    ├── synthetic_validation_pipeline.py
    ├── validation.py
    ├── robustness_tests.py
    ├── falsification_tests.py
    ├── test_modules.py
    └── data_persistence.py
```

---

## 3️⃣ FLUJO DE ANÁLISIS "MAX"

La función `_max_iniciar()` en BioConnect_App.py ejecuta un pipeline de 4 etapas:

### **Etapa 1: Tiempo Real**
- Módulo: `BCV1_tiempo_real.analizar_tiempo_real()`
- Función: Análisis en tiempo real del video

### **Etapa 2: Análisis General**
- Función: `leer_video()` → extrae tiempo e intensidad
- Extracción: `parameter_extraction.extraer_parametros()` → 4 parámetros
  - **T1:** Tiempo de llegada del bolo (umbral ≤ 10 s)
  - **T2:** Tiempo al pico máximo (umbral ≤ 30 s)
  - **Pendiente:** Velocidad de subida (umbral ≥ 5 u/s)
  - **Índice NIR:** Integral de intensidad (umbral ≥ 50 a.u.)

### **Etapa 3: Mapa de Calor v2 + Segmentación**
- Genera matriz 8×8 de T1 por celda
- Crea mascara de tejido válido
- Segmenta tejido y localiza línea de sección

### **Etapa 4: Reporte PDF** ⚠️ **AQUÍ ESTÁ EL ERROR**
- Función: `generar_pdf()` (BioConnect_App.py línea 570)
- Problema: Guarda el PDF como `nombre_caso_reporte.pdf` (sin ruta)

---

## 4️⃣ IDENTIFICACIÓN DEL ERROR: "PDF NO SE GUARDA"

### **Problema principal:**

En la función `generar_pdf()` (BioConnect_App.py:582):
```python
nombre_pdf = nombre_caso.replace(" ","_") + "_reporte.pdf"  # ❌ RUTA RELATIVA
```

**Consecuencia:** El PDF se guarda en el **directorio de trabajo actual** (cwd), no en una ubicación predecible.

### **Ubicaciones donde ocurre el mismo problema:**

1. **BCV1_reporte_pdf.py** (línea 76-77):
   ```python
   if nombre_pdf is None:
       nombre_pdf = nombre_caso.replace(" ", "_") + "_reporte.pdf"  # ❌ RELATIVA
   ```

2. **BioConnect_App.py** (línea 582):
   ```python
   nombre_pdf = nombre_caso.replace(" ","_") + "_reporte.pdf"  # ❌ RELATIVA
   ```

### **Por qué el usuario no "ve" el PDF:**

- Se guarda en el cwd de ejecución (podría ser `C:\Users\...`, `/home/user/`, etc.)
- La app muestra el nombre en un messagebox pero no abre una carpeta
- No hay diálogo de "Guardar como" → el usuario no controla la ubicación

---

## 5️⃣ ANÁLISIS MODULAR

### **BCV1_reporte_pdf.py** (15,992 bytes)
✅ Bien estructurado | ✅ Usa ReportLab profesionalmente  
**Función principal:** `generar_reporte_pdf()`
- Parámetros: tiempo, intensidad, params, resultado, color, detalle, aprobados, score, nombre_caso, nombre_pdf
- **Problema:** `nombre_pdf` es None → genera ruta relativa

### **BioConnect_App.py** (88,477 bytes)
✅ GUI completa con Tkinter | ✅ 5 módulos independientes integrados  
**Estructura:**
- Clase `App` con 2000+ líneas
- 5 tabs principales: Tiempo Real, Vídeo, Mapa de Calor, Segmentación, **MAX** ← donde está el error
- Motor de análisis integrado

### **BCV1.py** (13,164 bytes)
Motor de análisis genérico con utilidades de visualización

### **config.py** (129 bytes)
✅ Centralización perfecta de umbrales  
Parámetros validados contra Son et al. (2023)

### **parameter_extraction.py** (3,280 bytes)
Extrae 4 parámetros clínicos de la curva ICG

---

## 6️⃣ FORTALEZAS DEL PROYECTO

✅ **Arquitectura modular:** Cada módulo tiene responsabilidad única  
✅ **Centralización de umbrales:** Todo viene de config.py  
✅ **Validación robusta:** Módulos de validación separados  
✅ **GUI profesional:** Tkinter con paleta MATLAB  
✅ **Documentación clínica:** Incluye referencias (Son et al. 2023)  
✅ **Threading:** Análisis sin bloquear GUI  
✅ **Reportes clínicos:** PDF estructurado y profesional  

---

## 7️⃣ DEBILIDADES IDENTIFICADAS

❌ **Rutas hardcodeadas/relativas** → PDFs en ubicación desconocida  
❌ **Sin diálogo "Guardar como"** → Usuario no controla dónde guardar  
❌ **Archivos temporales** → `_temp_*.png` en cwd  
❌ **Sin validación de permisos** → ¿Qué pasa si el cwd no es escribible?  
❌ **Sin historial de ubicaciones** → Cada PDF se guarda en un lugar diferente  
❌ **Sin confirmación post-generación** → No abre el PDF generado  

---

## 8️⃣ PROPUESTA DE SOLUCIÓN

### **Nivel 1: Rápido (Fix inmediato)**
```python
# En _max_iniciar() agregar:
pdf_ruta = filedialog.asksaveasfilename(
    defaultextension=".pdf",
    filetypes=[("PDF", "*.pdf")],
    initialfile=nombre_caso + "_MAX_reporte.pdf"
)
if not pdf_ruta:
    return  # Usuario canceló
```

### **Nivel 2: Intermedio (Mejor UX)**
- Agregar carpeta de salida en config
- Crear carpeta automáticamente si no existe
- Historial de 10 últimas ubicaciones
- Botón "Abrir carpeta"

### **Nivel 3: Completo (Producción)**
- Selector de carpeta en GUI principal
- Guardar preferencia en archivo config
- Validar permisos de escritura antes
- Agrupar PDFs por fecha/caso
- Log de todas las generaciones

---

## 9️⃣ DEPENDENCIAS IDENTIFICADAS

```
tkinter (GUI)
opencv-python (cv2) — lectura de video
numpy — cálculos numéricos
scipy — filtrado Savitzky-Golay, estadísticas
matplotlib — visualización
reportlab — generación de PDF ← CRÍTICA PARA LA FUNCIÓN MAX
```

---

## 🔟 PRÓXIMOS PASOS RECOMENDADOS

1. **Implementar selector de carpeta** antes de generar PDF
2. **Crear carpeta de salida default** (ej: `BioConnect_Reports/`)
3. **Guardar ruta en config.json** para recordar último lugar
4. **Abrir PDF automáticamente** después de generar
5. **Agregar validación** de permisos de escritura
6. **Documentar** el flujo de guardado en README

---

## 📝 NOTAS FINALES

- **El proyecto es académico de calidad universitaria** ✅
- **El error NO es crítico** (el PDF SÍ se genera, solo que en el lugar incorrecto)
- **La solución es simple** (2-3 líneas de código para Nivel 1)
- **Se recomienda Nivel 2-3** para uso clínico real

---

**Generado para:** Emma (emmanuel.guerrero0545@alumnos.udg.mx)  
**Próxima fase:** Implementación de selector de carpeta + persistencia de preferencias
