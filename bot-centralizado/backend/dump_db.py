# -*- coding: utf-8 -*-
"""
Aurex — Dump de la BD SQLite a CSV versionable (B4)
===================================================
Exporta aurex_trades.db a aurex_trades_dump.csv (texto plano) para que el
contenido de la base de datos quede versionado en git (los .db binarios no
van bien en git). Solo lectura sobre la BD. No toca broker ni estrategia.

Uso:
  python dump_db.py
"""
import os
import csv
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'aurex_trades.db')
DUMP_CSV = os.path.join(BASE_DIR, 'aurex_trades_dump.csv')


def dump() -> int:
    if not os.path.isfile(DB_PATH):
        print('[DUMP] No existe aurex_trades.db — nada que exportar.')
        return 0
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute('SELECT * FROM trades ORDER BY id').fetchall()
    except sqlite3.OperationalError as e:
        print('[DUMP] Error leyendo tabla trades: ' + str(e))
        conn.close()
        return 0
    conn.close()

    if not rows:
        # Escribir al menos cabecera vacia coherente
        cols = ['id', 'datetime_utc', 'epic', 'source', 'direction',
                'entry_price', 'sl', 'tp', 'rr', 'size', 'riesgo_usd',
                'rsi', 'atr', 'ema_align', 'h1_trend', 'h4_trend',
                'deal_id', 'equity_before', 'notas']
        with open(DUMP_CSV, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(cols)
        print('[DUMP] BD vacia — escrita cabecera en aurex_trades_dump.csv')
        return 0

    cols = rows[0].keys()
    with open(DUMP_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    print('[DUMP] Exportadas ' + str(len(rows)) + ' filas -> aurex_trades_dump.csv')
    return len(rows)


if __name__ == '__main__':
    dump()
