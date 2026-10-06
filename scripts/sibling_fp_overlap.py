"""Compare the engine's pairs-tier false positives against the cases a newer
test-set version removes.

Answers one question before a test-set pin bump: are the engine's
`sibling_negative` false positives on the currently pinned data the same pairs
the next test-set version drops as mislabeled (possibly the same person), or
do some survive - meaning a real engine gap remains after the bump?

Runs every pair in `--old` through the same normalize -> extract ->
`evaluate_pair` path as `tests/test_onc_regression.py`, using the same
category bucketing, then diffs case ids against `--new`. Pairs are keyed by
`case_id` (`<source id>::<target id>::<kind>`), which is stable across
test-set versions for pairs that are kept. Also reports overall pairs-tier
confusion on both files, so the effect of the bump on the recall floor and
FPR ceiling is visible before the pin moves.

Prints a JSON report to stdout. Analysis aid, not a test gate.

Usage:
    uv run python scripts/sibling_fp_overlap.py \\
        --old tests/fixtures/onc/sample_labeled_pairs.jsonl \\
        --new <path to the newer test-set's evaluation/cases/sample_labeled_pairs.jsonl>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from patient_matching.matching.backend import FieldCriterion, MatchingBackend
from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

Case = Dict[str, Any]
Predict = Callable[[Case], bool]

DEFAULT_CATEGORY = "sibling_negative"


def _category(case: Case) -> str:
    # Same bucketing as tests/test_onc_regression.py.
    category: str = case["rationale"].split("/")[0].split(" ")[0]
    return category


def load_pairs(path: Path) -> List[Case]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def false_positive_ids(pairs: List[Case], predict: Predict, category: str) -> Set[str]:
    """Case ids in `category` labeled non-match that `predict` links anyway."""
    return {
        case["case_id"]
        for case in pairs
        if _category(case) == category and not case["expected_match"] and predict(case)
    }


def overlap_report(
    fp_ids: Set[str], old_ids: Set[str], new_ids: Set[str]
) -> Dict[str, List[str]]:
    """Split false positives by whether the new version removes their case.

    `fp_kept` is the number that matters: false positives the new version
    still labels non-match, i.e. what the pin bump leaves unresolved.
    """
    removed = old_ids - new_ids
    return {
        "false_positives": sorted(fp_ids),
        "removed": sorted(removed),
        "fp_removed": sorted(fp_ids & removed),
        "fp_kept": sorted(fp_ids - removed),
        "removed_not_fp": sorted(removed - fp_ids),
    }


def confusion(pairs: List[Case], predict: Predict) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    for case in pairs:
        predicted, actual = predict(case), case["expected_match"]
        if predicted and actual:
            tp += 1
        elif predicted:
            fp += 1
        elif actual:
            fn += 1
        else:
            tn += 1
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
        "fpr": fp / (fp + tn) if (fp + tn) else float("nan"),
    }


class _NoSearchBackend(MatchingBackend):
    """`evaluate_pair()` never searches, but the engine requires a backend."""

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []


def engine_predict() -> Predict:
    """Pairwise decision via the same path as tests/test_onc_regression.py."""
    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    engine = MatchingEngine(backend=_NoSearchBackend())

    def predict(case: Case) -> bool:
        source = extractor.extract(normalizer.normalize(case["source"]))
        target = extractor.extract(normalizer.normalize(case["target"]))
        return bool(engine.evaluate_pair(source, target))

    return predict


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--category", default=DEFAULT_CATEGORY)
    args = parser.parse_args(argv)

    old_pairs, new_pairs = load_pairs(args.old), load_pairs(args.new)
    predict = engine_predict()

    def ids_in_category(pairs: List[Case]) -> Set[str]:
        return {c["case_id"] for c in pairs if _category(c) == args.category}

    report: Dict[str, Any] = {
        "category": args.category,
        **overlap_report(
            false_positive_ids(old_pairs, predict, args.category),
            ids_in_category(old_pairs),
            ids_in_category(new_pairs),
        ),
        "old_confusion": confusion(old_pairs, predict),
        "new_confusion": confusion(new_pairs, predict),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
