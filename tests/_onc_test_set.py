"""Shared helpers for tests that consume the vendored ONC-derived test data under
`tests/fixtures/onc/` (both the per-provision pairs tier and the population-query
tier - see `tests/fixtures/onc/README.md` for provenance and
`cms-hte-patient-matching-test-set`'s `evaluation/cases/README.md` for how each
tier was originally generated).

Not itself a test module - `test_*.py` files import from here.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ONC_CASES_DIR = REPO_ROOT / "tests" / "fixtures" / "onc"


def missing_fixture_data_reason(path: Path) -> str:
    """Skip reason for tests gated on vendored fixture data being present.

    This data is checked into the repo (see the relevant `tests/fixtures/*/README.md`
    for provenance and how to refresh it), so this should never be missing in a
    normal checkout - this is defense-in-depth for a corrupted or partial clone,
    not the expected path.
    """
    return (
        f"Vendored test data not found at {path}. See the README.md in that "
        "fixture directory for provenance and how to restore it."
    )
