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
    Verdict,
    classify,
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
