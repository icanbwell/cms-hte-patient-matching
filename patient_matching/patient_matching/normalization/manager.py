"""High-level manager for normalizing FHIR Patient resources.

Provides a single entry point that accepts a raw FHIR Patient dict,
applies all normalization rules (text, name, address, phone, date,
placeholder suppression), and returns a normalized copy ready for
matching.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .address_normalizer import AddressNormalizer
from .date_normalizer import DateNormalizer
from .name_normalizer import NameNormalizer
from .normalizer import PatientNormalizer
from .phone_normalizer import PhoneNormalizer
from .placeholder_detector import PlaceholderDetector

logger = logging.getLogger(__name__)


class NormalizationManager:
    """Manages FHIR Patient normalization for demographic matching.

    Wraps the PatientNormalizer and its sub-normalizers, exposing a
    simple ``normalize()`` method as well as convenience methods for
    normalizing individual fields when needed.

    Args:
        phone_default_region: Default region code for phone number
            parsing (default ``"US"``).
        placeholder_detector: Custom placeholder detector.  If ``None``
            a default detector is used.

    Example::

        manager = NormalizationManager()
        normalized = manager.normalize(raw_patient)
        # normalized is a FHIR R4 Patient dict ready for matching

        # Batch usage
        results = manager.normalize_batch([patient_a, patient_b])
    """

    def __init__(
        self,
        *,
        phone_default_region: str = "US",
        placeholder_detector: Optional[PlaceholderDetector] = None,
    ) -> None:
        self._placeholders = placeholder_detector or PlaceholderDetector()

        self._name_normalizer = NameNormalizer(
            placeholder_detector=self._placeholders,
        )
        self._address_normalizer = AddressNormalizer(
            placeholder_detector=self._placeholders,
        )
        self._phone_normalizer = PhoneNormalizer(
            default_region=phone_default_region,
            placeholder_detector=self._placeholders,
        )
        self._date_normalizer = DateNormalizer(
            placeholder_detector=self._placeholders,
        )

        self._normalizer = PatientNormalizer(
            placeholder_detector=self._placeholders,
            name_normalizer=self._name_normalizer,
            address_normalizer=self._address_normalizer,
            phone_normalizer=self._phone_normalizer,
            date_normalizer=self._date_normalizer,
        )

    def normalize(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single FHIR Patient resource.

        The original dict is not mutated.

        Args:
            patient: A FHIR R4 Patient resource dictionary.

        Returns:
            A new dictionary with all demographic fields normalized
            and placeholder values removed.
        """
        return self._normalizer.normalize(patient)

    def normalize_batch(self, patients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize a list of FHIR Patient resources.

        Args:
            patients: A list of FHIR R4 Patient resource dictionaries.

        Returns:
            A list of normalized Patient dictionaries in the same order.
        """
        return [self._normalizer.normalize(p) for p in patients]

    def suffixes_conflict(
        self, suffix_a: Optional[str], suffix_b: Optional[str]
    ) -> bool:
        """Check if two generational suffixes conflict (rule B.5).

        If both sides have a recognizable suffix and they differ,
        the match SHALL be negated.

        Args:
            suffix_a: Suffix from the first patient.
            suffix_b: Suffix from the second patient.

        Returns:
            True if both suffixes are present and do not match.
        """
        return self._name_normalizer.suffixes_conflict(suffix_a, suffix_b)

    def get_nicknames(self, given_name: str) -> set[str]:
        """Return the set of known nicknames for a given name.

        Useful for callers that need nickname expansion outside of
        the full normalization pipeline (e.g. query-time expansion).

        Args:
            given_name: A first/given name string.

        Returns:
            A set of normalized nickname strings.
        """
        return self._name_normalizer.get_nicknames(given_name)

    @property
    def placeholder_table_version(self) -> str:
        """Version of the placeholder reference tables."""
        return self._placeholders.version

    @property
    def nickname_table_version(self) -> str:
        """Version of the nickname reference table (B.1)."""
        return self._name_normalizer.nickname_table_version

    @property
    def suffix_table_version(self) -> str:
        """Version of the suffix expansion table (B.6)."""
        return self._name_normalizer.suffix_table_version
