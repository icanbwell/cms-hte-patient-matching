"""Tests for score_test_set.py on small synthetic rows (no ONC data, no engine).

The scorer takes `prepare(patient) -> fields` and `match(a, b) -> bool`, so these
tests drive it with a toy matcher: two patients match iff their `name` strings
are equal.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from z_scripts.score_test_set import score_pairs, score_population


def _prepare(patient: Dict[str, Any]) -> Any:
    if patient.get("boom"):
        raise ValueError("bad record")
    return patient["name"]


def _match(a: Any, b: Any) -> bool:
    return bool(a == b)


def _pair(
    case_id: str, src: str, tgt: str, expected: bool, rationale: str
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "source": {"name": src},
        "target": {"name": tgt},
        "expected_match": expected,
        "rationale": rationale,
    }


def test_score_pairs_confusion_matrix_and_rates() -> None:
    rows = [
        _pair("1", "ann", "ann", True, "fuzzy_variant/dob_typo"),  # tp
        _pair("2", "ann", "anne", True, "fuzzy_variant/dob_swap"),  # fn
        _pair("3", "bob", "bob", False, "sibling_negative/x"),  # fp
        _pair("4", "bob", "rob", False, "sibling_negative/y"),  # tn
    ]
    m = score_pairs(rows, _prepare, _match)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (1, 1, 1, 1)
    assert m["recall"] == 0.5 and m["fpr"] == 0.5 and m["precision"] == 0.5
    assert m["errors"] == []


def test_score_pairs_breaks_down_by_top_category_and_subcategory() -> None:
    rows = [
        _pair("1", "ann", "ann", True, "fuzzy_variant/dob_typo"),
        _pair("2", "ann", "anne", True, "fuzzy_variant/dob_swap"),
        _pair("3", "bob", "bob", False, "sibling_negative/x"),
    ]
    m = score_pairs(rows, _prepare, _match)
    assert m["by_category"]["fuzzy_variant"] == {"tp": 1, "fp": 0, "tn": 0, "fn": 1}
    assert m["by_subcategory"]["fuzzy_variant/dob_swap"]["fn"] == 1
    assert m["by_category"]["sibling_negative"]["fp"] == 1


def test_score_pairs_lists_false_positive_case_ids_with_rationale() -> None:
    rows = [
        _pair("1", "ann", "ann", True, "fuzzy_variant/dob_typo"),
        _pair("3", "bob", "bob", False, "twin_like_negative/x"),
    ]
    m = score_pairs(rows, _prepare, _match)
    assert m["fp_cases"] == [{"case_id": "3", "rationale": "twin_like_negative/x"}]


def test_score_population_lists_false_positive_pairs_with_query_rationale() -> None:
    candidates = [
        {"id": "c1", "patient": {"name": "ann"}},
        {"id": "c2", "patient": {"name": "ann"}},
    ]
    queries = [
        {
            "query_id": "q1",
            "query": {"name": "ann"},
            "candidate_ids": ["c1", "c2"],
            "expected_match_ids": ["c1"],
            "rationale": "population/household_member_negative",
        },
    ]
    m = score_population(queries, candidates, _prepare, _match)
    assert m["fp_cases"] == [
        {
            "query_id": "q1",
            "candidate_id": "c2",
            "rationale": "population/household_member_negative",
        }
    ]


def test_score_pairs_records_errors_instead_of_crashing() -> None:
    rows = [_pair("1", "ann", "ann", True, "a/b")]
    rows[0]["target"] = {"boom": True}
    m = score_pairs(rows, _prepare, _match)
    assert m["tp"] + m["fn"] == 0
    assert len(m["errors"]) == 1 and m["errors"][0].startswith("1:")


def test_score_population_flattens_every_query_candidate_pair() -> None:
    candidates = [
        {"id": "c1", "patient": {"name": "ann"}},
        {"id": "c2", "patient": {"name": "ann"}},
        {"id": "c3", "patient": {"name": "zed"}},
    ]
    queries = [
        # c1 expected & matched (tp); c2 matched but not expected (fp); c3 tn
        {
            "query_id": "q1",
            "query": {"name": "ann"},
            "candidate_ids": ["c1", "c2", "c3"],
            "expected_match_ids": ["c1"],
            "rationale": "population/fuzzy_variant",
        },
        # zero-match query: c3 expected? no; nothing expected, nothing matched -> tn, tn
        {
            "query_id": "q2",
            "query": {"name": "bob"},
            "candidate_ids": ["c1", "c3"],
            "expected_match_ids": [],
            "rationale": "population/",
        },
        # c3 expected but not matched (fn)
        {
            "query_id": "q3",
            "query": {"name": "zee"},
            "candidate_ids": ["c3"],
            "expected_match_ids": ["c3"],
            "rationale": "population/fuzzy_variant",
        },
    ]
    m = score_population(queries, candidates, _prepare, _match)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (1, 1, 3, 1)
    assert m["n_evals"] == 6 and m["n_queries"] == 3 and m["n_candidates"] == 3
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert math.isclose(m["f1"], 0.5)


def test_score_population_breaks_down_by_expected_match_count() -> None:
    candidates = [{"id": "c1", "patient": {"name": "ann"}}]
    queries = [
        {
            "query_id": "q0",
            "query": {"name": "ann"},
            "candidate_ids": ["c1"],
            "expected_match_ids": [],
            "rationale": "population/",
        },
        {
            "query_id": "q1",
            "query": {"name": "ann"},
            "candidate_ids": ["c1"],
            "expected_match_ids": ["c1"],
            "rationale": "population/x",
        },
    ]
    m = score_population(queries, candidates, _prepare, _match)
    assert m["by_match_count"]["0"] == {
        "tp": 0,
        "fp": 1,
        "tn": 0,
        "fn": 0,
        "queries": 1,
    }
    assert m["by_match_count"]["1"] == {
        "tp": 1,
        "fp": 0,
        "tn": 0,
        "fn": 0,
        "queries": 1,
    }
