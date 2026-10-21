"""Per-record disagreement report: CMS Table 2 engine vs `helix.personmatching`.

`evaluation/legacy_comparison.py` prints aggregate counts per matcher, so it cannot say
*which* cases the two matchers disagree on. This script runs both matchers over the same
labeled cases and records one row per case: what was expected, what each matcher said,
and who was right.

Each matcher is a `Side(prepare, match)` pair injected into the comparators, the same
pattern as `score_test_set.py`, so the comparison logic is tested with toy matchers and
only the adapters in this module import `patient_matching` / `helix_personmatching`.

Not part of the shippable `patient_matching` package and not run by CI.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Sequence

from z_scripts.score_test_set import _bucket


@dataclass(frozen=True)
class Verdict:
    """One matcher's answer for one pair. `score` and `rule` are informational."""

    matched: bool
    score: float = 0.0
    rule: str = ""


@dataclass(frozen=True)
class Side:
    """One matcher: `prepare(patient) -> fields`, `match(a, b) -> Verdict`."""

    prepare: Callable[[Dict[str, Any]], Any]
    match: Callable[[Any, Any], Verdict]


@dataclass(frozen=True)
class DisagreementRow:
    tier: str
    case_id: str
    category: str
    expected: bool
    engine_pred: bool
    helix_pred: bool
    bucket: str
    helix_score: float
    helix_rule: str


# Ids, category and verdicts only. Never patient fields.
CSV_COLUMNS: tuple[str, ...] = (
    "tier",
    "case_id",
    "category",
    "expected",
    "engine_pred",
    "helix_pred",
    "bucket",
    "helix_score",
    "helix_rule",
)


def classify(expected: bool, engine_pred: bool, helix_pred: bool) -> str:
    engine_right = engine_pred == expected
    helix_right = helix_pred == expected
    if engine_right and helix_right:
        return "both_right"
    if engine_right:
        return "engine_only_right"
    if helix_right:
        return "helix_only_right"
    return "both_wrong"


def summarize(rows: Sequence[DisagreementRow]) -> Dict[str, Dict[str, int]]:
    """Category -> {bucket: count}."""
    by_category: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        by_category[row.category][row.bucket] += 1
    return {cat: dict(buckets) for cat, buckets in by_category.items()}


def confusion(
    rows: Sequence[DisagreementRow], who: Literal["engine", "helix"]
) -> Dict[str, int]:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for row in rows:
        predicted = row.engine_pred if who == "engine" else row.helix_pred
        counts[_bucket(predicted, row.expected)] += 1
    return counts


def write_csv(rows: Sequence[DisagreementRow], path: Path) -> int:
    """Write every row where at least one matcher is wrong; return how many."""
    written = 0
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            if row.bucket == "both_right":
                continue
            writer.writerow(asdict(row))
            written += 1
    return written
