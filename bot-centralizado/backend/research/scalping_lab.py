# -*- coding: utf-8 -*-
"""
Read-only scalping lab for Aurex.

Fetches Capital.com candles and evaluates simple intraday hypotheses with
spread-aware accounting. This script never opens, modifies, or closes trades.
"""
import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capital_client import CapitalClient
from strategy import StrategyConfig, calculate_indicators


DEFAULT_EPICS = ["GOLD", "US500", "US100", "DE40", "OIL_CRUDE", "OIL_BRENT", "SP35"]
DEFAULT_TIMEFRAMES = ["MINUTE_5", "MINUTE_15"]
DEFAULT_SPREAD_MULTIPLIERS = [1.0, 1.5, 2.0, 3.0]


@dataclass
class ScalpTrade:
    entry_time: str
    exit_time: str
    epic: str
    timeframe: str
    direction: str
    entry: float
    exit: float
    sl: float
    tp: float
    size: float
    pnl: float
    result: str


def _session_ok(timestamp: pd.Timestamp, session: str) -> bool:
    hour = timestamp.hour
    if session == "all":
        return True
    if session == "london":
        return 7 <= hour < 12
    if session == "ny_overlap":
        return 12 <= hour < 17
    return True


def _stats(
    trades: List[ScalpTrade],
    initial_capital: float,
    final_equity: float,
    *,
    stopped_days: int = 0,
) -> Dict:
    if not trades:
        return {
            "total_trades": 0,
            "days_stopped_by_loss": stopped_days,
            "classification": "NO_DATA",
        }
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    day_counts: Dict[str, int] = {}
    for trade in trades:
        equity += trade.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        day = trade.entry_time[:10]
        day_counts[day] = day_counts.get(day, 0) + 1
    expectancy = sum(t.pnl for t in trades) / len(trades)
    return {
        "total_trades": len(trades),
        "days": len(day_counts),
        "avg_trades_per_day": round(len(trades) / max(len(day_counts), 1), 2),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
        "expectancy_eur": round(expectancy, 3),
        "total_pnl_eur": round(sum(t.pnl for t in trades), 2),
        "return_pct": round(100 * (final_equity - initial_capital) / initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "max_drawdown_eur": round(max_dd, 2),
        "max_drawdown_pct": round(100 * max_dd / initial_capital, 2),
        "best_trade_eur": round(max(t.pnl for t in trades), 2),
        "worst_trade_eur": round(min(t.pnl for t in trades), 2),
        "days_stopped_by_loss": stopped_days,
    }


def _classify(stats: Dict, *, min_trades: int, max_drawdown_pct: float) -> str:
    trades = stats.get("total_trades", 0)
    if trades <= 0:
        return "NO_DATA"
    if trades < min_trades:
        return "EXPLORATORY_LOW_SAMPLE"

    profit_factor = stats.get("profit_factor") or 0
    expectancy = stats.get("expectancy_eur") or 0
    drawdown = stats.get("max_drawdown_pct") or 0
    if profit_factor >= 1.3 and expectancy > 0 and drawdown <= max_drawdown_pct:
        return "CANDIDATE"
    return "REJECTED"


def _split_df(df: pd.DataFrame, split_ratio: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < split_ratio < 1:
        raise ValueError("split_ratio must be between 0 and 1")
    split_idx = max(1, min(len(df) - 1, int(len(df) * split_ratio)))
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def _walk_forward_splits(
    df: pd.DataFrame,
    *,
    train_size: int,
    test_size: int,
    step_size: int,
) -> List[Tuple[str, pd.DataFrame, pd.DataFrame]]:
    if train_size <= 0 or test_size <= 0 or step_size <= 0:
        raise ValueError("walk-forward sizes must be positive")
    splits = []
    start = 0
    window = 1
    while start + train_size + test_size <= len(df):
        train = df.iloc[start:start + train_size].copy()
        test = df.iloc[start + train_size:start + train_size + test_size].copy()
        splits.append((f"wf_{window}", train, test))
        start += step_size
        window += 1
    return splits


def _run_breakout(
    df: pd.DataFrame,
    *,
    epic: str,
    timeframe: str,
    initial_capital: float,
    risk_eur: float,
    target_eur: float,
    spread_points: float,
    slippage_points: float,
    session: str,
    max_trades_per_day: int,
    max_daily_loss_eur: float,
    min_trades: int,
    max_drawdown_pct: float,
) -> Dict:
    cfg = StrategyConfig(
        ema_fast=5,
        ema_slow=13,
        ema_long=34,
        rsi_period=10,
        atr_period=10,
        bb_period=20,
        vol_sma_period=20,
    )
    df = calculate_indicators(df, cfg)
    df["roll_high"] = df["high"].rolling(12).max().shift(1)
    df["roll_low"] = df["low"].rolling(12).min().shift(1)

    equity = initial_capital
    trades: List[ScalpTrade] = []
    in_trade = None
    trades_by_day: Dict[str, int] = {}
    pnl_by_day: Dict[str, float] = {}
    stopped_days = set()
    total_cost_points = spread_points + slippage_points

    for i in range(40, len(df) - 1):
        row = df.iloc[i]
        nxt = df.iloc[i + 1]
        ts = pd.to_datetime(row["timestamp"])
        day = str(ts.date())

        if in_trade:
            direction = in_trade["direction"]
            exit_price = None
            result = None
            if direction == "LONG":
                if nxt["low"] <= in_trade["sl"]:
                    exit_price = in_trade["sl"]
                    result = "SL"
                elif nxt["high"] >= in_trade["tp"]:
                    exit_price = in_trade["tp"]
                    result = "TP"
            else:
                if nxt["high"] >= in_trade["sl"]:
                    exit_price = in_trade["sl"]
                    result = "SL"
                elif nxt["low"] <= in_trade["tp"]:
                    exit_price = in_trade["tp"]
                    result = "TP"
            if exit_price is not None:
                points = exit_price - in_trade["entry"] if direction == "LONG" else in_trade["entry"] - exit_price
                pnl = (points * in_trade["size"]) - (total_cost_points * in_trade["size"])
                equity += pnl
                exit_day = str(pd.to_datetime(nxt["timestamp"]).date())
                pnl_by_day[exit_day] = pnl_by_day.get(exit_day, 0.0) + pnl
                trades.append(ScalpTrade(
                    entry_time=str(in_trade["entry_time"]),
                    exit_time=str(nxt["timestamp"]),
                    epic=epic,
                    timeframe=timeframe,
                    direction=direction,
                    entry=round(float(in_trade["entry"]), 5),
                    exit=round(float(exit_price), 5),
                    sl=round(float(in_trade["sl"]), 5),
                    tp=round(float(in_trade["tp"]), 5),
                    size=round(float(in_trade["size"]), 5),
                    pnl=round(float(pnl), 4),
                    result=result,
                ))
                in_trade = None
            continue

        if not _session_ok(ts, session):
            continue
        if pnl_by_day.get(day, 0.0) <= -abs(max_daily_loss_eur):
            stopped_days.add(day)
            continue
        if trades_by_day.get(day, 0) >= max_trades_per_day:
            continue
        if pd.isna(row["atr"]) or row["atr"] <= 0:
            continue

        trend_up = row["ema_fast"] > row["ema_slow"] > row["ema_long"]
        trend_down = row["ema_fast"] < row["ema_slow"] < row["ema_long"]
        direction = None
        if trend_up and row["close"] > row["roll_high"] and row["rsi"] < 75:
            direction = "LONG"
        elif trend_down and row["close"] < row["roll_low"] and row["rsi"] > 25:
            direction = "SHORT"
        if direction is None:
            continue

        atr_stop_points = max(float(row["atr"]) * 0.45, spread_points * 3)
        size = risk_eur / atr_stop_points
        if size <= 0:
            continue
        target_points = target_eur / size
        if target_points <= total_cost_points * 2:
            continue

        entry = float(nxt["open"])
        if direction == "LONG":
            sl = entry - atr_stop_points
            tp = entry + target_points
        else:
            sl = entry + atr_stop_points
            tp = entry - target_points
        in_trade = {
            "entry_time": nxt["timestamp"],
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "size": size,
        }
        trades_by_day[day] = trades_by_day.get(day, 0) + 1

    result = {
        "strategy": "ema_breakout_fixed_eur_target",
        "epic": epic,
        "timeframe": timeframe,
        "session": session,
        "risk_eur": risk_eur,
        "target_eur": target_eur,
        "spread_points": spread_points,
        "slippage_points": slippage_points,
        "first_candle": str(df["timestamp"].iloc[0]) if len(df) else None,
        "last_candle": str(df["timestamp"].iloc[-1]) if len(df) else None,
        "stats": _stats(trades, initial_capital, equity, stopped_days=len(stopped_days)),
        "sample_trades": [asdict(t) for t in trades[-5:]],
    }
    result["stats"]["classification"] = _classify(
        result["stats"],
        min_trades=min_trades,
        max_drawdown_pct=max_drawdown_pct,
    )
    return result


def _spread_points(client: CapitalClient, epic: str) -> float:
    market = client.get_market_info(epic) or {}
    snapshot = market.get("snapshot", market)
    bid = snapshot.get("bid")
    offer = snapshot.get("offer")
    if bid is None or offer is None:
        return 0.0
    return abs(float(offer) - float(bid))


def run_lab(epics: Iterable[str], timeframes: Iterable[str], args) -> List[Dict]:
    os.environ.setdefault("CAPITAL_MODE", "DEMO")
    client = CapitalClient()
    if not client.login():
        raise RuntimeError("Capital login failed")

    results = []
    for epic in epics:
        spread = _spread_points(client, epic)
        if spread <= 0:
            continue
        for timeframe in timeframes:
            df = client.get_prices(epic, timeframe, args.max_candles)
            if df is None or len(df) < 100:
                results.append({
                    "epic": epic,
                    "timeframe": timeframe,
                    "error": "not enough candles",
                })
                continue
            if args.walk_forward:
                splits = _walk_forward_splits(
                    df,
                    train_size=args.wf_train_size,
                    test_size=args.wf_test_size,
                    step_size=args.wf_step_size,
                )
            else:
                train_df, test_df = _split_df(df, args.split_ratio)
                splits = [("split_1", train_df, test_df)]

            for spread_multiplier in args.spread_multipliers:
                for session in args.sessions:
                    common = {
                        "epic": epic,
                        "timeframe": timeframe,
                        "initial_capital": args.initial_capital,
                        "risk_eur": args.risk_eur,
                        "target_eur": args.target_eur,
                        "spread_points": spread * spread_multiplier,
                        "slippage_points": spread * args.slippage_spread_fraction,
                        "session": session,
                        "max_trades_per_day": args.max_trades_per_day,
                        "max_daily_loss_eur": args.max_daily_loss_eur,
                        "min_trades": args.min_trades_promote,
                        "max_drawdown_pct": args.max_drawdown_pct,
                    }
                    for window_name, train_df, test_df in splits:
                        for split_name, split_df in (("in_sample", train_df), ("out_of_sample", test_df)):
                            result = _run_breakout(split_df, **common)
                            result["window"] = window_name
                            result["split"] = split_name
                            result["spread_multiplier"] = spread_multiplier
                            result["observed_spread_points"] = spread
                            results.append(result)
    return results


def summarize_configs(results: List[Dict], *, min_trades: int, max_drawdown_pct: float) -> List[Dict]:
    grouped: Dict[Tuple, List[Dict]] = {}
    for result in results:
        if result.get("split") != "out_of_sample" or "stats" not in result:
            continue
        key = (
            result.get("epic"),
            result.get("timeframe"),
            result.get("session"),
            result.get("spread_multiplier"),
        )
        grouped.setdefault(key, []).append(result)

    summary = []
    for key, rows in grouped.items():
        stats_rows = [r["stats"] for r in rows if r["stats"].get("total_trades", 0) > 0]
        total_trades = sum(s.get("total_trades", 0) for s in stats_rows)
        total_pnl = sum(s.get("total_pnl_eur", 0) for s in stats_rows)
        weighted_expectancy = total_pnl / total_trades if total_trades else 0.0
        positive_windows = sum(1 for s in stats_rows if s.get("total_pnl_eur", 0) > 0)
        max_dd = max((s.get("max_drawdown_pct", 0) for s in stats_rows), default=0)
        profit_factors = [s.get("profit_factor") for s in stats_rows if s.get("profit_factor") is not None]
        avg_pf = sum(profit_factors) / len(profit_factors) if profit_factors else None
        stable = bool(stats_rows) and positive_windows >= max(1, len(stats_rows) // 2 + 1)
        aggregate = {
            "total_trades": total_trades,
            "windows": len(rows),
            "windows_with_trades": len(stats_rows),
            "positive_windows": positive_windows,
            "total_pnl_eur": round(total_pnl, 2),
            "expectancy_eur": round(weighted_expectancy, 3),
            "avg_profit_factor": round(avg_pf, 2) if avg_pf is not None else None,
            "max_drawdown_pct": round(max_dd, 2),
        }
        aggregate["classification"] = _classify(
            {
                "total_trades": total_trades,
                "profit_factor": aggregate["avg_profit_factor"],
                "expectancy_eur": aggregate["expectancy_eur"],
                "max_drawdown_pct": aggregate["max_drawdown_pct"],
            },
            min_trades=min_trades,
            max_drawdown_pct=max_drawdown_pct,
        )
        if aggregate["classification"] == "CANDIDATE" and not stable:
            aggregate["classification"] = "REJECTED_UNSTABLE_WINDOWS"
        epic, timeframe, session, spread_multiplier = key
        summary.append({
            "epic": epic,
            "timeframe": timeframe,
            "session": session,
            "spread_multiplier": spread_multiplier,
            "aggregate": aggregate,
        })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epics", default=",".join(DEFAULT_EPICS))
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument("--initial-capital", type=float, default=500.0)
    parser.add_argument("--risk-eur", type=float, default=3.0)
    parser.add_argument("--target-eur", type=float, default=3.0)
    parser.add_argument("--max-candles", type=int, default=1000)
    parser.add_argument("--max-trades-per-day", type=int, default=20)
    parser.add_argument("--max-daily-loss-eur", type=float, default=10.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=15.0)
    parser.add_argument("--min-trades-promote", type=int, default=100)
    parser.add_argument("--split-ratio", type=float, default=0.7)
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--wf-train-size", type=int, default=500)
    parser.add_argument("--wf-test-size", type=int, default=200)
    parser.add_argument("--wf-step-size", type=int, default=200)
    parser.add_argument("--spread-multipliers", default=",".join(str(v) for v in DEFAULT_SPREAD_MULTIPLIERS))
    parser.add_argument("--slippage-spread-fraction", type=float, default=0.25)
    parser.add_argument("--sessions", nargs="+", default=["all", "london", "ny_overlap"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    epics = [e.strip() for e in args.epics.split(",") if e.strip()]
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    args.spread_multipliers = [
        float(value.strip())
        for value in args.spread_multipliers.split(",")
        if value.strip()
    ]
    results = run_lab(epics, timeframes, args)
    summaries = summarize_configs(
        results,
        min_trades=args.min_trades_promote,
        max_drawdown_pct=args.max_drawdown_pct,
    )
    if args.json:
        print(json.dumps({
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "mode": os.getenv("CAPITAL_MODE", "DEMO"),
            "broker_mutations": "disabled",
            "configurations_tested": len(summaries),
            "summary": summaries,
            "results": results,
        }, indent=2))
        return 0

    ranked = sorted(
        [r for r in summaries if r["aggregate"].get("total_trades", 0) > 0],
        key=lambda r: (
            r["aggregate"].get("classification") == "CANDIDATE",
            r["aggregate"].get("avg_profit_factor") or 0,
            r["aggregate"].get("expectancy_eur") or 0,
        ),
        reverse=True,
    )
    print("AUREX SCALPING LAB | read-only | generated UTC " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    print("Initial capital EUR:", args.initial_capital, "| risk EUR:", args.risk_eur, "| target EUR:", args.target_eur)
    print("Spread multipliers:", ", ".join(str(v) for v in args.spread_multipliers))
    print("Slippage:", args.slippage_spread_fraction, "x spread")
    print("Split ratio:", args.split_ratio, "| min promoted trades:", args.min_trades_promote)
    if args.walk_forward:
        print("Walk-forward:", args.wf_train_size, "train /", args.wf_test_size, "test /", args.wf_step_size, "step")
    print("Configurations tested:", len(summaries))
    print()
    for r in ranked[:12]:
        s = r["aggregate"]
        print(
            f"{r['epic']} {r['timeframe']} {r['session']} spread_x={r['spread_multiplier']} | "
            f"trades={s['total_trades']} windows={s['positive_windows']}/{s['windows_with_trades']} "
            f"pnl={s['total_pnl_eur']} avg_pf={s['avg_profit_factor']} "
            f"exp={s['expectancy_eur']} dd={s['max_drawdown_pct']}% "
            f"class={s['classification']}"
        )
    if not ranked:
        print("No strategy variant produced trades under the current filters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
