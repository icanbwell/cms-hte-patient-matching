"""Structured record of values normalization dropped, for troubleshooting.

normalize() silently drops placeholder/invalid values per requirements
D.1-D.6 -- e.g. a phone number with a fictional "555" exchange, or a name
matching the literal placeholder list ("jane doe"). That's correct
matching behavior (a dropped value must never be compared), but it leaves
a caller troubleshooting an unexpected no-match with no way to tell "this
field was never on the source Patient" from "it was there, and
normalization silently rejected it" -- both look identical in the
normalized output (the field is just absent).

Report collection is opt-in (see NormalizationManager.normalize_with_report)
so existing callers of normalize() see no behavior change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class DroppedValue:
    """One value normalization discarded before it could reach matching.

    Attributes:
        path: Where the value came from on the source FHIR Patient, e.g.
            "name[0].given[0]", "name[0]" (whole name entry), "birthDate",
            "telecom[1].value", "address[0].line[0]", "identifier[2].value".
        raw_value: The original, pre-normalization string.
        reason: A short, stable code for why it was dropped. Each
            normalizer documents the exact set of codes it can produce
            (see PhoneNormalizer, NameNormalizer, DateNormalizer,
            AddressNormalizer, and PatientNormalizer._normalize_identifiers).
    """

    path: str
    raw_value: str
    reason: str


@dataclass
class NormalizationReport:
    """Collects every DroppedValue produced by one normalize() call."""

    dropped: List[DroppedValue] = field(default_factory=list)

    def record(self, path: str, raw_value: str, reason: str) -> None:
        self.dropped.append(DroppedValue(path=path, raw_value=raw_value, reason=reason))
