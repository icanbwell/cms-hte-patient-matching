"""Shared helpers for tests that consume the ONC-derived test data fetched into
`tests/fixtures/onc/` by `scripts/fetch_onc_test_data.py` (both the per-provision
pairs tier and the population-query tier - see `tests/fixtures/onc/README.md` for
provenance and `cms-hte-patient-matching-test-set`'s `evaluation/cases/README.md`
for how each tier was originally generated).

Not itself a test module - `test_*.py` files import from here.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ONC_CASES_DIR = REPO_ROOT / "tests" / "fixtures" / "onc"


def missing_fixture_data_reason(path: Path) -> str:
    """Skip reason for tests gated on fetched fixture data being present.

    This data is downloaded on demand (`make fetch-onc-data`, see
    `scripts/fetch_onc_test_data.py`), not committed - so this is the expected
    path before that's been run, not defense-in-depth for a corrupted clone.
    """
    return (
        f"ONC test data not found at {path}. Run `make fetch-onc-data` "
        "(see tests/fixtures/onc/README.md) to download it."
    )
