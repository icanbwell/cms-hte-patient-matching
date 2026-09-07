"""End-to-end patient matching service.

Orchestrates the full pipeline:
  - IAL2 Token → verify → extract → FHIR Patient
  - Normalize incoming demographics
  - Match against the patient cache
  - Return FHIR Patient IDs with confidence scores
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..cache.cache_backend import CacheBackend
from ..cache.matching_adapter import CacheMatchingBackend
from ..ial2_extraction.ial2_extractor import IAL2Extractor
from ..matching.match_result import MatchOutcome, MatchResult
from ..matching.matching_engine import MatchingEngine
from ..matching.field_extractor import FieldExtractor
from ..matching.field_comparator import FieldComparator
from ..matching.household_rules import CATEGORY_2_RULES
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
        rule_evaluations_summary: Summary of rules evaluated.
    """

    outcome: str
    matched_patient_ids: List[str] = field(default_factory=list)
    matched_patients: List[Dict[str, Any]] = field(default_factory=list)
    matched_rule_id: Optional[str] = None
    match_type: Optional[str] = None
    confidence_score: float = 0.0
    candidate_count: int = 0
    rule_evaluations_summary: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ServiceConfig:
    """Configuration for the patient matching service.

    Attributes:
        rules: Subset of Table 2 rules to evaluate. Defaults to all 26.
    """

    rules: Optional[tuple[MatchingRule, ...]] = None


class PatientMatcherService:
    """End-to-end patient matching service.

    Chains IAL2 extraction, normalization, and matching into a single
    pipeline. Can also match pre-built FHIR Patient resources directly.

    Args:
        cache: The patient cache backend.
        ial2_extractor: Optional IAL2 token extractor.
        normalizer: Optional normalization manager.
        config: Optional service configuration.

    Example::

        service = PatientMatcherService(
            cache=duckdb_cache,
            ial2_extractor=ial2_extractor,
        )
        # Match from IAL2 token
        result = await service.match_from_token(jwt_token)

        # Match from FHIR Patient
        result = await service.match_patient(normalized_patient)
    """

    def __init__(
        self,
        *,
        cache: CacheBackend,
        ial2_extractor: Optional[IAL2Extractor] = None,
        normalizer: Optional[NormalizationManager] = None,
        config: Optional[ServiceConfig] = None,
    ) -> None:
        self._cache = cache
        self._ial2_extractor = ial2_extractor
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

    async def match_from_token(self, token: str) -> MatchResponse:
        """Match a patient from an IAL2 JWT token.

        Full pipeline: verify token → extract demographics →
        convert to FHIR → normalize → match against cache.

        Args:
            token: A signed IAL2 JWT token string.

        Returns:
            A MatchResponse with outcome and matched patient IDs.

        Raises:
            ValueError: If no IAL2 extractor is configured.
            TokenVerificationError: If the token is invalid.
        """
        if self._ial2_extractor is None:
            raise ValueError(
                "IAL2 extractor not configured. Provide an IAL2Extractor "
                "to match from tokens."
            )

        logger.info("Matching from IAL2 token")

        # Step 1: Verify token and extract FHIR Patient
        fhir_patient = await self._ial2_extractor.extract(token)

        # Step 2: Normalize
        normalized = self._normalizer.normalize(fhir_patient)

        # Step 3: Match
        return await self._match_and_respond(normalized)

    async def match_patient(
        self, patient: Dict[str, Any], *, skip_normalization: bool = False
    ) -> MatchResponse:
        """Match a FHIR Patient resource against the cache.

        Args:
            patient: A FHIR R4 Patient resource dict.
            skip_normalization: If True, assumes the patient is already
                normalized. Default False.

        Returns:
            A MatchResponse with outcome and matched patient IDs.
        """
        if skip_normalization:
            normalized = patient
        else:
            normalized = self._normalizer.normalize(patient)

        return await self._match_and_respond(normalized)

    async def _match_and_respond(
        self, normalized_patient: Dict[str, Any]
    ) -> MatchResponse:
        """Run matching engine and build response."""
        result = await self._engine.match(normalized_patient)
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

    for hh_rule in CATEGORY_2_RULES:
        if hh_rule.rule_id == result.matched_rule_id:
            p_collision = (
                hh_rule.p_collision_fuzzy
                if result.match_type == "fuzzy"
                else hh_rule.p_collision_exact
            )
            return max(0.0, min(1.0, 1.0 - p_collision))

    return 0.0
