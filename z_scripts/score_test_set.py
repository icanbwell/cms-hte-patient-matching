"""Score the Table 2 engine against one snapshot of cms-hte-patient-matching-test-set.

Same pipeline and confusion-matrix rules as tests/test_onc_regression.py (pairs tier)
and tests/test_onc_population_regression.py (population tier), pointed at any
directory of case files, with per-category breakdowns added. Used for BAI-1167
(before/after accuracy across test-set versions).

    PYTHONPATH=. python z_scripts/score_test_set.py --cases-dir DIR --tier curated --out m.json

`--tier curated` reads sample_labeled_pairs / population_{queries,candidates};
`--tier realistic` reads the realistic_* files.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List

Prepare = Callable[[Dict[str, Any]], Any]
Match = Callable[[Any, Any], bool]

TIER_FILES = {
    "curated": ("sample_labeled_pairs", "population_queries", "population_candidates"),
    "realistic": (
        "realistic_labeled_pairs",
        "realistic_population_queries",
        "realistic_population_candidates",
    ),
}


def _bucket(predicted: bool, actual: bool) -> str:
    if predicted:
        return "tp" if actual else "fp"
    return "fn" if actual else "tn"


def _empty() -> Dict[str, int]:
    return {"tp": 0, "fp": 0, "tn": 0, "fn": 0}


def _rates(c: Dict[str, int]) -> Dict[str, float]:
    tp, fp, tn, fn = c["tp"], c["fp"], c["tn"], c["fn"]
    nan = float("nan")
    precision = tp / (tp + fp) if tp + fp else nan
    recall = tp / (tp + fn) if tp + fn else nan
    return {
        "precision": precision,
        "recall": recall,
        "fpr": fp / (fp + tn) if fp + tn else nan,
        "f1": 2 * precision * recall / (precision + recall)
        if tp and (precision + recall)
        else (0.0 if tp + fp + fn else nan),
    }


def score_pairs(
    rows: List[Dict[str, Any]], prepare: Prepare, match: Match
) -> Dict[str, Any]:
    """Pairs tier: one (source, target, expected_match) per row."""
    total = _empty()
    by_category: Dict[str, Dict[str, int]] = defaultdict(_empty)
    by_subcategory: Dict[str, Dict[str, int]] = defaultdict(_empty)
    errors: List[str] = []
    fp_cases: List[Dict[str, str]] = []
    for case in rows:
        try:
            predicted = bool(match(prepare(case["source"]), prepare(case["target"])))
        except Exception as exc:  # noqa: BLE001 - tally, don't crash (same as the regression test)
            errors.append(f"{case['case_id']}: {exc!r}")
            continue
        b = _bucket(predicted, bool(case["expected_match"]))
        parts = case["rationale"].split("/")
        category = parts[0].split(" ")[0]
        sub = "/".join(parts[:2]).split(" ")[0]
        if b == "fp":
            fp_cases.append(
                {"case_id": case["case_id"], "rationale": case["rationale"]}
            )
        total[b] += 1
        by_category[category][b] += 1
        by_subcategory[sub][b] += 1
    return {
        "n": len(rows),
        **total,
        **_rates(total),
        "errors": errors,
        "fp_cases": fp_cases,
        "by_category": {k: dict(v) for k, v in sorted(by_category.items())},
        "by_subcategory": {k: dict(v) for k, v in sorted(by_subcategory.items())},
    }


def score_population(
    queries: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    prepare: Prepare,
    match: Match,
) -> Dict[str, Any]:
    """Population tier: every (query, candidate) in every pool, one confusion matrix."""
    errors: List[str] = []
    fields: Dict[str, Any] = {}
    for cand in candidates:
        try:
            fields[cand["id"]] = prepare(cand["patient"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"candidate {cand['id']}: {exc!r}")
    total = _empty()
    by_match_count: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {**_empty(), "queries": 0}
    )
    n_evals = 0
    fp_cases: List[Dict[str, str]] = []
    for q in queries:
        expected = set(q["expected_match_ids"])
        n = len(expected)
        key = str(n) if n < 2 else "2+"
        by_match_count[key]["queries"] += 1
        try:
            qf = prepare(q["query"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"query {q['query_id']}: {exc!r}")
            continue
        for cid in q["candidate_ids"]:
            if cid not in fields:
                errors.append(f"query {q['query_id']}: candidate {cid} missing")
                continue
            n_evals += 1
            try:
                predicted = bool(match(qf, fields[cid]))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"query {q['query_id']} x {cid}: {exc!r}")
                continue
            b = _bucket(predicted, cid in expected)
            if b == "fp":
                fp_cases.append(
                    {
                        "query_id": q["query_id"],
                        "candidate_id": cid,
                        "rationale": q["rationale"],
                    }
                )
            total[b] += 1
            by_match_count[key][b] += 1
    return {
        "n_queries": len(queries),
        "n_candidates": len(candidates),
        "n_evals": n_evals,
        **total,
        **_rates(total),
        "accuracy": (total["tp"] + total["tn"]) / n_evals if n_evals else float("nan"),
        "errors": errors,
        "fp_cases": fp_cases,
        "by_match_count": {k: dict(v) for k, v in sorted(by_match_count.items())},
    }


def _load(path: Path) -> List[Dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _engine() -> tuple[Prepare, Match]:
    from patient_matching.matching.field_extractor import FieldExtractor
    from patient_matching.matching.matching_engine import MatchingEngine
    from patient_matching.normalization.manager import NormalizationManager
    from tests._null_backend import NullBackend

    normalizer, extractor = NormalizationManager(), FieldExtractor()
    engine = MatchingEngine(backend=NullBackend())
    return (lambda p: extractor.extract(normalizer.normalize(p))), engine.evaluate_pair


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-dir", type=Path, required=True)
    ap.add_argument("--tier", choices=sorted(TIER_FILES), required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--limit", type=int, default=0, help="first N pair rows / queries (smoke test)"
    )
    args = ap.parse_args()

    pairs_name, queries_name, cands_name = TIER_FILES[args.tier]
    pairs = _load(args.cases_dir / f"{pairs_name}.jsonl")
    queries = _load(args.cases_dir / f"{queries_name}.jsonl")
    if args.limit:
        pairs, queries = pairs[: args.limit], queries[: args.limit]
    candidates = _load(args.cases_dir / f"{cands_name}.jsonl")
    if args.limit:
        wanted = {c for q in queries for c in q["candidate_ids"]}
        candidates = [c for c in candidates if c["id"] in wanted]

    prepare, match = _engine()
    result = {
        "pairs": score_pairs(pairs, prepare, match),
        "population": score_population(queries, candidates, prepare, match),
    }
    args.out.write_text(json.dumps(result, indent=2, default=str))
    for tier, m in result.items():
        print(
            f"{args.tier}/{tier}: tp={m['tp']} fp={m['fp']} tn={m['tn']} fn={m['fn']} "
            f"recall={m['recall']:.4f} fpr={m['fpr']:.5f} precision={m['precision']:.4f} "
            f"f1={m['f1']:.4f} errors={len(m['errors'])}"
        )


if __name__ == "__main__":
    main()
