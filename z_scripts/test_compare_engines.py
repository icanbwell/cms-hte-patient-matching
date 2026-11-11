"""Tests for compare_engines.py on small synthetic rows (no ONC data).

The comparison logic takes injected `Side(prepare, match)` pairs, so most tests drive it
with toy matchers. Two tests reach further: the engine adapter test needs this repo's
`patient_matching` package, and the helix adapter test skips unless `HELIX_REPO` points at a
helix.personmatching checkout. CI collects this file with the rest of `pytest .`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from z_scripts import compare_engines
from z_scripts.compare_engines import (
    CSV_COLUMNS,
    EMPTY_STRING_RETRIES,
    LIBRARY_DEFAULT_HELIX_THRESHOLD,
    DisagreementRow,
    Side,
    TierReport,
    Verdict,
    _build_helix_side,
    _helix_label,
    classify,
    compare_pairs,
    compare_population,
    confusion,
    engine_side,
    make_helix_side,
    run_tier,
    summarize,
    with_threshold,
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


def test_write_csv_omits_both_right_rows_and_writes_the_full_header(
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
    assert result.errors == ()


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


def test_comparison_results_hold_immutable_tuples() -> None:
    queries, candidates = _population()
    pairs = compare_pairs([_case("c1", True)], ENGINE_STUB, HELIX_STUB, "curated")
    population = compare_population(
        queries, candidates, ENGINE_STUB, HELIX_STUB, "curated"
    )

    for result in (pairs, population):
        assert isinstance(result.rows, tuple)
        assert isinstance(result.errors, tuple)


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


def test_compare_population_counts_every_pair_of_an_unusable_candidate_as_an_error() -> (
    None
):
    queries, candidates = _population()

    # Candidate "a" is the query's only expected match and cannot be prepared.
    result = compare_population(
        queries, candidates, _raising_side("a"), _side({"a"}), tier="realistic"
    )

    assert [r.case_id for r in result.rows] == ["q1xb"]
    # One error for the cause, one for the excluded pair q1xa, one for the missing zzz.
    assert sum(e.startswith("candidate a:") for e in result.errors) == 1
    assert sum(e.startswith("q1xa:") for e in result.errors) == 1
    assert len(result.errors) == 3


def test_compare_population_counts_every_pair_of_an_unusable_query_as_an_error() -> (
    None
):
    queries, candidates = _population()

    result = compare_population(
        queries, candidates, _raising_side("q1"), _side({"a"}), tier="realistic"
    )

    assert result.rows == ()
    # One error for the cause, then one for each of the query's three candidate pairs.
    assert sum(e.startswith("query q1:") for e in result.errors) == 1
    for pair in ("q1xa", "q1xb", "q1xzzz"):
        assert sum(e.startswith(f"{pair}:") for e in result.errors) == 1
    assert len(result.errors) == 4


# --- real adapters ----------------------------------------------------------------


@dataclass
class _FakeRuleScore:
    rule_name: str
    rule_score: float


@dataclass
class _FakeResult:
    matched: bool
    total_score: float
    rule_scores: list[_FakeRuleScore] = field(default_factory=list)


class _FakeMatcher:
    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = results

    def match_resources(self, source: Any, target: Any) -> list[_FakeResult]:
        return self._results


class _FakePatient:
    """Stands in for fhir.resources' Patient: rejects empty strings like FHIR's `string`."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    @classmethod
    def parse_obj(cls, raw: dict[str, Any]) -> "_FakePatient":
        if "" in raw.values():
            raise ValueError("string must have a non-whitespace character")
        return cls(raw)


def test_helix_side_maps_an_empty_result_to_a_non_match() -> None:
    side = _build_helix_side(_FakeMatcher([]), _FakePatient)

    assert side.match(object(), object()) == Verdict(False, 0.0, "")


def test_helix_side_reports_matched_if_any_rule_result_matched_with_top_score_and_rule() -> (
    None
):
    results = [
        _FakeResult(False, 0.90, [_FakeRuleScore("A", 0.5)]),
        _FakeResult(True, 0.97, [_FakeRuleScore("A", 0.4), _FakeRuleScore("B", 0.9)]),
    ]
    side = _build_helix_side(_FakeMatcher(results), _FakePatient)

    assert side.match(object(), object()) == Verdict(True, 0.97, "B")


