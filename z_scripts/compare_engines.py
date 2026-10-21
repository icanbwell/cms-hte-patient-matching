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
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence

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


@dataclass(frozen=True)
class ComparisonResult:
    rows: List[DisagreementRow]
    errors: List[str]


def _category(rationale: Optional[str]) -> str:
    """Top-level rationale category, e.g. `fuzzy_variant/given_nickname` -> `fuzzy_variant`."""
    return (rationale or "").split("/")[0].split(" ")[0] or "unknown"


def _make_row(
    tier: str,
    case_id: str,
    category: str,
    expected: bool,
    engine_verdict: Verdict,
    helix_verdict: Verdict,
) -> DisagreementRow:
    return DisagreementRow(
        tier=tier,
        case_id=case_id,
        category=category,
        expected=expected,
        engine_pred=engine_verdict.matched,
        helix_pred=helix_verdict.matched,
        bucket=classify(expected, engine_verdict.matched, helix_verdict.matched),
        helix_score=helix_verdict.score,
        helix_rule=helix_verdict.rule,
    )


def compare_pairs(
    cases: Sequence[Dict[str, Any]], engine: Side, helix: Side, tier: str
) -> ComparisonResult:
    """Pairs tier: one (source, target, expected_match) per case."""
    rows: List[DisagreementRow] = []
    errors: List[str] = []
    for case in cases:
        try:
            engine_verdict = engine.match(
                engine.prepare(case["source"]), engine.prepare(case["target"])
            )
            helix_verdict = helix.match(
                helix.prepare(case["source"]), helix.prepare(case["target"])
            )
        except Exception as exc:  # noqa: BLE001 - tally, don't crash
            errors.append(f"{case['case_id']}: {exc!r}")
            continue
        rows.append(
            _make_row(
                tier,
                case["case_id"],
                _category(case.get("rationale")),
                bool(case["expected_match"]),
                engine_verdict,
                helix_verdict,
            )
        )
    return ComparisonResult(rows, errors)


def compare_population(
    queries: Sequence[Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
    engine: Side,
    helix: Side,
    tier: str,
) -> ComparisonResult:
    """Population tier: every (query, candidate) pair in every query's pool."""
    rows: List[DisagreementRow] = []
    errors: List[str] = []
    engine_fields: Dict[str, Any] = {}
    helix_fields: Dict[str, Any] = {}
    unusable: set[str] = set()  # failed to prepare; already reported once below
    for cand in candidates:
        try:
            prepared = (engine.prepare(cand["patient"]), helix.prepare(cand["patient"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"candidate {cand['id']}: {exc!r}")
            unusable.add(cand["id"])
            continue
        engine_fields[cand["id"]], helix_fields[cand["id"]] = prepared

    for query in queries:
        query_id = query["query_id"]
        try:
            engine_query = engine.prepare(query["query"])
            helix_query = helix.prepare(query["query"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"query {query_id}: {exc!r}")
            continue
        expected_ids = set(query["expected_match_ids"])
        category = _category(query.get("rationale"))
        for candidate_id in query["candidate_ids"]:
            if candidate_id in unusable:
                continue
            case_id = f"{query_id}x{candidate_id}"
            if candidate_id not in engine_fields:
                errors.append(f"{case_id}: missing candidate {candidate_id}")
                continue
            try:
                engine_verdict = engine.match(engine_query, engine_fields[candidate_id])
                helix_verdict = helix.match(helix_query, helix_fields[candidate_id])
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{case_id}: {exc!r}")
                continue
            rows.append(
                _make_row(
                    tier,
                    case_id,
                    category,
                    candidate_id in expected_ids,
                    engine_verdict,
                    helix_verdict,
                )
            )
    return ComparisonResult(rows, errors)
