"""Tests for the matching helpers and rule scoping in scripts/lever_recall.py."""

from __future__ import annotations

import patient_matching.matching.field_comparator as fc
from scripts import lever_recall
from scripts.collision_feasibility import rule_views


def test_initial_match_is_symmetric_and_requires_a_full_name_on_one_side():
    assert lever_recall.initial_match({"s"}, {"stanley"})
    assert lever_recall.initial_match({"stanley"}, {"s"})
    assert not lever_recall.initial_match({"s"}, {"mary"})
    assert not lever_recall.initial_match({"s"}, {"s"})  # exact, not an initial match
    assert not lever_recall.initial_match({"stanley"}, {"stan"})


def test_dob_dl1_match_accepts_one_digit_swap_and_month_day_swap_only():
    assert lever_recall.dob_dl1_match({"2000-03-07"}, {"2000-03-17"})  # one digit
    assert lever_recall.dob_dl1_match({"2000-03-07"}, {"2000-07-03"})  # month/day swap
    assert lever_recall.dob_dl1_match({"2000-03-07"}, {"2000-03-08"})  # +1 day
    assert not lever_recall.dob_dl1_match({"2000-03-07"}, {"2001-04-17"})  # many edits


def test_dob_swap_match_does_not_accept_a_digit_replacement():
    assert lever_recall.dob_swap_match({"2000-03-07"}, {"2000-07-03"})
    assert not lever_recall.dob_swap_match({"2000-03-07"}, {"2000-03-17"})


def test_patch_is_scoped_and_restored():
    lever_recall._patch_for(("initial_all",))
    try:
        assert fc.FieldComparator.exact_match({"s"}, {"stanley"})
    finally:
        lever_recall._restore()
    assert not fc.FieldComparator.exact_match({"s"}, {"stanley"})
    assert fc.MIN_FUZZY_LENGTH == 5


def test_min4_lowers_the_fuzzy_minimum_only_while_patched():
    lever_recall._patch_for(("min4",))
    try:
        assert fc.FieldComparator.fuzzy_match({"mary"}, {"marx"})
    finally:
        lever_recall._restore()
    assert not fc.FieldComparator.fuzzy_match({"mary"}, {"marx"})


def test_unrestricted_assigns_each_lever_only_where_its_scope_applies():
    rules = rule_views()
    got = lever_recall.unrestricted(rules, ("initial_c2", "dob_dl1_fuzzy"))
    assert got["C2-13"] == (
        "initial_c2",
    )  # household: initial applies, DOB not fuzzy-eligible there
    assert got["02"] == (
        "dob_dl1_fuzzy",
    )  # flat rule with fuzzy DOB: only the DOB lever
    assert got["11"] == ()  # exact-DOB flat rule: neither


def test_restore_leaves_the_comparator_usable_as_instance_and_class_calls():
    # Regression: assigning the plain function back turned the staticmethods into
    # instance methods, so every later `engine._comparator.exact_match(q, c)` raised.
    lever_recall._patch_for(("initial_all", "dob_dl1_all"))
    lever_recall._restore()
    comparator = fc.FieldComparator()
    assert comparator.exact_match({"a"}, {"a"})
    assert fc.FieldComparator.exact_match({"a"}, {"a"})
    assert comparator.dob_fuzzy_match({"2000-03-07"}, {"2000-03-08"})
