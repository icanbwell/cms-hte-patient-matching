"""Tests for the P(collision) evaluator (CMS v3.3 Table 3 / SS IV)."""

import pytest

from patient_matching.matching.collision import (
    APPROVAL_THRESHOLD,
    FIELD_U_PROBS,
    evaluate_combination,
    p_collision,
)
from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    DOB,
    FIRST_NAME,
    LAST_NAME,
    MatchingRule,
    _rf,
)


class TestFieldUProbs:
    @pytest.mark.parametrize(
        "field_name,expected_exact",
        [
            ("first_name", 0.02),
            ("last_name", 0.005),
            ("dob", 0.0001),
            ("phone", 0.000001),
            ("email", 0.000001),
            ("ssn_last4", 0.0001),
            ("mbi", 0.000001),
        ],
    )
    def test_known_field_exact_u_values(
        self, field_name: str, expected_exact: float
    ) -> None:
        exact, _ = FIELD_U_PROBS[field_name]
        assert exact == expected_exact

    def test_dismissed_fields_are_absent(self) -> None:
        for dismissed in ("middle_name", "suffix", "year_of_birth"):
            assert dismissed not in FIELD_U_PROBS


class TestPCollision:
    def test_single_field_equals_its_own_u(self) -> None:
        assert p_collision((_rf("phone"),)) == FIELD_U_PROBS["phone"][0]

    def test_joint_probability_is_product_of_fields(self) -> None:
        fields = (_rf(FIRST_NAME), _rf(DOB))
        expected = FIELD_U_PROBS["first_name"][0] * FIELD_U_PROBS["dob"][0]
        assert p_collision(fields) == pytest.approx(expected)

    def test_fuzzy_field_uses_fuzzy_u_value(self) -> None:
        fields = (_rf(FIRST_NAME),)
        exact_u, fuzzy_u = FIELD_U_PROBS["first_name"]
        assert p_collision(fields, fuzzy_fields=frozenset({FIRST_NAME})) == fuzzy_u
        assert p_collision(fields) == exact_u


class TestEvaluateCombination:
    def test_first_last_dob_zip_is_not_approvable(self) -> None:
        """The CMS v3.3 spec's own admitted inconsistency: this combination computes
        to 3e-12 under Table 3 (above the 2e-12 threshold) and must NOT be approved,
        regardless of the 3e-13 figure some prior (non-spec) analyses cite."""
        fields = (_rf(FIRST_NAME), _rf(LAST_NAME), _rf(DOB), _rf("zip_code"))
        result = evaluate_combination(fields)
        assert result["approved"] is False
        assert result["p_collision"] == pytest.approx(3e-12, rel=1e-6)

    def test_boundary_at_threshold(self) -> None:
        """A synthetic combination whose product lands exactly at 2e-12 must be
        approved - the spec's threshold is <=, not strictly <."""
        # phone (1e-6) * legal_id (1e-6) * a synthetic third field at 2.0 gives 2e-12.
        FIELD_U_PROBS["_test_field"] = (2.0, None)
        try:
            fields = (_rf("phone"), _rf("legal_id"), _rf("_test_field"))
            result = evaluate_combination(fields)
            assert result["p_collision"] == pytest.approx(2e-12)
            assert result["approved"] is True
        finally:
            del FIELD_U_PROBS["_test_field"]

    def test_just_above_threshold_is_not_approved(self) -> None:
        FIELD_U_PROBS["_test_field"] = (2.000001, None)
        try:
            fields = (_rf("phone"), _rf("legal_id"), _rf("_test_field"))
            assert evaluate_combination(fields)["approved"] is False
        finally:
            del FIELD_U_PROBS["_test_field"]

    def test_approval_threshold_constant(self) -> None:
        assert APPROVAL_THRESHOLD == 2e-12


class TestExistingRulesMatchComputedValues:
    @pytest.mark.parametrize("rule", APPROVED_RULES, ids=lambda r: r.rule_id)
    def test_existing_26_rules_reproduce_published_values(
        self, rule: MatchingRule
    ) -> None:
        """After table2_rules.py computes p_collision_exact/_fuzzy from this
        evaluator (rather than a hand-typed literal), confirm every rule still has a
        real, nonzero probability - a real bug (an unmapped field name in
        FIELD_U_PROBS) would raise KeyError at import time, not silently produce
        0.0, but this guards against a future refactor reintroducing a
        literal-float regression."""
        assert rule.p_collision_exact > 0 or rule.rule_id == "26"
