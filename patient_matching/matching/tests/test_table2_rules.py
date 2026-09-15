"""Tests for Table 2 rule definitions."""

import pytest

from patient_matching.matching.household_rules import CATEGORY_2_RULES
from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    FieldRole,
)


class TestApprovedRules:
    """Verify the integrity of the flat (Category 1) rule definitions.

    30 rules, numbered 01-30 with no gaps per CMS v3.4.0's renumbering
    (session 16). Pre-v3.4.0, this set used the v3.2.2/v3.3 numbering
    (01-12, 17-33, 36, with 13-16 removed to Category 2). v3.4.0's clean
    renumbering reassigns bare 13-16 to brand-new flat content (First
    Name+Phone/Email+SSN/ITIN Last4) - unrelated to Category 2's rules,
    which now carry a `C2-` prefix specifically to avoid this collision
    (household_rules.py); see docs/sessions/in_review/session_16.md for the
    full old->new mapping and that decision's rationale.
    """

    def test_total_count(self) -> None:
        assert len(APPROVED_RULES) == 30

    def test_unique_rule_ids(self) -> None:
        ids = [r.rule_id for r in APPROVED_RULES]
        assert len(ids) == len(set(ids))

    def test_ids_are_the_expected_v340_category1_set(self) -> None:
        """v3.4.0 renumbers Category 1 into a clean, gapless 01-30 sequence -
        no gaps left for 13-16 (which live in household_rules.CATEGORY_2_RULES
        under those same IDs, unchanged by this renumbering)."""
        expected = {f"{i:02d}" for i in range(1, 31)}
        actual = {r.rule_id for r in APPROVED_RULES}
        assert actual == expected

    def test_rule_ids_disjoint_from_category_2(self) -> None:
        """Category 1's bare 13-16 (new v3.4.0 flat content) must never
        collide with Category 2's C2-13..C2-16 (household+individual
        pairings) - the two containers' rule_ids feed the same audit-record
        field (SS VII "Table 2 combination evaluated"), so an accidental
        overlap would make that field ambiguous."""
        category1_ids = {r.rule_id for r in APPROVED_RULES}
        category2_ids = {r.rule_id for r in CATEGORY_2_RULES}
        assert not category1_ids & category2_ids

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
        # max_fuzzy_fields caps simultaneous *string*-fuzzy fields for scoring
        # purposes; DOB's +/-1 day tolerance (v3.4.0) doesn't count against it
        # (see matching_engine.py's DOB-fuzzy dispatch note), so this stays 2
        # even though 4 fields are now marked fuzzy-eligible below.
        assert r.max_fuzzy_fields == 2
        fuzzy_count = sum(1 for f in r.fields if f.role == FieldRole.FUZZY_ELIGIBLE)
        assert fuzzy_count == 4  # first_name*, last_name*, dob*, street_line*

    def test_rule_22_namespace_id_only(self) -> None:
        r = next(r for r in APPROVED_RULES if r.rule_id == "22")
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
