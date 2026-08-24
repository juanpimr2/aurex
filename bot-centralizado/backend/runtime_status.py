# -*- coding: utf-8 -*-
"""
Read-only runtime status contracts for Aurex.

This module is side-effect free: it never logs in to Capital.com and never
opens, modifies, or closes broker positions.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from runtime_config import broker_mutation_allowed, real_trading_allowed, resolve_capital_mode


RUNTIME_STATUS_SCHEMA_VERSION = "runtime-status.v1"
REAL_TRADING_VERDICT = "NO_GO_FOR_REAL_TRADING"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gate(name: str, allowed: bool, reason: str) -> Dict[str, Any]:
    return {
        "name": name,
        "allowed": bool(allowed),
        "reason": reason,
    }


def build_runtime_gates() -> list:
    """Return current runtime gates without touching broker state."""
    mode = resolve_capital_mode()
    mutation_allowed, mutation_reason = broker_mutation_allowed("BROKER_MUTATION")
    swing_allowed, swing_reason = real_trading_allowed("SWING")
    scalp_allowed, scalp_reason = real_trading_allowed("SCALP")
    m15_allowed, m15_reason = real_trading_allowed("M15")

    dashboard_reason = "dashboard runtime endpoints are read-only and never submit broker mutations"
    return [
        _gate("dashboard_mutation_surface", False, dashboard_reason),
        _gate("capital_mode_real", mode == "REAL", "CAPITAL_MODE is " + mode),
        _gate("broker_mutation_boundary", mutation_allowed, mutation_reason),
        _gate("swing_real", swing_allowed, swing_reason),
        _gate("scalp_real", scalp_allowed, scalp_reason),
        _gate("m15_real", m15_allowed, m15_reason),
    ]


def build_runtime_status(
    *,
    broker_ok: Optional[bool] = None,
    balance: Optional[Dict[str, Any]] = None,
    positions: Optional[Iterable[Dict[str, Any]]] = None,
    monitors: Optional[Dict[str, Any]] = None,
    errors: Optional[Iterable[str]] = None,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the canonical read-only runtime status response."""
    positions_list = list(positions or [])
    errors_list = list(errors or [])
    mode = resolve_capital_mode()

    return {
        "schema_version": RUNTIME_STATUS_SCHEMA_VERSION,
        "updated_at": updated_at or utc_now_iso(),
        "mode": mode,
        "verdict": REAL_TRADING_VERDICT,
        "broker": {
            "ok": bool(broker_ok) if broker_ok is not None else None,
            "source": "capital.com",
            "read_only": True,
        },
        "account": {
            "currency": "EUR",
            "balance": balance,
            "positions_count": len(positions_list),
            "positions": positions_list,
        },
        "runtime_gates": build_runtime_gates(),
        "monitors": monitors or {},
        "events": [
            {
                "level": "info",
                "message": "runtime status endpoint is read-only",
            },
            {
                "level": "warning",
                "message": "real trading remains NO-GO",
            },
        ],
        "errors": errors_list,
    }
