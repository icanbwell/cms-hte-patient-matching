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

TABLE_VERSION = "1.1.0"

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

# Spec V.D, Date of Birth: default-fill dates. Spec-literal on purpose: a real 2000-01-01
# birthday is treated as absent. Dates before (current year - 120) are
# already rejected by the range check; they are listed so the reason is explicit.
_PLACEHOLDER_DATES: FrozenSet[str] = frozenset(
    {
        "1800-01-01",
        "1900-01-01",
        "1901-01-01",
        "2000-01-01",
        "1111-11-11",
        "0001-01-01",
    }
)

# Spec V.D, SSN / ITIN Last 4. Spec-literal on purpose: a real last four of 1234/0000/9999
# (or repeated digits) is treated as absent. That only removes evidence, and shared defaults
# are a real false-positive source.
_PLACEHOLDER_LAST4: FrozenSet[str] = frozenset({"0000", "9999", "1234"})
_REPEATED_DIGITS = re.compile(r"^(\d)\1{3}$")

# Spec V.D, Phone: "any number in the 555 exchange" (NXX = 555 of a 10-digit NANP number).
_NANP_555_EXCHANGE = re.compile(r"^1?\d{3}555\d{4}$")

# Spec V.D, First / Last Name: single-character or repeated-character strings ("X", "ZZZ").
_REPEATED_CHARACTER = re.compile(r"^(.)\1{2,}$")

# Unknown-value words that are placeholders when they are a whole name. Deliberately not the
# whole _UNKNOWN_PLACEHOLDERS list: "nil" and "null" are real given names/surnames, and "na"
# is a common Korean surname (it is already in _UNIDENTIFIED_NAMES for the "N/A" spelling).
_UNKNOWN_NAME_WORDS: FrozenSet[str] = frozenset(
    {"tbd", "pending", "missing", "unavailable", "unspecified", "notavailable"}
)

# Reason codes that may drop a FAMILY name on its own (a placeholder family name with a real
# given name). Deliberately narrow:
# - Not the prefix-anchored name patterns ("^infant", "^baby", "^zz+"): they are meant for a
#   given name ("Baby Boy") and would drop real surnames (Infante, Babyak, Zzaman).
# - Not "test_name" or "newborn_temp_name": "Sample", "Demo" and "Baby" are real surnames
#   (Baby is a common Kerala surname), so those words are placeholders only as a given name
#   or when the given name is a placeholder too (that case is handled separately).
FAMILY_NAME_EXACT_REASONS: FrozenSet[str] = frozenset(
    {
        "unidentified_name",
        "unknown_placeholder",
        "single_or_repeated_character",
    }
)

# A second address line that is a unit: has a digit, or is a unit designator word.
_UNIT_LIKE = re.compile(
    r"\d|^(apt|apartment|unit|ste|suite|rm|room|fl|floor|bldg|building|lot|spc|space|"
    r"trlr|trailer|dept|department|ph|bsmt|frnt|rear|ofc|lbby|lowr|uppr|hngr|pier|slip|"
    r"stop|key)\b",
    re.IGNORECASE,
)

# A phone extension, which must not hide a 555 exchange ("212-555-1212 ext 3", "x12", ";ext=4").
_PHONE_EXTENSION = re.compile(
    r"\s*(?:;\s*ext=|,|ext\.?|extension|x|#)\s*\d+\s*$", re.IGNORECASE
)

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

# Spec V.D, Street Address: "123 Main St" only counts as a placeholder when it is not
# accompanied by a real unit; "PO Box 0" always does.
_GENERIC_STREET = re.compile(r"^123\s+main\s+(st|street)\s*[.,]?$", re.IGNORECASE)
_PLACEHOLDER_ADDRESS_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^(p\.?\s*o\.?|post\s+office)\s*box\s*#?\s*0+\s*\.?$", re.IGNORECASE),
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
    re.compile(r"^unknown@", re.IGNORECASE),
]

