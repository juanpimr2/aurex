# -*- coding: utf-8 -*-
"""
Central risk policy for Aurex live monitors.

Values are intentionally conservative until broker reconciliation and SPEC-001
guards are fully validated.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPolicy:
    risk_pct: float
    max_risk_open_pct: float = 5.0
    max_dd_pct: float = 10.0
    max_dd_day_pct: float = 5.0


RISK_POLICIES = {
    "SWING": RiskPolicy(risk_pct=1.0, max_risk_open_pct=5.0, max_dd_pct=10.0, max_dd_day_pct=5.0),
    "SCALP": RiskPolicy(risk_pct=1.0, max_risk_open_pct=5.0, max_dd_pct=10.0, max_dd_day_pct=5.0),
    "M15": RiskPolicy(risk_pct=1.0, max_risk_open_pct=5.0, max_dd_pct=10.0, max_dd_day_pct=5.0),
}


def get_risk_policy(strategy_name: str) -> RiskPolicy:
    key = strategy_name.strip().upper()
    if key not in RISK_POLICIES:
        raise KeyError("Unknown risk policy: " + strategy_name)
    return RISK_POLICIES[key]
