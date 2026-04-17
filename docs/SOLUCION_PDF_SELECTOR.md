# 🎯 SOLUCIÓN: SELECTOR DE CARPETA PARA PDF

**Fecha:** 2026-04-07  
**Usuario:** Emma  
**Objetivo:** Permitir al usuario elegir dónde guardar los PDF

---

## 📌 PROBLEMA RESUMIDO

Función `_max_iniciar()` en **BioConnect_App.py** genera PDF pero lo guarda en el directorio de trabajo actual sin opción de seleccionar ubicación.

```python
# ❌ ACTUAL (línea 1498-1500)
pdf = generar_pdf(t, s, params, resultado,
                   color, detalle, aprobados, score,
                   nombre + "_MAX", mapa_path, seg_path)
```

---

## ✅ SOLUCIÓN NIVEL 1: RÁPIDA (Recomendada para empezar)

**Tiempo de implementación:** 5-10 minutos  
**Complejidad:** Mínima (3 líneas)  
**Resultado:** Usuario elige carpeta antes de generar PDF

### Paso 1: Agregar importación
En `BioConnect_App.py`, después del `import threading` (línea ~8):

```python
from tkinter import filedialog  # ← Ya está en la línea 7, ¡perfecto!
```

### Paso 2: Modificar función `_max_iniciar()`

Busca la línea 1416 donde inicia `def _max_iniciar(self):` y modifica la función `proceso()` (línea 1424):

**ANTES (línea 1498-1500):**
```python
            self._max_progs["pdf"].set(50)
            pdf = generar_pdf(t, s, params, resultado,
                               color, detalle, aprobados, score,
                               nombre + "_MAX", mapa_path, seg_path)
```

**DESPUÉS:**
```python
            self._max_progs["pdf"].set(50)
            
            # ← AGREGAR ESTO (selector de carpeta)
            pdf_ruta = filedialog.asksaveasfilename(
                title="Guardar reporte PDF como...",
                defaultextension=".pdf",
                filetypes=[("PDF Document", "*.pdf"), ("All Files", "*.*")],
                initialfile=nombre + "_MAX_reporte.pdf",
                initialdir=os.path.expanduser("~")  # Inicia en Home
            )
            
            if not pdf_ruta:  # Usuario canceló
                self._max_progs["pdf"].set(0)
                self.after(0, lambda: self._max_set("pdf", "Cancelado", GRIS))
                return
            
            pdf = generar_pdf(t, s, params, resultado,
                               color, detalle, aprobados, score,
                               nombre + "_MAX", mapa_path, seg_path,
                               pdf_ruta)  # ← Pasar la ruta elegida
```

### Paso 3: Modificar función `generar_pdf()`

En la línea 570, modifica la firma de la función:

**ANTES:**
```python
def generar_pdf(tiempo, intensidad, params, resultado,
                color_hex, detalle, aprobados, score,
                nombre_caso, fig_extra=None, seg_extra=None):
```

**DESPUÉS:**
```python
def generar_pdf(tiempo, intensidad, params, resultado,
                color_hex, detalle, aprobados, score,
                nombre_caso, fig_extra=None, seg_extra=None, ruta_pdf=None):
```

### Paso 4: Usar la ruta elegida en `generar_pdf()`

En la línea 582:

**ANTES:**
```python
        nombre_pdf = nombre_caso.replace(" ","_") + "_reporte.pdf"
```

**DESPUÉS:**
```python
        if ruta_pdf:
            nombre_pdf = ruta_pdf
        else:
            nombre_pdf = nombre_caso.replace(" ","_") + "_reporte.pdf"
```

---

## 🔧 SOLUCIÓN NIVEL 2: INTERMEDIA (Recomendada para producción)

**Tiempo:** 20-30 minutos  
**Complejidad:** Media (almacenamiento de preferencias)  
**Resultado:** Recuerda última carpeta usada

### Modificar `config.py` para agregar carpeta default

Agregar al final de `config.py` (antes del `REFERENCES`):

```python
# Configuración de guardado de reportes
REPORTE_CONFIG = {
    "carpeta_default": os.path.expanduser("~/BioConnect_Reports"),
    "crear_subcarpetas": True,
    "formato_subcarpeta": "YYYY-MM",  # Agrupar por mes
    "guardar_ubicacion_preferencia": True,  # Recordar última carpeta
}

# Archivo de preferencias
ARCHIVO_PREFERENCIAS = os.path.expanduser("~/.bioconnect_prefs.json")
```

