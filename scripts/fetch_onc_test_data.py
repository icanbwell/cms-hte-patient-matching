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

Fetches by commit SHA, not by the tag name, even though the tag is what a
human bumps: git tags are mutable refs that can be force-moved to point at a
different commit upstream, which would silently defeat the entire point of
pinning - a data-version change is supposed to show up here as a one-line,
reviewable diff, not happen invisibly on the other side of a tag.

Usage: `make fetch-onc-data`, or directly:
    uv run python scripts/fetch_onc_test_data.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# The tag to fetch comes from the ONC_TEST_SET_TAG env var (the Makefile supplies the
# checked-in default, so bumping the version is a one-line diff there; override per run
# with `ONC_TEST_SET_TAG=<tag> make fetch-onc-data`). The tag is resolved to its commit
# SHA at fetch time and the files are fetched by SHA, since a git tag is a mutable ref.
SOURCE_REPO = "icanbwell/cms-hte-patient-matching-test-set"
TAG_ENV_VAR = "ONC_TEST_SET_TAG"
REPO_URL = f"https://github.com/{SOURCE_REPO}"


def get_source_tag() -> str:
    tag = os.environ.get(TAG_ENV_VAR, "").strip()
    if not tag:
        raise RuntimeError(
            f"{TAG_ENV_VAR} is not set. Run via `make fetch-onc-data` (which defaults "
            f"it) or set it to a tag of {SOURCE_REPO}, e.g. {TAG_ENV_VAR}=0.0.3"
        )
    return tag


def resolve_commit(tag: str) -> str:
    """Resolve `tag` to a commit SHA (peeling annotated tags to their commit)."""
    result = subprocess.run(
        ["git", "ls-remote", REPO_URL, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-remote {REPO_URL} failed: {result.stderr.strip()}")
    shas = {}
    for line in result.stdout.splitlines():
        line_sha, ref = line.split("\t")
        shas[ref] = line_sha
    sha = shas.get(f"refs/tags/{tag}^{{}}") or shas.get(f"refs/tags/{tag}")
    if not sha:
        raise RuntimeError(f"Tag {tag!r} not found in {SOURCE_REPO}")
    return sha


def base_url(commit: str) -> str:
    """Return the raw-content base URL for the test-set cases at `commit`."""
    return f"https://raw.githubusercontent.com/{SOURCE_REPO}/{commit}/evaluation/cases"


FILES = (
    "sample_labeled_pairs.jsonl",
    "population_queries.jsonl",
    "population_candidates.jsonl",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = REPO_ROOT / "tests" / "fixtures" / "onc"

CURL_RETRY_COUNT = "3"
CURL_RETRY_DELAY_SECONDS = "2"
CURL_MAX_TIME_SECONDS = "60"


def fetch(filename: str, commit: str, tag: str) -> None:
    url = f"{base_url(commit)}/{filename}"
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
            CURL_RETRY_COUNT,
            "--retry-delay",
            CURL_RETRY_DELAY_SECONDS,
            "--max-time",
            CURL_MAX_TIME_SECONDS,
            "--output",
            str(dest),
            url,
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to fetch {url} (curl exit {result.returncode}). Confirm "
            f"commit {commit!r} (tag {tag!r}) still exists "
            f"at github.com/{SOURCE_REPO}."
        )
    if dest.stat().st_size == 0:
        raise RuntimeError(f"{url} downloaded to an empty file")


def main() -> None:
    tag = get_source_tag()
    commit = resolve_commit(tag)
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        fetch(filename, commit, tag)
    print(f"Done. Fetched {len(FILES)} files from {tag!r} ({commit}) into {DEST_DIR}")


if __name__ == "__main__":
    main()
