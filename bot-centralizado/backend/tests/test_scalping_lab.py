# -*- coding: utf-8 -*-
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.scalping_lab import (
    ScalpTrade,
    _classify,
    _split_df,
    _stats,
    _walk_forward_splits,
    summarize_configs,
)


def test_split_df_preserves_order_and_splits_by_ratio():
    df = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=10, freq="h")})

    train, test = _split_df(df, 0.7)

    assert len(train) == 7
    assert len(test) == 3
    assert train["timestamp"].iloc[-1] < test["timestamp"].iloc[0]


def test_walk_forward_splits_build_rolling_windows():
    df = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=12, freq="h")})

    splits = _walk_forward_splits(df, train_size=5, test_size=3, step_size=2)

    assert [name for name, _, _ in splits] == ["wf_1", "wf_2", "wf_3"]
    assert len(splits[0][1]) == 5
    assert len(splits[0][2]) == 3
    assert splits[1][1]["timestamp"].iloc[0] == df["timestamp"].iloc[2]


def test_classify_marks_low_sample_exploratory():
    stats = {
        "total_trades": 6,
        "profit_factor": 2.2,
        "expectancy_eur": 0.8,
        "max_drawdown_pct": 1.0,
    }

    assert _classify(stats, min_trades=100, max_drawdown_pct=15) == "EXPLORATORY_LOW_SAMPLE"


def test_classify_requires_profitability_and_drawdown():
    good = {
        "total_trades": 120,
        "profit_factor": 1.35,
        "expectancy_eur": 0.15,
        "max_drawdown_pct": 10,
    }
    weak = {
        "total_trades": 120,
        "profit_factor": 1.1,
        "expectancy_eur": -0.05,
        "max_drawdown_pct": 10,
    }

    assert _classify(good, min_trades=100, max_drawdown_pct=15) == "CANDIDATE"
    assert _classify(weak, min_trades=100, max_drawdown_pct=15) == "REJECTED"


def test_stats_include_daily_stop_count():
    trades = [
        ScalpTrade(
            entry_time="2026-01-01 10:00:00",
            exit_time="2026-01-01 10:15:00",
            epic="GOLD",
            timeframe="MINUTE_15",
            direction="LONG",
            entry=100,
            exit=103,
            sl=97,
            tp=103,
            size=1,
            pnl=3,
            result="TP",
        )
    ]

    stats = _stats(trades, 500, 503, stopped_days=2)

    assert stats["total_trades"] == 1
    assert stats["days_stopped_by_loss"] == 2
    assert stats["expectancy_eur"] == 3


def test_summarize_configs_keeps_low_sample_exploratory():
    results = [
        {
            "epic": "US500",
            "timeframe": "MINUTE_15",
            "session": "london",
            "spread_multiplier": 1.5,
            "split": "out_of_sample",
            "stats": {
                "total_trades": 6,
                "profit_factor": 2.2,
                "expectancy_eur": 0.8,
                "total_pnl_eur": 4.8,
                "max_drawdown_pct": 1.0,
            },
        }
    ]

    summary = summarize_configs(results, min_trades=100, max_drawdown_pct=15)

    assert len(summary) == 1
    assert summary[0]["aggregate"]["classification"] == "EXPLORATORY_LOW_SAMPLE"
    assert summary[0]["aggregate"]["total_trades"] == 6
