"""Name normalization per requirements B.1-B.6.

Handles:
  - Parsing names into discrete components (B.2)
  - Nickname expansion via versioned reference table (B.1)
  - Suffix expansion and comparison (B.5-B.6)
  - Historical/maiden/AKA name collection (B.3)
  - Punctuation and whitespace removal (B.4)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from nicknames import NickNamer

from .placeholder_detector import PlaceholderDetector
from .report import NormalizationReport
from .text_utils import normalize_text

logger = logging.getLogger(__name__)

NICKNAME_TABLE_VERSION = "1.0.0"
SUFFIX_TABLE_VERSION = "1.0.0"

# B.6: Suffix expansion table — maps abbreviations/variants to canonical forms
_SUFFIX_EXPANSIONS: Dict[str, str] = {
    "jr": "jr",
    "junior": "jr",
    "jnr": "jr",
    "sr": "sr",
    "senior": "sr",
    "snr": "sr",
    "i": "i",
    "1st": "i",
    "first": "i",
    "ii": "ii",
    "2nd": "ii",
    "second": "ii",
    "iii": "iii",
    "3rd": "iii",
    "third": "iii",
    "iv": "iv",
    "4th": "iv",
    "fourth": "iv",
    "v": "v",
    "5th": "v",
    "fifth": "v",
    "vi": "vi",
    "6th": "vi",
    "esq": "esq",
    "esquire": "esq",
    "md": "md",
    "phd": "phd",
    "do": "do",
    "dds": "dds",
}


@dataclass
class NormalizedName:
    """A fully normalized name with all components separated.

    Attributes:
        given: Normalized first/given name(s).
        middle: Normalized middle name(s).
        family: Normalized last/family name.
        suffix: Canonical suffix (e.g. 'jr', 'iii').
        prefix: Normalized prefix/title.
        text: Full text representation.
        nicknames: Set of known nicknames for the given name.
        is_placeholder: Whether this name was detected as placeholder.
    """

    given: str = ""
    middle: str = ""
    family: str = ""
    suffix: str = ""
    prefix: str = ""
    text: str = ""
    nicknames: Set[str] = field(default_factory=set)
    is_placeholder: bool = False


class NameNormalizer:
    """Normalizes FHIR HumanName entries per CMS matching requirements.

    Args:
        placeholder_detector: Detector for placeholder/test values.
    """

    def __init__(
        self,
        *,
        placeholder_detector: Optional[PlaceholderDetector] = None,
    ) -> None:
        self._placeholders = placeholder_detector or PlaceholderDetector()
        self._nicker = NickNamer()

    @property
    def nickname_table_version(self) -> str:
        return NICKNAME_TABLE_VERSION

    @property
    def suffix_table_version(self) -> str:
        return SUFFIX_TABLE_VERSION

    def normalize_patient_names(
        self,
        patient: Dict[str, Any],
        *,
        report: Optional[NormalizationReport] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize all name entries on a FHIR Patient resource.

        Returns a new list of FHIR HumanName dicts with normalized values
        and nickname expansions added. Placeholder names are excluded --
        pass `report` to record why (see PlaceholderDetector.reason_for_name).
        """
        raw_names: List[Dict[str, Any]] = patient.get("name", [])
        if not raw_names:
            return []

        result: List[Dict[str, Any]] = []
        for index, name_entry in enumerate(raw_names):
            normalized = self._normalize_human_name(
                name_entry, index=index, report=report
            )
            if normalized is not None:
                result.append(normalized)

        return result

    def normalize_suffix(self, suffix: str) -> str:
        """Normalize a suffix to its canonical form using the expansion table."""
        cleaned = normalize_text(suffix)
        return _SUFFIX_EXPANSIONS.get(cleaned, cleaned)

    def get_nicknames(self, given_name: str) -> Set[str]:
        """Look up known nicknames for a given name.

        Returns a set of normalized nickname strings (all lowercase,
        no punctuation/whitespace).
        """
        if not given_name:
            return set()

        cleaned = normalize_text(given_name)
        try:
            raw_nicknames = tuple(self._nicker.nicknames_of(cleaned))
        except Exception:
            raw_nicknames = ()

        result: Set[str] = set()
        for nick in raw_nicknames:
            normalized = normalize_text(nick)
            if normalized and normalized != cleaned:
                result.add(normalized)
        return result

    def suffixes_conflict(
        self, suffix_a: Optional[str], suffix_b: Optional[str]
    ) -> bool:
        """Check if two suffixes conflict per requirement B.5.

        If a generational suffix can be identified on BOTH sides
        and they do not match, this returns True (the match must be negated).
        Returns False if either side has no suffix.
        """
        if not suffix_a or not suffix_b:
            return False

        canon_a = self.normalize_suffix(suffix_a)
        canon_b = self.normalize_suffix(suffix_b)

        if not canon_a or not canon_b:
            return False

        return canon_a != canon_b

    def _normalize_human_name(
        self,
        name_entry: Dict[str, Any],
        *,
        index: int = 0,
        report: Optional[NormalizationReport] = None,
    ) -> Optional[Dict[str, Any]]:
        """Normalize a single FHIR HumanName dict.

        Returns None if the name is detected as a placeholder.
        """
        family = name_entry.get("family") or ""
        given_list: List[str] = name_entry.get("given") or []
        suffix_list: List[str] = name_entry.get("suffix") or []
        prefix_list: List[str] = name_entry.get("prefix") or []
        text = name_entry.get("text") or ""
        use = name_entry.get("use") or ""

        # Normalize components
        norm_family = normalize_text(family) if family else ""
        norm_given = [normalize_text(g) for g in given_list if g]
        norm_suffix = [self.normalize_suffix(s) for s in suffix_list if s]
        norm_prefix = [normalize_text(p) for p in prefix_list if p]

        # Check for placeholders (D.5 — applies to both requestor and responder)
        primary_given = norm_given[0] if norm_given else ""
        full_name = f"{primary_given}{norm_family}"

        given_reason = self._placeholders.reason_for_name(primary_given)
        family_reason = self._placeholders.reason_for_name(norm_family)
        if given_reason is not None and family_reason is not None:
            if report is not None:
                raw = f"{given_list[0] if given_list else ''} {family}".strip()
                report.record(f"name[{index}]", raw, family_reason)
            return None

        full_name_reason = (
            self._placeholders.reason_for_name(full_name) if full_name else None
        )
        if full_name_reason is not None:
            if report is not None:
                raw = f"{given_list[0] if given_list else ''} {family}".strip()
                report.record(f"name[{index}]", raw, full_name_reason)
            return None

        # Build normalized FHIR HumanName
        result: Dict[str, Any] = {}
        if use:
            result["use"] = use

        if norm_family:
            result["family"] = norm_family

        if norm_given:
            result["given"] = norm_given
            # Add nicknames for the primary given name (B.1)
            nicks = self.get_nicknames(primary_given)
            if nicks:
                result["_nicknames"] = sorted(nicks)

        if norm_suffix:
            result["suffix"] = norm_suffix

        if norm_prefix:
            result["prefix"] = norm_prefix

        if text:
            result["text"] = normalize_text(text, preserve_spaces=True)

        return result
