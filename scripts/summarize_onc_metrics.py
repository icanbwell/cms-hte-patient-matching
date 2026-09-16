"""Render the ONC regression tests' measured metrics as a GitHub Actions job
summary.

`tests/test_onc_regression.py` and `tests/test_onc_population_regression.py`
each write their measured metrics to `reports/onc_<tier>_metrics.json` (see
`tests/_onc_test_set.py`'s `write_metrics_report`) before asserting on them,
so the file exists whether the test passed or failed. This script reads both
files and prints a markdown table; the "Report ONC metrics" step in
`.github/workflows/build_and_test.yml` redirects that into
`$GITHUB_STEP_SUMMARY` and runs with `if: always()` so the table renders
even when a threshold regressed. A tier's file being absent (test skipped
for missing fixture data, or errored before reporting) is rendered as its
own state, not an error in this script - the gate is the test itself, this
is a reporting aid.

Usage: `uv run python scripts/summarize_onc_metrics.py`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"

PAIRS_METRICS_PATH = REPORTS_DIR / "onc_pairs_metrics.json"
POPULATION_METRICS_PATH = REPORTS_DIR / "onc_population_metrics.json"


def _read_metrics(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    result: Dict[str, Any] = json.loads(path.read_text())
    return result


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _not_run_note(missing_files: str) -> str:
    return (
        f"_Not run - {missing_files} wasn't fetched, or the test errored "
        "before reporting. See the `tests` step's log._\n"
    )


def _pairs_section(metrics: Optional[Dict[str, Any]]) -> str:
    if metrics is None:
        return "### ONC pairs tier\n\n" + _not_run_note("`sample_labeled_pairs.jsonl`")

    passed = (
        metrics["recall"] >= metrics["recall_floor"]
        and metrics["fpr"] <= metrics["fpr_ceiling"]
    )
    lines = [
        "### ONC pairs tier",
        "",
        f"{'✅' if passed else '❌'} n={metrics['n']} "
        f"(tp={metrics['tp']} fp={metrics['fp']} tn={metrics['tn']} fn={metrics['fn']}, "
        f"{metrics['extraction_errors']} extraction errors)",
        "",
        "| Metric | Value | Threshold |",
        "|---|---|---|",
        f"| Recall | {_fmt(metrics['recall'])} | ≥ {_fmt(metrics['recall_floor'])} |",
        f"| FPR | {_fmt(metrics['fpr'])} | ≤ {_fmt(metrics['fpr_ceiling'])} |",
        f"| Precision (not gated - see test docstring) | {_fmt(metrics['precision'])} | - |",
        "",
        "<details><summary>By rationale category</summary>",
        "",
        "| Category | tp | fp | tn | fn |",
        "|---|---|---|---|---|",
    ]
    for category, counts in sorted(metrics["by_category"].items()):
        lines.append(
            f"| {category} | {counts['tp']} | {counts['fp']} | {counts['tn']} | {counts['fn']} |"
        )
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def _population_section(metrics: Optional[Dict[str, Any]]) -> str:
    if metrics is None:
        return "### ONC population tier\n\n" + _not_run_note(
            "`population_queries.jsonl`/`population_candidates.jsonl`"
        )

    passed = (
        metrics["precision"] >= metrics["precision_floor"]
        and metrics["recall"] >= metrics["recall_floor"]
        and metrics["fpr"] <= metrics["fpr_ceiling"]
        and metrics["f1"] >= metrics["f1_floor"]
    )
    lines = [
        "### ONC population tier",
        "",
        f"{'✅' if passed else '❌'} n_queries={metrics['n_queries']} "
        f"n_candidates={metrics['n_candidates']} n_evals={metrics['n_evals']} "
        f"(tp={metrics['tp']} fp={metrics['fp']} tn={metrics['tn']} fn={metrics['fn']}, "
        f"{metrics['extraction_errors']} extraction errors)",
        "",
        "| Metric | Value | Threshold |",
        "|---|---|---|",
        f"| Precision | {_fmt(metrics['precision'])} | ≥ {_fmt(metrics['precision_floor'])} |",
        f"| Recall | {_fmt(metrics['recall'])} | ≥ {_fmt(metrics['recall_floor'])} |",
        f"| FPR | {_fmt(metrics['fpr'])} | ≤ {_fmt(metrics['fpr_ceiling'])} |",
        f"| F1 | {_fmt(metrics['f1'])} | ≥ {_fmt(metrics['f1_floor'])} |",
        f"| Accuracy | {_fmt(metrics['accuracy'])} | - |",
        "",
    ]
    return "\n".join(lines)


def build_markdown(
    pairs_metrics: Optional[Dict[str, Any]],
    population_metrics: Optional[Dict[str, Any]],
) -> str:
    return (
        "## ONC regression test results\n\n"
        + _pairs_section(pairs_metrics)
        + "\n"
        + _population_section(population_metrics)
    )


def main() -> None:
    markdown = build_markdown(
        _read_metrics(PAIRS_METRICS_PATH), _read_metrics(POPULATION_METRICS_PATH)
    )
    print(markdown)


if __name__ == "__main__":
    main()
