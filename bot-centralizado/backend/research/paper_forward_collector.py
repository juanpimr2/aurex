# -*- coding: utf-8 -*-
"""
Read-only paper forward-test collector for Aurex scalping candidates.

This module never talks to Capital.com directly and never opens, modifies, or
closes broker positions. It records and resolves simulated candidates only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy import StrategyConfig, calculate_indicators


SCHEMA_VERSION = "paper-forward.v1"
DEFAULT_STORE = os.path.join(os.path.dirname(__file__), "paper_forward_events.jsonl")
DEFAULT_EPICS = ["GOLD", "US500", "US100", "DE40", "OIL_CRUDE", "OIL_BRENT", "SP35"]
DEFAULT_TIMEFRAMES = ["MINUTE_5", "MINUTE_15"]


@dataclass
class PaperCandidate:
    candidate_id: str
    observed_at: str
    epic: str
    timeframe: str
    strategy: str
    session: str
    direction: str
    entry_time: str
    entry: float
    sl: float
    tp: float
    spread_points: float
    slippage_points: float
    filters: Dict[str, Any]
    runtime_verdict: str
    status: str = "OPEN"
    outcome: Optional[str] = None
    exit_time: Optional[str] = None
    exit: Optional[float] = None
    pnl_points: Optional[float] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_candidate_id(
    *,
    epic: str,
    timeframe: str,
    strategy: str,
    direction: str,
    entry_time: str,
    entry: float,
) -> str:
    raw = "|".join([
        epic.upper(),
        timeframe.upper(),
        strategy,
        direction.upper(),
        str(entry_time),
        f"{float(entry):.5f}",
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_candidate(
    *,
    epic: str,
    timeframe: str,
    strategy: str,
    session: str,
    direction: str,
    entry_time: str,
    entry: float,
    sl: float,
    tp: float,
    spread_points: float,
    slippage_points: float,
    filters: Optional[Dict[str, Any]] = None,
    runtime_verdict: str = "NO_GO_FOR_REAL_TRADING",
    observed_at: Optional[str] = None,
) -> PaperCandidate:
    direction = direction.upper()
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("direction must be LONG or SHORT")
    candidate_id = build_candidate_id(
        epic=epic,
        timeframe=timeframe,
        strategy=strategy,
        direction=direction,
        entry_time=entry_time,
        entry=entry,
    )
    return PaperCandidate(
        candidate_id=candidate_id,
        observed_at=observed_at or utc_now_iso(),
        epic=epic.upper(),
        timeframe=timeframe,
        strategy=strategy,
        session=session,
        direction=direction,
        entry_time=str(entry_time),
        entry=round(float(entry), 5),
        sl=round(float(sl), 5),
        tp=round(float(tp), 5),
        spread_points=round(float(spread_points), 5),
        slippage_points=round(float(slippage_points), 5),
        filters=filters or {},
        runtime_verdict=runtime_verdict,
    )


def load_candidates(path: str = DEFAULT_STORE) -> List[PaperCandidate]:
    if not os.path.isfile(path):
        return []
    candidates = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            candidates.append(PaperCandidate(**data))
    return candidates


def write_candidates(candidates: Iterable[PaperCandidate], path: str = DEFAULT_STORE) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for candidate in candidates:
            handle.write(json.dumps(asdict(candidate), sort_keys=True) + "\n")


def upsert_candidate(
    candidates: List[PaperCandidate],
    candidate: PaperCandidate,
) -> bool:
    if any(existing.candidate_id == candidate.candidate_id for existing in candidates):
        return False
    candidates.append(candidate)
    return True


def session_bucket(timestamp: Any) -> str:
    ts = pd.to_datetime(timestamp)
    hour = ts.hour
    if 7 <= hour < 12:
        return "london"
    if 12 <= hour < 17:
        return "ny_overlap"
    return "all"


def _strategy_config() -> StrategyConfig:
    return StrategyConfig(
        ema_fast=5,
        ema_slow=13,
        ema_long=34,
        rsi_period=10,
        atr_period=10,
        bb_period=20,
        vol_sma_period=20,
    )


def _spread_points(client: Any, epic: str) -> float:
    market = client.get_market_info(epic) or {}
    snapshot = market.get("snapshot", market)
    bid = snapshot.get("bid")
    offer = snapshot.get("offer")
    if bid is None or offer is None:
        return 0.0
    return abs(float(offer) - float(bid))


def candidate_from_signal_bar(
    *,
    signal_bar: pd.Series,
    entry_bar: pd.Series,
    epic: str,
    timeframe: str,
    strategy: str,
    spread_points: float,
    slippage_points: float,
    risk_eur: float,
    target_eur: float,
    runtime_verdict: str,
) -> Optional[PaperCandidate]:
    if pd.isna(signal_bar.get("atr")) or float(signal_bar.get("atr")) <= 0:
        return None

    trend_up = (
        signal_bar["ema_fast"] > signal_bar["ema_slow"] > signal_bar["ema_long"]
    )
    trend_down = (
        signal_bar["ema_fast"] < signal_bar["ema_slow"] < signal_bar["ema_long"]
    )
    direction = None
    if (
        trend_up
        and signal_bar["close"] > signal_bar["roll_high"]
        and signal_bar["rsi"] < 75
    ):
        direction = "LONG"
    elif (
        trend_down
        and signal_bar["close"] < signal_bar["roll_low"]
        and signal_bar["rsi"] > 25
    ):
        direction = "SHORT"
    if direction is None:
        return None

    stop_points = max(float(signal_bar["atr"]) * 0.45, spread_points * 3)
    if stop_points <= 0 or risk_eur <= 0 or target_eur <= 0:
        return None
    size = risk_eur / stop_points
    target_points = target_eur / size
    if target_points <= (spread_points + slippage_points) * 2:
        return None

    entry = float(entry_bar["open"])
    if direction == "LONG":
        sl = entry - stop_points
        tp = entry + target_points
    else:
        sl = entry + stop_points
        tp = entry - target_points

    filters = {
        "trend_up": bool(trend_up),
        "trend_down": bool(trend_down),
        "breakout_high": bool(signal_bar["close"] > signal_bar["roll_high"]),
        "breakout_low": bool(signal_bar["close"] < signal_bar["roll_low"]),
        "rsi": round(float(signal_bar["rsi"]), 2),
        "atr": round(float(signal_bar["atr"]), 5),
        "reference_signal_time": str(signal_bar["timestamp"]),
        "paper_size": round(float(size), 5),
        "risk_eur": float(risk_eur),
        "target_eur": float(target_eur),
    }
    return make_candidate(
        epic=epic,
        timeframe=timeframe,
        strategy=strategy,
        session=session_bucket(signal_bar["timestamp"]),
        direction=direction,
        entry_time=str(entry_bar["timestamp"]),
        entry=entry,
        sl=sl,
        tp=tp,
        spread_points=spread_points,
        slippage_points=slippage_points,
        filters=filters,
        runtime_verdict=runtime_verdict,
    )


def build_breakout_candidate_from_candles(
    candles: pd.DataFrame,
    *,
    epic: str,
    timeframe: str,
    spread_points: float,
    slippage_points: float,
    risk_eur: float = 3.0,
    target_eur: float = 3.0,
    runtime_verdict: str = "NO_GO_FOR_REAL_TRADING",
) -> Optional[PaperCandidate]:
    if candles is None or len(candles) < 42:
        return None
    df = calculate_indicators(candles, _strategy_config())
    df["roll_high"] = df["high"].rolling(12).max().shift(1)
    df["roll_low"] = df["low"].rolling(12).min().shift(1)
    signal_bar = df.iloc[-2]
    entry_bar = df.iloc[-1]
    return candidate_from_signal_bar(
        signal_bar=signal_bar,
        entry_bar=entry_bar,
        epic=epic,
        timeframe=timeframe,
        strategy="ema_breakout_fixed_eur_target",
        spread_points=spread_points,
        slippage_points=slippage_points,
        risk_eur=risk_eur,
        target_eur=target_eur,
        runtime_verdict=runtime_verdict,
    )


def _after_entry(candles: pd.DataFrame, entry_time: str) -> pd.DataFrame:
    df = candles.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    entry_ts = pd.to_datetime(entry_time)
    return df[df["timestamp"] > entry_ts].sort_values("timestamp")


def resolve_candidate(
    candidate: PaperCandidate,
    candles: pd.DataFrame,
) -> PaperCandidate:
    if candidate.status != "OPEN":
        return candidate
    future = _after_entry(candles, candidate.entry_time)
    for _, row in future.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        if candidate.direction == "LONG":
            if low <= candidate.sl:
                return _with_outcome(candidate, row["timestamp"], candidate.sl, "SL")
            if high >= candidate.tp:
                return _with_outcome(candidate, row["timestamp"], candidate.tp, "TP")
        else:
            if high >= candidate.sl:
                return _with_outcome(candidate, row["timestamp"], candidate.sl, "SL")
            if low <= candidate.tp:
                return _with_outcome(candidate, row["timestamp"], candidate.tp, "TP")
    return candidate


def _with_outcome(
    candidate: PaperCandidate,
    exit_time: Any,
    exit_price: float,
    outcome: str,
) -> PaperCandidate:
    total_cost = candidate.spread_points + candidate.slippage_points
    if candidate.direction == "LONG":
        pnl_points = float(exit_price) - candidate.entry - total_cost
    else:
        pnl_points = candidate.entry - float(exit_price) - total_cost
    data = asdict(candidate)
    data.update({
        "status": "CLOSED",
        "outcome": outcome,
        "exit_time": str(exit_time),
        "exit": round(float(exit_price), 5),
        "pnl_points": round(float(pnl_points), 5),
    })
    return PaperCandidate(**data)


def resolve_open_candidates(
    candidates: Iterable[PaperCandidate],
    candles_by_key: Dict[str, pd.DataFrame],
) -> List[PaperCandidate]:
    resolved = []
    for candidate in candidates:
        key = f"{candidate.epic}:{candidate.timeframe}"
        candles = candles_by_key.get(key)
        if candles is None:
            resolved.append(candidate)
            continue
        resolved.append(resolve_candidate(candidate, candles))
    return resolved


def summarize_paper_state(path: str = DEFAULT_STORE) -> Dict[str, Any]:
    candidates = load_candidates(path)
    closed = [candidate for candidate in candidates if candidate.status == "CLOSED"]
    open_items = [candidate for candidate in candidates if candidate.status == "OPEN"]
    wins = [candidate for candidate in closed if (candidate.pnl_points or 0) > 0]
    losses = [candidate for candidate in closed if (candidate.pnl_points or 0) <= 0]
    gross_profit = sum(candidate.pnl_points or 0 for candidate in wins)
    gross_loss = abs(sum(candidate.pnl_points or 0 for candidate in losses))
    latest = sorted(candidates, key=lambda item: item.observed_at, reverse=True)[:5]
    return {
        "schema_version": SCHEMA_VERSION,
        "store": path,
        "status": "NO_DATA" if not candidates else "ACTIVE",
        "total_candidates": len(candidates),
        "open_candidates": len(open_items),
        "closed_candidates": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(closed), 1) if closed else None,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
        "total_pnl_points": round(sum(candidate.pnl_points or 0 for candidate in closed), 5),
        "broker_mutations": "disabled",
        "latest": [asdict(candidate) for candidate in latest],
    }


def collect_live(
    *,
    client: Any,
    epics: Iterable[str],
    timeframes: Iterable[str],
    store: str = DEFAULT_STORE,
    max_candles: int = 220,
    risk_eur: float = 3.0,
    target_eur: float = 3.0,
    slippage_spread_fraction: float = 0.25,
    runtime_verdict: str = "NO_GO_FOR_REAL_TRADING",
) -> Dict[str, Any]:
    candidates = load_candidates(store)
    before = {candidate.candidate_id: candidate.status for candidate in candidates}
    candles_by_key: Dict[str, pd.DataFrame] = {}
    added = 0

    for epic in epics:
        epic = epic.strip().upper()
        if not epic:
            continue
        spread = _spread_points(client, epic)
        if spread <= 0:
            continue
        for timeframe in timeframes:
            timeframe = timeframe.strip().upper()
            if not timeframe:
                continue
            candles = client.get_prices(epic, timeframe, max_candles)
            if candles is None or len(candles) < 42:
                continue
            key = f"{epic}:{timeframe}"
            candles_by_key[key] = candles
            candidate = build_breakout_candidate_from_candles(
                candles,
                epic=epic,
                timeframe=timeframe,
                spread_points=spread,
                slippage_points=spread * slippage_spread_fraction,
                risk_eur=risk_eur,
                target_eur=target_eur,
                runtime_verdict=runtime_verdict,
            )
            if candidate and upsert_candidate(candidates, candidate):
                added += 1

    candidates = resolve_open_candidates(candidates, candles_by_key)
    resolved = sum(
        1
        for candidate in candidates
        if before.get(candidate.candidate_id) == "OPEN" and candidate.status == "CLOSED"
    )
    if candidates:
        write_candidates(candidates, store)

    summary = summarize_paper_state(store)
    summary.update({
        "added_candidates": added,
        "resolved_candidates": resolved,
        "epics_checked": [epic.strip().upper() for epic in epics if epic.strip()],
        "timeframes_checked": [timeframe.strip().upper() for timeframe in timeframes if timeframe.strip()],
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--collect-live", action="store_true")
    parser.add_argument("--store", default=DEFAULT_STORE)
    parser.add_argument("--epics", default=",".join(DEFAULT_EPICS))
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument("--max-candles", type=int, default=220)
    parser.add_argument("--risk-eur", type=float, default=3.0)
    parser.add_argument("--target-eur", type=float, default=3.0)
    parser.add_argument("--slippage-spread-fraction", type=float, default=0.25)
    parser.add_argument("--runtime-verdict", default="NO_GO_FOR_REAL_TRADING")
    args = parser.parse_args()

    if args.summary:
        print(json.dumps(summarize_paper_state(args.store), indent=2))
        return 0
    if args.collect_live:
        os.environ.setdefault("CAPITAL_MODE", "DEMO")
        from capital_client import CapitalClient

        client = CapitalClient()
        if not client.login():
            raise RuntimeError("Capital login failed")
        print(json.dumps(
            collect_live(
                client=client,
                epics=[item for item in args.epics.split(",")],
                timeframes=[item for item in args.timeframes.split(",")],
                store=args.store,
                max_candles=args.max_candles,
                risk_eur=args.risk_eur,
                target_eur=args.target_eur,
                slippage_spread_fraction=args.slippage_spread_fraction,
                runtime_verdict=args.runtime_verdict,
            ),
            indent=2,
        ))
        return 0

    parser.error("no action selected; use --summary or --collect-live")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
