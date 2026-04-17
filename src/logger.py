# ============================================================
#  BIOCONNECT — Logging Centralizado
# Universidad de Guadalajara
# ============================================================

import logging
import os

_LOG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_LOG_DIR, "bioconnect.log")

# Configurar logger raíz de bioconnect
logger = logging.getLogger("bioconnect")
logger.setLevel(logging.INFO)

# Handler de archivo
_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))
logger.addHandler(_file_handler)

# Handler de consola (solo WARNING+)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(logging.Formatter(
    "[%(levelname)s] %(name)s: %(message)s"
))
logger.addHandler(_console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Retorna un sub-logger con el nombre dado.

    Uso:
        from logger import get_logger
        log = get_logger("modulo_x")
        log.info("Mensaje informativo")
        log.warning("Algo no esperado")
        log.error("Error crítico")

    Args:
        name: str — nombre del módulo (e.g., "config", "validation")

    Returns:
        logging.Logger
    """
    return logging.getLogger(f"bioconnect.{name}")
