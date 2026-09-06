#!/usr/bin/env python3
"""Compare this repo's Table 2 engine against `helix.personmatching`'s legacy
weighted-score engine, on the exact same vendored ONC-derived data this
repo's own tests use (`tests/fixtures/onc/`) - same pairs, same ground truth,
same confusion-matrix definition. Only the algorithm differs.

Background and the first run's full results/interpretation:
`docs/ONC_REGRESSION_TEST_DESIGN.md`, "Comparison to helix.personmatching".

Not part of the shippable `patient_matching` package, and not run by pytest
or CI - same treatment as the sibling `cms-hte-patient-matching-test-set`
repo's `evaluation/rule_eval.py` ("intentionally not a dependency of the
shippable patient_matching package"). This script additionally needs
`helix.personmatching` cloned as a sibling repo, since it imports that
engine directly - the same eval-only cross-repo dependency
`docs/PROJECT_MAP.md` §4 flags as an explicit, deliberate decision (there, in
the context of session 8's planned legacy-comparison report). Running this
script is that decision exercised, not a hidden default - it does nothing
unless invoked directly.

Setup (one-time, separate from `uv sync` - these are helix.personmatching's
dependencies, not this repo's):

    pip install "fhir.resources>=8.3.0,<9" "fhir-core>=1.1.9,<2" nominally \
        python-crfsuite requests rapidfuzz usaddress usaddress-scourgify \
        phonenumbers phonetics nicknames

Usage:

    python evaluation/legacy_comparison.py
    python evaluation/legacy_comparison.py --tier pairs
    python evaluation/legacy_comparison.py --tier population
    python evaluation/legacy_comparison.py --helix-repo /path/to/helix.personmatching
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
ONC_CASES_DIR = REPO_ROOT / "tests" / "fixtures" / "onc"
DEFAULT_HELIX_REPO = REPO_ROOT.parent / "helix.personmatching"


class _NullBackend:
    """No-op backend for this repo's MatchingEngine - evaluate_pair() never
    calls it, but the constructor requires a backend instance. Duplicated
    (not imported) from tests/_null_backend.py - this script lives in
    evaluation/, deliberately outside the test suite's own package."""

    def search(self, criteria: List[Any]) -> List[Dict[str, Any]]:
        return []


def _is_empty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() == ""


def _strip_empty_strings(obj: Any) -> Any:
    """Recursively drop empty/whitespace-only strings - FHIR's `string` type
    requires >=1 non-whitespace character, but a handful of ONC-derived
    records have an empty city/state/given value. Used only as a fallback
    when strict validation fails."""
    if isinstance(obj, dict):
        return {
            k: _strip_empty_strings(v) for k, v in obj.items() if not _is_empty_str(v)
        }
    if isinstance(obj, list):
        cleaned = [_strip_empty_strings(v) for v in obj]
        return [v for v in cleaned if not _is_empty_str(v)]
    return obj


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def _confusion_metrics(tp: int, fp: int, tn: int, fn: int) -> Dict[str, float]:
    return {
        "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
        "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        "fpr": fp / (fp + tn) if (fp + tn) else float("nan"),
    }


def _print_report(
    engine_name: str,
    tier: str,
    n: int,
    tp: int,
    fp: int,
    tn: int,
    fn: int,
    errors: List[str],
) -> None:
    m = _confusion_metrics(tp, fp, tn, fn)
    print(f"\n--- {engine_name} / {tier} ---")
    print(f"n={n} tp={tp} fp={fp} tn={tn} fn={fn} errors={len(errors)}")
    print(f"recall={m['recall']:.4f} precision={m['precision']:.4f} fpr={m['fpr']:.4f}")
    if errors:
        print(f"first errors ({len(errors)} total):")
        for e in errors[:5]:
            print(f"  {e}")


# --- This repo's engine -----------------------------------------------------


def run_our_engine_pairs(pairs: List[Dict[str, Any]]) -> None:
    from patient_matching.matching.field_extractor import FieldExtractor
    from patient_matching.matching.matching_engine import MatchingEngine
    from patient_matching.normalization.manager import NormalizationManager

    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    engine = MatchingEngine(backend=_NullBackend())  # type: ignore[arg-type]

    tp = fp = tn = fn = 0
    errors: List[str] = []
    by_cat: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    )

    for case in pairs:
        category = case["rationale"].split("/")[0].split(" ")[0]
        try:
            sf = extractor.extract(normalizer.normalize(case["source"]))
            tf = extractor.extract(normalizer.normalize(case["target"]))
            predicted = engine.evaluate_pair(sf, tf)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{case['case_id']}: {exc!r}")
            continue
        actual = case["expected_match"]
        bucket = (
            "tp"
            if predicted and actual
            else "fp"
            if predicted
            else "fn"
            if actual
            else "tn"
        )
        by_cat[category][bucket] += 1
        if bucket == "tp":
            tp += 1
        elif bucket == "fp":
            fp += 1
        elif bucket == "fn":
            fn += 1
        else:
            tn += 1

    _print_report("this repo (Table 2)", "pairs", len(pairs), tp, fp, tn, fn, errors)
    for cat, c in sorted(by_cat.items()):
        print(f"  {cat}: tp={c['tp']} fp={c['fp']} tn={c['tn']} fn={c['fn']}")


