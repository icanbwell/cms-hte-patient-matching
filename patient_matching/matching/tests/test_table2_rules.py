"""Tests for Table 2 rule definitions."""

import pytest

from patient_matching.matching.collision import APPROVAL_THRESHOLD
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
        under `C2-`-prefixed IDs, e.g. `C2-13`, to avoid colliding with
        Category 1's brand-new bare 13-16 - see test_rule_ids_disjoint_from_category_2
        below)."""
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

    def test_all_rules_clear_the_approval_threshold(self) -> None:
        """Every Category 1 rule's fuzzy P(collision) is under the 2e-12
        approval threshold - the flat-rule equivalent of
        test_household_rules.py's Category 2 guard, added because Category
        1 had no such regression test (adversarial-review finding: rules
        01/10 were within ~2x of the bar even before v3.4.0 extended DOB*
        to them, and Table 3 publishes no separate fuzzy u-probability for
        "dob" - see matching_engine.py's DOB-fuzzy dispatch note for why
        that isn't priced into these figures)."""
        for rule in APPROVED_RULES:
            assert rule.p_collision_fuzzy <= APPROVAL_THRESHOLD, (
                f"Rule {rule.rule_id} breaches the approval threshold: "
                f"{rule.p_collision_fuzzy} > {APPROVAL_THRESHOLD}"
            )

    def test_field_composition_matches_the_v340_renumbering_table(self) -> None:
        """Locks each rule_id to its exact field/role composition, not just
        set membership - adversarial-review finding: the prior tests only
        checked that the *set* of IDs equals {01..30}
        (test_ids_are_the_expected_v340_category1_set) and spot-checked two
        rules (01, 22). A transposition during the manual renumbering (e.g.
        swapping two adjacent rules' bodies, or misassigning a field role)
        would have passed every other test in this file while silently
        corrupting the SS VII audit-record field for two rules. See
        docs/sessions/in_review/session_16.md for the source old->new
        mapping this locks in."""
        expected = {
            "01": {
                ("dob", "fuzzy_eligible"),
                ("first_name", "fuzzy_eligible"),
                ("last_name", "fuzzy_eligible"),
                ("street_line", "fuzzy_eligible"),
            },
            "02": {
                ("dob", "fuzzy_eligible"),
                ("first_name", "exact"),
                ("last_name", "fuzzy_eligible"),
                ("phone", "exact"),
            },
            "03": {
                ("dob", "fuzzy_eligible"),
                ("email", "exact"),
                ("first_name", "fuzzy_eligible"),
                ("last_name", "fuzzy_eligible"),
            },
            "04": {
                ("dob", "exact"),
                ("first_name", "fuzzy_eligible"),
                ("last_name", "exact"),
                ("ssn_last4", "exact"),
            },
            "05": {
                ("dob", "exact"),
                ("first_name", "exact"),
                ("last_name", "fuzzy_eligible"),
                ("ssn_last4", "exact"),
            },
            "06": {
                ("dob", "exact"),
                ("first_name", "fuzzy_eligible"),
                ("itin_last4", "exact"),
                ("last_name", "exact"),
            },
            "07": {
                ("dob", "exact"),
                ("first_name", "exact"),
                ("itin_last4", "exact"),
                ("last_name", "fuzzy_eligible"),
            },
            "08": {("dob", "exact"), ("first_name", "exact"), ("mbi", "exact")},
            "09": {("dob", "exact"), ("first_name", "exact"), ("legal_id", "exact")},
            "10": {
                ("dob", "fuzzy_eligible"),
                ("last_name", "fuzzy_eligible"),
                ("legal_id", "exact"),
            },
            "11": {("dob", "exact"), ("first_name", "exact"), ("phone", "exact")},
            "12": {("dob", "exact"), ("email", "exact"), ("first_name", "exact")},
            "13": {("first_name", "exact"), ("phone", "exact"), ("ssn_last4", "exact")},
            "14": {
                ("first_name", "exact"),
                ("itin_last4", "exact"),
                ("phone", "exact"),
            },
            "15": {("email", "exact"), ("first_name", "exact"), ("ssn_last4", "exact")},
            "16": {
                ("email", "exact"),
                ("first_name", "exact"),
                ("itin_last4", "exact"),
            },
            "17": {("mbi", "exact"), ("phone", "exact")},
            "18": {("legal_id", "exact"), ("phone", "exact")},
            "19": {("email", "exact"), ("mbi", "exact")},
            "20": {("email", "exact"), ("legal_id", "exact")},
            "21": {("legal_id", "exact"), ("mbi", "exact")},
            "22": {("namespace_id", "exact")},
            "23": {
                ("dob", "exact"),
                ("first_name", "exact"),
                ("insurance_member_id", "exact"),
            },
            "24": {
                ("dob", "fuzzy_eligible"),
                ("insurance_member_id", "exact"),
                ("last_name", "fuzzy_eligible"),
            },
            "25": {("insurance_member_id", "exact"), ("phone", "exact")},
            "26": {("email", "exact"), ("insurance_member_id", "exact")},
            "27": {
                ("dob", "exact"),
                ("first_name", "fuzzy_eligible"),
                ("insurance_subscriber_id", "exact"),
                ("last_name", "exact"),
            },
            "28": {
                ("dob", "exact"),
                ("first_name", "exact"),
                ("insurance_subscriber_id", "exact"),
                ("last_name", "fuzzy_eligible"),
            },
            "29": {
                ("first_name", "fuzzy_eligible"),
                ("last_name", "fuzzy_eligible"),
                ("phone", "exact"),
                ("zip_code", "exact"),
            },
            "30": {
                ("dob", "exact"),
                ("last_name", "fuzzy_eligible"),
                ("phone", "exact"),
            },
        }
        actual = {
            rule.rule_id: {(f.name, f.role.value) for f in rule.fields}
            for rule in APPROVED_RULES
        }
        assert actual == expected

    def test_dob_fuzzy_extended_to_exactly_the_intended_rules(self) -> None:
        """v3.4.0 extends DOB* from rule 24 alone to {01, 02, 03, 10, 24} -
        pin the exact set so a future copy-paste (e.g. onto rule 30's
        near-identical Last Name*+DOB+Phone) doesn't silently widen or
        narrow it unnoticed."""
        from patient_matching.matching.table2_rules import DOB

        dob_fuzzy_rule_ids = {
            rule.rule_id
            for rule in APPROVED_RULES
            for f in rule.fields
            if f.name == DOB and f.role == FieldRole.FUZZY_ELIGIBLE
        }
        assert dob_fuzzy_rule_ids == {"01", "02", "03", "10", "24"}
