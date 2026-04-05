"""Abstract cache storage interface for normalized patient records.

Implementations persist normalized patient demographics in a way
that supports efficient field-level lookups for the matching engine.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class CachedPatient:
    """A normalized patient record stored in the cache.

    Stores both the extracted canonical field values (for fast lookup)
    and the original FHIR resource (for return in match results).

    Attributes:
        patient_id: The FHIR Patient resource ID.
        first_names: Normalized first/given names.
        last_names: Normalized family names.
        suffixes: Generational suffixes.
        dob: Date of birth (YYYY-MM-DD).
        street_lines: Normalized street address lines.
        phones: E.164 phone numbers.
        emails: Normalized email addresses.
        ssn_last4: Last 4 digits of SSN.
        itin_last4: Last 4 digits of ITIN.
        mbi: Medicare Beneficiary Identifier.
        legal_ids: Legal ID values with namespace.
        namespace_ids: Namespace-bound unique identifiers.
        fhir_resource: The full normalized FHIR Patient dict.
    """

    patient_id: str
    first_names: Set[str] = field(default_factory=set)
    last_names: Set[str] = field(default_factory=set)
    suffixes: Set[str] = field(default_factory=set)
    dob: Set[str] = field(default_factory=set)
    street_lines: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    emails: Set[str] = field(default_factory=set)
    ssn_last4: Set[str] = field(default_factory=set)
    itin_last4: Set[str] = field(default_factory=set)
    mbi: Set[str] = field(default_factory=set)
    legal_ids: Set[str] = field(default_factory=set)
    namespace_ids: Set[str] = field(default_factory=set)
    fhir_resource: Dict[str, Any] = field(default_factory=dict)


class CacheBackend(ABC):
    """Abstract interface for patient cache storage.

    Implementations must support:
      - Bulk upsert of normalized patient records
      - Field-level search (exact and fuzzy) for candidate retrieval
      - Cache statistics and lifecycle management
    """

    @abstractmethod
    def upsert_patients(self, patients: List[CachedPatient]) -> int:
        """Insert or update normalized patient records.

        Args:
            patients: List of CachedPatient records to store.

        Returns:
            Number of records upserted.
        """

    @abstractmethod
    def search_by_field(
        self,
        field_name: str,
        value: str,
        *,
        fuzzy: bool = False,
    ) -> List[CachedPatient]:
        """Search cached patients by a single field value.

        Args:
            field_name: Canonical field name (e.g. "first_name", "dob").
            value: The value to search for.
            fuzzy: If True, use fuzzy matching (DL distance <= 1).

        Returns:
            List of matching CachedPatient records.
        """

    @abstractmethod
    def get_patient(self, patient_id: str) -> Optional[CachedPatient]:
        """Retrieve a single cached patient by ID.

        Args:
            patient_id: The FHIR Patient resource ID.

        Returns:
            The CachedPatient, or None if not found.
        """

    @abstractmethod
    def count(self) -> int:
        """Return the total number of cached patients."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all cached patients."""

    @abstractmethod
    def close(self) -> None:
        """Release resources held by the backend."""
