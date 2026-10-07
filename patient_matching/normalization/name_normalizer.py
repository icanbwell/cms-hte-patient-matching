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
import re
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
    "sixth": "vi",
    "vii": "vii",
    "7th": "vii",
    "seventh": "vii",
    "viii": "viii",
    "8th": "viii",
    "eighth": "viii",
    "ix": "ix",
    "9th": "ix",
    "ninth": "ix",
    "x": "x",
    "10th": "x",
    "tenth": "x",
    "2d": "ii",
    "3d": "iii",
    "esq": "esq",
    "esquire": "esq",
    "md": "md",
    "phd": "phd",
    "do": "do",
    "dds": "dds",
}


# The canonical forms in _SUFFIX_EXPANSIONS that are generational ("Jr", "III"). Only these can
# veto a match (spec Name Handling: "If a generational suffix can be identified on both the query
# and the response and they do not match..."); a professional or honorific suffix (MD, PhD, Esq)
# says nothing about which generation of a family someone is.
GENERATIONAL_SUFFIXES: frozenset[str] = frozenset(
    {"jr", "sr", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
)

# A raw suffix string can hold several ("Jr., MD", "Jr III") or an article ("the second").
_SUFFIX_SPLIT = re.compile(r"[\s,;]+")
_SUFFIX_STOPWORDS = frozenset({"the"})


def split_suffix(raw: str) -> List[str]:
    """Break a raw suffix string into its separate suffixes ("Jr., MD" -> ["Jr.", "MD"])."""
    return [
        t for t in _SUFFIX_SPLIT.split(raw) if t and t.lower() not in _SUFFIX_STOPWORDS
    ]


def canonical_suffix(token: str) -> str:
    """One suffix token in its canonical form ("Jr." -> "jr", "2nd" -> "ii")."""
    cleaned = normalize_text(token)
    return _SUFFIX_EXPANSIONS.get(cleaned, cleaned)


def generational_suffixes(raw: Any) -> Set[str]:
    """The generational suffixes in a raw suffix value (a string, possibly compound)."""
    if not isinstance(raw, str):
        return set()
    return {
        canon
        for canon in (canonical_suffix(token) for token in split_suffix(raw))
        if canon in GENERATIONAL_SUFFIXES
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
        return canonical_suffix(suffix)

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
        Returns False if either side has no generational suffix (a non-generational
        suffix such as "md" never conflicts).
        """
        if not suffix_a or not suffix_b:
            return False

        generational_a = generational_suffixes(suffix_a)
        generational_b = generational_suffixes(suffix_b)

        if not generational_a or not generational_b:
            return False

        return generational_a.isdisjoint(generational_b)

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
        # A bare string is one suffix (not a sequence of characters); a compound string
        # ("Jr., MD") is split into its separate suffixes.
        if isinstance(suffix_list, str):
            suffix_list = [suffix_list]
        norm_suffix = [
            self.normalize_suffix(token)
            for s in suffix_list
            if s
            for token in split_suffix(s)
        ]
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

        # A placeholder given name ("Baby Girl") with a real family name keeps
        # the family and drops the given names. The prefix-anchored patterns
        # would otherwise flag the concatenated given+family string below and
        # discard the real family name along with the placeholder.
        if given_reason is not None:
            if report is not None and norm_given:
                raw_given = next(g for g in given_list if g)
                report.record(f"name[{index}].given", raw_given, given_reason)
            norm_given = []
            primary_given = ""
            full_name = norm_family

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
