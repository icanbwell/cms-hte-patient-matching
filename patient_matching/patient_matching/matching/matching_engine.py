"""Core matching engine implementing CMS Proposal v3.2.2 Table 2 rules.

Evaluates a query patient against candidates from the backend, applying:
  - All 26 approved field combinations
  - Constrained fuzzy matching (Damerau-Levenshtein <= 1, min 5 chars)
  - Suffix conflict detection (B.5 — negates match)
  - Uniqueness check (must produce exactly 1 candidate)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from .backend import FieldCriterion, MatchType, MatchingBackend
from .field_comparator import FieldComparator
from .field_extractor import FieldExtractor, PatientFields
from .match_result import MatchOutcome, MatchResult, RuleEvaluation
from .table2_rules import (
    APPROVED_RULES,
    FieldRole,
    MatchingRule,
)

logger = logging.getLogger(__name__)


class MatchingEngine:
    """Evaluates Table 2 matching rules against backend candidates.

    Args:
        backend: The data-access backend for candidate retrieval.
        extractor: Field extractor. Default created if None.
        comparator: Field comparator. Default created if None.
        rules: Subset of Table 2 rules to evaluate. Defaults to all 26.
    """

    def __init__(
        self,
        *,
        backend: MatchingBackend,
        extractor: Optional[FieldExtractor] = None,
        comparator: Optional[FieldComparator] = None,
        rules: Optional[tuple[MatchingRule, ...]] = None,
    ) -> None:
        self._backend = backend
        self._extractor = extractor or FieldExtractor()
        self._comparator = comparator or FieldComparator()
        self._rules = rules or APPROVED_RULES

    def match(self, query_patient: Dict[str, Any]) -> MatchResult:
        """Match a query patient against the backend.

        Iterates over all applicable Table 2 rules, retrieves candidates
        from the backend, verifies field-by-field, and returns the result.

        Args:
            query_patient: A normalized FHIR R4 Patient resource dict.

        Returns:
            A MatchResult with outcome, matched patients, and audit data.
        """
        query_fields = self._extractor.extract(query_patient)
        all_evaluations: List[RuleEvaluation] = []
        matched_patients_by_rule: Dict[str, List[Dict[str, Any]]] = {}

        for rule in self._rules:
            # Check if the query has all required fields for this rule
            if not self._query_has_fields(query_fields, rule):
                continue

            # Build criteria and search backend
            criteria = self._build_criteria(query_fields, rule)
            candidates = self._backend.search(criteria)

            # Evaluate each candidate against this rule
            rule_matches: List[Dict[str, Any]] = []
            for candidate in candidates:
                cand_fields = self._extractor.extract(candidate)
                evaluation = self._evaluate_rule(
                    rule, query_fields, cand_fields
                )
                all_evaluations.append(evaluation)

                if evaluation.matched:
                    # Check suffix conflict (B.5)
                    if self._suffix_conflict(
                        query_fields.suffixes, cand_fields.suffixes
                    ):
                        evaluation.matched = False
                        evaluation.negated_by_suffix = True
                    else:
                        rule_matches.append(candidate)

            if rule_matches:
                matched_patients_by_rule[rule.rule_id] = rule_matches

        return self._build_result(
            matched_patients_by_rule, all_evaluations
        )

    def _query_has_fields(
        self, query_fields: PatientFields, rule: MatchingRule
    ) -> bool:
        """Check if the query patient has all fields required by a rule."""
        for rf in rule.fields:
            if not query_fields.has_field(rf.name):
                return False
        return True

    def _build_criteria(
        self,
        query_fields: PatientFields,
        rule: MatchingRule,
    ) -> List[FieldCriterion]:
        """Build backend search criteria from a rule's fields.

        Uses exact-match criteria for blocking/candidate retrieval.
        The engine verifies fuzzy matches locally after retrieval.
        """
        criteria: List[FieldCriterion] = []
        for rf in rule.fields:
            values = query_fields.get_values(rf.name)
            if values:
                # Use the first value for backend blocking; the engine
                # will check all values during verification.
                primary_value = next(iter(values))
                match_type = (
                    MatchType.FUZZY
                    if rf.role == FieldRole.FUZZY_ELIGIBLE
                    else MatchType.EXACT
                )
                criteria.append(
                    FieldCriterion(
                        field_name=rf.name,
                        value=primary_value,
                        match_type=match_type,
                    )
                )
        return criteria

    def _evaluate_rule(
        self,
        rule: MatchingRule,
        query_fields: PatientFields,
        cand_fields: PatientFields,
    ) -> RuleEvaluation:
        """Evaluate a single rule against a single candidate.

        Returns a RuleEvaluation with field-by-field outcomes.
        Respects max_fuzzy_fields constraint.
        """
        evaluation = RuleEvaluation(rule_id=rule.rule_id)
        fuzzy_count = 0
        all_matched = True

        for rf in rule.fields:
            q_values = query_fields.get_values(rf.name)
            c_values = cand_fields.get_values(rf.name)

            if not q_values or not c_values:
                evaluation.field_outcomes[rf.name] = "missing"
                all_matched = False
                continue

            # Try exact match first
            if self._comparator.exact_match(q_values, c_values):
                evaluation.field_outcomes[rf.name] = "exact"
                continue

            # Try fuzzy if eligible
            if (
                rf.role == FieldRole.FUZZY_ELIGIBLE
                and rule.max_fuzzy_fields > 0
                and self._comparator.fuzzy_match(q_values, c_values)
            ):
                fuzzy_count += 1
                if fuzzy_count <= rule.max_fuzzy_fields:
                    evaluation.field_outcomes[rf.name] = "fuzzy"
                    evaluation.fuzzy_fields.append(rf.name)
                    continue
                else:
                    # Exceeded max fuzzy fields
                    evaluation.field_outcomes[rf.name] = "fuzzy_exceeded"
                    all_matched = False
                    continue

            # No match
            evaluation.field_outcomes[rf.name] = "no_match"
            all_matched = False

        evaluation.matched = all_matched
        if evaluation.matched:
            evaluation.match_type = (
                "fuzzy" if evaluation.fuzzy_fields else "exact"
            )

        return evaluation

    @staticmethod
    def _suffix_conflict(
        query_suffixes: Set[str], cand_suffixes: Set[str]
    ) -> bool:
        """Check for generational suffix conflict per B.5.

        If both sides have suffixes and no overlap, the match is negated.
        """
        if not query_suffixes or not cand_suffixes:
            return False
        return not bool(query_suffixes & cand_suffixes)

    @staticmethod
    def _build_result(
        matched_by_rule: Dict[str, List[Dict[str, Any]]],
        evaluations: List[RuleEvaluation],
    ) -> MatchResult:
        """Build final MatchResult applying uniqueness check."""
        if not matched_by_rule:
            return MatchResult(
                outcome=MatchOutcome.NO_MATCH,
                rule_evaluations=evaluations,
            )

        # Collect all unique matched patients across rules
        all_matched: List[Dict[str, Any]] = []
        seen_ids: set[int] = set()
        first_rule_id: Optional[str] = None
        first_match_type = "exact"

        for rule_id, patients in matched_by_rule.items():
            for p in patients:
                pid = id(p)
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    all_matched.append(p)
                    if first_rule_id is None:
                        first_rule_id = rule_id
                        # Find the evaluation for this rule
                        for ev in evaluations:
                            if (
                                ev.rule_id == rule_id
                                and ev.matched
                            ):
                                first_match_type = ev.match_type
                                break

        # Uniqueness check: must produce exactly 1 candidate
        if len(all_matched) == 1:
            return MatchResult(
                outcome=MatchOutcome.MATCH,
                matched_patients=all_matched,
                matched_rule_id=first_rule_id,
                match_type=first_match_type,
                is_unique=True,
                rule_evaluations=evaluations,
                candidate_count=len(all_matched),
            )
        else:
            # Ambiguous: 2+ candidates matched
            return MatchResult(
                outcome=MatchOutcome.AMBIGUOUS,
                matched_patients=all_matched,
                matched_rule_id=first_rule_id,
                match_type=first_match_type,
                is_unique=False,
                rule_evaluations=evaluations,
                candidate_count=len(all_matched),
            )
