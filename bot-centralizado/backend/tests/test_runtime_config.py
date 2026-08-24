# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime_config import broker_mutation_allowed, real_trading_allowed, resolve_capital_mode


def test_capital_mode_defaults_to_demo(monkeypatch):
    monkeypatch.delenv("CAPITAL_MODE", raising=False)
    assert resolve_capital_mode() == "DEMO"


def test_invalid_capital_mode_fails(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "LIVE")
    with pytest.raises(ValueError):
        resolve_capital_mode()


def test_real_trading_requires_global_allow(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "REAL")
    monkeypatch.delenv("AUREX_ALLOW_REAL", raising=False)
    allowed, reason = real_trading_allowed("SWING")
    assert allowed is False
    assert "AUREX_ALLOW_REAL=YES" in reason


def test_scalp_requires_strategy_specific_allow(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "REAL")
    monkeypatch.setenv("AUREX_ALLOW_REAL", "YES")
    monkeypatch.delenv("AUREX_ALLOW_SCALP_REAL", raising=False)
    allowed, reason = real_trading_allowed("SCALP")
    assert allowed is False
    assert "AUREX_ALLOW_SCALP_REAL=YES" in reason


def test_swing_can_be_allowed_explicitly(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "REAL")
    monkeypatch.setenv("AUREX_ALLOW_REAL", "YES")
    allowed, reason = real_trading_allowed("SWING")
    assert allowed is True
    assert "explicitly allowed" in reason


def test_broker_mutation_allowed_in_demo(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "DEMO")
    monkeypatch.delenv("AUREX_ALLOW_REAL", raising=False)
    monkeypatch.delenv("AUREX_ALLOW_BROKER_MUTATION", raising=False)
    allowed, reason = broker_mutation_allowed("OPEN_POSITION")
    assert allowed is True
    assert "DEMO" in reason


def test_broker_mutation_blocks_real_without_double_opt_in(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "REAL")
    monkeypatch.setenv("AUREX_ALLOW_REAL", "YES")
    monkeypatch.delenv("AUREX_ALLOW_BROKER_MUTATION", raising=False)
    allowed, reason = broker_mutation_allowed("OPEN_POSITION")
    assert allowed is False
    assert "AUREX_ALLOW_BROKER_MUTATION=YES" in reason


def test_broker_mutation_allows_real_with_double_opt_in(monkeypatch):
    monkeypatch.setenv("CAPITAL_MODE", "REAL")
    monkeypatch.setenv("AUREX_ALLOW_REAL", "YES")
    monkeypatch.setenv("AUREX_ALLOW_BROKER_MUTATION", "YES")
    allowed, reason = broker_mutation_allowed("MODIFY_POSITION")
    assert allowed is True
    assert "REAL" in reason
