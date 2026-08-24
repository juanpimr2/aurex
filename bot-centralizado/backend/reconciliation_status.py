# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE = Path(__file__).resolve().parent
RECONCILIATION_SCHEMA_VERSION = "reconciliation.v1"
SIGNAL_LOGS = (
    ("M15", "m15_signal_log.csv"),
    ("SWING", "swing_signal_log.csv"),
    ("SCALP", "trade_log.csv"),
)
OPEN_RESULTS = {"PENDIENTE", "OPEN"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _extract_deal_id(row: Dict[str, Any]) -> Optional[str]:
    for key in ("deal_id", "dealId", "deal"):
        value = _clean(row.get(key))
        if value:
            return value

    notes = _clean(row.get("notas") or row.get("notes"))
    match = re.search(r"(?:DealID|Deal)\s*:?\s*([A-Za-z0-9_-]+)", notes, re.I)
    return match.group(1) if match else None


def _result_is_open(value: str) -> bool:
    normalized = _clean(value).upper()
    return normalized in OPEN_RESULTS or normalized.startswith("OPEN")


def read_pending_signal_rows(base: Path = BASE) -> List[Dict[str, Any]]:
    """Return local CSV rows that still claim an open/pending trade."""
    pending: List[Dict[str, Any]] = []

    for source, filename in SIGNAL_LOGS:
        path = base / filename
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=2):
                result = _clean(row.get("resultado") or row.get("result"))
                if not _result_is_open(result):
                    continue
                pending.append({
                    "source": source,
                    "file": filename,
                    "line": index,
                    "datetime_utc": _clean(row.get("datetime_utc") or row.get("datetime")),
                    "epic": _clean(row.get("epic")),
                    "direction": _clean(row.get("direction") or row.get("dir")).upper(),
                    "result": result,
                    "deal_id": _extract_deal_id(row),
                })

    return pending


def _position_key(position: Dict[str, Any]) -> tuple[str, str]:
    return (
        _clean(position.get("epic")).upper(),
        _clean(position.get("direction") or position.get("dir")).upper(),
    )


def _pending_matches_broker(row: Dict[str, Any], positions: List[Dict[str, Any]]) -> bool:
    deal_id = row.get("deal_id")
    if deal_id:
        return any(_clean(p.get("deal_id")) == deal_id for p in positions)

    row_key = (_clean(row.get("epic")).upper(), _clean(row.get("direction")).upper())
    if not row_key[0]:
        return False
    return any(_position_key(position) == row_key for position in positions)


def build_reconciliation_status(
    *,
    positions: Optional[Iterable[Dict[str, Any]]] = None,
    base: Path = BASE,
) -> Dict[str, Any]:
    """Compare local open/pending logs with broker positions already fetched upstream."""
    positions_list = list(positions or [])
    pending_rows = read_pending_signal_rows(base)
    unmatched = [
        row for row in pending_rows
        if not _pending_matches_broker(row, positions_list)
    ]

    status = "ok" if not unmatched else "stale_local_state"
    reason = (
        "local pending/open logs match broker positions"
        if status == "ok"
        else "local logs still claim open/pending trades that are not open at broker"
    )

    return {
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "status": status,
        "ready_for_real_trading": False,
        "reason": reason,
        "broker_open_positions": len(positions_list),
        "local_pending_rows": len(pending_rows),
        "unmatched_pending_rows": len(unmatched),
        "unmatched": unmatched[:10],
    }
