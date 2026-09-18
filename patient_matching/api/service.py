"""End-to-end patient matching service.

Orchestrates the full pipeline:
  - Normalize incoming FHIR Patient demographics
  - Match against the patient cache
  - Return FHIR Patient IDs with confidence scores

Callers presenting an IAL2 token must convert it to a FHIR Patient
themselves first, e.g. with the `cms-hte-ial2-reader` package, then pass
the result to match_patient().
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..cache.cache_backend import CacheBackend
from ..cache.matching_adapter import CacheMatchingBackend
from ..matching.match_result import MatchOutcome, MatchResult
from ..matching.matching_engine import MatchingEngine
from ..matching.field_extractor import FieldExtractor
from ..matching.field_comparator import FieldComparator
from ..matching.household_rules import CATEGORY_2_RULES
from ..matching.relationship_linkage_rules import RELATIONSHIP_LINKAGE_RULES
from ..matching.table2_rules import APPROVED_RULES, MatchingRule
from ..normalization.manager import NormalizationManager

logger = logging.getLogger(__name__)


@dataclass
class MatchResponse:
    """Response from the patient matching service.

    Attributes:
        outcome: The match outcome (match, no_match, ambiguous).
        matched_patient_ids: List of matched FHIR Patient resource IDs.
        matched_patients: List of matched FHIR Patient resource dicts.
        matched_rule_id: The first rule that produced a match.
        match_type: "exact" or "fuzzy".
        confidence_score: Estimated match confidence (0.0 - 1.0).
        candidate_count: Total number of candidates found.
        rule_evaluations_summary: Per-rule audit/troubleshooting detail,
            one dict per RuleEvaluation the engine produced (see
            match_result.RuleEvaluation for what each key means -- this
            carries the same field-by-field/blocking detail, not just
            rule_id/matched/match_type/fuzzy_fields/negated_by_suffix).
            **Sizing note:** as of the field_values/candidates_retrieved
            work, a genuine no_match against a large/empty candidate pool
            now produces one entry per rule the query has fields for
            (previously it produced none at all, since only rules whose
            blocking search() returned >=1 candidate got an entry) --
            measured at 13 entries / ~5KB for a demographically-complete
            query against an empty cache. This is the intended SS VII
            audit detail, not a bug, but any caller persisting/logging the
            full MatchResponse should budget for it.
        query_initiator: SS VII audit field (session 18) - the caller-
            supplied identifier passed to match_patient(), echoed back
            here. None if the caller didn't supply one.
        timestamp: SS VII audit field (session 18) - ISO 8601 UTC timestamp
            for this query.
    """

    outcome: str
    matched_patient_ids: List[str] = field(default_factory=list)
    matched_patients: List[Dict[str, Any]] = field(default_factory=list)
    matched_rule_id: Optional[str] = None
    match_type: Optional[str] = None
    confidence_score: float = 0.0
    candidate_count: int = 0
    rule_evaluations_summary: List[Dict[str, Any]] = field(default_factory=list)
    query_initiator: Optional[str] = None
    timestamp: str = ""


@dataclass
class ServiceConfig:
    """Configuration for the patient matching service.

    Attributes:
        rules: Subset of Table 2 rules to evaluate. Defaults to all 26.
    """

    rules: Optional[tuple[MatchingRule, ...]] = None


class PatientMatcherService:
    """End-to-end patient matching service.

    Normalizes and matches FHIR Patient resources against the cache.
    Callers holding an IAL2 token must convert it to a FHIR Patient
    themselves (e.g. via `cms-hte-ial2-reader`) before calling
    match_patient().

    Args:
        cache: The patient cache backend.
        normalizer: Optional normalization manager.
        config: Optional service configuration.

    Example::

        service = PatientMatcherService(cache=duckdb_cache)
        result = await service.match_patient(normalized_patient)
    """

    def __init__(
        self,
        *,
        cache: CacheBackend,
        normalizer: Optional[NormalizationManager] = None,
        config: Optional[ServiceConfig] = None,
    ) -> None:
        self._cache = cache
        self._normalizer = normalizer or NormalizationManager()
        self._config = config or ServiceConfig()

        # Build the matching engine with the cache as backend
        backend = CacheMatchingBackend(cache)
        rules = self._config.rules or APPROVED_RULES
        self._engine = MatchingEngine(
            backend=backend,
            extractor=FieldExtractor(),
            comparator=FieldComparator(),
            rules=rules,
        )

    async def match_patient(
        self,
        patient: Dict[str, Any],
        *,
        skip_normalization: bool = False,
        query_initiator: Optional[str] = None,
    ) -> MatchResponse:
        """Match a FHIR Patient resource against the cache.

        Args:
            patient: A FHIR R4 Patient resource dict.
            skip_normalization: If True, assumes the patient is already
                normalized. Default False.
            query_initiator: SS VII audit field (session 18) - an opaque,
                caller-supplied identifier for whoever/whatever issued this
                query. Not validated or required.

        Returns:
            A MatchResponse with outcome and matched patient IDs.
        """
        if skip_normalization:
            normalized = patient
        else:
            normalized = self._normalizer.normalize(patient)

        return await self._match_and_respond(
            normalized, query_initiator=query_initiator
        )

    async def _match_and_respond(
        self,
        normalized_patient: Dict[str, Any],
        *,
        query_initiator: Optional[str] = None,
    ) -> MatchResponse:
        """Run matching engine and build response."""
        result = await self._engine.match(
            normalized_patient, query_initiator=query_initiator
        )
        return self._build_response(result)

    @staticmethod
    def _build_response(result: MatchResult) -> MatchResponse:
        """Convert a MatchResult to a MatchResponse."""
        patient_ids = []
        for p in result.matched_patients:
            pid = p.get("id", "")
            if pid:
                patient_ids.append(pid)

        # Compute confidence score based on match outcome and rule P(collision)
        confidence = _compute_confidence(result)

        eval_summary = []
        for ev in result.rule_evaluations:
            eval_summary.append(
                {
                    "rule_id": ev.rule_id,
                    "matched": ev.matched,
                    "match_type": ev.match_type,
                    "fuzzy_fields": ev.fuzzy_fields,
                    "negated_by_suffix": ev.negated_by_suffix,
                    # Everything below was previously dropped here, even
                    # though RuleEvaluation carries it -- silently
                    # stripping the field-by-field/blocking detail this
                    # SS VII audit record's own module docstring
                    # (match_result.py) says it satisfies.
                    "step": ev.step,
                    "field_outcomes": ev.field_outcomes,
                    "field_values": ev.field_values,
                    "field_fuzzy_detail": ev.field_fuzzy_detail,
                    "candidates_retrieved": ev.candidates_retrieved,
                    "blocking_criteria": ev.blocking_criteria,
                    "suffix_values": ev.suffix_values,
                    "p_collision_exact": ev.p_collision_exact,
                    "p_collision_fuzzy": ev.p_collision_fuzzy,
                }
            )

        return MatchResponse(
            outcome=result.outcome.value,
            matched_patient_ids=patient_ids,
            matched_patients=result.matched_patients,
            matched_rule_id=result.matched_rule_id,
            match_type=result.match_type,
            confidence_score=confidence,
            candidate_count=result.candidate_count,
            rule_evaluations_summary=eval_summary,
            query_initiator=result.query_initiator,
            timestamp=result.timestamp,
        )


def _compute_confidence(result: MatchResult) -> float:
    """Compute a confidence score for the match.

    Uses the P(collision) values from the matched rule to derive
    a confidence score. Lower P(collision) = higher confidence.

    For exact matches, confidence = 1.0 - P(collision_exact).
    For fuzzy matches, confidence = 1.0 - P(collision_fuzzy).
    """
    if result.outcome != MatchOutcome.MATCH:
        return 0.0

    if not result.matched_rule_id:
        return 0.0

    # Look up the rule's P(collision). Flat (Category 1) rules and
    # household/individual (Category 2) rules share the same rule_id/
    # p_collision_exact/p_collision_fuzzy attribute shape but aren't a
    # common type, so they're searched via two loops rather than one
    # heterogeneous tuple (mypy can't type-check `object` attribute access).
    for flat_rule in APPROVED_RULES:
        if flat_rule.rule_id == result.matched_rule_id:
            p_collision = (
                flat_rule.p_collision_fuzzy
                if result.match_type == "fuzzy"
                else flat_rule.p_collision_exact
            )
            # Confidence = 1 - P(collision), clamped to [0, 1]
            return max(0.0, min(1.0, 1.0 - p_collision))

    # CATEGORY_2_RULES (the original 8) and RELATIONSHIP_LINKAGE_RULES
    # (session 17's C2-39/C2-40) are searched together - MatchingEngine's
    # own default likewise combines both (see matching_engine.py's
    # _ALL_CATEGORY_2_RULES), so a match via either must resolve to a real
    # confidence score here, not silently fall through to 0.0 below.
    for hh_rule in CATEGORY_2_RULES + RELATIONSHIP_LINKAGE_RULES:
        if hh_rule.rule_id == result.matched_rule_id:
            p_collision = (
                hh_rule.p_collision_fuzzy
                if result.match_type == "fuzzy"
                else hh_rule.p_collision_exact
            )
            return max(0.0, min(1.0, 1.0 - p_collision))

    return 0.0
