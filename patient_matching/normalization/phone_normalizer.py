"""Phone number normalization per requirements C.3-C.4.

Normalizes all phone numbers to E.164 format. Phone numbers match
regardless of designated type (home, cell, work, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import phonenumbers

from .placeholder_detector import PlaceholderDetector
from .report import NormalizationReport

logger = logging.getLogger(__name__)

_DEFAULT_REGION = "US"


class PhoneNormalizer:
    """Normalizes FHIR ContactPoint phone entries to E.164 format.

    Args:
        default_region: Default region code for parsing phone numbers
            without a country code. Defaults to "US".
        placeholder_detector: Detector for placeholder phone values.
    """

    def __init__(
        self,
        *,
        default_region: str = _DEFAULT_REGION,
        placeholder_detector: Optional[PlaceholderDetector] = None,
    ) -> None:
        self._default_region = default_region
        self._placeholders = placeholder_detector or PlaceholderDetector()

    def normalize_patient_telecoms(
        self,
        patient: Dict[str, Any],
        *,
        report: Optional[NormalizationReport] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize all telecom entries on a FHIR Patient resource.

        Phone numbers are converted to E.164. Email addresses are
        lowercased. Placeholder values are excluded -- pass `report` to
        record why (see normalize_phone's reason codes, and
        PlaceholderDetector.reason_for_email for dropped emails).
        """
        raw_telecoms: List[Dict[str, Any]] = patient.get("telecom", [])
        if not raw_telecoms:
            return []

        result: List[Dict[str, Any]] = []
        for index, telecom in enumerate(raw_telecoms):
            normalized = self._normalize_telecom(telecom, index=index, report=report)
            if normalized is not None:
                result.append(normalized)

        return result

    def normalize_phone(
        self,
        phone_str: str,
        *,
        path: str = "phone",
        report: Optional[NormalizationReport] = None,
    ) -> Optional[str]:
        """Normalize a phone number string to E.164 format.

        Args:
            phone_str: Raw phone number string.
            path: Where this value came from, for `report` (e.g.
                "telecom[1].value").
            report: If given, records why a dropped value was dropped.
                Reason codes: PlaceholderDetector.reason_for_phone's codes,
                plus "unparseable" (phonenumbers couldn't parse it at all)
                and "invalid_number" (parsed, but neither a valid number nor
                a well-formed NANP one -- see _is_well_formed_nanp).

        Returns:
            E.164 formatted string (e.g. "+15551234567"), or None
            if the number cannot be parsed or is invalid.
        """
        if not phone_str:
            if report is not None:
                report.record(path, phone_str, "empty")
            return None

        placeholder_reason = self._placeholders.reason_for_phone(phone_str)
        if placeholder_reason is not None:
            if report is not None:
                report.record(path, phone_str, placeholder_reason)
            return None

        try:
            parsed = phonenumbers.parse(phone_str, self._default_region)
            if not (
                phonenumbers.is_valid_number(parsed)
                or self._is_well_formed_nanp(parsed)
            ):
                if report is not None:
                    report.record(path, phone_str, "invalid_number")
                return None
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException:
            logger.debug("Could not parse phone number: %s", phone_str)
            if report is not None:
                report.record(path, phone_str, "unparseable")
            return None

    @staticmethod
    def _is_well_formed_nanp(parsed: phonenumbers.PhoneNumber) -> bool:
        """A +1 number that is invalid only because its exchange is unassigned.

        `phonenumbers.is_valid_number` requires an assigned area code *and*
        exchange. ~11% of ONC's synthetic phones have a well-formed number with
        an unassigned exchange (leading 0/1), which it rejects. Those are still
        usable identifiers - two records holding the same number are linked by
        it, so dropping them silently discards real match evidence. Detected by
        re-checking with the exchange's first digit swapped for a valid one, so
        unassigned area codes (e.g. 555) and wrong lengths are still rejected.
        Placeholders (0000000000, 5555555555, ...) are caught earlier by
        PlaceholderDetector.
        """
        national = str(parsed.national_number)
        if parsed.country_code != 1 or len(national) != 10 or national[3] not in "01":
            return False
        probe = phonenumbers.parse(f"+1{national[:3]}2{national[4:]}")
        return phonenumbers.is_valid_number(probe)

    def _normalize_telecom(
        self,
        telecom: Dict[str, Any],
        *,
        index: int = 0,
        report: Optional[NormalizationReport] = None,
    ) -> Optional[Dict[str, Any]]:
        """Normalize a single FHIR ContactPoint dict."""
        system = telecom.get("system", "")
        value = telecom.get("value", "")
        use = telecom.get("use", "")

        if not value:
            return None

        result: Dict[str, Any] = {}
        path = f"telecom[{index}].value"

        if system == "phone":
            normalized_phone = self.normalize_phone(value, path=path, report=report)
            if normalized_phone is None:
                return None
            result["system"] = "phone"
            result["value"] = normalized_phone
        elif system == "email":
            normalized_email = value.strip().lower()
            email_reason = self._placeholders.reason_for_email(normalized_email)
            if email_reason is not None:
                if report is not None:
                    report.record(path, value, email_reason)
                return None
            result["system"] = "email"
            result["value"] = normalized_email
        else:
            # Pass through other systems (fax, pager, etc.) with basic normalization
            result["system"] = system
            result["value"] = value.strip()

        if use:
            result["use"] = use

        # Preserve any other fields (rank, period, etc.)
        for key in telecom:
            if key not in ("system", "value", "use"):
                result[key] = telecom[key]

        return result
