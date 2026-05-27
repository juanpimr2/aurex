"""
Aurex — SQLite persistence layer
=================================
All trade opens are logged here regardless of source (M15, SCALP, SWING).
Provides a single queryable history for reporting and analysis.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'aurex_trades.db')


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime_utc  TEXT    NOT NULL,
            epic          TEXT    NOT NULL,
            source        TEXT    NOT NULL,
            direction     TEXT    NOT NULL,
            entry_price   REAL,
            sl            REAL,
            tp            REAL,
            rr            REAL,
            size          REAL,
            riesgo_usd    REAL,
            rsi           REAL,
            atr           REAL,
            ema_align     TEXT,
            h1_trend      TEXT,
            h4_trend      TEXT,
            deal_id       TEXT,
            equity_before REAL,
            notas         TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_trade_open(
    datetime_utc:  str,
    epic:          str,
    source:        str,
    direction:     str,
    entry_price:   float,
    sl:            float,
    tp:            float,
    rr:            float,
    size:          float,
    riesgo_usd:    float,
    rsi:           float,
    atr:           float,
    ema_align:     str,
    h1_trend:      str,
    h4_trend:      str,
    deal_id:       str  = None,
    equity_before: float = None,
    notas:         str  = None,
) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO trades
            (datetime_utc, epic, source, direction, entry_price, sl, tp, rr,
             size, riesgo_usd, rsi, atr, ema_align, h1_trend, h4_trend,
             deal_id, equity_before, notas)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (datetime_utc, epic, source, direction, entry_price, sl, tp, rr,
          size, riesgo_usd, rsi, atr, ema_align, h1_trend, h4_trend,
          deal_id, equity_before, notas))
    conn.commit()
    conn.close()


def get_trades(date_str: str = None, source: str = None) -> list:
    """Return trades optionally filtered by date (YYYY-MM-DD) or source."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM trades WHERE 1=1"
    params = []
    if date_str:
        q += " AND datetime_utc LIKE ?"
        params.append(date_str + "%")
    if source:
        q += " AND source = ?"
        params.append(source)
    q += " ORDER BY id"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
