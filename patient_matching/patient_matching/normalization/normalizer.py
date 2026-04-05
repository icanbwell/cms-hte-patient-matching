"""Main orchestrator for FHIR Patient normalization.

Composes all domain-specific normalizers (name, address, phone, date)
and placeholder detection into a single entry point that accepts a
FHIR Patient resource dict and returns a normalized copy.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

from .address_normalizer import AddressNormalizer
from .date_normalizer import DateNormalizer
from .name_normalizer import NameNormalizer
from .phone_normalizer import PhoneNormalizer
from .placeholder_detector import PlaceholderDetector

logger = logging.getLogger(__name__)


class PatientNormalizer:
    """Normalizes a FHIR R4 Patient resource for demographic matching.

    Applies all normalization rules:
      A. Text normalization (case, whitespace, punctuation, diacritics)
      B. Name handling (components, nicknames, suffix expansion)
      C. Demographic fields (addresses, phones, E.164)
      D. Placeholder suppression

    The original Patient dict is not mutated; a normalized copy is returned.

    Args:
        placeholder_detector: Custom placeholder detector. If None, a
            default detector is created.
        name_normalizer: Custom name normalizer.
        address_normalizer: Custom address normalizer.
        phone_normalizer: Custom phone normalizer.
        date_normalizer: Custom date normalizer.
    """

    def __init__(
        self,
        *,
        placeholder_detector: Optional[PlaceholderDetector] = None,
        name_normalizer: Optional[NameNormalizer] = None,
        address_normalizer: Optional[AddressNormalizer] = None,
        phone_normalizer: Optional[PhoneNormalizer] = None,
        date_normalizer: Optional[DateNormalizer] = None,
    ) -> None:
        self._placeholders = placeholder_detector or PlaceholderDetector()
        self._names = name_normalizer or NameNormalizer(
            placeholder_detector=self._placeholders
        )
        self._addresses = address_normalizer or AddressNormalizer(
            placeholder_detector=self._placeholders
        )
        self._phones = phone_normalizer or PhoneNormalizer(
            placeholder_detector=self._placeholders
        )
        self._dates = date_normalizer or DateNormalizer(
            placeholder_detector=self._placeholders
        )

    def normalize(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a FHIR Patient resource for matching.

        Args:
            patient: A FHIR R4 Patient resource dictionary.

        Returns:
            A new dictionary with all demographic fields normalized.
            Fields identified as placeholders are removed.
        """
        result = copy.deepcopy(patient)

        # Ensure resourceType is preserved
        result["resourceType"] = "Patient"

        # Normalize names (B.1-B.6)
        normalized_names = self._names.normalize_patient_names(result)
        if normalized_names:
            result["name"] = normalized_names
        else:
            result.pop("name", None)

        # Normalize birth date (A.5, D.6)
        birth_date = result.get("birthDate")
        if birth_date:
            normalized_date = self._dates.normalize_birth_date(birth_date)
            if normalized_date:
                result["birthDate"] = normalized_date
            else:
                result.pop("birthDate", None)

        # Normalize telecoms — phones to E.164, emails lowercased (C.3-C.4)
        normalized_telecoms = self._phones.normalize_patient_telecoms(result)
        if normalized_telecoms:
            result["telecom"] = normalized_telecoms
        else:
            result.pop("telecom", None)

        # Normalize addresses to USPS standard (C.1-C.2)
        normalized_addresses = self._addresses.normalize_patient_addresses(result)
        if normalized_addresses:
            result["address"] = normalized_addresses
        else:
            result.pop("address", None)

        # Normalize identifiers — suppress placeholder SSNs
        if "identifier" in result:
            normalized_ids = self._normalize_identifiers(result["identifier"])
            if normalized_ids:
                result["identifier"] = normalized_ids
            else:
                result.pop("identifier", None)

        return result

    def _normalize_identifiers(
        self, identifiers: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        """Filter out placeholder identifiers (e.g. fake SSNs)."""
        result = []
        for ident in identifiers:
            value = ident.get("value", "")
            system = ident.get("system", "")

            # Check SSN placeholders
            if system == "http://hl7.org/fhir/sid/us-ssn":
                if self._placeholders.is_placeholder_ssn(value):
                    continue

            # Check general placeholders
            if value and self._placeholders.is_placeholder_general(value):
                continue

            result.append(ident)
        return result
