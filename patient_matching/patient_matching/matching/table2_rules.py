"""Table 2: Approved matching combinations from CMS Proposal v3.2.2.

Each rule defines the required fields, which fields allow fuzzy matching
(marked with * in the spec), and the maximum number of simultaneously
fuzzy fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class FieldRole(Enum):
    """How a field participates in a matching rule."""

    EXACT = "exact"
    FUZZY_ELIGIBLE = "fuzzy_eligible"


@dataclass(frozen=True)
class RuleField:
    """A field within a matching rule.

    Attributes:
        name: Canonical field name.
        role: Whether this field must be exact or may be fuzzy.
    """

    name: str
    role: FieldRole = FieldRole.EXACT


@dataclass(frozen=True)
class MatchingRule:
    """A single Table 2 approved matching combination.

    Attributes:
        rule_id: Two-digit identifier from Table 2 (e.g. "01").
        description: Human-readable description of the combination.
        fields: The required fields and their roles.
        max_fuzzy_fields: Maximum fields that may use fuzzy matching
            simultaneously. Default 1 per spec; some rules allow more.
        p_collision_exact: Conservative P(collision) for exact matching.
        p_collision_fuzzy: Conservative P(collision) for fuzzy matching.
    """

    rule_id: str
    description: str
    fields: tuple[RuleField, ...]
    max_fuzzy_fields: int = 1
    p_collision_exact: float = 0.0
    p_collision_fuzzy: float = 0.0


# Canonical field name constants
FIRST_NAME = "first_name"
LAST_NAME = "last_name"
DOB = "dob"
STREET_LINE = "street_line"
PHONE = "phone"
EMAIL = "email"
SSN_LAST4 = "ssn_last4"
ITIN_LAST4 = "itin_last4"
MBI = "mbi"
LEGAL_ID = "legal_id"
NAMESPACE_ID = "namespace_id"

# Helper constructors
_E = FieldRole.EXACT
_F = FieldRole.FUZZY_ELIGIBLE


def _rf(name: str, role: FieldRole = _E) -> RuleField:
    return RuleField(name=name, role=role)


APPROVED_RULES: tuple[MatchingRule, ...] = (
    MatchingRule(
        rule_id="01",
        description="First Name* + Last Name* + DOB + Street Line*",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(STREET_LINE, _F),
        ),
        max_fuzzy_fields=2,
        p_collision_exact=3e-13,
        p_collision_fuzzy=9e-13,
    ),
    MatchingRule(
        rule_id="02",
        description="First Name + Last Name* + DOB + Phone Number",
        fields=(
            _rf(FIRST_NAME),
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(PHONE),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=1e-14,
        p_collision_fuzzy=2e-14,
    ),
    MatchingRule(
        rule_id="03",
        description="First Name* + Last Name* + DOB + Email Address",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(EMAIL),
        ),
        max_fuzzy_fields=2,
        p_collision_exact=1e-14,
        p_collision_fuzzy=3e-14,
    ),
    MatchingRule(
        rule_id="04",
        description="First Name* + Last Name + DOB + SSN Last 4",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME),
            _rf(DOB),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=1e-12,
        p_collision_fuzzy=2e-12,
    ),
    MatchingRule(
        rule_id="05",
        description="First Name + Last Name* + DOB + SSN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=1e-12,
        p_collision_fuzzy=2e-12,
    ),
    MatchingRule(
        rule_id="06",
        description="First Name* + Last Name + DOB + ITIN Last 4",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME),
            _rf(DOB),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=1e-12,
        p_collision_fuzzy=2e-12,
    ),
    MatchingRule(
        rule_id="07",
        description="First Name + Last Name* + DOB + ITIN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=1e-12,
        p_collision_fuzzy=2e-12,
    ),
    MatchingRule(
        rule_id="08",
        description="First Name + DOB + MBI",
        fields=(
            _rf(FIRST_NAME),
            _rf(DOB),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="09",
        description="First Name + DOB + Legal ID",
        fields=(
            _rf(FIRST_NAME),
            _rf(DOB),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="10",
        description="Last Name* + DOB + Legal ID",
        fields=(
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=5e-13,
        p_collision_fuzzy=1e-12,
    ),
    MatchingRule(
        rule_id="11",
        description="First Name + DOB + Phone Number",
        fields=(
            _rf(FIRST_NAME),
            _rf(DOB),
            _rf(PHONE),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="12",
        description="First Name + DOB + Email Address",
        fields=(
            _rf(FIRST_NAME),
            _rf(DOB),
            _rf(EMAIL),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="13",
        description="Last Name + Phone Number + SSN Last 4",
        fields=(
            _rf(LAST_NAME),
            _rf(PHONE),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=5e-13,
    ),
    MatchingRule(
        rule_id="14",
        description="Last Name + Phone Number + ITIN Last 4",
        fields=(
            _rf(LAST_NAME),
            _rf(PHONE),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=5e-13,
    ),
    MatchingRule(
        rule_id="15",
        description="Last Name* + Email Address + SSN Last 4",
        fields=(
            _rf(LAST_NAME, _F),
            _rf(EMAIL),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=5e-13,
        p_collision_fuzzy=1e-12,
    ),
    MatchingRule(
        rule_id="16",
        description="Last Name* + Email Address + ITIN Last 4",
        fields=(
            _rf(LAST_NAME, _F),
            _rf(EMAIL),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=5e-13,
        p_collision_fuzzy=1e-12,
    ),
    MatchingRule(
        rule_id="17",
        description="First Name + Phone Number + SSN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(PHONE),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="18",
        description="First Name + Phone Number + ITIN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(PHONE),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="19",
        description="First Name + Email Address + SSN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(EMAIL),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="20",
        description="First Name + Email Address + ITIN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(EMAIL),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=2e-12,
    ),
    MatchingRule(
        rule_id="21",
        description="Phone Number + MBI",
        fields=(
            _rf(PHONE),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=1e-12,
    ),
    MatchingRule(
        rule_id="22",
        description="Phone Number + Legal ID (w/issuing-authority namespace)",
        fields=(
            _rf(PHONE),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=1e-12,
    ),
    MatchingRule(
        rule_id="23",
        description="Email Address + MBI",
        fields=(
            _rf(EMAIL),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=1e-12,
    ),
    MatchingRule(
        rule_id="24",
        description="Email Address + Legal ID (w/issuing-authority namespace)",
        fields=(
            _rf(EMAIL),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=1e-12,
    ),
    MatchingRule(
        rule_id="25",
        description="Legal ID + MBI",
        fields=(
            _rf(LEGAL_ID),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=1e-12,
    ),
    MatchingRule(
        rule_id="26",
        description="Namespace bound unique identifiers (EMPI, FHIR Patient ID, CSP UUID)",
        fields=(_rf(NAMESPACE_ID),),
        max_fuzzy_fields=0,
        p_collision_exact=0.0,
    ),
)
