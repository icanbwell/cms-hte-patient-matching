"""ONC population-query regression test for the CMS Table 2 matching engine.

Companion to `test_onc_regression.py`, which only asserts recall/FPR because
its data source (the per-provision pairs tier) deliberately over-samples
rare/high-risk categories and so isn't representative. This test uses the
*population-query* tier instead: one query patient against a realistic
~40-candidate pool (a real duplicate cluster mixed into mostly-random
distractors), which is naturally representative - see
`cms-hte-patient-matching-test-set`'s `evaluation/cases/README.md`, "Option B:
computing precision/FDR/F1/accuracy over the population tier." That's what
makes precision/F1/accuracy valid to assert here, unlike in the pairs test.

Mirrors what `helix.personmatching`'s `tests/cms_dataset/test_cms_performance.py`
does for the legacy scoring engine (matching a masked query against the rest
of the population), but uses that repo's pre-built candidate pools (with real
mined/constructed non-matches) rather than self-matching an unmasked baseline.

Data is vendored into `tests/fixtures/onc/` (see that directory's README.md
for provenance and how to refresh it) rather than read live from the
`cms-hte-patient-matching-test-set` repo, so this test runs standalone - no
second repo needs to be checked out alongside this one, including in CI.

Every (query, candidate) pair in every pool is flattened into one confusion
matrix, per that repo's Option B. Measured on the current dataset
(2,000 queries, 8,016 unique candidates, 80,000 query-candidate evaluations)
with the current rule set (30 Category 1 rules + 8 household rules):
precision=0.9990, recall=0.9710, FPR=0.0001, accuracy=0.9978, F1=0.9848, 0
extraction errors. The floors/ceiling below leave headroom above/below those
measured values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from patient_matching.matching.field_extractor import FieldExtractor, PatientFields
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

from ._onc_test_set import ONC_CASES_DIR, NullBackend, missing_fixture_data_reason

POPULATION_QUERIES_PATH = ONC_CASES_DIR / "population_queries.jsonl"
POPULATION_CANDIDATES_PATH = ONC_CASES_DIR / "population_candidates.jsonl"

# Regression guards (see module docstring for the measured values these
# leave headroom around). Update deliberately - with a note of why - if a
# rule change intentionally moves these.
PRECISION_FLOOR = 0.99
RECALL_FLOOR = 0.95
FPR_CEILING = 0.001
F1_FLOOR = 0.97


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f]


@pytest.mark.skipif(
    not (POPULATION_QUERIES_PATH.exists() and POPULATION_CANDIDATES_PATH.exists()),
    reason=missing_fixture_data_reason(POPULATION_QUERIES_PATH),
)
def test_onc_population_precision_recall_fpr_f1() -> None:
    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    engine = MatchingEngine(backend=NullBackend())

    candidates = _load_jsonl(POPULATION_CANDIDATES_PATH)
    queries = _load_jsonl(POPULATION_QUERIES_PATH)
    assert candidates, f"{POPULATION_CANDIDATES_PATH} is empty"
    assert queries, f"{POPULATION_QUERIES_PATH} is empty"

    errors: List[str] = []

    # Each candidate is shared across multiple queries' pools - normalize and
    # extract once per candidate rather than once per (query, candidate) pair.
    candidate_fields: Dict[str, PatientFields] = {}
    for candidate in candidates:
        candidate_id = candidate["id"]
        try:
            candidate_fields[candidate_id] = extractor.extract(
                normalizer.normalize(candidate["patient"])
            )
        except Exception as exc:  # noqa: BLE001 - tally as a failure, not a crash
            errors.append(f"candidate {candidate_id}: {exc!r}")

    tp = fp = tn = fn = 0
    n_evals = 0

    for query_case in queries:
        query_id = query_case["query_id"]
        try:
            query_fields = extractor.extract(normalizer.normalize(query_case["query"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"query {query_id}: {exc!r}")
            continue

        expected = set(query_case["expected_match_ids"])
        for candidate_id in query_case["candidate_ids"]:
            if candidate_id not in candidate_fields:
                errors.append(
                    f"query {query_id}: candidate {candidate_id} missing extracted "
                    "fields (failed earlier or absent from candidates file)"
                )
                continue
            n_evals += 1
            try:
                predicted_match = engine.evaluate_pair(
                    query_fields, candidate_fields[candidate_id]
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"query {query_id} x candidate {candidate_id}: {exc!r}")
                continue

            actual_match = candidate_id in expected
            if predicted_match and actual_match:
                tp += 1
            elif predicted_match and not actual_match:
                fp += 1
            elif not predicted_match and actual_match:
                fn += 1
            else:
                tn += 1

    # Per the sibling repo's Option B guidance: report (and here, gate on) how
    # many query-candidate evaluations actually succeeded vs. errored, rather
    # than silently reporting metrics only over what worked.
    assert not errors, (
        f"{len(errors)} query/candidate evaluations raised instead of "
        f"evaluating: " + "; ".join(errors[:10])
    )

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    fpr = fp / (fp + tn) if (fp + tn) else float("nan")
    accuracy = (tp + tn) / n_evals if n_evals else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else float("nan")
    )

    summary = (
        f"n_queries={len(queries)} n_candidates={len(candidates)} n_evals={n_evals} "
        f"tp={tp} fp={fp} tn={tn} fn={fn}\n"
        f"precision={precision:.4f} recall={recall:.4f} fpr={fpr:.4f} "
        f"accuracy={accuracy:.4f} f1={f1:.4f}"
    )

    assert precision >= PRECISION_FLOOR, (
        f"Precision regressed below {PRECISION_FLOOR}.\n{summary}"
    )
    assert recall >= RECALL_FLOOR, f"Recall regressed below {RECALL_FLOOR}.\n{summary}"
    assert fpr <= FPR_CEILING, (
        f"FPR regressed above {FPR_CEILING} - a false positive here is a "
        f"wrong-patient record link.\n{summary}"
    )
    assert f1 >= F1_FLOOR, f"F1 regressed below {F1_FLOOR}.\n{summary}"
