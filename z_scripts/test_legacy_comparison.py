"""Wiring test for `evaluation/legacy_comparison.py`'s helix parse step.

That script is run by hand, not by CI, and imports `z_scripts.empty_strings` lazily, so a broken
import would otherwise go unnoticed. It is loaded by path because `evaluation/` is not a package.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytest.importorskip("patient_matching")

LEGACY_PATH = (
    Path(__file__).resolve().parent.parent / "evaluation" / "legacy_comparison.py"
)
SUBPROCESS_TIMEOUT_SECONDS = 60


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


def test_parse_helix_patient_runs_without_the_repo_root_on_sys_path(
    tmp_path: Path,
) -> None:
    """The script's Usage block runs it as `python evaluation/legacy_comparison.py`, with no
    `PYTHONPATH=.`. `z_scripts` is not an installed package, so the helper import only works
    if the script puts the repo root on `sys.path` itself. pytest has the root on its path,
    so this has to run in a fresh interpreter (`-I`: no cwd, no PYTHON* variables)."""
    code = textwrap.dedent(
        f"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("legacy_comparison", {str(LEGACY_PATH)!r})
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)


        class Patient:
            @classmethod
            def model_validate(cls, raw):
                return raw


        assert legacy._parse_helix_patient({{"name": "x"}}, Patient, []) == {{"name": "x"}}
        """
    )

    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stderr
