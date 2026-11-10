"""Tests for the shared empty-string stripper used by the helix comparison scripts."""

from __future__ import annotations

from typing import Any

import pytest

from z_scripts.empty_strings import is_empty_str, strip_empty_strings


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
