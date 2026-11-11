"""Wiring test for `evaluation/legacy_comparison.py`'s helix parse step.

That script is run by hand, not by CI, and imports `z_scripts.empty_strings` lazily, so a broken
import would otherwise go unnoticed. It is loaded by path because `evaluation/` is not a package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytest.importorskip("patient_matching")

LEGACY_PATH = (
    Path(__file__).resolve().parent.parent / "evaluation" / "legacy_comparison.py"
)


def _load_legacy() -> ModuleType:
    spec = importlib.util.spec_from_file_location("legacy_comparison", LEGACY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakePatient:
    """Rejects any blank string, like FHIR's `string` type."""

    @classmethod
    def model_validate(cls, raw: dict[str, Any]) -> dict[str, Any]:
        if any(isinstance(v, str) and not v.strip() for v in raw.values()):
            raise ValueError("blank string")
        return raw


class _AlwaysInvalid:
    @classmethod
    def model_validate(cls, raw: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("invalid")


@pytest.mark.parametrize(
    ("raw", "expected", "expected_retries"),
    [
        ({"name": "x"}, {"name": "x"}, 0),
        ({"name": "x", "city": ""}, {"name": "x"}, 1),
    ],
)
def test_parse_helix_patient_retries_blank_strings_and_counts_the_retry(
    raw: dict[str, Any], expected: dict[str, Any], expected_retries: int
) -> None:
    legacy = _load_legacy()
    retries: list[bool] = []
    assert legacy._parse_helix_patient(raw, _FakePatient, retries) == expected
    assert len(retries) == expected_retries


def test_parse_helix_patient_reraises_when_the_retry_also_fails() -> None:
    legacy = _load_legacy()
    with pytest.raises(ValueError):
        legacy._parse_helix_patient({"city": ""}, _AlwaysInvalid, [])
