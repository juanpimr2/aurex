# -*- coding: utf-8 -*-
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.paper_forward_collector import (
    build_candidate_id,
    make_candidate,
    resolve_candidate,
    summarize_paper_state,
    upsert_candidate,
    write_candidates,
)


def _candles(rows):
    return pd.DataFrame(rows)


def test_candidate_id_is_stable_for_same_setup():
    first = build_candidate_id(
        epic="gold",
        timeframe="minute_5",
        strategy="breakout",
        direction="short",
        entry_time="2026-08-27 10:00:00",
        entry=4598.123456,
    )
    second = build_candidate_id(
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        direction="SHORT",
        entry_time="2026-08-27 10:00:00",
        entry=4598.123456,
    )

    assert first == second


def test_upsert_candidate_deduplicates_repeated_observations():
    candidate = make_candidate(
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        session="london",
        direction="SHORT",
        entry_time="2026-08-27 10:00:00",
        entry=4598,
        sl=4601,
        tp=4595,
        spread_points=0.5,
        slippage_points=0.1,
    )
    candidates = []

    assert upsert_candidate(candidates, candidate) is True
    assert upsert_candidate(candidates, candidate) is False
    assert len(candidates) == 1


def test_resolve_short_candidate_hits_take_profit_after_costs():
    candidate = make_candidate(
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        session="london",
        direction="SHORT",
        entry_time="2026-08-27 10:00:00",
        entry=4598,
        sl=4601,
        tp=4595,
        spread_points=0.5,
        slippage_points=0.1,
    )
    candles = _candles([
        {"timestamp": "2026-08-27 10:00:00", "high": 4599, "low": 4597, "close": 4598},
        {"timestamp": "2026-08-27 10:05:00", "high": 4598, "low": 4594.5, "close": 4595},
    ])

    resolved = resolve_candidate(candidate, candles)

    assert resolved.status == "CLOSED"
    assert resolved.outcome == "TP"
    assert resolved.exit == 4595
    assert resolved.pnl_points == 2.4


def test_resolve_long_candidate_hits_stop_loss_first():
    candidate = make_candidate(
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        session="london",
        direction="LONG",
        entry_time="2026-08-27 10:00:00",
        entry=4598,
        sl=4595,
        tp=4601,
        spread_points=0.5,
        slippage_points=0.1,
    )
    candles = _candles([
        {"timestamp": "2026-08-27 10:00:00", "high": 4599, "low": 4597, "close": 4598},
        {"timestamp": "2026-08-27 10:05:00", "high": 4602, "low": 4594.5, "close": 4596},
    ])

    resolved = resolve_candidate(candidate, candles)

    assert resolved.status == "CLOSED"
    assert resolved.outcome == "SL"
    assert resolved.pnl_points == -3.6


def test_summary_reports_no_data_without_creating_store(tmp_path):
    store = tmp_path / "paper.jsonl"

    summary = summarize_paper_state(str(store))

    assert summary["schema_version"] == "paper-forward.v1"
    assert summary["status"] == "NO_DATA"
    assert summary["total_candidates"] == 0
    assert summary["broker_mutations"] == "disabled"
    assert not store.exists()


def test_summary_aggregates_written_candidates(tmp_path):
    store = tmp_path / "paper.jsonl"
    win = make_candidate(
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        session="london",
        direction="SHORT",
        entry_time="2026-08-27 10:00:00",
        entry=4598,
        sl=4601,
        tp=4595,
        spread_points=0.5,
        slippage_points=0.1,
    )
    closed = resolve_candidate(
        win,
        _candles([
            {"timestamp": "2026-08-27 10:05:00", "high": 4598, "low": 4594, "close": 4595}
        ]),
    )
    write_candidates([closed], str(store))

    summary = summarize_paper_state(str(store))

    assert summary["status"] == "ACTIVE"
    assert summary["total_candidates"] == 1
    assert summary["closed_candidates"] == 1
    assert summary["wins"] == 1
    assert summary["total_pnl_points"] == 2.4
