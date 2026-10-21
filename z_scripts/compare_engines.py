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

import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence

from z_scripts.score_test_set import TIER_FILES, _bucket, _engine, _load


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


# --- real matchers ----------------------------------------------------------------


def engine_side() -> Side:
    """The CMS Table 2 engine, via the same normalize -> extract -> evaluate_pair path
    as `score_test_set.py`."""
    prepare, match = _engine()
    return Side(prepare=prepare, match=lambda a, b: Verdict(matched=bool(match(a, b))))


def _is_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == ""


def _strip_empty_strings(obj: Any) -> Any:
    """Recursively drop empty/whitespace-only strings. FHIR's `string` type needs at
    least one non-whitespace character, but a few ONC-derived records have an empty
    city/state/given value. Used only as a fallback when strict parsing fails.
    (Copied from `evaluation/legacy_comparison.py`, a non-package script.)"""
    if isinstance(obj, dict):
        return {
            k: _strip_empty_strings(v) for k, v in obj.items() if not _is_empty_str(v)
        }
    if isinstance(obj, list):
        cleaned = [_strip_empty_strings(v) for v in obj]
        return [v for v in cleaned if not _is_empty_str(v)]
    return obj


def _build_helix_side(matcher: Any, patient_cls: Any) -> Side:
    """Wrap a helix `Matcher` as a `Side`. Split from `make_helix_side` so tests can
    inject a fake matcher without importing helix."""

    def prepare(raw: Dict[str, Any]) -> Any:
        # helix pins fhir.resources<8, which only has the pydantic-v1 `parse_obj`.
        try:
            return patient_cls.parse_obj(raw)
        except Exception:  # noqa: BLE001 - retry once with empty strings dropped
            return patient_cls.parse_obj(_strip_empty_strings(raw))

    def match(source: Any, target: Any) -> Verdict:
        results = matcher.match_resources(source=source, target=target)
        if not results:
            return Verdict(False, 0.0, "")
        top = max(results, key=lambda r: r.total_score)
        best_rule = max(top.rule_scores, key=lambda r: r.rule_score, default=None)
        return Verdict(
            matched=any(r.matched for r in results),
            score=top.total_score,
            rule=best_rule.rule_name if best_rule else "",
        )

    return Side(prepare=prepare, match=match)


def make_helix_side(helix_repo: Path) -> Side:
    """helix.personmatching at `helix_repo` (a checkout or `git archive` of one).
    Imported lazily: helix is an eval-only dependency, never a dependency of the package."""
    sys.path.insert(0, str(helix_repo))
    from fhir.resources.R4B.patient import Patient
    from helix_personmatching.matchers.matcher import Matcher  # type: ignore[import-not-found]

    return _build_helix_side(Matcher(), Patient)


def with_threshold(side: Side, threshold: float) -> Side:
    """Re-decide `matched` as `score >= threshold`, keeping the score and rule.

    The library flags a match at 0.955; a caller with a different cut-off (the match service
    uses 0.9555) is scored by re-thresholding the same score, not by re-running the matcher."""

    def match(a: Any, b: Any) -> Verdict:
        verdict = side.match(a, b)
        return Verdict(
            matched=verdict.score >= threshold, score=verdict.score, rule=verdict.rule
        )

    return Side(prepare=side.prepare, match=match)


# --- run one tier + CLI -----------------------------------------------------------


def _confusion_line(label: str, counts: Dict[str, int]) -> str:
    return (
        f"  {label:<7}tp={counts['tp']} fp={counts['fp']} "
        f"tn={counts['tn']} fn={counts['fn']}"
    )


def _report_section(name: str, result: ComparisonResult) -> List[str]:
    lines = [
        f"== {name}: n={len(result.rows)} errors={len(result.errors)}",
        _confusion_line("engine", confusion(result.rows, "engine")),
        _confusion_line("helix", confusion(result.rows, "helix")),
        "  by category (bucket=count):",
    ]
    for category, buckets in sorted(summarize(result.rows).items()):
        counts = " ".join(f"{b}={n}" for b, n in sorted(buckets.items()))
        lines.append(f"    {category}: {counts}")
    lines.extend(f"  error: {e}" for e in result.errors[:5])
    return lines


def run_tier(
    cases_dir: Path, tier: str, engine: Side, helix: Side, out_dir: Path
) -> str:
    """Compare both matchers on one tier's pairs and population files; write
    `pairs_<tier>.csv` and `population_<tier>.csv` into `out_dir`; return the report."""
    pairs_name, queries_name, candidates_name = TIER_FILES[tier]
    pairs = compare_pairs(_load(cases_dir / f"{pairs_name}.jsonl"), engine, helix, tier)
    population = compare_population(
        _load(cases_dir / f"{queries_name}.jsonl"),
        _load(cases_dir / f"{candidates_name}.jsonl"),
        engine,
        helix,
        tier,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(pairs.rows, out_dir / f"pairs_{tier}.csv")
    write_csv(population.rows, out_dir / f"population_{tier}.csv")
    return "\n".join(
        [
            *_report_section(f"{tier}/pairs", pairs),
            *_report_section(f"{tier}/population", population),
        ]
    )


def _helix_label(helix_repo: Path) -> str:
    try:
        described = subprocess.run(
            ["git", "-C", str(helix_repo), "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        version = described.stdout.strip() if described.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        version = ""
    return f"{helix_repo} ({version or 'no git metadata'})"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases-dir", type=Path, required=True)
    parser.add_argument("--tier", choices=sorted(TIER_FILES), required=True)
    parser.add_argument("--helix-repo", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--helix-threshold",
        type=float,
        default=None,
        help="re-decide helix matches at this score (default: the library's own 0.955)",
    )
    args = parser.parse_args(argv)
    if not args.helix_repo.exists():
        parser.error(f"helix.personmatching not found at {args.helix_repo}")

    helix = make_helix_side(args.helix_repo)
    threshold_note = "library default (0.955)"
    if args.helix_threshold is not None:
        helix = with_threshold(helix, args.helix_threshold)
        threshold_note = str(args.helix_threshold)
    print(f"helix: {_helix_label(args.helix_repo)}, match threshold {threshold_note}")
    print(run_tier(args.cases_dir, args.tier, engine_side(), helix, args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
