# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from legacy.legacy_guard import legacy_runtime_allowed, require_legacy_runtime


def test_legacy_runtime_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AUREX_ALLOW_LEGACY_RUNTIME", raising=False)
    assert legacy_runtime_allowed() is False
    with pytest.raises(RuntimeError):
        require_legacy_runtime("legacy/test")


def test_legacy_runtime_requires_explicit_lab_opt_in(monkeypatch):
    monkeypatch.setenv("AUREX_ALLOW_LEGACY_RUNTIME", "YES")
    assert legacy_runtime_allowed() is True
    require_legacy_runtime("legacy/test")
