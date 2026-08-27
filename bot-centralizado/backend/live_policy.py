# -*- coding: utf-8 -*-
"""
Live-trading policy contract for Aurex.

The policy is deliberately conservative and side-effect free. It describes the
conditions required before supervised broker mutations can be considered; it
does not approve or execute them.
"""
import os
from typing import Any, Dict, Iterable


LIVE_POLICY_SCHEMA_VERSION = "live-policy.v1"
LIVE_POLICY_VERDICT = "NO_GO_FOR_REAL_TRADING"


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().upper() == "YES"


def _list(items: Iterable[Dict[str, Any]] | None) -> list:
    return list(items or [])


def build_live_policy(
    *,
    positions: Iterable[Dict[str, Any]] | None = None,
    working_orders: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    positions_list = _list(positions)
    working_orders_list = _list(working_orders)
    allowed_instruments = ["GOLD"]
    max_positions = 1
    non_policy_positions = [
        p.get("epic")
        for p in positions_list
        if p.get("epic") not in allowed_instruments
    ]
    unprotected_positions = [
        p.get("deal_id") or p.get("epic")
        for p in positions_list
        if not p.get("sl") or not p.get("tp")
    ]

    policy_accepted = _enabled("AUREX_LIVE_POLICY_ACCEPTED")
    session_approved = _enabled("AUREX_LIVE_SESSION_APPROVED")
    kill_switch_ready = _enabled("AUREX_KILL_SWITCH_READY")
    instrument_scope_ready = not non_policy_positions
    position_capacity_ready = len(positions_list) < max_positions
    protection_ready = not unprotected_positions
    no_working_orders = len(working_orders_list) == 0

    readiness = [
        {
            "name": "policy_accepted",
            "ready": policy_accepted,
            "reason": "AUREX_LIVE_POLICY_ACCEPTED=YES is required before supervised live trading",
        },
        {
            "name": "session_approved",
            "ready": session_approved,
            "reason": "AUREX_LIVE_SESSION_APPROVED=YES is required for the current supervised session",
        },
        {
            "name": "kill_switch_ready",
            "ready": kill_switch_ready,
            "reason": "AUREX_KILL_SWITCH_READY=YES is required before broker mutations are considered",
        },
        {
            "name": "instrument_scope",
            "ready": instrument_scope_ready,
            "reason": (
                "all open positions are inside policy scope"
                if instrument_scope_ready
                else "open positions outside policy scope: " + ", ".join(sorted(set(non_policy_positions)))
            ),
        },
        {
            "name": "position_capacity",
            "ready": position_capacity_ready,
            "reason": (
                "capacity available for a supervised position"
                if position_capacity_ready
                else "max open positions reached for policy V1"
            ),
        },
        {
            "name": "position_protection",
            "ready": protection_ready,
            "reason": (
                "all visible positions include stop loss and take profit"
                if protection_ready
                else "positions without full SL/TP protection: " + ", ".join(str(p) for p in unprotected_positions)
            ),
        },
        {
            "name": "no_working_orders",
            "ready": no_working_orders,
            "reason": (
                "no pending broker working orders detected"
                if no_working_orders
                else "pending broker working orders must be reviewed first"
            ),
        },
    ]

    return {
        "schema_version": LIVE_POLICY_SCHEMA_VERSION,
        "mode": "supervised_read_only_preparation",
        "verdict": LIVE_POLICY_VERDICT,
        "objective": {
            "starting_capital_eur": 500,
            "weekly_profit_target_eur": 50,
            "guaranteed": False,
            "note": "The target is a product/business objective, not an execution promise.",
        },
        "approval_model": {
            "broker_mutations": "disabled",
            "requires_explicit_user_approval": True,
            "approval_scope": "per supervised live session",
        },
        "risk_controls": {
            "allowed_instruments": allowed_instruments,
            "max_open_positions": max_positions,
            "max_risk_per_trade_pct": 1.0,
            "max_daily_loss_eur": 10,
            "max_weekly_loss_eur": 25,
            "require_stop_loss": True,
            "require_take_profit": True,
            "require_reconciliation_ok": True,
            "require_runtime_health_green": True,
        },
        "readiness": readiness,
    }
