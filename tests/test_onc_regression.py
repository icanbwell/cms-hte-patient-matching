"""ONC-dataset regression test for the CMS Table 2 matching engine.

Mirrors what `helix.personmatching`'s `tests/cms_dataset/test_cms_dataset.py`
does for the legacy scoring engine: run every labeled pair from a real,
publicly-sourced dataset through the engine and check recall/false-positive
rate haven't regressed.

Data source: the ONC 2017 Patient Matching Algorithm Challenge dataset (public,
synthetic, non-PHI), as mutated/mined into labeled pairs by the
`cms-hte-patient-matching-test-set` repo - see `tests/fixtures/onc/README.md`
for exactly which files were vendored, from where, and how to refresh them.
The data is vendored (copied) into `tests/fixtures/onc/` rather than read live
from that repo, so this test runs standalone - no second repo needs to be
checked out alongside this one, including in CI.

Only recall and FPR are asserted here, not precision - `sample_labeled_pairs.jsonl`
deliberately over-samples rare/high-risk categories (twins, institutional
addresses) for statistical power, so it isn't a representative sample and a
precision number computed over it has no real-world interpretation (see the
sibling repo's `evaluation/cases/README.md`, "Frequency and real-world
representativeness"). Computing precision/F1/accuracy would require the
population-query tier instead.

The floor/ceiling below are regression guards, not a re-derivation of the
sibling repo's own `evaluation/baselines/v3_2_2_onc_baseline.txt` - that
baseline was computed with 26 rules over a much larger (~2M-pair) generated
set; this engine currently ships 30 approved rules (Category 1) + 8
household/individual rules (Category 2), evaluated here over the smaller,
committed `sample_labeled_pairs.jsonl` (6,290 pairs). Measured on that file
with the current rule set: recall=0.9710, FPR=0.0069. The floor/ceiling give
headroom for legitimate improvement while catching a real regression - a false
positive here is a wrong-patient record link, the critical error this whole
engine exists to avoid, so the FPR ceiling is intentionally tight.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import pytest

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

from ._onc_test_set import ONC_CASES_DIR, NullBackend, missing_fixture_data_reason

ONC_PAIRS_PATH = ONC_CASES_DIR / "sample_labeled_pairs.jsonl"

# Regression guards (see module docstring for the measured values these
# leave headroom around). Update deliberately - with a note of why - if a
# rule change intentionally moves these.
RECALL_FLOOR = 0.95
FPR_CEILING = 0.01


def _load_pairs(path: Path) -> List[Dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f]


@pytest.mark.skipif(
    not ONC_PAIRS_PATH.exists(), reason=missing_fixture_data_reason(ONC_PAIRS_PATH)
)
def test_onc_labeled_pairs_recall_and_fpr() -> None:
    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    engine = MatchingEngine(backend=NullBackend())

    pairs = _load_pairs(ONC_PAIRS_PATH)
    assert pairs, f"{ONC_PAIRS_PATH} is empty"

    tp = fp = tn = fn = 0
    errors: List[str] = []
    by_category: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    )

    for case in pairs:
        case_id = case["case_id"]
        category = case["rationale"].split("/")[0].split(" ")[0]
        try:
            source_fields = extractor.extract(normalizer.normalize(case["source"]))
            target_fields = extractor.extract(normalizer.normalize(case["target"]))
            predicted_match = engine.evaluate_pair(source_fields, target_fields)
        except Exception as exc:  # noqa: BLE001 - tally as a failure, not a crash
            errors.append(f"{case_id}: {exc!r}")
            continue

        actual_match = case["expected_match"]
        if predicted_match and actual_match:
            bucket = "tp"
        elif predicted_match and not actual_match:
            bucket = "fp"
        elif not predicted_match and actual_match:
            bucket = "fn"
        else:
            bucket = "tn"

        by_category[category][bucket] += 1
        if bucket == "tp":
            tp += 1
        elif bucket == "fp":
            fp += 1
        elif bucket == "fn":
            fn += 1
        else:
            tn += 1

    # Per the sibling repo's Option A guidance: never silently skip cases and
    # report metrics only over what succeeded - a raised exception on any
    # case is itself a bug worth surfacing, not a case to drop.
    assert not errors, (
        f"{len(errors)}/{len(pairs)} pairs raised instead of evaluating: "
        + "; ".join(errors[:10])
    )

    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    fpr = fp / (fp + tn) if (fp + tn) else float("nan")

    breakdown = "\n".join(
        f"  {cat}: tp={c['tp']} fp={c['fp']} tn={c['tn']} fn={c['fn']}"
        for cat, c in sorted(by_category.items())
    )
    summary = (
        f"n={len(pairs)} tp={tp} fp={fp} tn={tn} fn={fn} "
        f"recall={recall:.4f} fpr={fpr:.4f}\nBy rationale category:\n{breakdown}"
    )

    assert recall >= RECALL_FLOOR, f"Recall regressed below {RECALL_FLOOR}.\n{summary}"
    assert fpr <= FPR_CEILING, (
        f"FPR regressed above {FPR_CEILING} - a false positive here is a "
        f"wrong-patient record link.\n{summary}"
    )
