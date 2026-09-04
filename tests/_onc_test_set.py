"""Shared helpers for tests that consume the sibling `cms-hte-patient-matching-test-set`
repo's generated ONC-derived data (both the per-provision pairs tier and the
population-query tier - see that repo's `evaluation/cases/README.md`).

Not itself a test module - `test_*.py` files import from here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from patient_matching.matching.backend import FieldCriterion, MatchingBackend

REPO_ROOT = Path(__file__).resolve().parents[1]
SIBLING_TEST_SET_REPO = REPO_ROOT.parent / "cms-hte-patient-matching-test-set"
ONC_CASES_DIR = SIBLING_TEST_SET_REPO / "evaluation" / "cases"


class NullBackend(MatchingBackend):
    """No-op backend - `MatchingEngine.evaluate_pair()` never calls it, but the
    engine's constructor requires a backend instance."""

    def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []


def missing_sibling_data_reason(path: Path) -> str:
    """Skip reason for tests gated on the sibling test-set repo being cloned.

    This repo's `.claude/skills/test-matching-rule/SKILL.md` already assumes
    `cms-hte-patient-matching-test-set` is cloned alongside this one; these
    tests make the same assumption and skip (never fail) if it isn't present,
    since CI for *this* repo does not currently check out the sibling repo.
    """
    return (
        f"ONC-derived test data not found at {path}. Clone "
        "icanbwell/cms-hte-patient-matching-test-set as a sibling of this repo "
        "to run this test (see .claude/skills/test-matching-rule/SKILL.md)."
    )
