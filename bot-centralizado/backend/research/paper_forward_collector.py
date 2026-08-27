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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


SCHEMA_VERSION = "paper-forward.v1"
DEFAULT_STORE = os.path.join(os.path.dirname(__file__), "paper_forward_events.jsonl")


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--store", default=DEFAULT_STORE)
    args = parser.parse_args()

    if args.summary:
        print(json.dumps(summarize_paper_state(args.store), indent=2))
        return 0

    parser.error("no action selected; use --summary")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