# Spec V.D, Street Address: ZIP 00000 or 99999.
_PLACEHOLDER_ZIPS: FrozenSet[str] = frozenset({"00000", "99999"})

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

    def reason_for_name(
        self, name: str, *, allow_initial: bool = False
    ) -> Optional[str]:
        """Why a name value would be treated as a placeholder (D.4), or
        None if it isn't one.

        `allow_initial` keeps a single character from counting as a placeholder. Spec V.D
        lists single-character strings ("X") as placeholder names, but an initial in a
        given-name position ("L." for "Lureane") is a legitimate abbreviation the matching
        rules are being extended to use (BAI-1061 levers), and treating it as absent costs
        ONC pairs-tier recall 0.9516 -> 0.9374. Callers pass True for given names.

        DELIBERATE DEVIATION FROM THE CMS SPEC: given-name initials stay matchable although
        V.D lists single-character names as placeholders. A single-character FAMILY name is
        still a placeholder. A ticket to revisit this is to be filed.

        Reason codes: "empty", "newborn_temp_name", "unidentified_name",
        "test_name", "unknown_placeholder", "single_or_repeated_character",
        "placeholder_pattern".
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
        if stripped in _UNKNOWN_NAME_WORDS:
            return "unknown_placeholder"
        if (len(stripped) == 1 and not allow_initial) or _REPEATED_CHARACTER.match(
            stripped
        ):
            return "single_or_repeated_character"

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

        Reason codes: "empty", "unknown_placeholder", "placeholder_date",
        "unparseable", "out_of_range".
        """
        if not date_str:
            return "empty"

        if date_str.lower() in _UNKNOWN_PLACEHOLDERS:
            return "unknown_placeholder"
        if date_str in _PLACEHOLDER_DATES:
            return "placeholder_date"

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

        Reason codes: "empty", "no_digits", "placeholder_pattern",
        "placeholder_555_exchange". Does
        not cover format/validity rejections (unparseable, not a valid
        number) -- those are PhoneNormalizer's responsibility, since they
        depend on the `phonenumbers` library, not this placeholder table.
        """
        if not phone:
            return "empty"

        # An extension must not hide the number it hangs off.
        number = _PHONE_EXTENSION.sub("", phone.strip())
        digits = re.sub(r"\D", "", number)
        if not digits:
            return "no_digits"

        for pattern in _PLACEHOLDER_PHONE_PATTERNS:
            if pattern.match(digits):
                return "placeholder_pattern"
        # The 555 exchange is a North American numbering plan rule: an international number
        # ("+46 8 555 1234") that happens to contain 555 there is not a placeholder.
        international = number.lstrip().startswith("+") and not digits.startswith("1")
        if not international and _NANP_555_EXCHANGE.match(digits):
            return "placeholder_555_exchange"

        return None

    def is_placeholder_address(
        self, address_line: str, *, has_unit: bool = False
    ) -> bool:
        """Check if an address value is a placeholder."""
        return self.reason_for_address(address_line, has_unit=has_unit) is not None

    def reason_for_address(
        self, address_line: str, *, has_unit: bool = False
    ) -> Optional[str]:
        """Why an address line would be treated as a placeholder, or None
        if it isn't one.

        `has_unit` says the address also carries a unit (address line 2): "123 Main St"
        is only a placeholder when it is not accompanied by one (spec V.D).

        Reason codes: "empty", "unknown_placeholder", "placeholder_pattern",
        "generic_street".
        """
        if not address_line:
            return "empty"

        stripped = address_line.strip()
        if stripped.lower() in _UNKNOWN_PLACEHOLDERS:
            return "unknown_placeholder"
        if not has_unit and _GENERIC_STREET.match(stripped):
            return "generic_street"

        for pattern in _PLACEHOLDER_ADDRESS_PATTERNS:
            if pattern.search(stripped):
                return "placeholder_pattern"

        return None

    def looks_like_unit(self, line: Optional[str]) -> bool:
        """True if an address line 2 is a real unit: it has a digit or is a unit designator
        word, and is not itself a placeholder ("N/A", "Unknown"). "Springfield, IL" is not."""
        text = (line or "").strip()
        if not text or self.reason_for_general(text) is not None:
            return False
        return bool(_UNIT_LIKE.search(text))

    def reason_for_postal_code(self, postal_code: str) -> Optional[str]:
        """Why a postal code would be treated as a placeholder (spec V.D: ZIP 00000
        or 99999), or None if it isn't one. Reason code: "placeholder_zip"."""
        digits = re.sub(r"[^0-9]", "", postal_code or "")
        if digits[:5] in _PLACEHOLDER_ZIPS and len(digits) in (5, 9):
            return "placeholder_zip"
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

    def reason_for_ssn_last4(self, last4: str) -> Optional[str]:
        """Why the last four digits of an SSN or ITIN would be treated as a placeholder
        (spec V.D: 0000, 9999, 1234, repeated digits), or None if they aren't.

        Reason code: "placeholder_last4".
        """
        if last4 in _PLACEHOLDER_LAST4 or _REPEATED_DIGITS.match(last4):
            return "placeholder_last4"
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
