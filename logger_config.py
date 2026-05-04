"""
logger_config.py — Logging centralizado del Hub.

Por qué logging en lugar de print()/st.error():
  - Persiste en disco: si algo falla a las 3am, tienes rastro.
  - Niveles: DEBUG, INFO, WARNING, ERROR — filtrables.
  - No contamina la UI con errores internos.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler


def get_logger(name: str = "streamlit_hub") -> logging.Logger:
    """
    Factory de loggers con configuración consistente.
    
    Patrón Factory: en lugar de configurar logging en cada módulo,
    todos piden su logger a esta función → un solo punto de control.
    
    Args:
        name: Nombre del logger (recomendado: __name__ del módulo llamante).
    
    Returns:
        Logger configurado con handlers de consola y archivo rotativo.
    """
    logger = logging.getLogger(name)

    # Guard: si ya tiene handlers, no duplicar
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler 1: consola (útil en desarrollo)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Handler 2: archivo rotativo (no crece infinitamente)
    # maxBytes=1MB, backupCount=3 → máximo ~3MB de logs en disco
    file_handler = RotatingFileHandler(
        filename="hub.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
