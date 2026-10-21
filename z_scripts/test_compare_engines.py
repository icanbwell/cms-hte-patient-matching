"""Tests for compare_engines.py on small synthetic rows (no ONC data, no engine, no helix).

The comparison logic takes injected `Side(prepare, match)` pairs, so these tests drive
it with toy matchers and never import `patient_matching` or `helix_personmatching`.
"""

from __future__ import annotations

from typing import Any

import pytest

from z_scripts.compare_engines import (
    CSV_COLUMNS,
    DisagreementRow,
    Side,
    Verdict,
    classify,
    compare_pairs,
    compare_population,
    confusion,
    summarize,
    write_csv,
)


def _row(**overrides: Any) -> DisagreementRow:
    fields: dict[str, Any] = {
        "tier": "realistic",
        "case_id": "c",
        "category": "fuzzy_variant",
        "expected": True,
        "engine_pred": True,
        "helix_pred": True,
        "bucket": "both_right",
        "helix_score": 0.0,
        "helix_rule": "",
    }
    fields.update(overrides)
    return DisagreementRow(**fields)


def test_verdict_defaults_to_zero_score_and_empty_rule() -> None:
    assert Verdict(matched=True) == Verdict(True, 0.0, "")


@pytest.mark.parametrize(
    ("expected", "engine_pred", "helix_pred", "bucket"),
    [
        (True, True, True, "both_right"),
        (False, False, False, "both_right"),
        (True, False, False, "both_wrong"),
        (False, True, True, "both_wrong"),
        (False, False, True, "engine_only_right"),
        (True, True, False, "engine_only_right"),
        (True, False, True, "helix_only_right"),
        (False, True, False, "helix_only_right"),
    ],
)
def test_classify_covers_every_bucket(
    expected: bool, engine_pred: bool, helix_pred: bool, bucket: str
) -> None:
    assert classify(expected, engine_pred, helix_pred) == bucket


def test_confusion_counts_each_side_separately() -> None:
    rows = [
        _row(expected=True, engine_pred=True, helix_pred=False),
        _row(expected=False, engine_pred=True, helix_pred=False),
    ]

    assert confusion(rows, "engine") == {"tp": 1, "fp": 1, "tn": 0, "fn": 0}
    assert confusion(rows, "helix") == {"tp": 0, "fp": 0, "tn": 1, "fn": 1}


def test_summarize_groups_buckets_by_category() -> None:
    rows = [
        _row(category="a", bucket="both_right"),
        _row(category="a", bucket="both_wrong"),
        _row(category="b", bucket="helix_only_right"),
    ]

    assert summarize(rows) == {
        "a": {"both_right": 1, "both_wrong": 1},
        "b": {"helix_only_right": 1},
    }


def test_write_csv_skips_both_right_and_has_only_id_and_verdict_columns(
    tmp_path: Any,
) -> None:
    rows = [_row(bucket="both_right"), _row(bucket="engine_only_right")]

    written = write_csv(rows, tmp_path / "out.csv")

    header = (tmp_path / "out.csv").read_text().splitlines()[0].split(",")
    assert written == 1
    assert tuple(header) == CSV_COLUMNS


# --- comparators ------------------------------------------------------------------
#
# Toy sides: `prepare` is the identity and `match(a, b)` looks only at the target's `k`,
# so a case/candidate "matches" iff its `k` is in the side's `matching` set.


def _side(matching: set[str], score: float = 0.0, rule: str = "") -> Side:
    def match(_a: Any, b: Any) -> Verdict:
        hit = b["k"] in matching
        return Verdict(hit, score if hit else 0.0, rule if hit else "")

    return Side(prepare=lambda patient: patient, match=match)


def _raising_side(bad_key: str) -> Side:
    def prepare(patient: dict[str, Any]) -> dict[str, Any]:
        if patient["k"] == bad_key:
            raise ValueError("bad record")
        return patient

    return Side(prepare=prepare, match=lambda _a, b: Verdict(True))


def _counting_side(matching: set[str]) -> tuple[Side, list[str]]:
    prepared: list[str] = []

    def prepare(patient: dict[str, Any]) -> dict[str, Any]:
        prepared.append(patient["k"])
        return patient

    return Side(prepare, lambda _a, b: Verdict(b["k"] in matching)), prepared


