"""NPPES matching test for the CMS Table 2 matching engine - practitioners.

**This is not a practitioner-matching compliance test** - it can't be one. This
repo's Table 2 rules and Table 3 collision probabilities are patient-specific
(see `docs/ONC_REGRESSION_TEST_DESIGN.md`'s "Alternatives Considered" for the
full reasoning) and the public NPPES NPI Registry never collects DOB, SSN, or
email - the fields nearly every approved rule requires. Practitioner/provider
matching is owned by `helix.personmatching`/`person-matching-service`, not
this repo (`docs/PROJECT_MAP.md` §1).

What this test *does* check: exactly one approved rule can evaluate at all
against NPPES-shaped data - **Rule 33, "First Name* + Last Name* + Phone
Number + ZIP Code"**, `max_fuzzy_fields=2` - the only approved rule requiring
none of DOB/SSN/MBI/email. It's tested both directions, like the ONC pairs
test:

- **Recall (does it match when it should):** an exact duplicate of a
  provider's record, and single-edit (Damerau-Levenshtein <= 1, per CMS SS
  E.2) typo variants of the first name, last name, or both (rule 33 allows
  fuzzy on both simultaneously) - phone and ZIP held fixed. All should match.
- **FPR (does it wrongly match when it shouldn't):** real, distinct providers
  (different NPI) who happen to share a practice phone + ZIP - common in
  group practices (130 such collisions found in this vendored sample, several
  sharing a last name too - likely colleagues or family). None should match.

A false positive here is a real, actionable finding, not a data-quality issue
to paper over the way an ONC hard-negative false positive would be - there's
no ambiguity about whether two different NPIs are the same person. A false
negative on the exact-duplicate or single-edit cases would mean rule 33's own
fuzzy tolerance is broken, independent of any practitioner-specific question.

Approach for FPR: normalize/extract every provider once, then block by
(phone, ZIP) - the two non-fuzzy fields rule 33 requires - and run
`evaluate_pair()` only within blocks with 2+ distinct NPIs (mirrors how the
real engine's own blocking works, and how the ONC test-set repo's
hard-negative miner blocks on strong fields before verifying fuzzy ones - see
that repo's `hard_negatives.py`). Full O(n^2) pairing isn't needed since every
other approved rule needs a field NPPES doesn't have, so a pair that doesn't
share (phone, ZIP) cannot match under any rule.

Approach for recall: generate deterministic single-edit variants (adjacent
transposition at the first index where two adjacent characters differ) rather
than random mutation, so the test is reproducible without needing a seeded
RNG. Only attempted on names >=5 characters after normalization, per CMS SS
E.3 (no fuzzy matching below that length) - shorter names are skipped as
not-applicable for that specific mutation, not silently counted as failures.

A provider whose practice phone didn't survive normalization at all (a
placeholder like "000-000-0000", or a non-US/APO number the phone normalizer
can't parse under its default US region - 27 of 4,943 in this sample) is
excluded from every recall case, including exact-duplicate - rule 33 can't
evaluate without phone present, even against an identical copy of itself.
That's a real, narrow NPPES-data-quality limitation worth surfacing plainly
(tracked as `not_applicable["missing_phone_or_zip"]` in the summary), not a
matching bug to conflate into recall by counting it as a false negative.

Measured on this vendored sample: recall 1.0000 (17,299/17,299 true-match
cases across all four categories, 0 false negatives), FPR 0.0000 (0/307
distinct-provider pairs). Precision (tp / (tp + fp) = 1.0000) is also computed
and included in the summary for visibility, not gated - it combines two
separately-sourced samples (the true-match cases and the mined
distinct-provider collisions), so like the ONC pairs tier's precision, it
isn't a real-world base rate.
"""

from __future__ import annotations

import csv
import glob
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from patient_matching.matching.field_extractor import FieldExtractor, PatientFields
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

from ._null_backend import NullBackend
from ._onc_test_set import REPO_ROOT, missing_fixture_data_reason

NPPES_FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "nppes"

# Regression guard for the recall side (see module docstring). Measured at
# 1.0000 (17,299/17,299 true-match cases, 0 false negatives) against the
# providers where rule 33's mandatory phone/ZIP fields were extractable - the
# floor leaves only enough headroom to not be a byte-exact pin (see
# docs/ONC_REGRESSION_TEST_DESIGN.md's "Alternatives Considered" for why exact
# pinning is avoided generally), not because a large drop is expected to be
# tolerable. FPR has no floor/ceiling - it's asserted at an exact zero, since
# a cross-provider false positive is a wrong-person record link, not a rate
# to tolerate a nonzero amount of.
RECALL_FLOOR = 0.99


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


def _transpose_variant(value: str) -> Optional[str]:
    """A single adjacent-character transposition - Damerau-Levenshtein
    distance exactly 1 from `value`. Returns None if no adjacent pair of
    distinct characters exists to swap (e.g. "AAAA") or `value` is too short
    for fuzzy matching to apply at all (CMS SS E.3, <5 chars)."""
    if len(value) < 5:
        return None
    chars = list(value)
    for i in range(len(chars) - 1):
        if chars[i] != chars[i + 1]:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
            return "".join(chars)
    return None


