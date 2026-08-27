# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_policy import LIVE_POLICY_SCHEMA_VERSION, build_live_policy


def test_live_policy_defaults_to_no_go(monkeypatch):
    monkeypatch.delenv("AUREX_LIVE_POLICY_ACCEPTED", raising=False)
    monkeypatch.delenv("AUREX_LIVE_SESSION_APPROVED", raising=False)
    monkeypatch.delenv("AUREX_KILL_SWITCH_READY", raising=False)

    policy = build_live_policy()

    assert policy["schema_version"] == LIVE_POLICY_SCHEMA_VERSION
    assert policy["verdict"] == "NO_GO_FOR_REAL_TRADING"
    assert policy["approval_model"]["broker_mutations"] == "disabled"
    assert policy["objective"]["guaranteed"] is False
    readiness = {item["name"]: item for item in policy["readiness"]}
    assert readiness["policy_accepted"]["ready"] is False
    assert readiness["session_approved"]["ready"] is False
    assert readiness["kill_switch_ready"]["ready"] is False
    assert readiness["instrument_scope"]["ready"] is True
    assert readiness["position_capacity"]["ready"] is True
    assert readiness["position_protection"]["ready"] is True
    assert readiness["no_working_orders"]["ready"] is True


def test_live_policy_reports_readiness_flags(monkeypatch):
    monkeypatch.setenv("AUREX_LIVE_POLICY_ACCEPTED", "YES")
    monkeypatch.setenv("AUREX_LIVE_SESSION_APPROVED", "YES")
    monkeypatch.setenv("AUREX_KILL_SWITCH_READY", "YES")

    policy = build_live_policy()
    readiness = {item["name"]: item for item in policy["readiness"]}

    assert readiness["policy_accepted"]["ready"] is True
    assert readiness["session_approved"]["ready"] is True
    assert readiness["kill_switch_ready"]["ready"] is True
    assert policy["verdict"] == "NO_GO_FOR_REAL_TRADING"


def test_live_policy_blocks_non_policy_position():
    policy = build_live_policy(
        positions=[
            {
                "deal_id": "manual-1",
                "epic": "SP35",
                "sl": 19578.4,
                "tp": 20871.5,
            }
        ]
    )
    readiness = {item["name"]: item for item in policy["readiness"]}

    assert readiness["instrument_scope"]["ready"] is False
    assert "SP35" in readiness["instrument_scope"]["reason"]
    assert readiness["position_capacity"]["ready"] is False


def test_live_policy_blocks_unprotected_positions_and_working_orders():
    policy = build_live_policy(
        positions=[{"deal_id": "gold-1", "epic": "GOLD", "sl": None, "tp": 4684.0}],
        working_orders=[{"deal_id": "order-1", "epic": "GOLD"}],
    )
    readiness = {item["name"]: item for item in policy["readiness"]}

    assert readiness["position_protection"]["ready"] is False
    assert readiness["no_working_orders"]["ready"] is False