### Crear módulo `bioconnect_prefs.py` (nuevo archivo)

```python
# ============================================================
#  BIOCONNECT — Gestión de Preferencias del Usuario
# ============================================================

import json
import os
from datetime import datetime

ARCHIVO_PREFS = os.path.expanduser("~/.bioconnect_prefs.json")

def cargar_preferencias():
    """Carga preferencias guardadas."""
    if os.path.exists(ARCHIVO_PREFS):
        try:
            with open(ARCHIVO_PREFS, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_preferencias(prefs):
    """Guarda preferencias."""
    try:
        with open(ARCHIVO_PREFS, 'w') as f:
            json.dump(prefs, f, indent=2)
        return True
    except:
        return False

def obtener_carpeta_reportes():
    """Obtiene la carpeta para guardar reportes."""
    prefs = cargar_preferencias()
    carpeta = prefs.get("ultima_carpeta_pdf")
    
    # Si no hay preferencia, usar default
    if not carpeta:
        carpeta = os.path.expanduser("~/BioConnect_Reports")
    
    # Crear carpeta si no existe
    os.makedirs(carpeta, exist_ok=True)
    return carpeta

def actualizar_carpeta_reportes(carpeta):
    """Actualiza y guarda la carpeta de reportes."""
    prefs = cargar_preferencias()
    prefs["ultima_carpeta_pdf"] = carpeta
    prefs["timestamp_actualizado"] = datetime.now().isoformat()
    return guardar_preferencias(prefs)
```

### Integración en `_max_iniciar()`

```python
# Agregar import
from bioconnect_prefs import obtener_carpeta_reportes, actualizar_carpeta_reportes

# En la función proceso():
            self._max_progs["pdf"].set(50)
            
            # Obtener carpeta default desde preferencias
            carpeta_default = obtener_carpeta_reportes()
            
            pdf_ruta = filedialog.asksaveasfilename(
                title="Guardar reporte PDF como...",
                defaultextension=".pdf",
                filetypes=[("PDF Document", "*.pdf"), ("All Files", "*.*")],
                initialfile=nombre + "_MAX_reporte.pdf",
                initialdir=carpeta_default
            )
            
            if not pdf_ruta:
                self._max_progs["pdf"].set(0)
                self.after(0, lambda: self._max_set("pdf", "Cancelado", GRIS))
                return
            
            # Guardar preferencia
            carpeta_elegida = os.path.dirname(pdf_ruta)
            actualizar_carpeta_reportes(carpeta_elegida)
            
            pdf = generar_pdf(...)
```

---

## 🚀 SOLUCIÓN NIVEL 3: COMPLETA (Producción clínica)

**Tiempo:** 45-60 minutos  
**Complejidad:** Alta (interfaz de configuración)  
**Resultado:** Control total del usuario sobre guardado

### Agregar pestana de configuración en GUI

En `BioConnect_App.py`, agregar nuevo tab en la inicialización de tabs (línea ~820):