def test_helix_side_prepare_retries_with_empty_strings_stripped() -> None:
    side = _build_helix_side(_FakeMatcher([]), _FakePatient)

    parsed = side.prepare({"city": "", "name": "x"})

    assert parsed.raw == {"name": "x"}


def test_helix_side_counts_each_retry_with_empty_strings_dropped() -> None:
    side = _build_helix_side(_FakeMatcher([]), _FakePatient)

    side.prepare({"name": "x"})
    assert side.stats[EMPTY_STRING_RETRIES] == 0
    side.prepare({"city": "", "name": "x"})
    side.prepare({"state": "", "name": "x"})

    assert side.stats[EMPTY_STRING_RETRIES] == 2


class _TypeErrorPatient:
    @classmethod
    def parse_obj(cls, raw: dict[str, Any]) -> "_TypeErrorPatient":
        raise TypeError("not a validation problem")


class _AlwaysInvalidPatient:
    @classmethod
    def parse_obj(cls, raw: dict[str, Any]) -> "_AlwaysInvalidPatient":
        raise ValueError("still invalid")


def test_helix_side_does_not_retry_an_error_that_is_not_a_validation_error() -> None:
    side = _build_helix_side(_FakeMatcher([]), _TypeErrorPatient)

    with pytest.raises(TypeError, match="not a validation problem"):
        side.prepare({"city": "", "name": "x"})

    assert side.stats[EMPTY_STRING_RETRIES] == 0


def test_helix_side_raises_when_the_retry_also_fails_and_still_counts_it() -> None:
    side = _build_helix_side(_FakeMatcher([]), _AlwaysInvalidPatient)

    with pytest.raises(ValueError, match="still invalid"):
        side.prepare({"city": "", "name": "x"})

    assert side.stats[EMPTY_STRING_RETRIES] == 1


# The ZIP must not be a placeholder: the engine drops `00000` (spec V.D placeholder table),
# which leaves an identical record with no usable Table 2 rule and so no match.
SYNTHETIC_PATIENT: dict[str, Any] = {
    "resourceType": "Patient",
    "id": "synthetic-1",
    "name": [{"family": "Testperson", "given": ["Synthia"]}],
    "birthDate": "1980-02-03",
    "gender": "female",
    "address": [
        {
            "line": ["1 Example Way"],
            "city": "Faketown",
            "state": "ZZ",
            "postalCode": "90210",
        }
    ],
    "telecom": [{"system": "phone", "value": "555-010-0100"}],
}


def test_engine_side_matches_an_identical_synthetic_patient_and_rejects_a_stranger() -> (
    None
):
    side = engine_side()
    stranger = {
        **SYNTHETIC_PATIENT,
        "name": [{"family": "Otherperson", "given": ["Zed"]}],
        "birthDate": "1999-09-09",
        "telecom": [{"system": "phone", "value": "555-010-0199"}],
        "address": [{"line": ["9 Nowhere Rd"], "city": "Elsewhere", "state": "ZZ"}],
    }

    same = side.match(side.prepare(SYNTHETIC_PATIENT), side.prepare(SYNTHETIC_PATIENT))
    other = side.match(side.prepare(SYNTHETIC_PATIENT), side.prepare(stranger))

    assert (same.matched, other.matched) == (True, False)


def test_make_helix_side_names_the_repo_when_helix_cannot_be_imported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))  # undo make_helix_side's insert
    monkeypatch.setitem(sys.modules, "fhir.resources.R4B.patient", None)
    monkeypatch.setitem(sys.modules, "helix_personmatching.matchers.matcher", None)

    with pytest.raises(RuntimeError, match=str(tmp_path)):
        make_helix_side(tmp_path)


