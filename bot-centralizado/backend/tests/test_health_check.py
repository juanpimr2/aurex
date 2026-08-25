# -*- coding: utf-8 -*-
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import health_check


def _write_trade_closes(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE trade_closes (
            date_utc TEXT,
            pnl REAL,
            tx_type TEXT
        )
    """)
    conn.executemany("INSERT INTO trade_closes VALUES (?,?,?)", rows)
    conn.commit()
    conn.close()


def test_risk_ignores_cash_withdrawals(monkeypatch, tmp_path):
    db_path = tmp_path / "aurex_trades.db"
    _write_trade_closes(db_path, [
        ("2026-08-01", 500.0, "DEPOSIT"),
        ("2026-08-02", 100.0, "TRADE"),
        ("2026-08-03", -300.0, "WITHDRAWAL"),
    ])
    monkeypatch.setattr(health_check, "DB_PATH", str(db_path))
    health_check.OK.clear()
    health_check.ISSUES.clear()

    health_check.check_risk(500.0)

    assert not health_check.ISSUES
    assert any("Drawdown realizado de trades: 0.0%" in msg for msg in health_check.OK)


def test_risk_flags_realized_trade_drawdown(monkeypatch, tmp_path):
    db_path = tmp_path / "aurex_trades.db"
    _write_trade_closes(db_path, [
        ("2026-08-01", 100.0, "TRADE"),
        ("2026-08-02", -100.0, "TRADE"),
    ])
    monkeypatch.setattr(health_check, "DB_PATH", str(db_path))
    health_check.OK.clear()
    health_check.ISSUES.clear()

    health_check.check_risk(500.0)

    expected = (
        "CRIT",
        "Drawdown realizado de trades: 20.0% "
        "(100.00 EUR; P&L 0.00 / pico 100.00) (>15%)",
    )
    assert expected in health_check.ISSUES