ENGINE_STUB = _side({"c1", "c2"})
HELIX_STUB = _side({"c2", "c3"}, score=0.97, rule="R1")


def _case(case_id: str, expected: bool, **overrides: Any) -> dict[str, Any]:
    case: dict[str, Any] = {
        "case_id": case_id,
        "expected_match": expected,
        "rationale": "fuzzy_variant/given_nickname",
        "source": {"k": case_id},
        "target": {"k": case_id},
    }
    case.update(overrides)
    return case


def test_compare_pairs_labels_each_disagreement_bucket() -> None:
    cases = [
        _case("c1", True),
        _case("c2", True),
        _case("c3", True),
        _case("c4", False),
    ]

    result = compare_pairs(cases, ENGINE_STUB, HELIX_STUB, tier="realistic")

    assert {r.case_id: r.bucket for r in result.rows} == {
        "c1": "engine_only_right",
        "c2": "both_right",
        "c3": "helix_only_right",
        "c4": "both_right",
    }
    assert result.errors == []


def test_compare_pairs_carries_tier_category_and_helix_score_and_rule() -> None:
    result = compare_pairs([_case("c2", True)], ENGINE_STUB, HELIX_STUB, tier="curated")

    row = result.rows[0]
    assert (row.tier, row.category) == ("curated", "fuzzy_variant")
    assert (row.expected, row.engine_pred, row.helix_pred) == (True, True, True)
    assert (row.helix_score, row.helix_rule) == (0.97, "R1")


def test_compare_pairs_records_a_raising_case_as_an_error_not_a_row() -> None:
    cases = [_case("c1", True), _case("boom", True)]

    result = compare_pairs(cases, _raising_side("boom"), HELIX_STUB, tier="curated")

    assert len(result.rows) + len(result.errors) == len(cases)
    assert [r.case_id for r in result.rows] == ["c1"]
    assert "boom" in result.errors[0]


@pytest.mark.parametrize("rationale_override", [{"rationale": ""}, {"rationale": None}])
def test_compare_pairs_uses_unknown_category_for_empty_rationale(
    rationale_override: dict[str, Any],
) -> None:
    result = compare_pairs(
        [_case("c1", True, **rationale_override)], ENGINE_STUB, HELIX_STUB, "curated"
    )

    assert result.rows[0].category == "unknown"


def test_compare_pairs_uses_unknown_category_for_missing_rationale() -> None:
    case = _case("c1", True)
    del case["rationale"]

    result = compare_pairs([case], ENGINE_STUB, HELIX_STUB, "curated")

    assert result.rows[0].category == "unknown"


def _population() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    queries = [
        {
            "query_id": "q1",
            "query": {"k": "q1"},
            "candidate_ids": ["a", "b", "zzz"],
            "expected_match_ids": ["a"],
            "rationale": "compound_variant/name_and_dob",
        }
    ]
    candidates = [
        {"id": "a", "patient": {"k": "a"}},
        {"id": "b", "patient": {"k": "b"}},
    ]
    return queries, candidates


def test_compare_population_rows_are_per_query_candidate_with_expected_labels() -> None:
    queries, candidates = _population()

    # Engine links a and b; helix links only a. Truth: a matches, b does not.
    result = compare_population(
        queries, candidates, _side({"a", "b"}), _side({"a"}), tier="realistic"
    )

    by_id = {r.case_id: r for r in result.rows}
    assert set(by_id) == {"q1xa", "q1xb"}
    assert (by_id["q1xa"].expected, by_id["q1xa"].bucket) == (True, "both_right")
    assert (by_id["q1xb"].expected, by_id["q1xb"].bucket) == (False, "helix_only_right")
    assert by_id["q1xa"].category == "compound_variant"


def test_compare_population_reports_missing_candidate_and_prepares_each_once() -> None:
    queries, candidates = _population()
    engine, engine_prepared = _counting_side({"a"})

    result = compare_population(
        queries, candidates, engine, _side({"a"}), tier="realistic"
    )

    assert any("missing candidate zzz" in e for e in result.errors)
    assert sorted(engine_prepared) == ["a", "b", "q1"]  # each exactly once