def test_helix_adapter_runs_on_one_synthetic_pair() -> None:
    helix_repo = os.environ.get("HELIX_REPO")
    if not helix_repo:
        pytest.skip(
            "set HELIX_REPO to a helix.personmatching checkout (eval-only dependency)"
        )
    side = make_helix_side(Path(helix_repo))

    verdict = side.match(
        side.prepare(SYNTHETIC_PATIENT), side.prepare(SYNTHETIC_PATIENT)
    )

    assert verdict.matched is True


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_run_tier_reads_tier_files_writes_both_csvs_and_summarizes(
    tmp_path: Path,
) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    _write_jsonl(
        cases / "realistic_labeled_pairs.jsonl", [_case("c1", True), _case("c2", True)]
    )
    queries, candidates = _population()
    _write_jsonl(cases / "realistic_population_queries.jsonl", queries)
    _write_jsonl(cases / "realistic_population_candidates.jsonl", candidates)
    out = tmp_path / "out"

    # Engine links c1, c2; helix links only c1 -> c2 is engine_only_right.
    report = run_tier(
        cases, "realistic", _side({"c1", "c2", "a"}), _side({"c1", "a"}), out
    ).text

    pairs_csv = (out / "pairs_realistic.csv").read_text().splitlines()
    assert pairs_csv[0] == ",".join(CSV_COLUMNS)
    assert len(pairs_csv) == 2 and "c2" in pairs_csv[1]
    assert (out / "population_realistic.csv").exists()
    assert "tp=2 fp=0 tn=0 fn=0" in report  # engine, pairs
    assert "tp=1 fp=0 tn=0 fn=1" in report  # helix, pairs


def _write_clean_tier(tmp_path: Path) -> Path:
    """A realistic tier whose every case and candidate is usable (no `zzz`)."""
    cases = tmp_path / "cases"
    cases.mkdir()
    _write_jsonl(
        cases / "realistic_labeled_pairs.jsonl", [_case("c1", True), _case("c2", True)]
    )
    queries, candidates = _population()
    queries[0]["candidate_ids"] = ["a", "b"]
    _write_jsonl(cases / "realistic_population_queries.jsonl", queries)
    _write_jsonl(cases / "realistic_population_candidates.jsonl", candidates)
    return cases


def test_run_tier_reports_zero_errors_and_no_exclusion_warning_on_a_clean_tier(
    tmp_path: Path,
) -> None:
    cases = _write_clean_tier(tmp_path)

    report = run_tier(
        cases, "realistic", _side({"c1", "a"}), _side({"c1", "a"}), tmp_path
    )

    assert report.error_count == 0
    assert "excluded" not in report.text


def test_run_tier_counts_errors_and_warns_that_their_cases_are_excluded(
    tmp_path: Path,
) -> None:
    cases = _write_clean_tier(tmp_path)

    report = run_tier(
        cases, "realistic", _raising_side("c1"), _side({"c1", "a"}), tmp_path
    )

    assert report.error_count == 1
    assert "errors=1" in report.text
    assert "excluded from every count" in report.text


def test_run_tier_reports_how_many_helix_parses_were_retried(tmp_path: Path) -> None:
    cases = _write_clean_tier(tmp_path)
    helix = Side(
        prepare=lambda patient: patient,
        match=lambda a, b: Verdict(matched=False),
        stats={EMPTY_STRING_RETRIES: 7},
    )

    report = run_tier(cases, "realistic", _side({"c1", "a"}), helix, tmp_path)

    assert "7 parse call(s) retried with empty strings dropped" in report.text


def test_run_tier_omits_the_retry_line_for_a_side_without_that_statistic(
    tmp_path: Path,
) -> None:
    cases = _write_clean_tier(tmp_path)

    report = run_tier(
        cases, "realistic", _side({"c1", "a"}), _side({"c1", "a"}), tmp_path
    )

    assert "retried" not in report.text


@pytest.mark.parametrize(
    ("score", "threshold", "matched"),
    [
        (0.9550, 0.9555, False),
        (0.9555, 0.9555, True),
        (0.9560, 0.9555, True),
        (0.9550, 0.9550, True),
    ],
)
def test_with_threshold_redecides_matched_from_the_score_and_keeps_score_and_rule(
    score: float, threshold: float, matched: bool
) -> None:
    base = Side(
        prepare=lambda patient: patient,
        match=lambda a, b: Verdict(matched=True, score=score, rule="R1"),
    )
    verdict = with_threshold(base, threshold).match({"k": 1}, {"k": 2})
    assert verdict == Verdict(matched=matched, score=score, rule="R1")