@pytest.mark.skipif(
    not NPPES_FIXTURES_DIR.exists() or not list(NPPES_FIXTURES_DIR.glob("*.csv")),
    reason=missing_fixture_data_reason(NPPES_FIXTURES_DIR),
)
def test_nppes_matching_recall_and_fpr() -> None:
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
    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        npi = row["NPI"]
        try:
            normalized = normalizer.normalize(_to_patient_shaped_dict(row))
            fields = extractor.extract(normalized)
        except Exception as exc:  # noqa: BLE001 - tally as a failure, not a crash
            errors.append(f"NPI {npi}: {exc!r}")
            continue
        provider_fields.append((npi, f"{row['First Name']} {row['Last Name']}", fields))
        normalized_rows.append(normalized)

    assert not errors, (
        f"{len(errors)}/{len(rows)} providers raised instead of extracting: "
        + "; ".join(errors[:10])
    )

    # --- Recall: exact duplicate + single-edit variants should all match ---
    tp = fn = 0
    recall_by_category: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fn": 0}
    )

    def _check_true_match(
        category: str, fields_a: PatientFields, fields_b: PatientFields
    ) -> None:
        nonlocal tp, fn
        if engine.evaluate_pair(fields_a, fields_b):
            tp += 1
            recall_by_category[category]["tp"] += 1
        else:
            fn += 1
            recall_by_category[category]["fn"] += 1

    not_applicable = {
        "missing_phone_or_zip": 0,
        "family_transpose": 0,
        "given_transpose": 0,
        "both_transpose": 0,
    }
    for (npi, _name, fields), normalized in zip(provider_fields, normalized_rows):
        # Rule 33 requires phone and ZIP as non-fuzzy, mandatory fields. A
        # provider whose practice phone didn't survive normalization (a
        # placeholder like "000-000-0000", or a non-US/APO number the phone
        # normalizer can't parse under its default US region) can't evaluate
        # under rule 33 at all - not even against an identical copy of
        # itself. That's a real, narrow limitation worth surfacing plainly
        # (see module docstring / design doc), not a matching bug to conflate
        # into recall by counting it as a false negative.
        if not fields.phones or not fields.zip_codes:
            not_applicable["missing_phone_or_zip"] += 1
            continue

        # Exact duplicate of the same record.
        _check_true_match("exact_duplicate", fields, fields)

        family = normalized["name"][0].get("family", "")
        given_list = normalized["name"][0].get("given") or []
        first_given = given_list[0] if given_list else ""

        family_variant = _transpose_variant(family)
        given_variant = _transpose_variant(first_given)

        if family_variant is not None:
            mutated = {
                **normalized,
                "name": [{**normalized["name"][0], "family": family_variant}],
            }
            mutated_fields = extractor.extract(mutated)
            _check_true_match("family_transpose", fields, mutated_fields)
        else:
            not_applicable["family_transpose"] += 1

        if given_variant is not None:
            mutated = {
                **normalized,
                "name": [
                    {**normalized["name"][0], "given": [given_variant, *given_list[1:]]}
                ],
            }
            mutated_fields = extractor.extract(mutated)
            _check_true_match("given_transpose", fields, mutated_fields)
        else:
            not_applicable["given_transpose"] += 1

        if family_variant is not None and given_variant is not None:
            mutated = {
                **normalized,
                "name": [
                    {
                        **normalized["name"][0],
                        "family": family_variant,
                        "given": [given_variant, *given_list[1:]],
                    }
                ],
            }
            mutated_fields = extractor.extract(mutated)
            _check_true_match("both_transpose", fields, mutated_fields)
        else:
            not_applicable["both_transpose"] += 1

    recall = tp / (tp + fn) if (tp + fn) else float("nan")

    # --- FPR: distinct real providers sharing (phone, zip) should never match ---
    blocks: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for idx, (_npi, _name, fields) in enumerate(provider_fields):
        for phone in fields.phones:
            for zip_code in fields.zip_codes:
                blocks[(phone, zip_code)].append(idx)

    false_positives: List[str] = []
    negative_pairs_evaluated = 0
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
                negative_pairs_evaluated += 1
                if engine.evaluate_pair(fields_a, fields_b):
                    false_positives.append(
                        f"NPI {npi_a} ({name_a}) matched NPI {npi_b} ({name_b}) "
                        f"via shared phone={phone!r} zip={zip_code!r}"
                    )

    fpr = (
        len(false_positives) / negative_pairs_evaluated
        if negative_pairs_evaluated
        else float("nan")
    )
    # Reported for visibility only, not gated: tp comes from the true-match
    # sample (exact duplicates/name variants) and fp from a separately-mined
    # true-non-match sample (distinct-provider collisions) - combining them
    # into one precision figure has the same "not a real base rate" caveat as
    # the ONC pairs tier's precision (see docs/ONC_REGRESSION_TEST_DESIGN.md).
    precision = (
        tp / (tp + len(false_positives))
        if (tp + len(false_positives))
        else float("nan")
    )

    breakdown = "\n".join(
        f"  {cat}: tp={c['tp']} fn={c['fn']}"
        for cat, c in sorted(recall_by_category.items())
    )
    summary = (
        f"n_providers={len(provider_fields)} tp={tp} fn={fn} recall={recall:.4f} "
        f"not_applicable={not_applicable}\nBy category:\n{breakdown}\n"
        f"blocks_with_multiple_providers={blocks_with_collisions} "
        f"negative_pairs_evaluated={negative_pairs_evaluated} fpr={fpr:.4f} "
        f"precision(not representative, see docstring)={precision:.4f}"
    )

    assert recall >= RECALL_FLOOR, f"Recall regressed below {RECALL_FLOOR}.\n{summary}"
    assert not false_positives, (
        f"Found {len(false_positives)} cross-provider false positive(s) - two "
        "genuinely distinct real practitioners (different NPI) were declared a "
        f"match.\n{summary}\n" + "\n".join(false_positives)
    )
