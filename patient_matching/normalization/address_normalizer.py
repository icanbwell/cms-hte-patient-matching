"""Address normalization per requirements C.1-C.2.

Normalizes addresses to Project US@ / USPS standard formats using
usaddress-scourgify. Addresses match regardless of designated type.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from scourgify import normalize_address_record
from scourgify.exceptions import (
    AddressNormalizationError,
    AmbiguousAddressError,
)

from .placeholder_detector import PlaceholderDetector
from .text_utils import normalize_text

logger = logging.getLogger(__name__)


class AddressNormalizer:
    """Normalizes FHIR Address entries to USPS standard format.

    Args:
        placeholder_detector: Detector for placeholder address values.
    """

    def __init__(
        self,
        *,
        placeholder_detector: Optional[PlaceholderDetector] = None,
    ) -> None:
        self._placeholders = placeholder_detector or PlaceholderDetector()

    def normalize_patient_addresses(
        self, patient: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Normalize all address entries on a FHIR Patient resource.

        Returns a new list of FHIR Address dicts with standardized values.
        Placeholder addresses are excluded. Per C.2, address type is
        preserved but does not affect matching.
        """
        raw_addresses: List[Dict[str, Any]] = patient.get("address", [])
        if not raw_addresses:
            return []

        result: List[Dict[str, Any]] = []
        for addr_entry in raw_addresses:
            normalized = self._normalize_address(addr_entry)
            if normalized is not None:
                result.append(normalized)

        return result

    def _normalize_address(self, addr: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize a single FHIR Address dict using scourgify.

        Returns None if the address is a placeholder.
        """
        lines: List[str] = addr.get("line") or []
        city = addr.get("city", "")
        state = addr.get("state", "")
        postal_code = addr.get("postalCode", "")
        country = addr.get("country", "")
        use = addr.get("use", "")
        addr_type = addr.get("type", "")

        line1 = lines[0] if len(lines) > 0 else ""
        line2 = lines[1] if len(lines) > 1 else ""

        # Check for placeholder addresses (D.5)
        if line1 and self._placeholders.is_placeholder_address(line1):
            return None

        # Attempt USPS standardization via scourgify
        normalized_line1, normalized_line2 = self._standardize_street(line1, line2)

        # Normalize city, state, postal with text normalization
        # (preserve spaces for address fields per A.2 exception)
        norm_city = normalize_text(city, preserve_spaces=True) if city else ""
        norm_state = normalize_text(state, preserve_spaces=True) if state else ""
        norm_postal = _normalize_postal_code(postal_code)

        # If everything is empty after normalization, skip
        if not any([normalized_line1, norm_city, norm_state, norm_postal]):
            return None

        result: Dict[str, Any] = {}

        if use:
            result["use"] = use
        if addr_type:
            result["type"] = addr_type

        new_lines: List[str] = []
        if normalized_line1:
            new_lines.append(normalized_line1)
        if normalized_line2:
            new_lines.append(normalized_line2)
        if new_lines:
            result["line"] = new_lines

        if norm_city:
            result["city"] = norm_city
        if norm_state:
            result["state"] = norm_state
        if norm_postal:
            result["postalCode"] = norm_postal
        if country:
            result["country"] = normalize_text(country, preserve_spaces=True)

        return result

    @staticmethod
    def _standardize_street(line1: str, line2: str) -> tuple[str, str]:
        """Standardize street address lines using scourgify.

        Falls back to basic text normalization if scourgify cannot parse.
        """
        if not line1:
            return ("", "")

        # Build a full address string for scourgify
        full_line = line1
        if line2:
            full_line = f"{line1}, {line2}"

        try:
            result = normalize_address_record(full_line)
            norm_line1 = result.get("address_line_1", "") or ""
            norm_line2 = result.get("address_line_2", "") or ""
            return (norm_line1.lower(), norm_line2.lower())
        except (AddressNormalizationError, AmbiguousAddressError):
            logger.debug("scourgify could not normalize address: %s", full_line)
        except Exception:
            logger.debug(
                "Unexpected error normalizing address: %s",
                full_line,
                exc_info=True,
            )

        # Fallback: basic text normalization
        return (
            normalize_text(line1, preserve_spaces=True),
            normalize_text(line2, preserve_spaces=True) if line2 else "",
        )


def _normalize_postal_code(postal: str) -> str:
    """Normalize a US postal code to standard format.

    Preserves ZIP+4 format (12345-6789) but strips other characters.
    """
    if not postal:
        return ""

    # Strip everything except digits and hyphens
    import re

    digits = re.sub(r"[^\d\-]", "", postal)

    # Handle ZIP+4: normalize to XXXXX-XXXX
    clean_digits = digits.replace("-", "")
    if len(clean_digits) == 9:
        return f"{clean_digits[:5]}-{clean_digits[5:]}"
    if len(clean_digits) == 5:
        return clean_digits

    return digits
