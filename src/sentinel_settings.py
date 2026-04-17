# ============================================================
#  SENTINEL — Panel de Configuracion (Settings)
#  Tecno-Sheep | Universidad de Guadalajara | Bioconnect
# ============================================================
#
#  Uso desde la app:
#    from sentinel_settings import abrir_settings
#    abrir_settings(parent, prefs, on_change=callback)
#
#  on_change(changed: dict) se invoca al guardar con los pares
#  clave→valor que cambiaron, permitiendo aplicacion en vivo.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pathlib

from i18n import t

# Paleta SENTINEL
_BG      = "#0F0F0F"
_PANEL   = "#1F1F1F"
_CARD    = "#2A2A2A"
_ROJO    = "#EF4444"
_NARANJA = "#FF9900"
_VERDE   = "#22C55E"
_TEXTO   = "#FFFFFF"
_GRIS    = "#666666"
_BORDE   = "#333333"


def abrir_settings(parent, prefs, on_change=None, on_restart=None):
    """Abre el modal de configuracion SENTINEL.

    Args:
        parent:     Ventana padre (tk.Tk o Toplevel).
        prefs:      Instancia de BioConnectPrefs.
        on_change:  Callback(changed: dict) invocado al guardar con los
                    valores que cambiaron — permite aplicación en vivo.
        on_restart: Callback() invocado cuando el usuario confirma reiniciar
                    la aplicacion (cambio de idioma o tipografia).
                    Si None, solo se muestra aviso sin reiniciar.
    """
    dlg = SettingsDialog(parent, prefs, on_change=on_change, on_restart=on_restart)
    dlg.grab_set()
    parent.wait_window(dlg)


