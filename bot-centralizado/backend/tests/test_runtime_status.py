# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime_status import RUNTIME_STATUS_SCHEMA_VERSION, build_runtime_status


def test_runtime_status_contract_defaults_to_read_only(monkeypatch):
    monkeypatch.delenv("CAPITAL_MODE", raising=False)
    status = build_runtime_status(
        broker_ok=True,
        balance={"balance": 500, "available": 500, "profit_loss": 0},
        positions=[],
        working_orders=[],
        monitors={},
        updated_at="2026-08-24T00:00:00+00:00",
    )

    assert status["schema_version"] == RUNTIME_STATUS_SCHEMA_VERSION
    assert status["mode"] == "DEMO"
    assert status["verdict"] == "NO_GO_FOR_REAL_TRADING"
    assert status["broker"]["read_only"] is True
    assert status["account"]["positions_count"] == 0
    assert status["account"]["working_orders_count"] == 0
    assert status["live_policy"]["verdict"] == "NO_GO_FOR_REAL_TRADING"
    assert any(g["name"] == "dashboard_mutation_surface" and g["allowed"] is False for g in status["runtime_gates"])


def test_runtime_status_reports_real_gates_without_enabling_dashboard_mutation(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "REAL")
    monkeypatch.setenv("AUREX_ALLOW_REAL", "YES")
    monkeypatch.setenv("AUREX_ALLOW_BROKER_MUTATION", "YES")
    monkeypatch.delenv("AUREX_ALLOW_SCALP_REAL", raising=False)

    status = build_runtime_status(updated_at="2026-08-24T00:00:00+00:00")
    gates = {gate["name"]: gate for gate in status["runtime_gates"]}

    assert status["mode"] == "REAL"
    assert status["verdict"] == "NO_GO_FOR_REAL_TRADING"
    assert gates["broker_mutation_boundary"]["allowed"] is True
    assert gates["scalp_real"]["allowed"] is False
    assert gates["dashboard_mutation_surface"]["allowed"] is False


def test_runtime_status_has_stable_error_contract(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "DEMO")
    status = build_runtime_status(
        broker_ok=False,
        balance=None,
        positions=None,
        monitors=None,
        errors=["broker timeout"],
        updated_at="2026-08-24T00:00:00+00:00",
    )

    assert status["broker"]["ok"] is False
    assert status["account"]["balance"] is None
    assert status["account"]["positions"] == []
    assert status["account"]["working_orders"] == []
    assert status["errors"] == ["broker timeout"]


def test_runtime_status_includes_working_orders(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "DEMO")
    working_orders = [
        {
            "deal_id": "order-1",
            "epic": "GOLD",
            "direction": "BUY",
            "size": 0.1,
            "level": 4600,
            "status": "OPEN",
        },
    ]

    status = build_runtime_status(
        working_orders=working_orders,
        updated_at="2026-08-24T00:00:00+00:00",
    )

    assert status["account"]["working_orders_count"] == 1
    assert status["account"]["working_orders"] == working_orders


def test_runtime_status_includes_reconciliation_warning(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "DEMO")
    reconciliation = {
        "schema_version": "reconciliation.v1",
        "status": "stale_local_state",
        "ready_for_real_trading": False,
        "unmatched_pending_rows": 1,
    }

    status = build_runtime_status(
        reconciliation=reconciliation,
        updated_at="2026-08-24T00:00:00+00:00",
    )

    assert status["reconciliation"] == reconciliation
    assert any(
        event["message"] == "broker/local reconciliation requires review"
        for event in status["events"]
    )
