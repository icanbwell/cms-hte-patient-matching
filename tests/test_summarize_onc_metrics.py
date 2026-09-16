"""Tests for `scripts/summarize_onc_metrics.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.summarize_onc_metrics as summarize_onc_metrics

PASSING_PAIRS_METRICS = {
    "n": 6290,
    "tp": 5830,
    "fp": 2,
    "tn": 288,
    "fn": 170,
    "recall": 0.9717,
    "fpr": 0.0069,
    "precision": 0.9997,
    "recall_floor": 0.95,
    "fpr_ceiling": 0.01,
    "extraction_errors": 0,
    "by_category": {
        "fuzzy_variant": {"tp": 100, "fp": 1, "tn": 10, "fn": 5},
        "normalization_edge_case": {"tp": 200, "fp": 0, "tn": 20, "fn": 2},
    },
}

PASSING_POPULATION_METRICS = {
    "n_queries": 2000,
    "n_candidates": 8016,
    "n_evals": 80000,
    "tp": 5830,
    "fp": 6,
    "tn": 73994,
    "fn": 170,
    "precision": 0.9990,
    "recall": 0.9717,
    "fpr": 0.0001,
    "accuracy": 0.9978,
    "f1": 0.9851,
    "precision_floor": 0.99,
    "recall_floor": 0.95,
    "fpr_ceiling": 0.001,
    "f1_floor": 0.97,
    "extraction_errors": 0,
}


def test_read_metrics_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert summarize_onc_metrics._read_metrics(tmp_path / "missing.json") is None


def test_build_markdown_reports_not_run_when_both_tiers_missing() -> None:
    markdown = summarize_onc_metrics.build_markdown(None, None)
    assert "Not run" in markdown
    assert markdown.count("Not run") == 2


def test_build_markdown_shows_pass_when_pairs_tier_within_thresholds() -> None:
    markdown = summarize_onc_metrics.build_markdown(PASSING_PAIRS_METRICS, None)
    assert "✅" in markdown
    assert "❌" not in markdown
    assert "0.9717" in markdown
    assert "fuzzy_variant" in markdown


def test_build_markdown_shows_fail_when_pairs_recall_below_floor() -> None:
    failing = {**PASSING_PAIRS_METRICS, "recall": 0.80}
    markdown = summarize_onc_metrics.build_markdown(failing, None)
    assert "### ONC pairs tier" in markdown
    pairs_section = markdown.split("### ONC population tier")[0]
    assert "❌" in pairs_section


def test_build_markdown_shows_fail_when_pairs_fpr_above_ceiling() -> None:
    failing = {**PASSING_PAIRS_METRICS, "fpr": 0.5}
    markdown = summarize_onc_metrics.build_markdown(failing, None)
    pairs_section = markdown.split("### ONC population tier")[0]
    assert "❌" in pairs_section


def test_build_markdown_shows_pass_when_population_tier_within_thresholds() -> None:
    markdown = summarize_onc_metrics.build_markdown(None, PASSING_POPULATION_METRICS)
    population_section = markdown.split("### ONC population tier")[1]
    assert "✅" in population_section
    assert "0.9990" in population_section


def test_build_markdown_shows_fail_when_population_f1_below_floor() -> None:
    failing = {**PASSING_POPULATION_METRICS, "f1": 0.5}
    markdown = summarize_onc_metrics.build_markdown(None, failing)
    population_section = markdown.split("### ONC population tier")[1]
    assert "❌" in population_section


def test_main_prints_markdown_built_from_reports_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    monkeypatch.setattr(summarize_onc_metrics, "REPORTS_DIR", tmp_path)
    pairs_path = tmp_path / "onc_pairs_metrics.json"
    monkeypatch.setattr(summarize_onc_metrics, "PAIRS_METRICS_PATH", pairs_path)
    monkeypatch.setattr(
        summarize_onc_metrics,
        "POPULATION_METRICS_PATH",
        tmp_path / "onc_population_metrics.json",
    )
    pairs_path.write_text(json.dumps(PASSING_PAIRS_METRICS))

    summarize_onc_metrics.main()

    captured = capsys.readouterr()
    assert "ONC regression test results" in captured.out
    assert "✅" in captured.out
    assert "Not run" in captured.out  # population tier's file was never written