class SettingsDialog(tk.Toplevel):
    """
    Modal de configuracion con 4 pestanas:
      1. General   — idioma, unidades, notificaciones
      2. Visual    — paleta de color, brillo, contraste, texto
      3. Accesibilidad — dislexia, animaciones, espaciado
      4. Avanzado  — PDF dir, exportar/importar, info del sistema
    """

    def __init__(self, parent, prefs, on_change=None, on_restart=None):
        super().__init__(parent)
        self.prefs      = prefs
        self._on_change  = on_change
        self._on_restart = on_restart   # Callback() para reinicio de la app
        self.title(t("settings.titulo_ventana"))
        self.configure(bg=_BG)
        self.resizable(False, False)

        ancho, alto = 580, 520
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - ancho) // 2
        y  = (sh - alto)  // 2
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

        self._vars = {}   # Variables Tkinter vinculadas a prefs
        self._build_ui()
        self._cargar_valores()

    # ----------------------------------------------------------
    # UI principal
    # ----------------------------------------------------------
    def _build_ui(self):
        # Encabezado
        enc = tk.Frame(self, bg=_PANEL, pady=10)
        enc.pack(fill="x")
        tk.Label(enc, text=t("settings.encabezado"),
                 font=("Arial", 14, "bold"), fg=_ROJO,
                 bg=_PANEL).pack(side="left", padx=16)
        tk.Frame(self, bg=_ROJO, height=1).pack(fill="x")

        # Notebook de pestanas
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Sentinel.TNotebook",
                        background=_BG, borderwidth=0)
        style.configure("Sentinel.TNotebook.Tab",
                        background=_CARD, foreground=_GRIS,
                        font=("Arial", 9, "bold"),
                        padding=[14, 6])
        style.map("Sentinel.TNotebook.Tab",
                  background=[("selected", _PANEL)],
                  foreground=[("selected", _TEXTO)])

        nb = ttk.Notebook(self, style="Sentinel.TNotebook")
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._tab_general(nb)
        self._tab_visual(nb)
        self._tab_accesibilidad(nb)
        self._tab_avanzado(nb)

        # Botones
        pie = tk.Frame(self, bg=_BG)
        pie.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(pie, text=t("settings.btn_cancelar"),
                  font=("Arial", 9), bg=_CARD, fg=_TEXTO,
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(6, 0))
        tk.Button(pie, text=t("settings.btn_guardar"),
                  font=("Arial", 9, "bold"), bg=_ROJO, fg=_TEXTO,
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._guardar).pack(side="right")
        tk.Button(pie, text=t("settings.btn_reset"),
                  font=("Arial", 9), bg=_CARD, fg=_GRIS,
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  command=self._reset).pack(side="left")

    # ----------------------------------------------------------
    # Pestaña 1 — General
    # ----------------------------------------------------------
    def _tab_general(self, nb):
        frame = self._frame_tab(nb)
        nb.add(frame, text=t("settings.tab_general"))

        self._seccion(frame, t("settings.sec_idioma"))
        idiomas = ["Español (MX)", "English", "Português (BR)",
                   "Français", "Deutsch", "Italiano",
                   "中文 (简体)", "日本語"]
        self._vars["language_display"] = tk.StringVar()
        self._combo(frame, self._vars["language_display"], idiomas)

        self._seccion(frame, t("settings.sec_unidades"))
        unidades = [t("settings.unidades_metrico"),
                    t("settings.unidades_imperial"),
                    t("settings.unidades_hibrido")]
        self._vars["units"] = tk.StringVar()
        self._combo(frame, self._vars["units"], unidades)

        self._seccion(frame, t("settings.sec_notificaciones"))
        checks = [
            (t("settings.notif_sonido"),  "notif_sound"),
            (t("settings.notif_popup"),   "notif_popup"),
            (t("settings.notif_silencio"),"notif_silent_or"),
        ]
        for label, key in checks:
            self._vars[key] = tk.BooleanVar()
            self._check(frame, label, self._vars[key])

    # ----------------------------------------------------------
    # Pestaña 2 — Visual
    # ----------------------------------------------------------
    def _tab_visual(self, nb):
        frame = self._frame_tab(nb)
        nb.add(frame, text=t("settings.tab_visual"))

        self._seccion(frame, t("settings.sec_paleta"))
        paletas = [
            t("settings.paleta_normal"),
            t("settings.paleta_protan"),
            t("settings.paleta_deutan"),
            t("settings.paleta_tritan"),
            t("settings.paleta_acro"),
        ]
        self._vars["color_palette"] = tk.StringVar()
        self._combo(frame, self._vars["color_palette"], paletas)

        self._seccion(frame, t("settings.sec_contraste"))
        self._vars["contrast_mode"] = tk.StringVar()
        self._combo(frame, self._vars["contrast_mode"],
                    [t("settings.contraste_normal"), t("settings.contraste_alto")])

        self._seccion(frame, t("settings.sec_fuente"))
        self._vars["font_size"] = tk.IntVar(value=12)
        slider_frame = tk.Frame(frame, bg=_PANEL)
        slider_frame.pack(fill="x", padx=18, pady=2)
        lbl_sz = tk.Label(slider_frame, textvariable=self._vars["font_size"],
                          font=("Arial", 10, "bold"), fg=_NARANJA, bg=_PANEL,
                          width=3)
        lbl_sz.pack(side="right")
        tk.Scale(slider_frame, from_=10, to=20,
                 orient="horizontal",
                 variable=self._vars["font_size"],
                 bg=_PANEL, fg=_TEXTO, troughcolor=_BORDE,
                 highlightthickness=0, showvalue=False,
                 sliderlength=16).pack(fill="x", expand=True, side="left")

    # ----------------------------------------------------------
    # Pestaña 3 — Accesibilidad
    # ----------------------------------------------------------
    def _tab_accesibilidad(self, nb):
        frame = self._frame_tab(nb)
        nb.add(frame, text=t("settings.tab_accesibilidad"))

        self._seccion(frame, t("settings.sec_tipografia"))
        self._vars["dyslexic_font"] = tk.BooleanVar()
        self._check(frame, t("settings.usar_dyslexic"),
                    self._vars["dyslexic_font"])

        self._seccion(frame, t("settings.sec_espaciado"))
        self._vars["line_spacing"] = tk.StringVar()
        self._combo(frame, self._vars["line_spacing"],
                    [t("settings.linea_normal"), t("settings.linea_comodo"),
                     t("settings.linea_amplio"), t("settings.linea_baja")])

        self._seccion(frame, t("settings.sec_animaciones"))
        self._vars["anim_speed"] = tk.StringVar()
        self._combo(frame, self._vars["anim_speed"],
                    [t("settings.anim_normal"), t("settings.anim_lenta"),
                     t("settings.anim_muy_lenta"), t("settings.anim_sin")])

        self._seccion(frame, t("settings.sec_otras"))
        extras = [
            (t("settings.alto_contraste_max"), "high_contrast_max"),
            (t("settings.parrafos_separados"), "paragraph_separated"),
        ]
        for label, key in extras:
            self._vars[key] = tk.BooleanVar()
            self._check(frame, label, self._vars[key])

    # ----------------------------------------------------------
    # Pestaña 4 — Avanzado
    # ----------------------------------------------------------
    def _tab_avanzado(self, nb):
        frame = self._frame_tab(nb)
        nb.add(frame, text=t("settings.tab_avanzado"))

        self._seccion(frame, t("settings.sec_pdf_dir"))
        pdf_row = tk.Frame(frame, bg=_PANEL)
        pdf_row.pack(fill="x", padx=18, pady=4)
        self._vars["pdf_dir_display"] = tk.StringVar()
        entry = tk.Entry(pdf_row, textvariable=self._vars["pdf_dir_display"],
                         bg=_CARD, fg=_TEXTO, insertbackground=_TEXTO,
                         relief="flat", font=("Arial", 9))
        entry.pack(side="left", fill="x", expand=True)
        tk.Button(pdf_row, text=t("settings.examinar"),
                  font=("Arial", 9), bg=_ROJO, fg=_TEXTO,
                  relief="flat", padx=8, cursor="hand2",
                  command=self._elegir_pdf_dir).pack(side="left", padx=(6, 0))

        self._seccion(frame, t("settings.sec_modo_op"))
        self._vars["offline_mode"] = tk.BooleanVar()
        self._check(frame, t("settings.offline"),
                    self._vars["offline_mode"])

        self._seccion(frame, t("settings.sec_export"))
        btn_row = tk.Frame(frame, bg=_PANEL)
        btn_row.pack(fill="x", padx=18, pady=4)
        tk.Button(btn_row, text=t("settings.exportar_config"),
                  font=("Arial", 9), bg=_CARD, fg=_TEXTO,
                  relief="flat", padx=10, cursor="hand2",
                  command=self._exportar).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text=t("settings.importar_config"),
                  font=("Arial", 9), bg=_CARD, fg=_TEXTO,
                  relief="flat", padx=10, cursor="hand2",
                  command=self._importar).pack(side="left")

        self._seccion(frame, t("settings.sec_info"))
        import sys, platform
        info_lines = [
            f"Python {sys.version.split()[0]}",
            f"OS: {platform.system()} {platform.release()}",
            f"SENTINEL v2.0  |  Bioconnect  |  Tecno-Sheep",
        ]
        for line in info_lines:
            tk.Label(frame, text=line, font=("Arial", 8),
                     fg=_GRIS, bg=_PANEL).pack(anchor="w", padx=18)

    # ----------------------------------------------------------
    # Helpers de UI
    # ----------------------------------------------------------
    def _frame_tab(self, nb) -> tk.Frame:
        f = tk.Frame(nb, bg=_PANEL)
        f.pack(fill="both", expand=True)
        return f

    def _seccion(self, parent, titulo: str):
        row = tk.Frame(parent, bg=_PANEL)
        row.pack(fill="x", padx=14, pady=(14, 2))
        tk.Label(row, text=titulo, font=("Arial", 9, "bold"),
                 fg=_NARANJA, bg=_PANEL).pack(side="left")
        tk.Frame(row, bg=_BORDE, height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0))

    def _combo(self, parent, var: tk.StringVar, valores: list):
        style = ttk.Style()
        style.configure("Sentinel.TCombobox",
                        fieldbackground=_CARD,
                        background=_CARD,
                        foreground=_TEXTO,
                        selectbackground=_ROJO,
                        arrowcolor=_TEXTO)
        cb = ttk.Combobox(parent, textvariable=var, values=valores,
                          state="readonly", style="Sentinel.TCombobox",
                          font=("Arial", 9))
        cb.pack(fill="x", padx=18, pady=3)

    def _check(self, parent, texto: str, var: tk.BooleanVar):
        tk.Checkbutton(parent, text=texto, variable=var,
                       font=("Arial", 9), fg=_TEXTO, bg=_PANEL,
                       activebackground=_PANEL, activeforeground=_TEXTO,
                       selectcolor=_CARD,
                       highlightthickness=0).pack(anchor="w", padx=24)

    def _elegir_pdf_dir(self):
        d = filedialog.askdirectory(title="Carpeta para reportes PDF")
        if d:
            self._vars["pdf_dir_display"].set(d)

    # ----------------------------------------------------------
    # Cargar / Guardar / Reset
    # ----------------------------------------------------------
    def _cargar_valores(self):
        """Lee prefs y refleja en las variables Tkinter."""
        _map_lang = {
            "es": "Español (MX)", "en": "English",
            "pt": "Português (BR)", "fr": "Français", "de": "Deutsch",
            "it": "Italiano", "zh": "中文 (简体)", "ja": "日本語",
        }
        self._vars["language_display"].set(
            _map_lang.get(self.prefs.language, "Español (MX)"))

        self._vars["units"].set(
            self.prefs.get("units", "Metrico (cm, kg)"))
        self._vars["notif_sound"].set(
            self.prefs.get("notif_sound", True))
        self._vars["notif_popup"].set(
            self.prefs.get("notif_popup", True))
        self._vars["notif_silent_or"].set(
            self.prefs.get("notif_silent_or", False))
        # Mapeo codigo canonico → texto traducido en UI
        _code_to_paleta = {
            "normal":        t("settings.paleta_normal"),
            "protanopia":    t("settings.paleta_protan"),
            "deuteranopia":  t("settings.paleta_deutan"),
            "tritanopia":    t("settings.paleta_tritan"),
            "acromatopsia":  t("settings.paleta_acro"),
        }
        stored_pal = self.prefs.get("color_palette", "normal")
        # Compatibilidad hacia atras: si se guardo el texto (no el codigo)
        if stored_pal not in _code_to_paleta:
            stored_pal = "normal"
        self._vars["color_palette"].set(
            _code_to_paleta.get(stored_pal, t("settings.paleta_normal")))
        self._vars["contrast_mode"].set(
            self.prefs.get("contrast_mode", "Normal"))
        self._vars["font_size"].set(
            self.prefs.get("font_size", 12))
        self._vars["dyslexic_font"].set(
            self.prefs.get("dyslexic_font", False))
        self._vars["line_spacing"].set(
            self.prefs.get("line_spacing", "1.0x (normal)"))
        self._vars["anim_speed"].set(
            self.prefs.get("anim_speed", "Normal"))
        self._vars["high_contrast_max"].set(
            self.prefs.get("high_contrast_max", False))
        self._vars["paragraph_separated"].set(
            self.prefs.get("paragraph_separated", False))
        self._vars["pdf_dir_display"].set(
            self.prefs.pdf_directory)
        self._vars["offline_mode"].set(
            self.prefs.get("offline_mode", False))

    def _guardar(self):
        """Persiste todos los valores en prefs y notifica cambios en vivo."""
        _map_lang_inv = {
            "Español (MX)": "es", "English": "en",
            "Português (BR)": "pt", "Français": "fr", "Deutsch": "de",
            "Italiano": "it", "中文 (简体)": "zh", "日本語": "ja",
        }
        nueva_lang = _map_lang_inv.get(
            self._vars["language_display"].get(), "es")

        # Mapeo texto UI → codigo canonico para paleta (independiente del idioma)
        _paleta_display_to_code = {
            t("settings.paleta_normal"):  "normal",
            t("settings.paleta_protan"):  "protanopia",
            t("settings.paleta_deutan"):  "deuteranopia",
            t("settings.paleta_tritan"):  "tritanopia",
            t("settings.paleta_acro"):    "acromatopsia",
        }
        nueva_paleta = _paleta_display_to_code.get(
            self._vars["color_palette"].get(), "normal")

        pares = [
            ("language",            nueva_lang),
            ("units",               self._vars["units"].get()),
            ("notif_sound",         self._vars["notif_sound"].get()),
            ("notif_popup",         self._vars["notif_popup"].get()),
            ("notif_silent_or",     self._vars["notif_silent_or"].get()),
            ("color_palette",       nueva_paleta),
            ("contrast_mode",       self._vars["contrast_mode"].get()),
            ("font_size",           self._vars["font_size"].get()),
            ("dyslexic_font",       self._vars["dyslexic_font"].get()),
            ("line_spacing",        self._vars["line_spacing"].get()),
            ("anim_speed",          self._vars["anim_speed"].get()),
            ("high_contrast_max",   self._vars["high_contrast_max"].get()),
            ("paragraph_separated", self._vars["paragraph_separated"].get()),
            ("offline_mode",        self._vars["offline_mode"].get()),
        ]

        # Detectar qué cambió antes de guardar
        changed = {}
        for key, nuevo_val in pares:
            anterior = self.prefs.get(key)
            if anterior != nuevo_val:
                changed[key] = nuevo_val
            self.prefs.set(key, nuevo_val)

        # Carpeta PDF
        pdf_dir = self._vars["pdf_dir_display"].get().strip()
        if pdf_dir and pdf_dir != self.prefs.pdf_directory:
            changed["pdf_directory"] = pdf_dir
            self.prefs.pdf_directory = pdf_dir

        # Notificar a la app los cambios (aplicacion en vivo)
        if self._on_change and changed:
            self._on_change(changed)

        # Detectar si hay cambios que requieren reinicio
        necesita_reinicio = {"language", "dyslexic_font", "color_palette"} & set(changed.keys())

        if necesita_reinicio:
            # Construir mensaje descriptivo según qué cambió
            cambios_desc = []
            if "language" in changed:
                cambios_desc.append(t("settings.cambio_idioma"))
            if "dyslexic_font" in changed:
                cambios_desc.append(t("settings.cambio_tipografia"))
            if "color_palette" in changed:
                cambios_desc.append(t("settings.cambio_paleta"))
            detalle = " · ".join(cambios_desc)

            respuesta = messagebox.askyesno(
                t("settings.reinicio_titulo"),
                t("settings.reinicio_msg").format(detalle=detalle),
            )
            self.destroy()  # Cerrar dialog antes de reiniciar
            if respuesta and self._on_restart:
                self._on_restart()
            elif respuesta and not self._on_restart:
                # Fallback: avisar que debe reiniciar manualmente
                messagebox.showinfo("SENTINEL",
                    t("settings.reinicio_fallback"))
        else:
            messagebox.showinfo("SENTINEL", t("settings.config_guardada"))
            self.destroy()

    def _reset(self):
        if messagebox.askyesno(t("settings.reset_titulo"), t("settings.reset_msg")):
            self.prefs.reset()
            self._cargar_valores()
            messagebox.showinfo("SENTINEL", t("settings.reset_ok"))

    def _exportar(self):
        import json
        dst = filedialog.asksaveasfilename(
            title=t("settings.export_dialogo"),
            defaultextension=".json",
            filetypes=[("JSON", "*.json")])
        if not dst:
            return
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(self.prefs._data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("SENTINEL", t("settings.export_ok").format(ruta=dst))

    def _importar(self):
        import json
        src = filedialog.askopenfilename(
            title=t("settings.import_dialogo"),
            filetypes=[("JSON", "*.json")])
        if not src:
            return
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Formato invalido")
            self.prefs._data.update(data)
            self.prefs._save()
            self._cargar_valores()
            messagebox.showinfo("SENTINEL", t("settings.import_ok"))
        except Exception as e:
            messagebox.showerror("Error", t("settings.import_error").format(e=e))
