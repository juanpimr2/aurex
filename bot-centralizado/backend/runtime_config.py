# -*- coding: utf-8 -*-
"""
Runtime safety helpers for Aurex.

This module is deliberately small and side-effect free: importing it never logs
in to Capital.com and never touches broker state.
"""
import os
from typing import Tuple


VALID_CAPITAL_MODES = {"DEMO", "REAL"}


def resolve_capital_mode() -> str:
    """Return DEMO or REAL. Missing mode fails closed to DEMO."""
    mode = os.getenv("CAPITAL_MODE", "DEMO").strip().upper()
    if mode not in VALID_CAPITAL_MODES:
        raise ValueError("CAPITAL_MODE must be DEMO or REAL, got: " + repr(mode))
    return mode


def real_trading_allowed(strategy_name: str) -> Tuple[bool, str]:
    """Return whether real order submission is explicitly allowed."""
    strategy = strategy_name.strip().upper()
    mode = resolve_capital_mode()
    if mode != "REAL":
        return False, "CAPITAL_MODE is " + mode + ", not REAL"

    if os.getenv("AUREX_ALLOW_REAL", "").strip().upper() != "YES":
        return False, "AUREX_ALLOW_REAL=YES is required for any real trading"

    if strategy in {"SCALP", "M15"}:
        key = "AUREX_ALLOW_" + strategy + "_REAL"
        if os.getenv(key, "").strip().upper() != "YES":
            return False, key + "=YES is required; " + strategy + " stays observation-only"

    return True, "REAL trading explicitly allowed for " + strategy


def broker_mutation_allowed(action_name: str) -> Tuple[bool, str]:
    """Return whether a broker mutation is allowed at the client boundary."""
    mode = resolve_capital_mode()
    action = action_name.strip().upper()
    if mode == "DEMO":
        return True, action + " allowed in DEMO"

    if os.getenv("AUREX_ALLOW_REAL", "").strip().upper() != "YES":
        return False, "blocked " + action + ": AUREX_ALLOW_REAL=YES is required in REAL"

    if os.getenv("AUREX_ALLOW_BROKER_MUTATION", "").strip().upper() != "YES":
        return False, "blocked " + action + ": AUREX_ALLOW_BROKER_MUTATION=YES is required in REAL"

    return True, action + " explicitly allowed in REAL"
