"""Shared helpers for tests that consume the vendored ONC-derived test data under
`tests/fixtures/onc/` (both the per-provision pairs tier and the population-query
tier - see `tests/fixtures/onc/README.md` for provenance and
`cms-hte-patient-matching-test-set`'s `evaluation/cases/README.md` for how each
tier was originally generated).

Not itself a test module - `test_*.py` files import from here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from patient_matching.matching.backend import FieldCriterion, MatchingBackend

REPO_ROOT = Path(__file__).resolve().parents[1]
ONC_CASES_DIR = REPO_ROOT / "tests" / "fixtures" / "onc"


class NullBackend(MatchingBackend):
    """No-op backend - `MatchingEngine.evaluate_pair()` never calls it, but the
    engine's constructor requires a backend instance."""

    def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []


def missing_fixture_data_reason(path: Path) -> str:
    """Skip reason for tests gated on the vendored ONC fixture data being present.

    This data is checked into `tests/fixtures/onc/` (see that directory's
    README.md for provenance and how to refresh it), so this should never be
    missing in a normal checkout - this is defense-in-depth for a corrupted or
    partial clone, not the expected path.
    """
    return (
        f"Vendored ONC-derived test data not found at {path}. See "
        "tests/fixtures/onc/README.md for provenance and how to restore it."
    )
