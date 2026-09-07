"""Adapter that bridges the cache to the matching engine's MatchingBackend.

This is the key integration point: the matching engine calls
``backend.search(criteria)`` and this adapter translates those
criteria into cache lookups, returning FHIR Patient dicts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from ..matching.backend import FieldCriterion, MatchingBackend, MatchType
from .cache_backend import CacheBackend

logger = logging.getLogger(__name__)


class CacheMatchingBackend(MatchingBackend):
    """MatchingBackend that retrieves candidates from the patient cache.

    Uses the first criterion (blocking key) to fetch candidates from
    the cache, then returns the FHIR Patient dicts for the matching
    engine to verify field-by-field.

    Args:
        cache: The cache backend to query.
    """

    def __init__(self, cache: CacheBackend) -> None:
        self._cache = cache

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        """Search for candidate patients matching the given criteria.

        Uses the criteria as blocking keys — fetches candidates from
        the cache that match ANY criterion, then intersects the
        result sets to find candidates matching ALL criteria.

        The matching engine will do precise field-by-field verification
        afterward, so this can cast a somewhat wide net.
        """
        if not criteria:
            return []

        # Use each criterion as a blocking key and intersect results
        candidate_sets: List[Set[str]] = []
        all_candidates: Dict[str, Dict[str, Any]] = {}

        for criterion in criteria:
            fuzzy = criterion.match_type == MatchType.FUZZY
            matches = await self._cache.search_by_field(
                criterion.field_name,
                criterion.value,
                fuzzy=fuzzy,
            )
            match_ids = set()
            for m in matches:
                match_ids.add(m.patient_id)
                if m.patient_id not in all_candidates:
                    all_candidates[m.patient_id] = m.fhir_resource
            candidate_sets.append(match_ids)

        if not candidate_sets:
            return []

        # Intersect all blocking key results (AND semantics)
        result_ids = candidate_sets[0]
        for s in candidate_sets[1:]:
            result_ids &= s

        return [all_candidates[pid] for pid in result_ids if pid in all_candidates]
