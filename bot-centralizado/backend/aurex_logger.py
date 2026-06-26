# -*- coding: utf-8 -*-
"""
Aurex — Logging estructurado (B2)
=================================
Logger compartido que escribe a logs/aurex_YYYY-MM.log (rotacion mensual por
nombre de fichero). Formato: timestamp UTC | nivel | componente | mensaje.

Solo anade observabilidad. NO toca broker, ordenes, dinero ni estrategia.
ASCII puro (la consola Windows es cp1252 y los emojis la rompen).
"""
import os
import logging
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)


class _UTCFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def _log_path() -> str:
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    return os.path.join(LOG_DIR, 'aurex_' + month + '.log')


def get_logger(component: str) -> logging.Logger:
    """Devuelve un logger que escribe al fichero mensual. Idempotente."""
    logger = logging.getLogger('aurex.' + component)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    target = _log_path()
    # Evitar handlers duplicados si ya existe uno apuntando al fichero del mes.
    for h in logger.handlers:
        if getattr(h, '_aurex_path', None) == target:
            return logger
        logger.removeHandler(h)

    fh = logging.FileHandler(target, encoding='utf-8')
    fh._aurex_path = target  # type: ignore[attr-defined]
    fmt = _UTCFormatter('%(asctime)s | %(levelname)-7s | %(name)s | %(message)s')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger
