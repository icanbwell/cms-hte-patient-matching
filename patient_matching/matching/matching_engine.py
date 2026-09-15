"""Core matching engine implementing CMS Patient Matching Proposal Table 2 rules.

Evaluates a query patient against candidates from the backend, applying:
  - All 30 approved Category 1 (flat) field combinations, plus Category 2
    (household/individual two-step) rules
  - Constrained fuzzy matching (Damerau-Levenshtein <= 1, min 5 chars),
    except DOB, which uses a +/-1 calendar day tolerance instead (v3.3)
  - Suffix conflict detection (B.5 — negates match)
  - Uniqueness check (must produce exactly 1 candidate)
"""

from __future__ import annotations

import importlib.resources
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .backend import FieldCriterion, MatchType, MatchingBackend
from .field_comparator import FieldComparator
from .field_extractor import FieldExtractor, PatientFields
from .household_rules import CATEGORY_2_RULES, HouseholdIndividualRule
from .match_result import MatchOutcome, MatchResult, RuleEvaluation
from .relationship_linkage_rules import RELATIONSHIP_LINKAGE_RULES
from .table2_rules import (
    APPROVED_RULES,
    DOB,
    FieldRole,
    MatchingRule,
    RuleField,
)

# All Category 2 (two-step) rules: the original 8 household+individual rules
# (household_rules.py) plus session 17's Relationship Linkage rules (C2-39,
# C2-40). Combined here rather than in household_rules.py itself to avoid a
# circular import (relationship_linkage_rules.py imports the Household/
# Individual/HouseholdIndividualRule types from household_rules.py).
_ALL_CATEGORY_2_RULES: tuple[HouseholdIndividualRule, ...] = (
    CATEGORY_2_RULES + RELATIONSHIP_LINKAGE_RULES
)

logger = logging.getLogger(__name__)


def _read_package_version() -> str:
    """Read the package version from the repo-root VERSION file.

    Falls back to "unknown" if VERSION can't be found (e.g. installed without
    the repo root present) rather than raising - a missing version string
    should never break matching.
    """
    try:
        package_dir = Path(str(importlib.resources.files("patient_matching")))
        version_path = package_dir.parent / "VERSION"
        return version_path.read_text().strip()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return "unknown"


_PACKAGE_VERSION = _read_package_version()


