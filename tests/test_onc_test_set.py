"""Tests for `tests/_onc_test_set.py::threshold`."""

from __future__ import annotations

import pytest

from ._onc_test_set import threshold


def test_threshold_defaults_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONC_X", raising=False)
    assert threshold("ONC_X", 0.9) == 0.9


def test_threshold_defaults_when_env_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONC_X", "  ")
    assert threshold("ONC_X", 0.9) == 0.9


def test_threshold_reads_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONC_X", "0.95")
    assert threshold("ONC_X", 0.9) == 0.95


def test_threshold_rejects_non_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONC_X", "high")
    with pytest.raises(ValueError, match="ONC_X='high' is not a number"):
        threshold("ONC_X", 0.9)
