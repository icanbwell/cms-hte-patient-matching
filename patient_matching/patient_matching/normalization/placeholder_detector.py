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
from typing import FrozenSet, List, Pattern

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


@dataclass(frozen=True)
class PlaceholderDetector:
    """Detects placeholder, temporary, unknown, test, or non-comparable values.

    All reference tables are versioned per requirement D.1.
    """

    version: str = TABLE_VERSION

    def is_placeholder_name(self, name: str) -> bool:
        """Check if a name value is a placeholder (D.4)."""
        if not name:
            return True

        stripped = re.sub(r"[\s\-\'\.]+", "", name).lower()

        if stripped in _NEWBORN_NAMES:
            return True
        if stripped in _UNIDENTIFIED_NAMES:
            return True
        if stripped in _TEST_NAMES:
            return True

        for pattern in _PLACEHOLDER_NAME_PATTERNS:
            if pattern.search(name):
                return True

        return False

    def is_placeholder_date(self, date_str: str) -> bool:
        """Check if a date of birth is placeholder or out of valid range.

        Per requirement D.6: dates before (current_year - 120) or after
        (current_date + 2 days) are treated as unavailable.
        """
        if not date_str:
            return True

        if date_str.lower() in _UNKNOWN_PLACEHOLDERS:
            return True

        try:
            parsed = date.fromisoformat(date_str)
        except ValueError:
            return True

        today = date.today()
        min_date = date(today.year - 120, 1, 1)
        max_date = today + timedelta(days=2)

        if parsed < min_date or parsed > max_date:
            return True

        return False

    def is_placeholder_phone(self, phone: str) -> bool:
        """Check if a phone number is a placeholder value."""
        if not phone:
            return True

        digits = re.sub(r"\D", "", phone)
        if not digits:
            return True

        for pattern in _PLACEHOLDER_PHONE_PATTERNS:
            if pattern.match(digits):
                return True

        return False

    def is_placeholder_address(self, address_line: str) -> bool:
        """Check if an address value is a placeholder."""
        if not address_line:
            return True

        stripped = address_line.strip()
        if stripped.lower() in _UNKNOWN_PLACEHOLDERS:
            return True

        for pattern in _PLACEHOLDER_ADDRESS_PATTERNS:
            if pattern.search(stripped):
                return True

        return False

    def is_placeholder_email(self, email: str) -> bool:
        """Check if an email address is a placeholder."""
        if not email:
            return True

        for pattern in _PLACEHOLDER_EMAIL_PATTERNS:
            if pattern.search(email):
                return True

        return False

    def is_placeholder_ssn(self, ssn: str) -> bool:
        """Check if an SSN is a placeholder value."""
        if not ssn:
            return True

        for pattern in _PLACEHOLDER_SSN_PATTERNS:
            if pattern.match(ssn):
                return True

        return False

    def is_placeholder_general(self, value: str) -> bool:
        """Check if any string value is a generic placeholder."""
        if not value:
            return True

        stripped = re.sub(r"[\s\-\'\.]+", "", value).lower()
        return stripped in _UNKNOWN_PLACEHOLDERS
