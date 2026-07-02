# -*- coding: utf-8 -*-
"""
Aurex F1.1 — Collector de velas historicas (persistencia propia)
================================================================
SOLO LECTURA sobre el broker. Acumula velas OHLCV de GOLD en la BD SQLite
(tabla `candles`, dedup por PK epic+tf+timestamp). La API de Capital.com solo
devuelve una ventana movil (M15: ~15 dias, H1: ~60 dias) — sin acumulacion
propia, las estrategias M15/SCALP jamas seran backtesteables.

Ejecutado 1 vez/dia (paso extra de daily_backup.py) captura todo: la ventana
de la API (>= 15 dias) cubre de sobra las 24h transcurridas entre corridas.

Uso: python collect_candles.py
"""
import os
import sys
import sqlite3
from datetime import datetime, timezone

os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capital_client import CapitalClient

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aurex_trades.db')
EPIC = 'GOLD'
TIMEFRAMES = ['DAY', 'HOUR_4', 'HOUR', 'MINUTE_15']
MAX_POINTS = 1000


def init_candles_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            epic      TEXT NOT NULL,
            tf        TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open      REAL, high REAL, low REAL, close REAL,
            volume    REAL,
            PRIMARY KEY (epic, tf, timestamp)
        )
    """)
    conn.commit()


def collect() -> dict:
    """Descarga y acumula velas. Devuelve {tf: velas_nuevas}."""
    client = CapitalClient()
    if not client.login():
        raise RuntimeError('Login fallido')

    conn = sqlite3.connect(DB_PATH)
    init_candles_table(conn)
    result = {}

    for tf in TIMEFRAMES:
        df = client.get_prices(EPIC, tf, MAX_POINTS)
        if df is None or len(df) == 0:
            result[tf] = -1  # sin datos
            continue
        rows = [
            (EPIC, tf, str(r['timestamp']), float(r['open']), float(r['high']),
             float(r['low']), float(r['close']), float(r['volume']))
            for _, r in df.iterrows()
        ]
        before = conn.execute(
            "SELECT COUNT(*) FROM candles WHERE epic=? AND tf=?", (EPIC, tf)
        ).fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO candles VALUES (?,?,?,?,?,?,?,?)", rows
        )
        conn.commit()
        after = conn.execute(
            "SELECT COUNT(*) FROM candles WHERE epic=? AND tf=?", (EPIC, tf)
        ).fetchone()[0]
        result[tf] = after - before

    conn.close()
    return result


def stats() -> None:
    """Muestra el estado de la tabla candles."""
    conn = sqlite3.connect(DB_PATH)
    init_candles_table(conn)
    for tf in TIMEFRAMES:
        row = conn.execute(
            "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM candles "
            "WHERE epic=? AND tf=?", (EPIC, tf)
        ).fetchone()
        n, t0, t1 = row
        rng = (str(t0)[:10] + ' -> ' + str(t1)[:10]) if n else '-'
        print('  ' + tf.ljust(10) + ': ' + str(n).rjust(6) + ' velas | ' + rng)
    conn.close()


if __name__ == '__main__':
    print('[CANDLES] Recolectando velas ' + EPIC + ' ('
          + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC') + ')')
    res = collect()
    for tf, n in res.items():
        print('  ' + tf.ljust(10) + ': ' + ('SIN DATOS' if n < 0 else '+' + str(n) + ' nuevas'))
    print('[CANDLES] Estado acumulado:')
    stats()
