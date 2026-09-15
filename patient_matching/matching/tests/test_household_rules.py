"""Tests for the CMS v3.3.1 Household/Individual two-step rule definitions.

Every row and Category 2 rule's p_collision is checked against the source
figures transcribed in docs/sessions/completed/session_6.md - this is the
same "does the evaluator reproduce the published numbers" sanity check
session 5 ran for the original 26 rules.
"""

import pytest

from patient_matching.matching.household_rules import (
    CATEGORY_2_RULES,
    HOUSEHOLD_ROWS,
    INDIVIDUAL_ROWS,
    HouseholdRow,
    H_01,
    H_02,
    H_03,
    H_04,
    H_05,
    H_06,
    H_07,
    H_08,
    H_09,
    H_10,
    H_11,
    H_12,
    H_13,
    H_14,
    I_01,
    I_02,
    I_03,
)


class TestHouseholdRowFigures:
    @pytest.mark.parametrize(
        "row,expected",
        [
            (H_01, 1.0e-10),
            (H_02, 1.0e-10),
            (H_03, 3.0e-9),
            (H_04, 1.0e-10),
            (H_05, 1.0e-10),
            (H_06, 3.0e-9),
            (H_07, 1.0e-10),
            (H_08, 1.0e-10),
            (H_09, 3.0e-9),
            (H_10, 1.0e-12),
            (H_11, 1.0e-8),
            (H_12, 3.0e-10),
            (H_13, 3.0e-10),
            (H_14, 3.0e-11),
        ],
        ids=lambda v: v if isinstance(v, float) else v.row_id,
    )
    def test_household_row_reproduces_published_figure(
        self, row: HouseholdRow, expected: float
    ) -> None:
        assert row.p_collision == pytest.approx(expected, rel=1e-6)

    def test_all_14_rows_present(self) -> None:
        assert len(HOUSEHOLD_ROWS) == 14
        assert len({r.row_id for r in HOUSEHOLD_ROWS}) == 14


class TestIndividualRowFigures:
    def test_i01_exact_and_fuzzy(self) -> None:
        assert I_01.p_collision_exact == pytest.approx(2.0e-6, rel=1e-6)
        assert I_01.p_collision_fuzzy == pytest.approx(3.0e-6, rel=1e-6)

    def test_i02_single_figure(self) -> None:
        assert I_02.p_collision_exact == pytest.approx(1.0e-8, rel=1e-6)

    def test_i03_single_figure(self) -> None:
        assert I_03.p_collision_exact == pytest.approx(0.02, rel=1e-6)

    def test_all_3_rows_present(self) -> None:
        assert len(INDIVIDUAL_ROWS) == 3


class TestCategory2Rules:
    @pytest.mark.parametrize(
        "rule_id,expected_exact",
        [
            ("C2-13", 2.0e-16),
            ("C2-14", 2.0e-16),
            ("C2-15", 2.0e-16),
            ("C2-16", 2.0e-16),
            ("C2-34", 6.0e-16),
            ("C2-35", 6.0e-16),
            ("C2-37", 6.0e-17),
            ("C2-38", 2.0e-16),
        ],
    )
    def test_combined_p_collision_matches_published_figure(
        self, rule_id: str, expected_exact: float
    ) -> None:
        rule = next(r for r in CATEGORY_2_RULES if r.rule_id == rule_id)
        assert rule.p_collision_exact == pytest.approx(expected_exact, rel=1e-6)

    def test_all_8_rules_present(self) -> None:
        """rule_ids carry a C2- prefix (session 16) so they can't collide with
        Category 1's own 13-16, which v3.4.0 reassigns to unrelated flat rules."""
        ids = {r.rule_id for r in CATEGORY_2_RULES}
        assert ids == {
            "C2-13",
            "C2-14",
            "C2-15",
            "C2-16",
            "C2-34",
            "C2-35",
            "C2-37",
            "C2-38",
        }

    def test_all_rules_clear_the_approval_threshold(self) -> None:
        """Every Category 2 rule's combined P(collision) is well under 2e-12 -
        the source doc's own margin claim (3-4 orders of magnitude)."""
        for rule in CATEGORY_2_RULES:
            assert rule.p_collision_exact <= 2e-12

    def test_last_name_is_not_a_field_in_any_category_2_rule(self) -> None:
        """Rules 13-16's Last Name is advisory-only corroboration per
        v3.3.1 - it must never be a gating field (household or individual),
        or a data-quality Last Name difference would silently reintroduce
        the exact blended-family failure these rules exist to fix."""
        for rule in CATEGORY_2_RULES:
            all_fields = rule.household_row.fields + rule.individual_row.fields
            assert "last_name" not in {f.name for f in all_fields}
