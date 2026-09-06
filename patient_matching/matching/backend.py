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
    """How a field criterion should be matched."""

    EXACT = "exact"
    FUZZY = "fuzzy"


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
    """

    @abstractmethod
    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        """Search for candidate patients matching the given criteria.

        Args:
            criteria: A list of field criteria that should ALL be
                satisfied (AND semantics). Fuzzy criteria allow
                approximate matching.

        Returns:
            A list of FHIR Patient resource dicts.
        """
