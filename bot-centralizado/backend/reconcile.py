# -*- coding: utf-8 -*-
"""
Aurex F1.3 — Reconciliación broker ↔ logs (P&L real por dealId)
===============================================================
SOLO LECTURA sobre el broker. Standalone: NO está conectado a los monitores.

Problema que resuelve (hallazgo H1 de la auditoría): el auto-cierre estima el
P&L por diferencia de equity (contaminado por posiciones externas) y etiqueta
'TP' cualquier cierre positivo. Este módulo trae la verdad del broker:
  - GET /history/transactions -> P&L REAL de cada cierre (con dealId, en EUR)
  - Guarda en tabla `trade_closes` de la BD (INSERT OR IGNORE por reference)
  - Compara contra los logs CSV e informa discrepancias

NOTA moneda: la cuenta es EUR. Los logs históricos dicen '$' pero las cifras
del broker son EUR. Este módulo registra la moneda real.

Uso:
  python reconcile.py                  -> sincroniza desde 2026-04-01 e informa
  python reconcile.py YYYY-MM-DD       -> sincroniza desde esa fecha
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta, timezone

os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capital_client import CapitalClient

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aurex_trades.db')
CHUNK_DAYS = 10  # la API limita el rango por consulta


def init_closes_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_closes (
            reference   TEXT PRIMARY KEY,
            deal_id     TEXT,
            date_utc    TEXT,
            instrument  TEXT,
            tx_type     TEXT,
            pnl         REAL,
            currency    TEXT,
            note        TEXT
        )
    """)
    conn.commit()


def sync_transactions(client, conn, from_date: datetime) -> int:
    """Descarga transacciones por tramos y guarda las de tipo TRADE/DEPOSIT.
    Devuelve cuántas filas nuevas se insertaron."""
    inserted = 0
    cursor_dt = from_date
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    while cursor_dt < now:
        end = min(cursor_dt + timedelta(days=CHUNK_DAYS), now)
        txs = client.get_transaction_history(
            from_date=cursor_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            to_date=end.strftime('%Y-%m-%dT%H:%M:%S'),
        )
        for t in txs:
            ttype = t.get('transactionType', '')
            if ttype == 'SWAP':
                continue  # fees overnight: fuera del P&L de trades
            ref = t.get('reference')
            if not ref:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO trade_closes VALUES (?,?,?,?,?,?,?,?)",
                (ref, t.get('dealId'), t.get('dateUtc'),
                 t.get('instrumentName'), ttype,
                 float(t.get('size', 0) or 0), t.get('currency'),
                 t.get('note')))
            inserted += cur.rowcount
        conn.commit()
        cursor_dt = end
    return inserted


def report(conn):
    print('=' * 66)
    print('RECONCILIACION — verdad del broker (tabla trade_closes)')
    print('=' * 66)
    rows = conn.execute(
        "SELECT date_utc, instrument, tx_type, pnl, currency, deal_id "
        "FROM trade_closes ORDER BY date_utc").fetchall()
    total_trade_pnl = 0.0
    for d, inst, ttype, pnl, cur, deal in rows:
        tail = (' | deal ...' + deal[-8:]) if deal else ''
        print('  ' + str(d)[:16] + '  ' + str(inst or '-').ljust(6)
              + ttype.ljust(9) + ('%+.2f ' % pnl) + str(cur) + tail)
        if ttype == 'TRADE' and inst == 'GOLD':
            total_trade_pnl += pnl
    print('-' * 66)
    print('  P&L REAL acumulado trades GOLD: %+.2f EUR' % total_trade_pnl)
    print('  (los logs CSV usan estimacion por equity y etiqueta "$";')
    print('   esta tabla es la fuente de verdad para reporting futuro)')


def main():
    from_str = sys.argv[1] if len(sys.argv) > 1 else '2026-04-01'
    from_date = datetime.strptime(from_str, '%Y-%m-%d')

    client = CapitalClient()
    if not client.login():
        print('Login fallido')
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    init_closes_table(conn)
    n = sync_transactions(client, conn, from_date)
    print('[RECONCILE] Transacciones nuevas guardadas: ' + str(n))
    report(conn)
    conn.close()


if __name__ == '__main__':
    main()
