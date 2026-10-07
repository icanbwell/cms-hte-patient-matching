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


COMMIT = "a" * 40
TAG = "9.9.9"


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
            fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl", COMMIT, TAG)


def test_fetch_raises_on_empty_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    (tmp_path / "sample_labeled_pairs.jsonl").write_bytes(b"")
    with patch.object(subprocess, "run", _mock_run(0)):
        with pytest.raises(RuntimeError, match="empty file"):
            fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl", COMMIT, TAG)


def test_fetch_succeeds_when_download_is_present_and_non_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    (tmp_path / "sample_labeled_pairs.jsonl").write_bytes(b"some data")
    with patch.object(subprocess, "run", _mock_run(0)):
        fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl", COMMIT, TAG)


def test_fetch_passes_safety_flags_and_correct_url_to_curl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", tmp_path)
    (tmp_path / "sample_labeled_pairs.jsonl").write_bytes(b"data")
    mock_run = _mock_run(0)
    with patch.object(subprocess, "run", mock_run):
        fetch_onc_test_data.fetch("sample_labeled_pairs.jsonl", COMMIT, TAG)

    cmd = mock_run.call_args[0][0]
    assert "--fail" in cmd
    assert cmd[cmd.index("--retry") + 1] == fetch_onc_test_data.CURL_RETRY_COUNT
    assert (
        cmd[cmd.index("--retry-delay") + 1]
        == fetch_onc_test_data.CURL_RETRY_DELAY_SECONDS
    )
    assert cmd[cmd.index("--max-time") + 1] == fetch_onc_test_data.CURL_MAX_TIME_SECONDS
    assert (
        cmd[-1] == f"{fetch_onc_test_data.base_url(COMMIT)}/sample_labeled_pairs.jsonl"
    )
    assert cmd[cmd.index("--output") + 1] == str(
        tmp_path / "sample_labeled_pairs.jsonl"
    )


def test_main_fetches_every_file_into_dest_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest_dir = tmp_path / "onc"
    monkeypatch.setattr(fetch_onc_test_data, "DEST_DIR", dest_dir)
    monkeypatch.setenv(fetch_onc_test_data.TAG_ENV_VAR, TAG)
    monkeypatch.setattr(fetch_onc_test_data, "resolve_commit", lambda tag: COMMIT)

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
    monkeypatch.setenv(fetch_onc_test_data.TAG_ENV_VAR, TAG)
    monkeypatch.setattr(fetch_onc_test_data, "resolve_commit", lambda tag: COMMIT)
    with patch.object(subprocess, "run", _mock_run(22)):
        with pytest.raises(RuntimeError):
            fetch_onc_test_data.main()


def test_base_url_pins_to_commit_sha_not_the_mutable_tag() -> None:
    # A git tag can be force-moved upstream to a different commit with no
    # trace in this repo's history; the fetch itself must pin to the commit
    # SHA the tag resolved to, not the tag name.
    assert COMMIT in fetch_onc_test_data.base_url(COMMIT)
    assert TAG not in fetch_onc_test_data.base_url(COMMIT)


def test_get_source_tag_requires_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(fetch_onc_test_data.TAG_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match="ONC_TEST_SET_TAG is not set"):
        fetch_onc_test_data.get_source_tag()
    monkeypatch.setenv(fetch_onc_test_data.TAG_ENV_VAR, " 0.0.3 ")
    assert fetch_onc_test_data.get_source_tag() == "0.0.3"


def _ls_remote(stdout: str, returncode: int = 0) -> MagicMock:
    return MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr="boom"
        )
    )


def test_resolve_commit_lightweight_tag() -> None:
    out = f"{COMMIT}\trefs/tags/{TAG}\n"
    with patch.object(subprocess, "run", _ls_remote(out)):
        assert fetch_onc_test_data.resolve_commit(TAG) == COMMIT


def test_resolve_commit_peels_annotated_tag() -> None:
    out = f"{'b' * 40}\trefs/tags/{TAG}\n{COMMIT}\trefs/tags/{TAG}^{{}}\n"
    with patch.object(subprocess, "run", _ls_remote(out)):
        assert fetch_onc_test_data.resolve_commit(TAG) == COMMIT


def test_resolve_commit_raises_when_tag_missing_or_ls_remote_fails() -> None:
    with patch.object(subprocess, "run", _ls_remote("")):
        with pytest.raises(RuntimeError, match="not found"):
            fetch_onc_test_data.resolve_commit(TAG)
    with patch.object(subprocess, "run", _ls_remote("", returncode=128)):
        with pytest.raises(RuntimeError, match="ls-remote"):
            fetch_onc_test_data.resolve_commit(TAG)
