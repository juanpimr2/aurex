# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dashboard_api_routes_are_read_only(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "DEMO")

    import dashboard

    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}
    api_rules = [rule for rule in dashboard.app.url_map.iter_rules() if rule.rule.startswith("/api/")]

    assert api_rules
    for rule in api_rules:
        assert not (set(rule.methods) & mutating_methods), rule.rule


def test_runtime_status_endpoint_uses_read_only_contract(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "DEMO")

    import dashboard

    def fake_status():
        return {
            "broker_ok": True,
            "balance": {"balance": 500, "available": 500, "profit_loss": 0},
            "positions": [],
            "monitors": {"monitor_swing": {"last_end": None, "ok": None}},
            "estado": "OPERATIVO",
        }

    monkeypatch.setattr(dashboard, "build_status", fake_status)
    client = dashboard.app.test_client()

    response = client.get("/api/runtime/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["schema_version"] == "runtime-status.v1"
    assert data["verdict"] == "NO_GO_FOR_REAL_TRADING"
    assert data["broker"]["read_only"] is True
    assert data["account"]["positions_count"] == 0
