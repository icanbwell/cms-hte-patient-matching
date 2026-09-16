"""Download the ONC-derived test data this repo's regression tests read.

Replaces the previous approach of committing these files into the repo (see
`tests/fixtures/onc/README.md` git history) - a committed copy silently drifts
from the source repo with no way to detect it. This script instead fetches a
pinned tagged release of `cms-hte-patient-matching-test-set` on demand, so the
data is never stale in git history and the pin is a one-line, reviewable diff
to bump instead of a multi-megabyte file diff.

Shells out to `curl` rather than using Python's own HTTP stack - both are
available everywhere this repo runs (local dev, GitHub Actions' ubuntu-latest),
and curl's `--retry` handles transient network blips without extra code here.

Usage: `make fetch-onc-data`, or directly:
    uv run python scripts/fetch_onc_test_data.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Bump deliberately, with a note of why, when the test-set repo cuts a new tag
# this repo should track. Resolves (as of this pin) to commit
# c2454c54be9d18155996dcc10d4fa259800236e1.
SOURCE_REPO = "icanbwell/cms-hte-patient-matching-test-set"
SOURCE_TAG = "0.0.1"

BASE_URL = (
    f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_TAG}/evaluation/cases"
)
FILES = (
    "sample_labeled_pairs.jsonl",
    "population_queries.jsonl",
    "population_candidates.jsonl",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = REPO_ROOT / "tests" / "fixtures" / "onc"


def fetch(filename: str) -> None:
    url = f"{BASE_URL}/{filename}"
    dest = DEST_DIR / filename
    print(f"Fetching {url} -> {dest}")
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--output",
            str(dest),
            url,
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to fetch {url} (curl exit {result.returncode}). Confirm "
            f"SOURCE_TAG={SOURCE_TAG!r} still exists at "
            f"github.com/{SOURCE_REPO}/tags."
        )
    if dest.stat().st_size == 0:
        raise RuntimeError(f"{url} downloaded to an empty file")


def main() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        fetch(filename)
    print(f"Done. Fetched {len(FILES)} files from tag {SOURCE_TAG!r} into {DEST_DIR}")


if __name__ == "__main__":
    main()
