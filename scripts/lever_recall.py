"""Recall uplift of each proposed widened match, applied only where P(collision) fits.

`scripts/collision_feasibility.py` says which rules can absorb each widening and stay at or
under the 2e-12 threshold. This script measures what recall is left once a lever is
restricted to those rules, next to the unrestricted number, so the analysis can report
uplift that is actually approvable rather than uplift that ignores the threshold.

Each lever is a monkeypatch of `FieldComparator` (and `MIN_FUZZY_LENGTH`) applied for the
duration of one rule's field verification, selected by `rule_id`. They approximate the
proposed rule changes; they are not implementations. Needs the ONC test data
(`make fetch-onc-data`, at the tag being analysed).

Usage:
    uv run python scripts/lever_recall.py [--json OUT.json]
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from rapidfuzz.distance import DamerauLevenshtein

import patient_matching.matching.field_comparator as fc
from patient_matching.matching.field_extractor import FieldExtractor, PatientFields
from patient_matching.matching.in_memory_backend import InMemoryBackend
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

try:  # imported as a package module (pytest) or run as a script (scripts/ on sys.path)
    from .collision_feasibility import (
        BASES,
        COMBOS,
        LEVERS,
        Multipliers,
        RuleView,
        assign,
        rule_views,
    )
except ImportError:  # pragma: no cover - script invocation
    # mypy sees the relative import above as the only definition and cannot resolve the
    # bare module that exists only when scripts/ is on sys.path; both ignores are for that.
    from collision_feasibility import (  # type: ignore[no-redef,import-not-found]
        BASES,
        COMBOS,
        LEVERS,
        Multipliers,
        RuleView,
        assign,
        rule_views,
    )

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "onc"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_orig_exact = fc.FieldComparator.exact_match
_orig_dob_fuzzy = fc.FieldComparator.dob_fuzzy_match


def initial_match(q: Set[str], c: Set[str]) -> bool:
    return any(
        (len(a) == 1 and len(b) > 1 and b.startswith(a))
        or (len(b) == 1 and len(a) > 1 and a.startswith(b))
        for a in q
        for b in c
    )


def _swap(d: str) -> str | None:
    y, m, dd = d.split("-")
    try:
        date.fromisoformat(f"{y}-{dd}-{m}")
    except ValueError:
        return None
    return f"{y}-{dd}-{m}"


def dob_swap_match(q: Set[str], c: Set[str]) -> bool:
    if _orig_dob_fuzzy(q, c):
        return True
    return any(_swap(a) in c for a in q if _swap(a)) or any(
        _swap(b) in q for b in c if _swap(b)
    )


def dob_dl1_match(q: Set[str], c: Set[str]) -> bool:
    if dob_swap_match(q, c):
        return True
    return any(
        DamerauLevenshtein.distance(a.replace("-", ""), b.replace("-", "")) <= 1
        for a in q
        for b in c
    )


def _patch_for(levers: Tuple[str, ...]) -> None:
    # The ignores below are false positives: this harness deliberately replaces
    # FieldComparator's staticmethods at class level to approximate a rule change, and
    # mypy rejects assigning to a method and staticmethod-wrapped callables.
    initial = any(k.startswith("initial") for k in levers)
    dl1 = any(k.startswith("dob_dl1") for k in levers)
    swap = any(k.startswith("dob_swap") for k in levers)

    def exact(q: Set[str], c: Set[str]) -> bool:
        if _orig_exact(q, c) or (initial and initial_match(q, c)):
            return True
        return bool(
            dl1
            and q
            and c
            and all(_DATE.match(v) for v in q | c)
            and dob_dl1_match(q, c)
        )

    fc.FieldComparator.exact_match = staticmethod(exact)  # type: ignore[method-assign,assignment]
    fc.FieldComparator.dob_fuzzy_match = staticmethod(  # type: ignore[method-assign,assignment]
        dob_dl1_match if dl1 else dob_swap_match if swap else _orig_dob_fuzzy
    )
    fc.MIN_FUZZY_LENGTH = 4 if "min4" in levers else 5


def _restore() -> None:
    fc.FieldComparator.exact_match = _orig_exact  # type: ignore[method-assign]
    fc.FieldComparator.dob_fuzzy_match = _orig_dob_fuzzy  # type: ignore[method-assign]
    fc.MIN_FUZZY_LENGTH = 5


@dataclass
class Data:
    pairs: List[Tuple[Dict[str, Any], PatientFields, PatientFields]]
    queries: List[Tuple[Dict[str, Any], PatientFields]]
    candidates: Dict[str, PatientFields]


def load_data(fixtures: Path = FIXTURES) -> Data:
    norm, ext = NormalizationManager(), FieldExtractor()

    def extract(p: Dict[str, Any]) -> PatientFields:
        return ext.extract(norm.normalize(p))

    def rows(name: str) -> List[Dict[str, Any]]:
        with (fixtures / name).open() as f:
            return [json.loads(line) for line in f]

    return Data(
        pairs=[
            (c, extract(c["source"]), extract(c["target"]))
            for c in rows("sample_labeled_pairs.jsonl")
        ],
        queries=[(q, extract(q["query"])) for q in rows("population_queries.jsonl")],
        candidates={
            c["id"]: extract(c["patient"]) for c in rows("population_candidates.jsonl")
        },
    )


def evaluate(data: Data, assignment: Dict[str, Tuple[str, ...]]) -> Dict[str, Any]:
    """Run both tiers with `assignment` (rule_id -> levers) patched in per rule."""
    engine = MatchingEngine(backend=InMemoryBackend())
    original = engine._verify_fields

    def verify(*args: Any, **kwargs: Any) -> Any:
        _patch_for(assignment.get(kwargs["rule_id"], ()))
        try:
            return original(*args, **kwargs)
        finally:
            _restore()

    # Deliberate per-instance wrap of the engine's field verification (false positive).
    engine._verify_fields = verify  # type: ignore[method-assign]
    tp = fp = tn = fn = 0
    for case, s, t in data.pairs:
        predicted, actual = engine.evaluate_pair(s, t), case["expected_match"]
        tp, fp, tn, fn = (
            tp + (predicted and actual),
            fp + (predicted and not actual),
            tn + (not predicted and not actual),
            fn + (not predicted and actual),
        )
    ptp = pfp = pfn = 0
    for q, qf in data.queries:
        expected = set(q["expected_match_ids"])
        for cid in q["candidate_ids"]:
            predicted, actual = (
                engine.evaluate_pair(qf, data.candidates[cid]),
                cid in expected,
            )
            ptp, pfp, pfn = (
                ptp + (predicted and actual),
                pfp + (predicted and not actual),
                pfn + (not predicted and actual),
            )
    precision, recall = ptp / (ptp + pfp), ptp / (ptp + pfn)
    return {
        "pairs_recall": tp / (tp + fn),
        "pairs_fn": fn,
        "pairs_fp": fp,
        "pop_recall": recall,
        "pop_fn": pfn,
        "pop_fp": pfp,
        "pop_f1": 2 * precision * recall / (precision + recall),
    }


def unrestricted(
    rules: List[RuleView], combo: Tuple[str, ...]
) -> Dict[str, Tuple[str, ...]]:
    """Every lever in `combo` wherever its scope applies, ignoring the threshold."""
    out: Dict[str, Tuple[str, ...]] = {}
    for r in rules:
        out[r.rule_id] = tuple(
            k
            for k in combo
            if any(LEVERS[k].applies(r, f) for f in LEVERS[k].field_to_widening)
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    mult, rules, data = Multipliers.from_csv(), rule_views(), load_data()
    cache: Dict[str, Dict[str, Any]] = {}

    def run(assignment: Dict[str, Tuple[str, ...]]) -> Dict[str, Any]:
        key = json.dumps({k: v for k, v in sorted(assignment.items()) if v})
        if key not in cache:
            cache[key] = evaluate(data, assignment)
        return cache[key]

    results: Dict[str, Dict[str, Any]] = {"baseline": run({})}
    print(f"baseline {results['baseline']}", flush=True)
    for name, combo in [(k, (k,)) for k in LEVERS] + list(COMBOS.items()):
        entry = {"unrestricted": run(unrestricted(rules, combo))}
        for basis in BASES:
            assigned = assign(rules, combo, mult, basis)
            entry[basis] = {
                **run(assigned),
                "rules_with_lever": sorted(r for r, v in assigned.items() if v),
            }
        results[name] = entry
        print(
            name, {k: round(v["pairs_recall"], 4) for k, v in entry.items()}, flush=True
        )
    if args.json:
        args.json.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
