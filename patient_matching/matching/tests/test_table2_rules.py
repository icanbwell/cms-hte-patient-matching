"""Tests for Table 2 rule definitions."""

import pytest

from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    FieldRole,
)


class TestApprovedRules:
    """Verify the integrity of the flat (Category 1) rule definitions.

    30 rules: the original 26 minus 13/14/15/16 (amended into Category 2 -
    see household_rules.py), plus new rules 27-33 and 36 (session 6).
    """

    def test_total_count(self) -> None:
        assert len(APPROVED_RULES) == 30

    def test_unique_rule_ids(self) -> None:
        ids = [r.rule_id for r in APPROVED_RULES]
        assert len(ids) == len(set(ids))

    def test_ids_are_the_expected_v33_category1_set(self) -> None:
        """IDs are no longer sequential - 13-16 were removed (amended into
        Category 2) and 27-33/36 were added, leaving gaps."""
        expected = {f"{i:02d}" for i in list(range(1, 13)) + list(range(17, 34)) + [36]}
        actual = {r.rule_id for r in APPROVED_RULES}
        assert actual == expected

    def test_13_through_16_are_not_in_the_flat_rule_set(self) -> None:
        """13-16 moved to household_rules.CATEGORY_2_RULES - confirm the old
        3-field flat literal is gone, not just shadowed."""
        ids = {r.rule_id for r in APPROVED_RULES}
        assert not ids & {"13", "14", "15", "16"}

    def test_all_rules_have_fields(self) -> None:
        for rule in APPROVED_RULES:
            assert len(rule.fields) >= 1, f"Rule {rule.rule_id} has no fields"

    def test_all_rules_have_description(self) -> None:
        for rule in APPROVED_RULES:
            assert rule.description, f"Rule {rule.rule_id} has no description"

    def test_max_fuzzy_fields_non_negative(self) -> None:
        for rule in APPROVED_RULES:
            assert rule.max_fuzzy_fields >= 0

    def test_rule_01_has_4_fields_2_fuzzy(self) -> None:
        r = APPROVED_RULES[0]
        assert r.rule_id == "01"
        assert len(r.fields) == 4
        assert r.max_fuzzy_fields == 2
        fuzzy_count = sum(1 for f in r.fields if f.role == FieldRole.FUZZY_ELIGIBLE)
        assert fuzzy_count == 3  # first_name*, last_name*, street_line*

    def test_rule_26_namespace_id_only(self) -> None:
        r = next(r for r in APPROVED_RULES if r.rule_id == "26")
        assert len(r.fields) == 1
        assert r.fields[0].name == "namespace_id"
        assert r.max_fuzzy_fields == 0

    def test_rules_are_frozen(self) -> None:
        rule = APPROVED_RULES[0]
        with pytest.raises(AttributeError):
            rule.rule_id = "99"  # type: ignore[misc]

    def test_p_collision_values(self) -> None:
        for rule in APPROVED_RULES:
            assert rule.p_collision_exact >= 0.0
            if rule.max_fuzzy_fields > 0:
                assert rule.p_collision_fuzzy >= rule.p_collision_exact
