# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reconciliation_status import build_reconciliation_status


HEADER = (
    "datetime_utc,epic,direction,entry_price,sl,tp,rr,size_teorico,"
    "riesgo_teorico_usd,rsi_day,atr_day,ema_align_day,h4_trend,rsi_h4,"
    "resultado,pnl_teorico_usd,notas\n"
)


def test_reconciliation_flags_local_pending_row_missing_from_broker(tmp_path):
    (tmp_path / "swing_signal_log.csv").write_text(
        HEADER
        + "2026-07-08 10:00,GOLD,SELL,4044.14,4231.83,3715.68,1.75,0.0324,"
        + "6.08,46.8,93.85,BAJISTA,MIXTA/LATERAL,27.2,PENDIENTE,,"
        + "Trade SWING real abierto | eq_open=121.67\n",
        encoding="utf-8",
    )

    status = build_reconciliation_status(positions=[], base=tmp_path)

    assert status["schema_version"] == "reconciliation.v1"
    assert status["status"] == "stale_local_state"
    assert status["ready_for_real_trading"] is False
    assert status["broker_open_positions"] == 0
    assert status["local_pending_rows"] == 1
    assert status["unmatched_pending_rows"] == 1
    assert status["unmatched"][0]["source"] == "SWING"


def test_reconciliation_accepts_matching_broker_position(tmp_path):
    (tmp_path / "swing_signal_log.csv").write_text(
        HEADER
        + "2026-07-08 10:00,GOLD,SELL,4044.14,4231.83,3715.68,1.75,0.0324,"
        + "6.08,46.8,93.85,BAJISTA,MIXTA/LATERAL,27.2,PENDIENTE,,"
        + "Trade SWING real abierto | eq_open=121.67\n",
        encoding="utf-8",
    )

    status = build_reconciliation_status(
        positions=[{"epic": "GOLD", "dir": "SELL"}],
        base=tmp_path,
    )

    assert status["status"] == "ok"
    assert status["local_pending_rows"] == 1
    assert status["unmatched_pending_rows"] == 0
