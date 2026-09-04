"""NPPES cross-provider false-positive check for the CMS Table 2 matching engine.

**This is not a practitioner-matching compliance test** - it can't be one. This
repo's Table 2 rules and Table 3 collision probabilities are patient-specific
(see `docs/ONC_REGRESSION_TEST_DESIGN.md`'s "Alternatives Considered" for the
full reasoning) and the public NPPES NPI Registry never collects DOB, SSN, or
email - the fields nearly every approved rule requires. Practitioner/provider
matching is owned by `helix.personmatching`/`person-matching-service`, not
this repo (`docs/PROJECT_MAP.md` §1).

What this test *does* check: exactly one approved rule can evaluate at all
against NPPES-shaped data - **Rule 33, "First Name* + Last Name* + Phone
Number + ZIP Code"** - the only approved rule requiring none of
DOB/SSN/MBI/email. Real medical group practices commonly share one practice
phone number and ZIP across multiple distinct providers (confirmed in this
vendored sample: 130 (phone, ZIP) pairs shared by 2+ distinct NPIs, several
sharing a last name - likely colleagues or family practicing together). That's
exactly the shape of coincidence rule 33 has to get right without a
name-independent identifier to fall back on. This test verifies it does: no
two genuinely distinct real providers (different NPI) in this sample are
ever declared a match.

A hit here would be a real, actionable finding - not a data quality issue to
paper over, the way an ONC hard-negative false positive would be.

Approach: normalize/extract every provider once, then block by (phone, ZIP) -
the two non-fuzzy fields rule 33 requires - and run `evaluate_pair()` only
within blocks with 2+ distinct NPIs (mirrors how the real engine's own
blocking works, and how the ONC test-set repo's hard-negative miner blocks on
strong fields before verifying fuzzy ones - see that repo's `hard_negatives.py`).
Full O(n^2) pairing isn't needed since every other approved rule needs a field
NPPES doesn't have, so a pair that doesn't share (phone, ZIP) cannot match
under any rule.
"""

from __future__ import annotations

import csv
import glob
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from patient_matching.matching.field_extractor import FieldExtractor, PatientFields
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

from ._null_backend import NullBackend
from ._onc_test_set import REPO_ROOT, missing_fixture_data_reason

NPPES_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "nppes"


def _load_providers(fixtures_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for csv_path in sorted(glob.glob(str(fixtures_dir / "*.csv"))):
        with open(csv_path) as f:
            rows.extend(csv.DictReader(f))
    return rows


def _to_patient_shaped_dict(row: Dict[str, str]) -> Dict[str, Any]:
    """Build a minimal FHIR-Patient-shaped dict from an NPPES row - deliberately
    omitting `identifier` (the NPI) so it doesn't leak into `PatientFields` as a
    namespace ID and trivially "match" a record to itself; the NPI is tracked
    separately, purely as this test's own ground-truth key, the same role
    `EnterpriseID` plays in the ONC tests without being fed through the engine
    as a real-world patient identifier would be."""
    given = [row["First Name"]] if row["First Name"] else []
    if row.get("Middle Name"):
        given.append(row["Middle Name"])

    patient: Dict[str, Any] = {
        "name": [
            {
                "family": row["Last Name"],
                "given": given,
                "suffix": [row["Suffix"]] if row.get("Suffix") else [],
            }
        ],
    }

    if row.get("Practice Address Phone"):
        patient["telecom"] = [
            {"system": "phone", "value": row["Practice Address Phone"]}
        ]

    address: Dict[str, Any] = {}
    if row.get("Practice Address Line 1"):
        address["line"] = [row["Practice Address Line 1"]]
    if row.get("Practice Address City"):
        address["city"] = row["Practice Address City"]
    if row.get("Practice Address State"):
        address["state"] = row["Practice Address State"]
    if row.get("Practice Address Postal Code"):
        address["postalCode"] = row["Practice Address Postal Code"]
    if address:
        patient["address"] = [address]

    return patient


@pytest.mark.skipif(
    not NPPES_FIXTURES_DIR.exists() or not list(NPPES_FIXTURES_DIR.glob("*.csv")),
    reason=missing_fixture_data_reason(NPPES_FIXTURES_DIR),
)
def test_no_false_match_between_distinct_nppes_providers() -> None:
    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    engine = MatchingEngine(backend=NullBackend())

    rows = _load_providers(NPPES_FIXTURES_DIR)
    assert rows, f"{NPPES_FIXTURES_DIR} contains no providers"

    npis = [row["NPI"] for row in rows]
    assert len(npis) == len(set(npis)), "Duplicate NPI within the vendored sample"

    errors: List[str] = []
    provider_fields: List[
        Tuple[str, str, PatientFields]
    ] = []  # (npi, display_name, fields)
    for row in rows:
        npi = row["NPI"]
        try:
            fields = extractor.extract(
                normalizer.normalize(_to_patient_shaped_dict(row))
            )
        except Exception as exc:  # noqa: BLE001 - tally as a failure, not a crash
            errors.append(f"NPI {npi}: {exc!r}")
            continue
        provider_fields.append((npi, f"{row['First Name']} {row['Last Name']}", fields))

    assert not errors, (
        f"{len(errors)}/{len(rows)} providers raised instead of extracting: "
        + "; ".join(errors[:10])
    )

    # Block on (phone, zip) - the two non-fuzzy fields rule 33 requires. Every
    # other approved rule needs a field (DOB/SSN/ITIN/MBI/email/legal ID/
    # namespace ID) this NPPES-derived data never has, so a pair outside these
    # blocks cannot match under any rule.
    blocks: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for idx, (_npi, _name, fields) in enumerate(provider_fields):
        for phone in fields.phones:
            for zip_code in fields.zip_codes:
                blocks[(phone, zip_code)].append(idx)

    false_positives: List[str] = []
    pairs_evaluated = 0
    blocks_with_collisions = 0
    for (phone, zip_code), indices in blocks.items():
        distinct_npis = {provider_fields[i][0] for i in indices}
        if len(distinct_npis) < 2:
            continue
        blocks_with_collisions += 1
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                npi_a, name_a, fields_a = provider_fields[indices[a]]
                npi_b, name_b, fields_b = provider_fields[indices[b]]
                if npi_a == npi_b:
                    continue
                pairs_evaluated += 1
                if engine.evaluate_pair(fields_a, fields_b):
                    false_positives.append(
                        f"NPI {npi_a} ({name_a}) matched NPI {npi_b} ({name_b}) "
                        f"via shared phone={phone!r} zip={zip_code!r}"
                    )

    summary = (
        f"n_providers={len(provider_fields)} blocks_with_multiple_providers="
        f"{blocks_with_collisions} pairs_evaluated={pairs_evaluated}"
    )

    assert not false_positives, (
        f"Found {len(false_positives)} cross-provider false positive(s) - two "
        "genuinely distinct real practitioners (different NPI) were declared a "
        f"match.\n{summary}\n" + "\n".join(false_positives)
    )
