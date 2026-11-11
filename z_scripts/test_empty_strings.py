"""Tests for the shared empty-string stripper used by the helix comparison scripts."""

from __future__ import annotations

from typing import Any

import pytest

from z_scripts.empty_strings import (
    is_empty_str,
    parse_with_empty_string_fallback,
    strip_empty_strings,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", True), ("   ", True), ("\t\n", True), ("x", False), (" x ", False)]
    + [(None, False), (0, False), ([], False), ({}, False)],
)
def test_is_empty_str_is_true_only_for_blank_strings(
    value: Any, expected: bool
) -> None:
    assert is_empty_str(value) is expected


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ({"city": "", "name": "x"}, {"name": "x"}),
        ({"city": "  ", "name": "x"}, {"name": "x"}),
        ({"a": {"b": "", "c": "keep"}}, {"a": {"c": "keep"}}),
        ({"given": ["Ann", "", " "]}, {"given": ["Ann"]}),
        (
            {"address": [{"city": "", "line": ["1 Example Way", ""]}]},
            {"address": [{"line": ["1 Example Way"]}]},
        ),
        ({"n": 0, "flag": False, "none": None}, {"n": 0, "flag": False, "none": None}),
        ("not a container", "not a container"),
    ],
)
def test_strip_empty_strings_drops_blank_strings_at_every_depth(
    raw: Any, cleaned: Any
) -> None:
    assert strip_empty_strings(raw) == cleaned


def test_strip_empty_strings_does_not_mutate_its_input() -> None:
    raw = {"a": {"b": ""}, "c": ["", "x"]}

    strip_empty_strings(raw)

    assert raw == {"a": {"b": ""}, "c": ["", "x"]}


class _Rejects(ValueError):
    """Stands in for a pydantic ValidationError (a ValueError in v1 and v2)."""


def _parse_rejecting_blanks(raw: dict[str, Any]) -> dict[str, Any]:
    if any(is_empty_str(v) for v in raw.values()):
        raise _Rejects("blank string")
    return raw


@pytest.mark.parametrize(
    ("raw", "expected_obj", "expected_retries"),
    [
        ({"name": "x"}, {"name": "x"}, 0),
        ({"name": "x", "city": ""}, {"name": "x"}, 1),
    ],
)
def test_parse_with_empty_string_fallback_retries_only_when_strict_parse_fails(
    raw: dict[str, Any], expected_obj: dict[str, Any], expected_retries: int
) -> None:
    retries: list[bool] = []
    obj = parse_with_empty_string_fallback(
        _parse_rejecting_blanks, raw, on_retry=lambda: retries.append(True)
    )
    assert obj == expected_obj
    assert len(retries) == expected_retries


def test_parse_with_empty_string_fallback_reraises_but_still_counts_a_failed_retry() -> (
    None
):
    def always_invalid(raw: dict[str, Any]) -> dict[str, Any]:
        raise _Rejects("still invalid")

    retries: list[bool] = []
    with pytest.raises(_Rejects):
        parse_with_empty_string_fallback(
            always_invalid, {"city": ""}, on_retry=lambda: retries.append(True)
        )
    assert len(retries) == 1


def test_parse_with_empty_string_fallback_does_not_retry_other_errors() -> None:
    calls: list[dict[str, Any]] = []

    def broken(raw: dict[str, Any]) -> dict[str, Any]:
        calls.append(raw)
        raise RuntimeError("not a validation problem")

    with pytest.raises(RuntimeError):
        parse_with_empty_string_fallback(broken, {"city": ""})
    assert len(calls) == 1
