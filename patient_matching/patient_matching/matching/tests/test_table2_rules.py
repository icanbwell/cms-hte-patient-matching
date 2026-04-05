"""Tests for Table 2 rule definitions."""

import pytest

from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    FieldRole,
    MatchingRule,
    RuleField,
)


class TestApprovedRules:
    """Verify the integrity of the 26 approved rule definitions."""

    def test_total_count(self):
        assert len(APPROVED_RULES) == 26

    def test_unique_rule_ids(self):
        ids = [r.rule_id for r in APPROVED_RULES]
        assert len(ids) == len(set(ids))

    def test_sequential_ids(self):
        for i, rule in enumerate(APPROVED_RULES, start=1):
            assert rule.rule_id == f"{i:02d}"

    def test_all_rules_have_fields(self):
        for rule in APPROVED_RULES:
            assert len(rule.fields) >= 1, f"Rule {rule.rule_id} has no fields"

    def test_all_rules_have_description(self):
        for rule in APPROVED_RULES:
            assert rule.description, f"Rule {rule.rule_id} has no description"

    def test_max_fuzzy_fields_non_negative(self):
        for rule in APPROVED_RULES:
            assert rule.max_fuzzy_fields >= 0

    def test_rule_01_has_4_fields_2_fuzzy(self):
        r = APPROVED_RULES[0]
        assert r.rule_id == "01"
        assert len(r.fields) == 4
        assert r.max_fuzzy_fields == 2
        fuzzy_count = sum(
            1 for f in r.fields if f.role == FieldRole.FUZZY_ELIGIBLE
        )
        assert fuzzy_count == 3  # first_name*, last_name*, street_line*

    def test_rule_26_namespace_id_only(self):
        r = APPROVED_RULES[25]
        assert r.rule_id == "26"
        assert len(r.fields) == 1
        assert r.fields[0].name == "namespace_id"
        assert r.max_fuzzy_fields == 0

    def test_rules_are_frozen(self):
        rule = APPROVED_RULES[0]
        with pytest.raises(AttributeError):
            rule.rule_id = "99"

    def test_p_collision_values(self):
        for rule in APPROVED_RULES:
            assert rule.p_collision_exact >= 0.0
            if rule.max_fuzzy_fields > 0:
                assert rule.p_collision_fuzzy >= rule.p_collision_exact