def test_with_threshold_leaves_prepare_untouched() -> None:
    base = Side(
        prepare=lambda patient: ("prepared", patient["k"]),
        match=lambda a, b: Verdict(matched=False),
    )
    assert with_threshold(base, 0.9555).prepare({"k": 7}) == ("prepared", 7)


def test_with_threshold_keeps_the_live_stats_of_the_side_it_wraps() -> None:
    base = Side(
        prepare=lambda patient: patient,
        match=lambda a, b: Verdict(matched=False),
        stats={EMPTY_STRING_RETRIES: 3},
    )
    wrapped = with_threshold(base, 0.9555)

    base.stats[EMPTY_STRING_RETRIES] += 1

    assert wrapped.stats[EMPTY_STRING_RETRIES] == 4


def test_main_builds_the_engine_before_helix_so_helix_tests_package_cannot_shadow_ours(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """make_helix_side puts the helix tree first on sys.path, and that tree has its own
    `tests` package; the engine imports `tests._null_backend`, so it must be built first."""
    calls: list[str] = []
    stub = Side(prepare=lambda p: p, match=lambda a, b: Verdict(matched=False))

    def fake_engine() -> Side:
        calls.append("engine")
        return stub

    def fake_helix(helix_repo: Path) -> Side:
        calls.append("helix")
        return stub

    monkeypatch.setattr(compare_engines, "engine_side", fake_engine)
    monkeypatch.setattr(compare_engines, "make_helix_side", fake_helix)
    monkeypatch.setattr(
        compare_engines, "run_tier", lambda *args, **kwargs: TierReport("report", 0)
    )

    exit_code = compare_engines.main(
        [
            "--cases-dir",
            str(tmp_path),
            "--tier",
            "curated",
            "--helix-repo",
            str(tmp_path),
            "--out-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert calls == ["engine", "helix"]


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    engine: Side,
    helix: Side,
    extra_args: list[str] | None = None,
) -> int:
    monkeypatch.setattr(compare_engines, "engine_side", lambda: engine)
    monkeypatch.setattr(compare_engines, "make_helix_side", lambda helix_repo: helix)
    monkeypatch.setattr(
        compare_engines, "_helix_label", lambda helix_repo: "helix-label"
    )
    return compare_engines.main(
        [
            "--cases-dir",
            str(_write_clean_tier(tmp_path)),
            "--tier",
            "realistic",
            "--helix-repo",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "out"),
            *(extra_args or []),
        ]
    )


def test_main_exits_non_zero_when_any_case_errored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = _run_main(
        monkeypatch, tmp_path, _raising_side("c1"), _side({"c1", "a"})
    )

    assert exit_code == 1
    assert "1 case(s) errored" in capsys.readouterr().err


def test_main_exits_zero_when_no_case_errored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = _run_main(monkeypatch, tmp_path, _side({"c1", "a"}), _side({"c1", "a"}))

    assert exit_code == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("extra_args", "note"),
    [
        ([], f"library default ({LIBRARY_DEFAULT_HELIX_THRESHOLD})"),
        (["--helix-threshold", "0.9555"], "0.9555"),
    ],
)
def test_main_states_which_helix_cut_off_was_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra_args: list[str],
    note: str,
) -> None:
    _run_main(monkeypatch, tmp_path, _side({"c1", "a"}), _side({"c1", "a"}), extra_args)

    assert f"match threshold {note}" in capsys.readouterr().out


def _git_describe_result(outcome: Any) -> Any:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return fake_run


@pytest.mark.parametrize(
    ("outcome", "version"),
    [
        (subprocess.CompletedProcess([], 0, stdout="2.1.0\n"), "2.1.0"),
        (subprocess.CompletedProcess([], 128, stdout=""), "no git metadata"),
        (OSError("git not installed"), "no git metadata"),
        (subprocess.TimeoutExpired(cmd="git", timeout=1), "no git metadata"),
    ],
)
def test_helix_label_reports_the_git_version_or_says_there_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: Any, version: str
) -> None:
    monkeypatch.setattr(subprocess, "run", _git_describe_result(outcome))

    assert _helix_label(tmp_path) == f"{tmp_path} ({version})"