```python
("Configuracion\nGuardar PDF",
 MORADO,     self._mostrar_config),

# Luego en el método correspondiente:

def _mostrar_config(self):
    self._nav(self._build_config)

def _build_config(self):
    """Panel de configuración de almacenamiento."""
    frame = tk.Frame(self._contenedor, bg=BG_DARK)
    frame.pack(fill="both", expand=True, padx=12, pady=8)
    
    # --- Sección: Carpeta de reportes ---
    sec_frame = tk.Frame(frame, bg=BG_CARD,
                         highlightbackground=MORADO, highlightthickness=2)
    sec_frame.pack(fill="x", pady=(0,12))
    tk.Label(sec_frame, text="Ubicacion de Reportes PDF",
             font=("Arial",12,"bold"), fg=MORADO, bg=BG_CARD).pack(
                 side="left", padx=12, pady=8)
    
    # --- Mostrar carpeta actual ---
    carpeta_actual = obtener_carpeta_reportes()
    lbl_carpeta = tk.Label(frame, text=f"Carpeta actual: {carpeta_actual}",
                           font=("Arial",9), fg=GRIS, bg=BG_DARK, wraplength=500,
                           justify="left")
    lbl_carpeta.pack(fill="x", padx=12, pady=8)
    
    # --- Botones ---
    btn_frame = tk.Frame(frame, bg=BG_DARK)
    btn_frame.pack(fill="x", padx=12, pady=8)
    
    def seleccionar_carpeta():
        nueva = filedialog.askdirectory(
            title="Seleccionar carpeta para reportes",
            initialdir=carpeta_actual)
        if nueva:
            actualizar_carpeta_reportes(nueva)
            lbl_carpeta.config(text=f"Carpeta actual: {nueva}")
            messagebox.showinfo("Exito", "Carpeta guardada correctamente")
    
    tk.Button(btn_frame, text="Cambiar carpeta",
              font=("Arial",10,"bold"), bg=MORADO, fg="white",
              relief="flat", padx=12, pady=6, cursor="hand2",
              command=seleccionar_carpeta).pack(side="left", padx=4)
    
    tk.Button(btn_frame, text="Abrir carpeta",
              font=("Arial",10,"bold"), bg=AZUL_SEG, fg="white",
              relief="flat", padx=12, pady=6, cursor="hand2",
              command=lambda: os.startfile(carpeta_actual) if sys.platform=="win32" 
                              else os.system(f'open "{carpeta_actual}"')).pack(side="left", padx=4)
    
    # --- Información adicional ---
    info_text = """
    Los reportes PDF se guardarán en la carpeta seleccionada.
    
    La aplicación recordará esta carpeta para futuras sesiones.
    
    Espacio recomendado: Al menos 100 MB disponible
    """
    
    info_frame = tk.Frame(frame, bg=BG_PANEL,
                          highlightbackground=BORDE, highlightthickness=1)
    info_frame.pack(fill="both", expand=True, padx=12, pady=(12,0))
    tk.Label(info_frame, text=info_text, font=("Arial",9), fg=GRIS,
             bg=BG_PANEL, justify="left", wraplength=500).pack(
                 padx=12, pady=12, anchor="w")
```

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### Nivel 1 (Rápida):
- [ ] Agregar selector filedialog en `_max_iniciar()` 
- [ ] Pasar `pdf_ruta` a la función `generar_pdf()`
- [ ] Modificar firma de `generar_pdf()` para aceptar `ruta_pdf`
- [ ] Usar `ruta_pdf` si se proporciona
- [ ] Probar con un video

### Nivel 2 (Intermedia):
- [ ] Crear módulo `bioconnect_prefs.py`
- [ ] Modificar `config.py`
- [ ] Integrar carga/guardado de preferencias
- [ ] Usar carpeta default de preferencias
- [ ] Probar persistencia entre sesiones

### Nivel 3 (Completa):
- [ ] Crear tab de "Configuración"
- [ ] Panel para cambiar/abrir carpeta
- [ ] Información sobre espacio disponible
- [ ] Integración completa

---

## 🧪 PRUEBA RECOMENDADA

```python
# Crear archivo test en V2/test_pdf_selector.py

import tkinter as tk
from tkinter import filedialog
import os

def test_selector():
    root = tk.Tk()
    root.withdraw()  # Ocultar ventana principal
    
    # Test 1: Selector básico
    ruta = filedialog.asksaveasfilename(
        title="Test: Guardar PDF",
        defaultextension=".pdf",
        filetypes=[("PDF", "*.pdf")],
        initialfile="test_reporte.pdf",
        initialdir=os.path.expanduser("~")
    )
    
    print(f"Ruta elegida: {ruta}")
    print(f"Carpeta: {os.path.dirname(ruta)}")
    print(f"Nombre: {os.path.basename(ruta)}")
    
    root.destroy()

if __name__ == "__main__":
    test_selector()
```

---

## 🔗 REFERENCIAS ÚTILES

- **tkinter.filedialog:** https://docs.python.org/3/library/dialog.html
- **os.path.expanduser():** Para rutas portables
- **json en Python:** Para guardar preferencias

---

## 📝 NOTAS FINALES

✅ **Nivel 1** es suficiente para una mejora inmediata  
✅ **Nivel 2** es recomendado para uso regular  
✅ **Nivel 3** es ideal si hay múltiples usuarios  

**No olvides:**
- Importar `sys` si usas Nivel 3
- Probar en Windows y Linux si es posible
- Crear carpeta default si no existe

---

**¿Preguntas o necesitas ayuda con algún nivel?** Puedo proporcionarte código completo listo para copiar/pegar.
