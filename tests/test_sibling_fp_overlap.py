"""Tests for `scripts/sibling_fp_overlap.py`.

All records are synthetic (invented ids, placeholder names) - no real or
ONC-derived patient data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

import scripts.sibling_fp_overlap as overlap


def _case(
    case_id: str, expected_match: bool, rationale: str = "sibling_negative (x)"
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "source": {},
        "target": {},
        "expected_match": expected_match,
        "rationale": rationale,
    }


def _predict_from(matched_ids: Set[str]) -> overlap.Predict:
    return lambda case: case["case_id"] in matched_ids


def test_false_positive_ids_keeps_only_predicted_matches_labeled_non_match() -> None:
    pairs = [
        _case("fp", expected_match=False),
        _case("tn", expected_match=False),
        _case("tp", expected_match=True),
    ]

    result = overlap.false_positive_ids(
        pairs, _predict_from({"fp", "tp"}), "sibling_negative"
    )

    assert result == {"fp"}


def test_false_positive_ids_ignores_other_categories() -> None:
    pairs = [
        _case("sib", expected_match=False),
        _case("hh", expected_match=False, rationale="household_negative (x)"),
    ]

    result = overlap.false_positive_ids(
        pairs, _predict_from({"sib", "hh"}), "sibling_negative"
    )

    assert result == {"sib"}


def test_overlap_report_splits_false_positives_by_whether_new_version_removes_them() -> (
    None
):
    report = overlap.overlap_report(
        fp_ids={"a", "b", "c"},
        old_ids={"a", "b", "c", "d", "e"},
        new_ids={"c", "e"},
    )

    assert report["removed"] == ["a", "b", "d"]
    assert report["fp_removed"] == ["a", "b"]
    assert report["fp_kept"] == ["c"]
    assert report["removed_not_fp"] == ["d"]


def test_confusion_counts_and_rates() -> None:
    pairs = [
        _case("tp", expected_match=True),
        _case("fn", expected_match=True),
        _case("fp", expected_match=False),
        _case("tn1", expected_match=False),
        _case("tn2", expected_match=False),
        _case("tn3", expected_match=False),
    ]

    result = overlap.confusion(pairs, _predict_from({"tp", "fp"}))

    assert (result["tp"], result["fn"], result["fp"], result["tn"]) == (1, 1, 1, 3)
    assert result["recall"] == 0.5
    assert result["fpr"] == 0.25


def _patient(patient_id: str, given: str, birth_date: str) -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"family": "SYNTHETICFAMILY", "given": [given]}],
        "gender": "male",
        "birthDate": birth_date,
        "telecom": [{"system": "phone", "value": "555-010-0001"}],
        "address": [
            {
                "line": ["1 EXAMPLE ST"],
                "city": "TESTVILLE",
                "state": "NY",
                "postalCode": "00001",
            }
        ],
    }


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_main_reports_engine_false_positive_removed_by_new_version(
    tmp_path: Path, capsys: Any
) -> None:
    # Identical demographics under two ids: the real engine links them, so
    # labeled as a sibling non-match this is a false positive.
    same_person_like = {
        "case_id": "900001::900002::sibling",
        "source": _patient("900001", "ALPHA", "2000-01-01"),
        "target": _patient("900002", "ALPHA", "2000-01-01"),
        "expected_match": False,
        "rationale": "sibling_negative (age_gap_years=0)",
    }
    # Different first name and an 8-year DOB gap: no rule should link them.
    true_sibling = {
        "case_id": "900003::900004::sibling",
        "source": _patient("900003", "BRAVO", "1990-01-01"),
        "target": _patient("900004", "CHARLIE", "1998-06-15"),
        "expected_match": False,
        "rationale": "sibling_negative (age_gap_years=8)",
    }
    old = _write_jsonl(tmp_path / "old.jsonl", [same_person_like, true_sibling])
    new = _write_jsonl(tmp_path / "new.jsonl", [true_sibling])

    exit_code = overlap.main(["--old", str(old), "--new", str(new)])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["fp_removed"] == ["900001::900002::sibling"]
    assert report["fp_kept"] == []
    assert report["new_confusion"]["fp"] == 0
