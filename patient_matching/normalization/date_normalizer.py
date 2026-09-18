"""Date of birth normalization per requirements A.5 and D.6.

- Full dates are represented as YYYY-MM-DD.
- Partial dates (year-only or year-month) are preserved as-is and
  SHALL NOT be imputed, padded, or converted to a full date.
- Unknown or out-of-range dates are treated as unavailable.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .placeholder_detector import PlaceholderDetector
from .report import NormalizationReport

_FULL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_YEAR_ONLY_RE = re.compile(r"^\d{4}$")


class DateNormalizer:
    """Normalizes date of birth values for patient matching.

    Args:
        placeholder_detector: Detector for placeholder date values.
    """

    def __init__(
        self,
        *,
        placeholder_detector: Optional[PlaceholderDetector] = None,
    ) -> None:
        self._placeholders = placeholder_detector or PlaceholderDetector()

    def normalize_birth_date(
        self,
        birth_date: str,
        *,
        report: Optional[NormalizationReport] = None,
    ) -> Optional[str]:
        """Normalize a birth date string.

        Args:
            birth_date: The raw date string from the FHIR Patient resource.
            report: If given, records why a dropped value was dropped.
                Reason codes: PlaceholderDetector.reason_for_date's codes
                ("empty", "unknown_placeholder", "unparseable",
                "out_of_range" -- reused here for the partial-date year-
                range check too), plus "unrecognized_format" for a string
                that matches none of YYYY-MM-DD/YYYY-MM/YYYY.

        Returns:
            A normalized date string (YYYY-MM-DD, YYYY-MM, or YYYY),
            or None if the date is a placeholder, invalid, or out of range.
        """
        if not birth_date:
            if report is not None:
                report.record("birthDate", birth_date, "empty")
            return None

        stripped = birth_date.strip()

        # Full date: YYYY-MM-DD
        if _FULL_DATE_RE.match(stripped):
            reason = self._placeholders.reason_for_date(stripped)
            if reason is not None:
                if report is not None:
                    report.record("birthDate", birth_date, reason)
                return None
            return stripped

        # Partial: YYYY-MM — preserve as-is, validate year range
        if _YEAR_MONTH_RE.match(stripped):
            year = int(stripped[:4])
            if not self._is_valid_year(year):
                if report is not None:
                    report.record("birthDate", birth_date, "out_of_range")
                return None
            return stripped

        # Partial: YYYY — preserve as-is, validate year range
        if _YEAR_ONLY_RE.match(stripped):
            year = int(stripped)
            if not self._is_valid_year(year):
                if report is not None:
                    report.record("birthDate", birth_date, "out_of_range")
                return None
            return stripped

        # Not a recognized format
        if report is not None:
            report.record("birthDate", birth_date, "unrecognized_format")
        return None

    @staticmethod
    def _is_valid_year(year: int) -> bool:
        """Check if a year is within the acceptable range.

        Per D.6: years before (current_year - 120) or after
        current_year are treated as unavailable.
        """
        today = date.today()
        return (today.year - 120) <= year <= today.year