def run_our_engine_population(
    queries: List[Dict[str, Any]], candidates: List[Dict[str, Any]]
) -> None:
    from patient_matching.matching.field_extractor import FieldExtractor
    from patient_matching.matching.matching_engine import MatchingEngine
    from patient_matching.normalization.manager import NormalizationManager

    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    engine = MatchingEngine(backend=_NullBackend())  # type: ignore[arg-type]

    errors: List[str] = []
    candidate_fields = {}
    for c in candidates:
        try:
            candidate_fields[c["id"]] = extractor.extract(
                normalizer.normalize(c["patient"])
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"candidate {c['id']}: {exc!r}")

    tp = fp = tn = fn = 0
    for q in queries:
        try:
            qf = extractor.extract(normalizer.normalize(q["query"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"query {q['query_id']}: {exc!r}")
            continue
        expected = set(q["expected_match_ids"])
        for cid in q["candidate_ids"]:
            if cid not in candidate_fields:
                continue
            predicted = engine.evaluate_pair(qf, candidate_fields[cid])
            actual = cid in expected
            if predicted and actual:
                tp += 1
            elif predicted:
                fp += 1
            elif actual:
                fn += 1
            else:
                tn += 1

    n = tp + fp + tn + fn
    _print_report("this repo (Table 2)", "population", n, tp, fp, tn, fn, errors)


# --- helix.personmatching's engine ------------------------------------------


def _parse_helix_patient(raw: Dict[str, Any], patient_cls: Any) -> Any:
    try:
        return patient_cls.model_validate(raw)
    except Exception:  # noqa: BLE001
        return patient_cls.model_validate(_strip_empty_strings(raw))


def run_helix_pairs(pairs: List[Dict[str, Any]], helix_repo: Path) -> None:
    sys.path.insert(0, str(helix_repo))
    from fhir.resources.R4B.patient import Patient
    from helix_personmatching.matchers.matcher import Matcher

    matcher = Matcher()
    tp = fp = tn = fn = 0
    errors: List[str] = []
    by_cat: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    )

    for case in pairs:
        category = case["rationale"].split("/")[0].split(" ")[0]
        try:
            source = _parse_helix_patient(case["source"], Patient)
            target = _parse_helix_patient(case["target"], Patient)
            scores = matcher.match_resources(source=source, target=target)
            predicted = any(s.matched for s in scores) if scores else False
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{case['case_id']}: {exc!r}")
            continue
        actual = case["expected_match"]
        bucket = (
            "tp"
            if predicted and actual
            else "fp"
            if predicted
            else "fn"
            if actual
            else "tn"
        )
        by_cat[category][bucket] += 1
        if bucket == "tp":
            tp += 1
        elif bucket == "fp":
            fp += 1
        elif bucket == "fn":
            fn += 1
        else:
            tn += 1

    _print_report(
        "helix.personmatching (legacy)", "pairs", len(pairs), tp, fp, tn, fn, errors
    )
    for cat, c in sorted(by_cat.items()):
        print(f"  {cat}: tp={c['tp']} fp={c['fp']} tn={c['tn']} fn={c['fn']}")


def run_helix_population(
    queries: List[Dict[str, Any]], candidates: List[Dict[str, Any]], helix_repo: Path
) -> None:
    sys.path.insert(0, str(helix_repo))
    from fhir.resources.R4B.patient import Patient
    from helix_personmatching.matchers.matcher import Matcher

    matcher = Matcher()
    errors: List[str] = []
    candidate_patients = {}
    for c in candidates:
        try:
            candidate_patients[c["id"]] = _parse_helix_patient(c["patient"], Patient)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"candidate {c['id']}: {exc!r}")

    tp = fp = tn = fn = 0
    for q in queries:
        try:
            query_patient = _parse_helix_patient(q["query"], Patient)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"query {q['query_id']}: {exc!r}")
            continue
        expected = set(q["expected_match_ids"])
        for cid in q["candidate_ids"]:
            if cid not in candidate_patients:
                continue
            try:
                scores = matcher.match_resources(
                    source=query_patient, target=candidate_patients[cid]
                )
                predicted = any(s.matched for s in scores) if scores else False
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{q['query_id']}x{cid}: {exc!r}")
                continue
            actual = cid in expected
            if predicted and actual:
                tp += 1
            elif predicted:
                fp += 1
            elif actual:
                fn += 1
            else:
                tn += 1

    n = tp + fp + tn + fn
    _print_report(
        "helix.personmatching (legacy)", "population", n, tp, fp, tn, fn, errors
    )


# --- entry point -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier", choices=["pairs", "population", "both"], default="both"
    )
    parser.add_argument("--helix-repo", type=Path, default=DEFAULT_HELIX_REPO)
    args = parser.parse_args()

    if not args.helix_repo.exists():
        print(
            f"helix.personmatching not found at {args.helix_repo} - clone it as a "
            "sibling of this repo, or pass --helix-repo. See this script's module "
            "docstring for the (separate) dependencies it needs installed.",
            file=sys.stderr,
        )
        return 1

    pairs_path = ONC_CASES_DIR / "sample_labeled_pairs.jsonl"
    queries_path = ONC_CASES_DIR / "population_queries.jsonl"
    candidates_path = ONC_CASES_DIR / "population_candidates.jsonl"

    if args.tier in ("pairs", "both"):
        pairs = _load_jsonl(pairs_path)
        run_our_engine_pairs(pairs)
        run_helix_pairs(pairs, args.helix_repo)

    if args.tier in ("population", "both"):
        queries = _load_jsonl(queries_path)
        candidates = _load_jsonl(candidates_path)
        run_our_engine_population(queries, candidates)
        run_helix_population(queries, candidates, args.helix_repo)

    return 0


if __name__ == "__main__":
    sys.exit(main())
