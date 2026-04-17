# ============================================================
#  BIOCONNECT — Base de Datos de Casos Clínicos (SQLite)
# Universidad de Guadalajara
# ============================================================
#
#  Módulo de persistencia estructurada para casos analizados.
#  Reemplaza/complementa el historial JSON con un esquema
#  relacional completo que incluye parámetros, anotaciones
#  clínicas y diagnóstico del cirujano para validación.
#
#  Uso:
#    from bioconnect_db import BioConnectDB
#    db = BioConnectDB()
#    db.guardar_caso(...)
#    casos = db.cargar_casos()
# ============================================================

import sqlite3
import os
import csv
from datetime import datetime

# Ruta por defecto de la base de datos
DB_PATH = "bioconnect_casos.db"


class BioConnectDB:
    """
    Interfaz de alto nivel para la base de datos de casos SENTINEL.

    Cada caso registra:
      - Metadatos: fecha, identificador, módulo, ruta de video/PDF
      - Diagnóstico SENTINEL: resultado, score, parámetros T1/T2/pendiente/NIR
      - Anotación clínica: diagnóstico del cirujano, notas, etiquetas
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ----------------------------------------------------------
    # Inicialización y esquema
    # ----------------------------------------------------------

    def _init_db(self):
        """Crea las tablas si no existen. Seguro en multiples llamadas."""
        with self._conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS casos (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha               TEXT    NOT NULL,
                    caso_id             TEXT    NOT NULL,
                    modulo              TEXT    DEFAULT '',
                    resultado           TEXT    DEFAULT '',
                    score               REAL    DEFAULT 0,
                    aprobados           INTEGER DEFAULT 0,
                    t1                  REAL    DEFAULT NULL,
                    t2                  REAL    DEFAULT NULL,
                    pendiente           REAL    DEFAULT NULL,
                    indice_nir          REAL    DEFAULT NULL,
                    fmax                REAL    DEFAULT NULL,
                    t_half              REAL    DEFAULT NULL,
                    slope_ratio         REAL    DEFAULT NULL,
                    diagnostico_cirujano TEXT   DEFAULT '',
                    notas               TEXT    DEFAULT '',
                    etiquetas           TEXT    DEFAULT '',
                    ruta_video          TEXT    DEFAULT '',
                    ruta_pdf            TEXT    DEFAULT ''
                )
            """)
            # Migración segura: agregar columnas si son nuevas
            self._migrar(con)

    def _migrar(self, con):
        """Agrega columnas nuevas si la DB ya existía sin ellas."""
        cur = con.execute("PRAGMA table_info(casos)")
        columnas = {row[1] for row in cur.fetchall()}
        nuevas = {
            "aprobados":            "INTEGER DEFAULT 0",
            "t1":                   "REAL    DEFAULT NULL",
            "t2":                   "REAL    DEFAULT NULL",
            "pendiente":            "REAL    DEFAULT NULL",
            "indice_nir":           "REAL    DEFAULT NULL",
            "fmax":                 "REAL    DEFAULT NULL",
            "t_half":               "REAL    DEFAULT NULL",
            "slope_ratio":          "REAL    DEFAULT NULL",
            "diagnostico_cirujano": "TEXT    DEFAULT ''",
            "notas":                "TEXT    DEFAULT ''",
            "etiquetas":            "TEXT    DEFAULT ''",
            "ruta_video":           "TEXT    DEFAULT ''",
            "ruta_pdf":             "TEXT    DEFAULT ''",
        }
        for col, defn in nuevas.items():
            if col not in columnas:
                con.execute(f"ALTER TABLE casos ADD COLUMN {col} {defn}")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ----------------------------------------------------------
    # Escritura
    # ----------------------------------------------------------

    def guardar_caso(
        self,
        caso_id: str,
        modulo: str,
        resultado: str,
        score: float,
        aprobados: int,
        params: dict,
        ruta_video: str = "",
        ruta_pdf: str = "",
        fecha: str = "",
    ) -> int:
        """
        Inserta un nuevo caso en la base de datos.

        Args:
            caso_id:   Nombre o identificador del caso (ej. nombre del archivo).
            modulo:    Módulo que generó el análisis.
            resultado: ADECUADA / BORDERLINE / COMPROMETIDA.
            score:     Score de riesgo (0–100).
            aprobados: Número de parámetros que aprobaron (0–4).
            params:    Dict con T1, T2, pendiente, indice_NIR.
            ruta_video, ruta_pdf: Rutas opcionales de archivos.
            fecha:     Fecha ISO o display; si vacío usa datetime.now().

        Returns:
            ID del registro insertado.
        """
        if not fecha:
            fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        with self._conn() as con:
            cur = con.execute(
                """
                INSERT INTO casos
                    (fecha, caso_id, modulo, resultado, score, aprobados,
                     t1, t2, pendiente, indice_nir, fmax, t_half, slope_ratio,
                     ruta_video, ruta_pdf)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    fecha, caso_id, modulo, resultado,
                    round(float(score), 2), int(aprobados),
                    round(float(params.get("T1", 0) or 0), 3),
                    round(float(params.get("T2", 0) or 0), 3),
                    round(float(params.get("pendiente", 0) or 0), 3),
                    round(float(params.get("indice_NIR", 0) or 0), 3),
                    round(float(params.get("Fmax", 0) or 0), 3),
                    round(float(params.get("T_half", 0) or 0), 3),
                    round(float(params.get("slope_ratio", 0) or 0), 4),
                    ruta_video, ruta_pdf,
                ),
            )
            return cur.lastrowid

    def actualizar_anotacion(
        self,
        caso_id_db: int,
        diagnostico_cirujano: str = None,
        notas: str = None,
        etiquetas: str = None,
    ):
        """
        Actualiza los campos de anotación clínica de un caso.
        Solo actualiza los campos que no sean None.
        """
        campos = {}
        if diagnostico_cirujano is not None:
            campos["diagnostico_cirujano"] = diagnostico_cirujano.strip()
        if notas is not None:
            campos["notas"] = notas.strip()
        if etiquetas is not None:
            campos["etiquetas"] = etiquetas.strip()
        if not campos:
            return
        set_clause = ", ".join(f"{k} = ?" for k in campos)
        valores = list(campos.values()) + [caso_id_db]
        with self._conn() as con:
            con.execute(
                f"UPDATE casos SET {set_clause} WHERE id = ?", valores
            )

    def actualizar_ruta_pdf(self, caso_id_db: int, ruta_pdf: str):
        """Registra la ruta del PDF generado para un caso."""
        with self._conn() as con:
            con.execute(
                "UPDATE casos SET ruta_pdf = ? WHERE id = ?",
                (ruta_pdf, caso_id_db),
            )

    def eliminar_caso(self, caso_id_db: int):
        """Elimina un caso por su ID (acción destructiva, confirmada en GUI)."""
        with self._conn() as con:
            con.execute("DELETE FROM casos WHERE id = ?", (caso_id_db,))

    # ----------------------------------------------------------
    # Lectura
    # ----------------------------------------------------------

    def cargar_casos(
        self,
        modulo: str = None,
        resultado: str = None,
        busqueda: str = None,
        orden: str = "fecha DESC",
    ) -> list[dict]:
        """
        Carga casos con filtros opcionales.

        Args:
            modulo:   Filtrar por módulo específico.
            resultado: Filtrar por ADECUADA / BORDERLINE / COMPROMETIDA.
            busqueda: Texto libre que busca en caso_id, notas, etiquetas.
            orden:    Columna y dirección (ej. 'score DESC').

        Returns:
            Lista de dicts con todos los campos del caso.
        """
        clausulas, params = [], []
        if modulo:
            clausulas.append("modulo = ?");   params.append(modulo)
        if resultado:
            clausulas.append("resultado = ?"); params.append(resultado)
        if busqueda:
            like = f"%{busqueda}%"
            clausulas.append(
                "(caso_id LIKE ? OR notas LIKE ? OR etiquetas LIKE ?)"
            )
            params.extend([like, like, like])

        where = f"WHERE {' AND '.join(clausulas)}" if clausulas else ""
        sql = f"SELECT * FROM casos {where} ORDER BY {orden}"
        with self._conn() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def cargar_caso_por_id(self, caso_id_db: int) -> dict | None:
        """Devuelve un caso por su ID entero."""
        with self._conn() as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT * FROM casos WHERE id = ?", (caso_id_db,)
            ).fetchone()
        return dict(row) if row else None

    def estadisticas(self) -> dict:
        """
        Calcula estadísticas agregadas de todos los casos.

        Returns:
            Dict con totales, distribución, promedios por parámetro,
            y concordancia SENTINEL vs cirujano cuando disponible.
        """
        casos = self.cargar_casos()
        if not casos:
            return {"total": 0}

        total = len(casos)
        dist = {"ADECUADA": 0, "BORDERLINE": 0, "COMPROMETIDA": 0, "": 0}
        scores, t1s, t2s, pends, nirs = [], [], [], [], []
        concord = {"acuerdo": 0, "desacuerdo": 0, "sin_dx": 0}

        for c in casos:
            dist[c.get("resultado", "")] = dist.get(c.get("resultado", ""), 0) + 1
            if c["score"] is not None:   scores.append(c["score"])
            if c["t1"] is not None:      t1s.append(c["t1"])
            if c["t2"] is not None:      t2s.append(c["t2"])
            if c["pendiente"] is not None: pends.append(c["pendiente"])
            if c["indice_nir"] is not None: nirs.append(c["indice_nir"])

            dx_cir = (c.get("diagnostico_cirujano") or "").strip().upper()
            if not dx_cir:
                concord["sin_dx"] += 1
            elif dx_cir == c.get("resultado", "").upper():
                concord["acuerdo"] += 1
            else:
                concord["desacuerdo"] += 1

        def _stats(vals):
            if not vals:
                return {}
            import statistics as st
            return {
                "n":      len(vals),
                "media":  round(sum(vals)/len(vals), 2),
                "mediana":round(st.median(vals), 2),
                "min":    round(min(vals), 2),
                "max":    round(max(vals), 2),
            }

        return {
            "total":      total,
            "distribucion": dist,
            "scores":     _stats(scores),
            "params": {
                "T1":        _stats(t1s),
                "T2":        _stats(t2s),
                "pendiente": _stats(pends),
                "NIR":       _stats(nirs),
            },
            "concordancia": concord,
            "raw": {
                "scores": scores,
                "t1s": t1s, "t2s": t2s,
                "pends": pends, "nirs": nirs,
                "resultados": [c.get("resultado","") for c in casos],
                "dx_cirujano": [c.get("diagnostico_cirujano","") for c in casos],
            },
        }

    def modulos_disponibles(self) -> list[str]:
        """Lista de módulos con al menos un caso registrado."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT DISTINCT modulo FROM casos ORDER BY modulo"
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    # ----------------------------------------------------------
    # Exportación
    # ----------------------------------------------------------

    def exportar_csv(self, ruta: str, casos: list[dict] = None) -> int:
        """
        Exporta casos a CSV.

        Args:
            ruta:  Ruta completa del archivo .csv de salida.
            casos: Lista de casos a exportar; si None exporta todos.

        Returns:
            Número de filas exportadas.
        """
        if casos is None:
            casos = self.cargar_casos()
        if not casos:
            return 0

        columnas = [
            "id", "fecha", "caso_id", "modulo", "resultado", "score",
            "aprobados", "t1", "t2", "pendiente", "indice_nir",
            "fmax", "t_half", "slope_ratio",
            "diagnostico_cirujano", "notas", "etiquetas",
            "ruta_video", "ruta_pdf",
        ]
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
            w.writeheader()
            w.writerows(casos)
        return len(casos)
