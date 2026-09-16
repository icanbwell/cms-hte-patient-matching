"""Abstract backend interface for patient record lookups.

Implementations provide the data-access layer — searching a database,
FHIR server, in-memory store, etc. The matching engine calls the backend
to retrieve candidate patients, then applies Table 2 rules locally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class MatchType(Enum):
    """How a field criterion should be matched.

    DOB_TOLERANCE (CMS v3.3's +/-1 calendar day DOB tolerance) is distinct
    from FUZZY: a date string's Damerau-Levenshtein edit distance has no
    relationship to its calendar distance (e.g. "2000-02-29"->"2000-03-01"
    is 3 edits but 1 day apart, while "2015-06-01"->"2015-06-02" is 1 edit
    AND 1 day apart only by coincidence). A backend must expand
    DOB_TOLERANCE into an exact lookup on {value-1day, value, value+1day},
    never a fuzzy-text/edit-distance search.
    """

    EXACT = "exact"
    FUZZY = "fuzzy"
    DOB_TOLERANCE = "dob_tolerance"


@dataclass
class FieldCriterion:
    """A single field-level search criterion.

    Attributes:
        field_name: Canonical field name (e.g. "first_name", "dob").
        value: The normalized query value.
        match_type: Whether to search exact or fuzzy.
    """

    field_name: str
    value: str
    match_type: MatchType = MatchType.EXACT


class MatchingBackend(ABC):
    """Abstract interface for retrieving candidate patient records.

    Implementations should return FHIR Patient resource dicts that
    potentially match the given criteria. The matching engine will
    do precise field-by-field verification afterward.

    The backend may cast a wide net (e.g. blocking on DOB + last name
    initial) or be precise — the engine handles correctness either way.

    **Identity stability contract (CMS v3.4.0 SS C.7, session 19):**
    `MatchingEngine` cross-references candidates returned by separate
    `search()` calls within one `match()` invocation - both for its
    existing dedup logic and for the twin/multiple-birth tiebreak's
    `excluded_ids` mechanism, which must recognize a candidate excluded by
    one rule if a different rule's `search()` call also returns it.
    Identity is determined by FHIR `id` when present, falling back to
    Python object identity (`MatchingEngine._patient_id`) when it's not.
    A backend whose `search()` constructs a fresh dict per call for the
    same underlying record - rather than returning a shared/cached object
    reference - **must** populate a stable FHIR `id` on every returned
    dict, or these safety mechanisms silently no-op for that record.
    """

    @abstractmethod
    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        """Search for candidate patients matching the given criteria.

        Args:
            criteria: A list of field criteria that should ALL be
                satisfied (AND semantics). Fuzzy criteria allow
                approximate matching.

        Returns:
            A list of FHIR Patient resource dicts. See this class's
            docstring for the identity-stability contract these dicts
            must satisfy across calls within one MatchingEngine.match()
            invocation.
        """
