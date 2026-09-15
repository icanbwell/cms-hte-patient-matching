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
    FIRST_NAME,
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

# Sentinel distinguishing "the query carries no persistent-identifier
# anchor" (defer to the next tiebreak) from "an anchor was present but
# didn't resolve" (None - a disqualifying result in its own right). See
# MatchingEngine._break_twin_tie_with_namespace_id.
_NO_ANCHOR = object()


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

    async def match(
        self,
        query_patient: Dict[str, Any],
        *,
        query_initiator: Optional[str] = None,
    ) -> MatchResult:
        """Match a query patient against the backend.

        Iterates over all applicable Table 2 rules, retrieves candidates
        from the backend, verifies field-by-field, and returns the result.

        Args:
            query_patient: A normalized FHIR R4 Patient resource dict.
            query_initiator: SS VII audit field (session 18) - an opaque,
                caller-supplied identifier for whoever/whatever issued this
                query. Not validated or derived by this library - see
                MatchResult.query_initiator's docstring for why.

        Returns:
            A MatchResult with outcome, matched patients, and audit data.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        query_fields = self._extractor.extract(query_patient)
        all_evaluations: List[RuleEvaluation] = []
        matched_patients_by_rule: Dict[str, List[Dict[str, Any]]] = {}
        any_rule_evaluable = False

        for rule in self._rules:
            # Check if the query has all required fields for this rule
            if not self._query_has_all_fields(query_fields, rule.fields):
                continue
            any_rule_evaluable = True

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

        excluded_ids: Set[str] = set()
        for hh_rule in self._household_individual_rules:
            if self._query_has_all_fields(query_fields, hh_rule.household_row.fields):
                any_rule_evaluable = True
            (
                hh_matches,
                hh_evaluations,
                hh_excluded,
            ) = await self._evaluate_household_individual_rule(hh_rule, query_fields)
            all_evaluations.extend(hh_evaluations)
            if hh_matches:
                matched_patients_by_rule[hh_rule.rule_id] = hh_matches
            excluded_ids.update(self._patient_id(p) for p in hh_excluded)

        return self._build_result(
            matched_patients_by_rule,
            all_evaluations,
            query_initiator=query_initiator,
            timestamp=timestamp,
            any_rule_evaluable=any_rule_evaluable,
            excluded_ids=excluded_ids,
        )

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
    ) -> tuple[List[Dict[str, Any]], List[RuleEvaluation], List[Dict[str, Any]]]:
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

        CMS v3.4.0 SS C.7 twin/multiple-birth handling (session 19): twins
        share every household-tier field by definition, plus an exact DOB -
        First Name is the only field doing individuating work. When the
        household step surfaces multiple candidates sharing an identical
        DOB, First Name comparison is forced exact (never fuzzy) for those
        specific candidates (not the whole household - see
        `_shared_dob_values`), and a 2-candidate tie remaining after that is
        given one last-resort middle-name tiebreak, preceded by a
        persistent-identifier anchor check, before falling through to the
        base document's existing 1/2/3+ escalation.

        A tiebreak that positively resolves the tie is reported back to
        match() as an exclusion (the third tuple element): the losing
        candidate must not reappear in the final result merely because some
        other, less specific rule also matched it - see match()'s use of
        `excluded_ids` and this method's own note below for why that
        couldn't be left to _build_result's ordinary union.
        """
        evaluations: List[RuleEvaluation] = []
        household_fields = rule.household_row.fields
        if not self._query_has_all_fields(query_fields, household_fields):
            return [], evaluations, []

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
            return [], evaluations, []

        individual_fields = rule.individual_row.fields
        if not self._query_has_all_fields(query_fields, individual_fields):
            return [], evaluations, []

        # SS C.7(1): force exact First Name for any candidate whose own DOB
        # is shared with >=1 other household-tier match - the normal
        # one-edit fuzzy tolerance could otherwise conflate two genuinely
        # different but similar names (e.g. "Jayden" and "Jaden") between
        # twins/siblings. Scoped per-candidate (not household-wide): a
        # third household member whose DOB isn't part of any shared pair
        # (e.g. a parent) must keep ordinary fuzzy First Name matching -
        # forcing it for them too would regress the common non-twin case
        # whenever a twin pair happens to share their household.
        shared_dobs = self._shared_dob_values(household_matches)
        forced_individual_fields = self._force_exact_first_name(individual_fields)

        resolved: List[Dict[str, Any]] = []
        for candidate in household_matches:
            cand_fields = self._extractor.extract(candidate)
            fields_for_candidate = (
                forced_individual_fields
                if cand_fields.dob & shared_dobs
                else individual_fields
            )
            evaluation = self._verify_fields(
                rule_id=rule.rule_id,
                fields=fields_for_candidate,
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

        # SS C.7(2): placeholder/identical-name fail-closed and the
        # 2-candidate escalation itself need no new code here - a query
        # whose First Name resolves to nothing distinguishing (placeholder
        # stripped to empty, or identical between twins) naturally produces
        # 0 or 2+ entries in `resolved` above via the existing per-candidate
        # exact/missing-field checks, which _build_result already turns
        # into NO_MATCH or ESCALATE/AMBIGUOUS - no twin-specific branch
        # needed to reproduce that outcome.
        #
        # SS C.7(4) before (3): anchoring to a persistent identifier
        # (MRN/EMPI/FHIR Patient.id, i.e. namespace_id) takes priority over
        # the middle-name heuristic when both are available, since it's a
        # near-zero-collision signal rather than a last-resort one. If the
        # query carries an anchor but it fails to uniquely resolve one of
        # the tied candidates (matches zero or both), that's a disqualifying
        # signal in its own right and must NOT fall through to the
        # middle-name heuristic - _break_twin_tie_with_namespace_id
        # distinguishes "no anchor supplied" (defer) from "anchor supplied,
        # didn't resolve" (stop) via the _NO_ANCHOR sentinel.
        excluded: List[Dict[str, Any]] = []
        if len(resolved) == 2 and shared_dobs:
            anchor_result = self._break_twin_tie_with_namespace_id(
                query_fields, resolved
            )
            narrowed = (
                self._break_twin_tie_with_middle_name(query_fields, resolved)
                if anchor_result is _NO_ANCHOR
                else anchor_result
            )
            if narrowed is not None:
                # **Correction, found empirically while testing, not
                # assumed:** picking `narrowed` here is not by itself enough
                # to make the twin resolve cleanly end-to-end.
                # _build_result's cross-rule aggregation is a union of every
                # contributing rule's matches, not "the most specific rule
                # wins" - so if some other, less specific rule (e.g. a flat
                # Category 1 rule matching on a shared alias) also matched
                # the twin this tiebreak just rejected, that twin would
                # still resurface in the final result and defeat the whole
                # point of this method. The rejected candidate(s) must be
                # reported up as an explicit exclusion so match() can strip
                # them out of the union regardless of which other rule
                # contributed them.
                excluded = [c for c in resolved if c is not narrowed]
                resolved = [narrowed]

        return resolved, evaluations, excluded

    def _shared_dob_values(self, candidates: List[Dict[str, Any]]) -> Set[str]:
        """DOB values shared by 2+ candidates in this household-tier match
        set - the twin/multiple-birth signal SS C.7 keys off of. Compares
        candidates to each other, not to the query - the individual-tier
        DOB check against the query happens separately.

        Returns the specific shared values (not just a bool) so callers can
        scope exact-First-Name enforcement to only the candidates actually
        involved in a shared DOB, rather than the whole household - a
        household member whose own DOB isn't part of any shared pair (e.g.
        a parent living with twins) must keep ordinary fuzzy matching."""
        dob_counts: Dict[str, int] = {}
        for candidate in candidates:
            for dob_value in self._extractor.extract(candidate).dob:
                dob_counts[dob_value] = dob_counts.get(dob_value, 0) + 1
        return {dob for dob, count in dob_counts.items() if count > 1}

    @staticmethod
    def _patient_id(patient: Dict[str, Any]) -> str:
        """Identity key for cross-rule dedup/exclusion, matching
        _build_result's own fallback: FHIR resource ID if present,
        otherwise Python object identity (stable within one match() call,
        since a given backend call returns the same object references each
        time they're re-used across rules in this engine)."""
        return patient.get("id", "") or str(id(patient))

    @staticmethod
    def _force_exact_first_name(
        fields: tuple[RuleField, ...],
    ) -> tuple[RuleField, ...]:
        """Return a copy of `fields` with First Name's role forced to
        FieldRole.EXACT, leaving every other field untouched. RuleField is
        frozen, so this rebuilds the tuple rather than mutating in place."""
        return tuple(
            RuleField(name=rf.name, role=FieldRole.EXACT)
            if rf.name == FIRST_NAME
            else rf
            for rf in fields
        )

    def _break_twin_tie_with_namespace_id(
        self,
        query_fields: PatientFields,
        tied_candidates: List[Dict[str, Any]],
    ) -> Any:
        """SS C.7(4): if the query carries a namespace-bound persistent
        identifier (MRN/EMPI/FHIR Patient.id) recorded at a prior
        resolution, and it overlaps exactly one of the two tied candidates'
        own namespace_id, that candidate wins the tiebreak outright -
        skipping the name-based heuristics entirely, since this is a
        near-zero-collision signal rather than a last-resort one.

        Returns one of three distinct outcomes, since "no anchor" and "an
        anchor that failed to resolve" must be handled differently by the
        caller:
          - `_NO_ANCHOR` if the query has no namespace_id at all - defer to
            the middle-name tiebreak.
          - `None` if the query has a namespace_id but it matches zero or
            both tied candidates - this is itself a disqualifying signal
            (the anchor actively failed to discriminate), so the caller
            must NOT fall through to the middle-name heuristic in this
            case.
          - the resolved candidate if exactly one tied candidate's own
            namespace_id overlaps the query's.
        """
        if not query_fields.namespace_ids:
            return _NO_ANCHOR

        matches = [
            candidate
            for candidate in tied_candidates
            if query_fields.namespace_ids
            & self._extractor.extract(candidate).namespace_ids
        ]
        return matches[0] if len(matches) == 1 else None

    def _break_twin_tie_with_middle_name(
        self,
        query_fields: PatientFields,
        tied_candidates: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """SS C.7(3): if the query has a middle name and it overlaps exactly
        one of the two tied candidates' own middle names, that candidate
        wins the tiebreak. Returns None (still ambiguous) if the query has
        no middle name, if any tied candidate has no recorded middle name
        at all (absence of data must not be treated as discriminating - a
        candidate whose middle name was simply never captured must not lose
        the tiebreak on that missing data), or if both/neither candidate's
        middle name matches - a non-discriminating middle name must not
        force a pick."""
        if not query_fields.middle_names:
            return None

        candidate_middle_names = [
            self._extractor.extract(candidate).middle_names
            for candidate in tied_candidates
        ]
        if not all(candidate_middle_names):
            return None

        matches = [
            candidate
            for candidate, middle_names in zip(tied_candidates, candidate_middle_names)
            if query_fields.middle_names & middle_names
        ]
        return matches[0] if len(matches) == 1 else None

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
        *,
        query_initiator: Optional[str],
        timestamp: str,
        any_rule_evaluable: bool = True,
        excluded_ids: Optional[Set[str]] = None,
    ) -> MatchResult:
        """Build final MatchResult applying uniqueness check.

        `any_rule_evaluable=False` (adversarial-review finding, session 18
        post-review fix) means the query patient didn't carry enough fields
        for ANY Table 2 rule to even be attempted - a materially different
        SS VII "final match determination" than a query that WAS evaluated
        against real rules and genuinely found no candidate. Both cases
        previously reported MatchOutcome.NO_MATCH with an empty
        `rule_evaluations`, making them indistinguishable after the fact -
        MatchOutcome.INSUFFICIENT_FIELDS was defined for exactly this but
        never produced anywhere.

        `excluded_ids` (CMS v3.4.0 SS C.7, session 19): identity keys
        (MatchingEngine._patient_id) of candidates a household/individual
        rule's twin tiebreak positively ruled out. Applied across the
        *entire* union, not just that rule's own contribution - without
        this, a twin correctly resolved by one rule's tiebreak could still
        resurface here via a separate, less specific rule (e.g. a flat rule
        matching on a shared name alias) that independently matched the
        rejected twin, silently defeating the tiebreak.
        """
        if not matched_by_rule:
            return MatchResult(
                outcome=MatchOutcome.NO_MATCH
                if any_rule_evaluable
                else MatchOutcome.INSUFFICIENT_FIELDS,
                rule_evaluations=evaluations,
                query_initiator=query_initiator,
                timestamp=timestamp,
            )

        excluded_ids = excluded_ids or set()

        # Collect all unique matched patients across rules
        all_matched: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        first_rule_id: Optional[str] = None
        first_match_type = "exact"

        for rule_id, patients in matched_by_rule.items():
            for p in patients:
                # Deduplicate by FHIR resource ID if available,
                # falling back to Python object identity
                pid = MatchingEngine._patient_id(p)
                if pid in excluded_ids:
                    continue
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
        if not all_matched:
            return MatchResult(
                outcome=MatchOutcome.NO_MATCH,
                rule_evaluations=evaluations,
                query_initiator=query_initiator,
                timestamp=timestamp,
            )
        elif len(all_matched) == 1:
            return MatchResult(
                outcome=MatchOutcome.MATCH,
                matched_patients=all_matched,
                matched_rule_id=first_rule_id,
                match_type=first_match_type,
                is_unique=True,
                rule_evaluations=evaluations,
                candidate_count=len(all_matched),
                query_initiator=query_initiator,
                timestamp=timestamp,
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
                query_initiator=query_initiator,
                timestamp=timestamp,
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
                query_initiator=query_initiator,
                timestamp=timestamp,
            )