class MatchingEngine:
    """Evaluates Table 2 matching rules against backend candidates.

    Args:
        backend: The data-access backend for candidate retrieval.
        extractor: Field extractor. Default created if None.
        comparator: Field comparator. Default created if None.
        rules: Subset of Category 1 (flat) Table 2 rules to evaluate.
            Defaults to all 30.
        household_individual_rules: Subset of Category 2 (two-step
            household-then-individual) Table 2 rules to evaluate. Defaults
            to all 10 (the original 8 plus session 17's Relationship
            Linkage rules C2-39/C2-40). Independent of `rules` - passing a
            custom `rules` subset does not affect this default.
    """

    def __init__(
        self,
        *,
        backend: MatchingBackend,
        extractor: Optional[FieldExtractor] = None,
        comparator: Optional[FieldComparator] = None,
        rules: Optional[tuple[MatchingRule, ...]] = None,
        household_individual_rules: Optional[
            tuple[HouseholdIndividualRule, ...]
        ] = None,
    ) -> None:
        self._backend = backend
        self._extractor = extractor or FieldExtractor()
        self._comparator = comparator or FieldComparator()
        self._rules = rules if rules is not None else APPROVED_RULES
        self._household_individual_rules = (
            household_individual_rules
            if household_individual_rules is not None
            else _ALL_CATEGORY_2_RULES
        )

    async def match(self, query_patient: Dict[str, Any]) -> MatchResult:
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
            if not self._query_has_all_fields(query_fields, rule.fields):
                continue

            # Build criteria and search backend
            criteria = self._build_criteria_for_fields(query_fields, rule.fields)
            candidates = await self._backend.search(criteria)

            # Evaluate each candidate against this rule
            rule_matches: List[Dict[str, Any]] = []
            for candidate in candidates:
                cand_fields = self._extractor.extract(candidate)
                evaluation = self._evaluate_rule(rule, query_fields, cand_fields)
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

        for hh_rule in self._household_individual_rules:
            hh_matches, hh_evaluations = await self._evaluate_household_individual_rule(
                hh_rule, query_fields
            )
            all_evaluations.extend(hh_evaluations)
            if hh_matches:
                matched_patients_by_rule[hh_rule.rule_id] = hh_matches

        return self._build_result(matched_patients_by_rule, all_evaluations)

    def evaluate_pair(
        self, query_fields: PatientFields, candidate_fields: PatientFields
    ) -> bool:
        """Decide whether two already-extracted field sets match, per Table 2.

        This is the pure pairwise decision (no backend search, no uniqueness
        check) - the same logic match() applies per candidate, factored out so
        it can be used directly against precomputed pairs (see
        evaluation/onc_baseline.py) without needing a MatchingBackend at all.

        Known limitation: this checks a candidate's full known-value sets
        directly, while match()'s blocking (_build_criteria) only blocks on a
        single representative value per field before verification - so for a
        candidate with multiple values in a blocked field (e.g. multiple
        historical last names), the two paths are not guaranteed to agree.
        """
        for rule in self._rules:
            evaluation = self._evaluate_rule(rule, query_fields, candidate_fields)
            if evaluation.matched and not self._suffix_conflict(
                query_fields.suffixes, candidate_fields.suffixes
            ):
                return True

        for hh_rule in self._household_individual_rules:
            household_eval = self._verify_fields(
                rule_id=hh_rule.rule_id,
                fields=hh_rule.household_row.fields,
                max_fuzzy_fields=0,
                query_fields=query_fields,
                cand_fields=candidate_fields,
            )
            if not household_eval.matched:
                continue
            individual_eval = self._verify_fields(
                rule_id=hh_rule.rule_id,
                fields=hh_rule.individual_row.fields,
                max_fuzzy_fields=1,
                query_fields=query_fields,
                cand_fields=candidate_fields,
            )
            if individual_eval.matched and not self._suffix_conflict(
                query_fields.suffixes, candidate_fields.suffixes
            ):
                return True

        return False

    def _query_has_fields(
        self, query_fields: PatientFields, rule: MatchingRule
    ) -> bool:
        """Check if the query patient has all fields required by a rule."""
        return self._query_has_all_fields(query_fields, rule.fields)

    def _query_has_all_fields(
        self, query_fields: PatientFields, fields: tuple[RuleField, ...]
    ) -> bool:
        """Check if the query patient has all values needed for `fields`."""
        for rf in fields:
            if not query_fields.has_field(rf.name):
                return False
        return True

    def _build_criteria(
        self,
        query_fields: PatientFields,
        rule: MatchingRule,
    ) -> List[FieldCriterion]:
        """Build backend search criteria from a rule's fields."""
        return self._build_criteria_for_fields(query_fields, rule.fields)

    def _build_criteria_for_fields(
        self,
        query_fields: PatientFields,
        fields: tuple[RuleField, ...],
    ) -> List[FieldCriterion]:
        """Build backend search criteria from a field-role tuple.

        Uses exact-match criteria for blocking/candidate retrieval.
        The engine verifies fuzzy matches locally after retrieval.
        """
        criteria: List[FieldCriterion] = []
        for rf in fields:
            values = query_fields.get_values(rf.name)
            if values:
                # Use the first value for backend blocking; the engine
                # will check all values during verification.
                primary_value = next(iter(values))
                if rf.role != FieldRole.FUZZY_ELIGIBLE:
                    match_type = MatchType.EXACT
                elif rf.name == DOB:
                    # DOB's fuzzy tolerance is +/-1 calendar day, not a
                    # string edit distance (see MatchType.DOB_TOLERANCE) -
                    # routing it through MatchType.FUZZY would block on
                    # Damerau-Levenshtein distance, which silently drops
                    # genuine +/-1-day matches at month/year boundaries and
                    # plain digit rollovers (e.g. "...-09"->"...-10").
                    match_type = MatchType.DOB_TOLERANCE
                else:
                    match_type = MatchType.FUZZY
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
        """Evaluate a single flat (Category 1) rule against a candidate."""
        return self._verify_fields(
            rule_id=rule.rule_id,
            fields=rule.fields,
            max_fuzzy_fields=rule.max_fuzzy_fields,
            query_fields=query_fields,
            cand_fields=cand_fields,
        )

    def _verify_fields(
        self,
        *,
        rule_id: str,
        fields: tuple[RuleField, ...],
        max_fuzzy_fields: int,
        query_fields: PatientFields,
        cand_fields: PatientFields,
    ) -> RuleEvaluation:
        """Field-by-field verification shared by flat rules and each step of
        a household/individual two-step rule.

        Returns a RuleEvaluation with field-by-field outcomes. Respects
        max_fuzzy_fields, except for DOB: CMS v3.3's +/-1 day DOB tolerance
        (field_comparator.dob_fuzzy_match) is a date-tolerance mechanism, not
        the generic Damerau-Levenshtein string-fuzzy mechanism
        max_fuzzy_fields' collision-probability budget was designed around -
        Table 3 has no separate fuzzy u-probability for "dob" (FIELD_U_PROBS's
        dob entry carries no fuzzy variant), so a rule combining DOB* with
        another starred field (e.g. rule 24's Last Name*+DOB*) only reflects
        ONE field's fuzzy multiplier in its published p_collision_fuzzy
        figure - confirmed empirically: it always matches the OTHER starred
        field going fuzzy, never DOB. Counting DOB against max_fuzzy_fields
        would incorrectly block that other field from also going fuzzy on
        the same evaluation. DOB fuzzy usage is still recorded in
        fuzzy_fields/match_type for audit purposes.
        """
        evaluation = RuleEvaluation(
            rule_id=rule_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=_PACKAGE_VERSION,
        )
        fuzzy_count = 0
        all_matched = True

        for rf in fields:
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

            if rf.role != FieldRole.FUZZY_ELIGIBLE:
                evaluation.field_outcomes[rf.name] = "no_match"
                all_matched = False
                continue

            if rf.name == DOB:
                if self._comparator.dob_fuzzy_match(q_values, c_values):
                    evaluation.field_outcomes[rf.name] = "fuzzy"
                    evaluation.fuzzy_fields.append(rf.name)
                else:
                    evaluation.field_outcomes[rf.name] = "no_match"
                    all_matched = False
                continue

            # Generic string-fuzzy fields count against max_fuzzy_fields.
            if max_fuzzy_fields > 0 and self._comparator.fuzzy_match(
                q_values, c_values
            ):
                fuzzy_count += 1
                if fuzzy_count <= max_fuzzy_fields:
                    evaluation.field_outcomes[rf.name] = "fuzzy"
                    evaluation.fuzzy_fields.append(rf.name)
                else:
                    evaluation.field_outcomes[rf.name] = "fuzzy_exceeded"
                    all_matched = False
                continue

            evaluation.field_outcomes[rf.name] = "no_match"
            all_matched = False

        evaluation.matched = all_matched
        if evaluation.matched:
            evaluation.match_type = "fuzzy" if evaluation.fuzzy_fields else "exact"

        return evaluation

    async def _evaluate_household_individual_rule(
        self,
        rule: HouseholdIndividualRule,
        query_fields: PatientFields,
    ) -> tuple[List[Dict[str, Any]], List[RuleEvaluation]]:
        """CMS v3.3.1 SS3-4 two-step resolution for one Category 2 rule.

        Step 1 narrows backend candidates to those verified against the
        household-tier fields (fields often shared across a family, e.g.
        Phone/SSN-Last-4) - this can legitimately surface multiple
        candidates (household members who share that field). Step 2
        verifies that narrowed set against the individual-tier fields
        (First Name + DOB) to identify which member(s), if any, is the
        person being sought.

        This deliberately reuses the engine's existing, UNMODIFIED
        cross-rule uniqueness/escalation logic in _build_result (via
        match()'s matched_patients_by_rule aggregation) for the final
        1/2/3+ decision, rather than adding a second, separate escalation
        mechanism for the household step itself - v3.3.1 SS4.1 describes
        the tiered check as "applied at each step instead of once," but
        building an independent household-step escalation signal would
        duplicate logic session_6.md's own Task 4d explicitly says not to
        duplicate. Two sequential field-verification narrowing passes
        (household, then individual) achieves the same practical effect
        for this repo's Definition of Done.
        """
        evaluations: List[RuleEvaluation] = []
        household_fields = rule.household_row.fields
        if not self._query_has_all_fields(query_fields, household_fields):
            return [], evaluations

        household_criteria = self._build_criteria_for_fields(
            query_fields, household_fields
        )
        household_candidates = await self._backend.search(household_criteria)

        household_matches: List[Dict[str, Any]] = []
        for candidate in household_candidates:
            cand_fields = self._extractor.extract(candidate)
            verification = self._verify_fields(
                rule_id=rule.rule_id,
                fields=household_fields,
                max_fuzzy_fields=0,
                query_fields=query_fields,
                cand_fields=cand_fields,
            )
            if verification.matched:
                household_matches.append(candidate)

        if not household_matches:
            return [], evaluations

        individual_fields = rule.individual_row.fields
        if not self._query_has_all_fields(query_fields, individual_fields):
            return [], evaluations

        resolved: List[Dict[str, Any]] = []
        for candidate in household_matches:
            cand_fields = self._extractor.extract(candidate)
            evaluation = self._verify_fields(
                rule_id=rule.rule_id,
                fields=individual_fields,
                max_fuzzy_fields=1,
                query_fields=query_fields,
                cand_fields=cand_fields,
            )
            evaluations.append(evaluation)

            if evaluation.matched and not self._suffix_conflict(
                query_fields.suffixes, cand_fields.suffixes
            ):
                resolved.append(candidate)
            elif evaluation.matched:
                evaluation.matched = False
                evaluation.negated_by_suffix = True

        return resolved, evaluations

    @staticmethod
    def _suffix_conflict(query_suffixes: Set[str], cand_suffixes: Set[str]) -> bool:
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
        seen_ids: set[str] = set()
        first_rule_id: Optional[str] = None
        first_match_type = "exact"

        for rule_id, patients in matched_by_rule.items():
            for p in patients:
                # Deduplicate by FHIR resource ID if available,
                # falling back to Python object identity
                pid = p.get("id", "") or str(id(p))
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    all_matched.append(p)
                    if first_rule_id is None:
                        first_rule_id = rule_id
                        # Find the evaluation for this rule
                        for ev in evaluations:
                            if ev.rule_id == rule_id and ev.matched:
                                first_match_type = ev.match_type
                                break

        # Uniqueness check: tiered per CMS v3.3 - 1 unique / 2 escalate / 3+ stricter threshold
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
        elif len(all_matched) == 2:
            return MatchResult(
                outcome=MatchOutcome.ESCALATE,
                matched_patients=all_matched,
                matched_rule_id=first_rule_id,
                match_type=first_match_type,
                is_unique=False,
                rule_evaluations=evaluations,
                candidate_count=len(all_matched),
            )
        else:
            # 3+ candidates: CMS v3.3 requires a stricter 1e-6 threshold here. This engine
            # doesn't yet compute live P(collision) (see session 5) - until it does, every
            # 3+-candidate case is conservatively treated as failing that stricter bar
            # (i.e. always AMBIGUOUS/decline), which is the safe default: it can only ever
            # cause an under-return, never a wrong-patient release. Session 5/6 should
            # replace this comment and wire in a real check without changing the branch
            # structure above.
            return MatchResult(
                outcome=MatchOutcome.AMBIGUOUS,
                matched_patients=all_matched,
                matched_rule_id=first_rule_id,
                match_type=first_match_type,
                is_unique=False,
                rule_evaluations=evaluations,
                candidate_count=len(all_matched),
            )
