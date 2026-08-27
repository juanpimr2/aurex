# -*- coding: utf-8 -*-
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research import paper_forward_collector as pfc
from research.paper_forward_collector import (
    build_candidate_id,
    candidate_from_signal_bar,
    collect_live,
    make_candidate,
    resolve_candidate,
    summarize_paper_state,
    upsert_candidate,
    write_candidates,
)


def _candles(rows):
    return pd.DataFrame(rows)


def _flat_candles(periods=42, start="2026-08-27 06:35:00"):
    times = pd.date_range(start, periods=periods, freq="5min")
    return pd.DataFrame([
        {
            "timestamp": str(ts),
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1,
        }
        for ts in times
    ])


class FakeClient:
    def __init__(self, candles):
        self.candles = candles

    def get_market_info(self, epic):
        return {"snapshot": {"bid": 100.0, "offer": 100.5}}

    def get_prices(self, epic, timeframe, max_candles):
        return self.candles


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


def test_candidate_from_signal_bar_builds_long_candidate():
    signal_bar = pd.Series({
        "timestamp": "2026-08-27 10:00:00",
        "open": 99,
        "high": 101,
        "low": 98,
        "close": 101,
        "ema_fast": 100,
        "ema_slow": 99,
        "ema_long": 98,
        "roll_high": 100,
        "roll_low": 97,
        "rsi": 60,
        "atr": 2,
    })
    entry_bar = pd.Series({
        "timestamp": "2026-08-27 10:05:00",
        "open": 101.25,
    })

    candidate = candidate_from_signal_bar(
        signal_bar=signal_bar,
        entry_bar=entry_bar,
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        spread_points=0.5,
        slippage_points=0.1,
        risk_eur=3,
        target_eur=3,
        runtime_verdict="NO_GO_FOR_REAL_TRADING",
    )

    assert candidate is not None
    assert candidate.direction == "LONG"
    assert candidate.session == "london"
    assert candidate.entry == 101.25
    assert candidate.sl == 99.75
    assert candidate.tp == 102.75


def test_candidate_from_signal_bar_returns_none_without_breakout():
    signal_bar = pd.Series({
        "timestamp": "2026-08-27 10:00:00",
        "close": 99,
        "ema_fast": 100,
        "ema_slow": 99,
        "ema_long": 98,
        "roll_high": 100,
        "roll_low": 97,
        "rsi": 60,
        "atr": 2,
    })
    entry_bar = pd.Series({"timestamp": "2026-08-27 10:05:00", "open": 101.25})

    candidate = candidate_from_signal_bar(
        signal_bar=signal_bar,
        entry_bar=entry_bar,
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        spread_points=0.5,
        slippage_points=0.1,
        risk_eur=3,
        target_eur=3,
        runtime_verdict="NO_GO_FOR_REAL_TRADING",
    )

    assert candidate is None


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


def test_collect_live_adds_candidate_once(monkeypatch, tmp_path):
    store = tmp_path / "paper.jsonl"
    candles = _flat_candles()
    entry_time = str(candles.iloc[-1]["timestamp"])
    candidate = make_candidate(
        epic="GOLD",
        timeframe="MINUTE_5",
        strategy="breakout",
        session="london",
        direction="LONG",
        entry_time=entry_time,
        entry=101,
        sl=99,
        tp=103,
        spread_points=0.5,
        slippage_points=0.1,
    )
    monkeypatch.setattr(
        pfc,
        "build_breakout_candidate_from_candles",
        lambda *args, **kwargs: candidate,
    )
    client = FakeClient(candles)

    first = collect_live(
        client=client,
        epics=["GOLD"],
        timeframes=["MINUTE_5"],
        store=str(store),
        max_candles=220,
    )
    second = collect_live(
        client=client,
        epics=["GOLD"],
        timeframes=["MINUTE_5"],
        store=str(store),
        max_candles=220,
    )

    assert first["added_candidates"] == 1
    assert second["added_candidates"] == 0
    assert second["total_candidates"] == 1


def test_collect_live_resolves_existing_open_candidate(monkeypatch, tmp_path):
    store = tmp_path / "paper.jsonl"
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
    write_candidates([candidate], str(store))
    monkeypatch.setattr(pfc, "build_breakout_candidate_from_candles", lambda *args, **kwargs: None)
    candles = _flat_candles(periods=40, start="2026-08-27 06:40:00")
    candles = pd.concat([
        candles,
        _candles([
            {"timestamp": "2026-08-27 10:00:00", "open": 4598, "high": 4599, "low": 4597, "close": 4598, "volume": 1},
            {"timestamp": "2026-08-27 10:05:00", "open": 4598, "high": 4598, "low": 4594, "close": 4595, "volume": 1},
        ]),
    ], ignore_index=True)
    client = FakeClient(candles)

    summary = collect_live(
        client=client,
        epics=["GOLD"],
        timeframes=["MINUTE_5"],
        store=str(store),
        max_candles=220,
    )

    assert summary["resolved_candidates"] == 1
    assert summary["closed_candidates"] == 1
    assert summary["wins"] == 1
