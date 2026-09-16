"""Tests for `scripts/fetch_onc_test_data.py`.

Mocks `subprocess.run` throughout - these exercise `fetch()`/`main()`'s own
control flow (the curl invocation, the returncode check, the empty-file
check, the commit-vs-tag pin) without hitting the network. The real download
is exercised by `make fetch-onc-data` itself, in CI and locally.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.fetch_onc_test_data as fetch_onc_test_data


def _mock_run(returncode: int) -> MagicMock:
    return MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=returncode)
    )


def test_fetch_raises_on_nonzero_curl_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    with patch.object(subprocess, "run", _mock_run(22)):
        with pytest.raises(RuntimeError, match="curl exit 22"):
            fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl")


def test_fetch_raises_on_empty_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    (tmp_path / "sample_labeled_pairs.jsonl").write_bytes(b"")
    with patch.object(subprocess, "run", _mock_run(0)):
        with pytest.raises(RuntimeError, match="empty file"):
            fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl")


def test_fetch_succeeds_when_download_is_present_and_non_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    (tmp_path / "sample_labeled_pairs.jsonl").write_bytes(b"some data")
    with patch.object(subprocess, "run", _mock_run(0)):
        fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl")


def test_fetch_passes_safety_flags_and_correct_url_to_curl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    (tmp_path / "sample_labeled_pairs.jsonl").write_bytes(b"data")
    mock_run = _mock_run(0)
    with patch.object(subprocess, "run", mock_run):
        fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl")

    cmd = mock_run.call_args[0][0]
    assert "--fail" in cmd
    assert cmd[cmd.index("--retry") + 1] == fetch_onc_test_data.CURL_RETRY_COUNT
    assert (
        cmd[cmd.index("--retry-delay") + 1]
        == fetch_onc_test_data.CURL_RETRY_DELAY_SECONDS
    )
    assert cmd[cmd.index("--max-time") + 1] == fetch_onc_test_data.CURL_MAX_TIME_SECONDS
    assert cmd[-1] == f"{fetch_onc_test_data.BASE_URL}/sample_labeled_pairs.jsonl"
    assert cmd[cmd.index("--output") + 1] == str(
        tmp_path / "sample_labeled_pairs.jsonl"
    )


def test_main_fetches_every_file_into_dest_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest_dir = tmp_path / "onc"
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", dest_dir)

    def fake_run(
        cmd: list[str], check: bool = False
    ) -> subprocess.CompletedProcess[bytes]:
        dest = Path(cmd[cmd.index("--output") + 1])
        dest.write_bytes(b"data")
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    with patch.object(subprocess, "run", side_effect=fake_run) as mock_run:
        fetch_onc_test_data.main()

    assert dest_dir.is_dir()
    assert mock_run.call_count == len(fetch_onc_test_data.FILES)
    for filename in fetch_onc_test_data.FILES:
        assert (dest_dir / filename).read_bytes() == b"data"


def test_main_stops_at_first_failing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest_dir = tmp_path / "onc"
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", dest_dir)
    with patch.object(subprocess, "run", _mock_run(22)):
        with pytest.raises(RuntimeError):
            fetch_onc_test_data.main()


def test_base_url_pins_to_commit_sha_not_the_mutable_tag() -> None:
    # A git tag can be force-moved upstream to a different commit with no
    # trace in this repo's history; the fetch itself must pin to the commit
    # SHA, not the tag name, or bumping SOURCE_TAG would stop being the
    # single reviewable diff this design relies on.
    assert fetch_onc_test_data.SOURCE_COMMIT in fetch_onc_test_data.BASE_URL
    assert fetch_onc_test_data.SOURCE_TAG not in fetch_onc_test_data.BASE_URL
