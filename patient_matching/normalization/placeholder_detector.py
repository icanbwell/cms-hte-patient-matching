"""Placeholder value detection per requirements D.1-D.5.

Maintains versioned reference tables of non-comparable values and
patterns for each demographic field. When a value is identified as
placeholder, temporary, unknown, test, or otherwise non-comparable,
it is treated as unavailable for matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import FrozenSet, List, Optional, Pattern

TABLE_VERSION = "1.0.0"

# D.4: Newborn temporary names
_NEWBORN_NAMES: FrozenSet[str] = frozenset(
    {
        "babyboy",
        "babygirl",
        "baby",
        "newborn",
        "infantboy",
        "infantgirl",
        "infant",
        "nbboy",
        "nbgirl",
        "nb",
        "boybabyof",
        "girlbabyof",
        "babyof",
        "twinA",
        "twinB",
        "twina",
        "twinb",
    }
)

# D.4: Unidentified patient names
_UNIDENTIFIED_NAMES: FrozenSet[str] = frozenset(
    {
        "unknown",
        "unk",
        "unidentified",
        "doe",
        "johndoe",
        "janedoe",
        "john doe",
        "jane doe",
        "patient",
        "noname",
        "none",
        "na",
        "notapplicable",
        "anonymous",
        "anon",
    }
)

# D.4: Test/training values
_TEST_NAMES: FrozenSet[str] = frozenset(
    {
        "test",
        "testing",
        "testpatient",
        "testuser",
        "demo",
        "demopatient",
        "sample",
        "samplepatient",
        "training",
        "trainingpatient",
        "zztest",
        "zzztestpatient",
        "fake",
        "fakepatient",
        "dummy",
    }
)

# D.4: Unknown-value placeholders
_UNKNOWN_PLACEHOLDERS: FrozenSet[str] = frozenset(
    {
        "unknown",
        "unk",
        "none",
        "na",
        "n/a",
        "notavailable",
        "notapplicable",
        "null",
        "nil",
        "tbd",
        "pending",
        "missing",
        "unavailable",
        "unspecified",
    }
)

# D.2: Regex patterns for placeholder detection
_PLACEHOLDER_NAME_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^baby\s*(boy|girl)?\s*(of\s+)?", re.IGNORECASE),
    re.compile(r"^(boy|girl)\s*baby\s*of\s+", re.IGNORECASE),
    re.compile(r"^infant\s*(boy|girl)?\s*(of\s+)?", re.IGNORECASE),
    re.compile(r"^newborn\s*(boy|girl)?\s*(of\s+)?", re.IGNORECASE),
    re.compile(r"^twin\s*[a-z]$", re.IGNORECASE),
    re.compile(r"^zz+", re.IGNORECASE),
    re.compile(r"^test\s*patient", re.IGNORECASE),
    re.compile(r"^x{2,}$", re.IGNORECASE),
    re.compile(r"^\.+$"),
]

_PLACEHOLDER_PHONE_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^0{7,}$"),
    re.compile(r"^1{10}$"),
    re.compile(r"^5{10}$"),
    re.compile(r"^9{10}$"),
    re.compile(r"^(\d)\1{6,}$"),
    re.compile(r"^1234567890$"),
    re.compile(r"^0000000000$"),
    re.compile(r"^5555555555$"),
]

_PLACEHOLDER_SSN_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^0{3}"),
    re.compile(r"^9{3}"),
    re.compile(r"^000-00-0000$"),
    re.compile(r"^999-99-9999$"),
    re.compile(r"^(\d)\1{2}-\1{2}-\1{4}$"),
]

_PLACEHOLDER_ADDRESS_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^unknown", re.IGNORECASE),
    re.compile(r"^(homeless|no\s*(fixed\s*)?address)", re.IGNORECASE),
    re.compile(r"^general\s*delivery$", re.IGNORECASE),
    re.compile(r"^none$", re.IGNORECASE),
    re.compile(r"^n/?a$", re.IGNORECASE),
]

_PLACEHOLDER_EMAIL_PATTERNS: List[Pattern[str]] = [
    re.compile(
        r"^(test|noreply|no-reply|donotreply|nobody|null|none|fake)", re.IGNORECASE
    ),
    re.compile(r"@(example\.com|test\.com|invalid|nowhere)$", re.IGNORECASE),
]

# v3.3.4: all-zero/all-nine strings, and common payer default/test-enrollment
# values ("PENDING", "TBD", "NONE") for Subscriber/Member IDs.
_PLACEHOLDER_SUBSCRIBER_ID_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^0+$"),
    re.compile(r"^9+$"),
    re.compile(r"^(pending|tbd|none)$", re.IGNORECASE),
]


@dataclass(frozen=True)
class PlaceholderDetector:
    """Detects placeholder, temporary, unknown, test, or non-comparable values.

    All reference tables are versioned per requirement D.1.
    """

    version: str = TABLE_VERSION

    def is_placeholder_name(self, name: str) -> bool:
        """Check if a name value is a placeholder (D.4)."""
        return self.reason_for_name(name) is not None

    def reason_for_name(self, name: str) -> Optional[str]:
        """Why a name value would be treated as a placeholder (D.4), or
        None if it isn't one.

        Reason codes: "empty", "newborn_temp_name", "unidentified_name",
        "test_name", "placeholder_pattern".
        """
        if not name:
            return "empty"

        stripped = re.sub(r"[\s\-\'\.]+", "", name).lower()

        if stripped in _NEWBORN_NAMES:
            return "newborn_temp_name"
        if stripped in _UNIDENTIFIED_NAMES:
            return "unidentified_name"
        if stripped in _TEST_NAMES:
            return "test_name"

        for pattern in _PLACEHOLDER_NAME_PATTERNS:
            if pattern.search(name):
                return "placeholder_pattern"

        return None

    def is_placeholder_date(self, date_str: str) -> bool:
        """Check if a date of birth is placeholder or out of valid range.

        Per requirement D.6: dates before (current_year - 120) or after
        (current_date + 2 days) are treated as unavailable.
        """
        return self.reason_for_date(date_str) is not None

    def reason_for_date(self, date_str: str) -> Optional[str]:
        """Why a date of birth would be treated as unavailable (D.6), or
        None if it's usable.

        Reason codes: "empty", "unknown_placeholder", "unparseable",
        "out_of_range".
        """
        if not date_str:
            return "empty"

        if date_str.lower() in _UNKNOWN_PLACEHOLDERS:
            return "unknown_placeholder"

        try:
            parsed = date.fromisoformat(date_str)
        except ValueError:
            return "unparseable"

        today = date.today()
        min_date = date(today.year - 120, 1, 1)
        max_date = today + timedelta(days=2)

        if parsed < min_date or parsed > max_date:
            return "out_of_range"

        return None

    def is_placeholder_phone(self, phone: str) -> bool:
        """Check if a phone number is a placeholder value."""
        return self.reason_for_phone(phone) is not None

    def reason_for_phone(self, phone: str) -> Optional[str]:
        """Why a phone number would be treated as a placeholder, or None
        if it isn't one.

        Reason codes: "empty", "no_digits", "placeholder_pattern". Does
        not cover format/validity rejections (unparseable, not a valid
        number) -- those are PhoneNormalizer's responsibility, since they
        depend on the `phonenumbers` library, not this placeholder table.
        """
        if not phone:
            return "empty"

        digits = re.sub(r"\D", "", phone)
        if not digits:
            return "no_digits"

        for pattern in _PLACEHOLDER_PHONE_PATTERNS:
            if pattern.match(digits):
                return "placeholder_pattern"

        return None

    def is_placeholder_address(self, address_line: str) -> bool:
        """Check if an address value is a placeholder."""
        return self.reason_for_address(address_line) is not None

    def reason_for_address(self, address_line: str) -> Optional[str]:
        """Why an address line would be treated as a placeholder, or None
        if it isn't one.

        Reason codes: "empty", "unknown_placeholder", "placeholder_pattern".
        """
        if not address_line:
            return "empty"

        stripped = address_line.strip()
        if stripped.lower() in _UNKNOWN_PLACEHOLDERS:
            return "unknown_placeholder"

        for pattern in _PLACEHOLDER_ADDRESS_PATTERNS:
            if pattern.search(stripped):
                return "placeholder_pattern"

        return None

    def is_placeholder_email(self, email: str) -> bool:
        """Check if an email address is a placeholder."""
        return self.reason_for_email(email) is not None

    def reason_for_email(self, email: str) -> Optional[str]:
        """Why an email address would be treated as a placeholder, or
        None if it isn't one.

        Reason codes: "empty", "placeholder_pattern".
        """
        if not email:
            return "empty"

        for pattern in _PLACEHOLDER_EMAIL_PATTERNS:
            if pattern.search(email):
                return "placeholder_pattern"

        return None

    def is_placeholder_ssn(self, ssn: str) -> bool:
        """Check if an SSN is a placeholder value."""
        return self.reason_for_ssn(ssn) is not None

    def reason_for_ssn(self, ssn: str) -> Optional[str]:
        """Why an SSN would be treated as a placeholder, or None if it
        isn't one.

        Reason codes: "empty", "placeholder_pattern".
        """
        if not ssn:
            return "empty"

        for pattern in _PLACEHOLDER_SSN_PATTERNS:
            if pattern.match(ssn):
                return "placeholder_pattern"

        return None

    def is_placeholder_subscriber_id(self, value: str) -> bool:
        """Check if a Subscriber/Member ID is a placeholder value (v3.3.4)."""
        return self.reason_for_subscriber_id(value) is not None

    def reason_for_subscriber_id(self, value: str) -> Optional[str]:
        """Why a Subscriber/Member ID would be treated as a placeholder
        (v3.3.4), or None if it isn't one.

        Reason codes: "empty", "placeholder_pattern".
        """
        if not value:
            return "empty"

        stripped = value.strip()
        for pattern in _PLACEHOLDER_SUBSCRIBER_ID_PATTERNS:
            if pattern.match(stripped):
                return "placeholder_pattern"

        return None

    def is_placeholder_general(self, value: str) -> bool:
        """Check if any string value is a generic placeholder."""
        return self.reason_for_general(value) is not None

    def reason_for_general(self, value: str) -> Optional[str]:
        """Why a generic string value would be treated as a placeholder,
        or None if it isn't one.

        Reason codes: "empty", "unknown_placeholder".
        """
        if not value:
            return "empty"

        stripped = re.sub(r"[\s\-\'\.]+", "", value).lower()
        if stripped in _UNKNOWN_PLACEHOLDERS:
            return "unknown_placeholder"
        return None
