"""Table 2 Category 1 (flat) rules: approved matching combinations per CMS
Proposal v3.4.0.

Each rule defines the required fields, which fields allow fuzzy matching
(marked with * in the spec), and the maximum number of simultaneously
fuzzy fields. `rule_id` values match v3.4.0's clean 01-30 Category 1
numbering (session 16). Category 2 (household+individual) rules live in
household_rules.py under a `C2-` prefix (`C2-13`, `C2-14`, ..., `C2-38`) -
v3.4.0's renumbering happens to reassign bare 13-16 to unrelated new flat
rules here, so Category 2 keeps its historically-meaningful numbers but
prefixed, to avoid colliding with this module's IDs (see household_rules.py's
module docstring for the full rationale).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .collision import p_collision


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
# CMS v3.3 additions (session 6)
ZIP_CODE = "zip_code"
INSURANCE_MEMBER_ID = "insurance_member_id"
INSURANCE_SUBSCRIBER_ID = "insurance_subscriber_id"

# Helper constructors
_E = FieldRole.EXACT
_F = FieldRole.FUZZY_ELIGIBLE


def _rf(name: str, role: FieldRole = _E) -> RuleField:
    return RuleField(name=name, role=role)


# Rules 13, 14, 15, 16 (v3.2.2 flat combinations using Last Name + Phone/Email +
# SSN/ITIN Last 4) were amended by CMS v3.3.1 into the Household/Individual
# two-step architecture, since Phone/Email/SSN-Last-4 are frequently shared by
# an entire household and can only establish "same household," not "same
# person," on their own. Their Category 2 replacements live in
# household_rules.py's CATEGORY_2_RULES, alongside new rules 34/35/37/38.
APPROVED_RULES: tuple[MatchingRule, ...] = (
    MatchingRule(
        rule_id="01",
        description="First Name* + Last Name* + DOB* + Street Line*",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME, _F),
            _rf(DOB, _F),
            _rf(STREET_LINE, _F),
        ),
        max_fuzzy_fields=2,
        p_collision_exact=p_collision(
            (
                _rf(FIRST_NAME, _F),
                _rf(LAST_NAME, _F),
                _rf(DOB, _F),
                _rf(STREET_LINE, _F),
            )
        ),
        # v3.4.0 marks DOB fuzzy-eligible (+/-1 day) here too - like rule 24's
        # Last Name*+DOB*, this doesn't change the fuzzy figure itself (Table 3
        # has no dob-fuzzy u-value; see matching_engine.py's DOB-fuzzy dispatch
        # note), so fuzzy_fields below is unchanged from the pre-v3.4.0 figure.
        p_collision_fuzzy=p_collision(
            (
                _rf(FIRST_NAME, _F),
                _rf(LAST_NAME, _F),
                _rf(DOB, _F),
                _rf(STREET_LINE, _F),
            ),
            fuzzy_fields=frozenset({FIRST_NAME, LAST_NAME}),
        ),
    ),
    MatchingRule(
        rule_id="02",
        description="First Name + Last Name* + DOB* + Phone Number",
        fields=(
            _rf(FIRST_NAME),
            _rf(LAST_NAME, _F),
            _rf(DOB, _F),
            _rf(PHONE),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME), _rf(LAST_NAME, _F), _rf(DOB, _F), _rf(PHONE))
        ),
        # v3.4.0 DOB* addition - no numeric effect, see rule 01's comment above.
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME), _rf(LAST_NAME, _F), _rf(DOB, _F), _rf(PHONE)),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
    ),
    MatchingRule(
        rule_id="03",
        description="First Name* + Last Name* + DOB* + Email Address",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME, _F),
            _rf(DOB, _F),
            _rf(EMAIL),
        ),
        max_fuzzy_fields=2,
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(DOB, _F), _rf(EMAIL))
        ),
        # v3.4.0 DOB* addition - no numeric effect, see rule 01's comment above.
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(DOB, _F), _rf(EMAIL)),
            fuzzy_fields=frozenset({FIRST_NAME, LAST_NAME}),
        ),
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
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME), _rf(DOB), _rf(SSN_LAST4))
        ),
        # Computed 1.5e-12, not the v3.2.2-era hardcoded 2e-12: that value implicitly
        # assumed a first_name fuzzy u of 0.04 (2x exact); the real v3.3 Table 3 states
        # 0.03 (1.5x). This is the drift this evaluator exists to catch - see
        # docs/sessions/pending/session_5.md Task 3.
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME), _rf(DOB), _rf(SSN_LAST4)),
            fuzzy_fields=frozenset({FIRST_NAME}),
        ),
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
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME), _rf(LAST_NAME, _F), _rf(DOB), _rf(SSN_LAST4))
        ),
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME), _rf(LAST_NAME, _F), _rf(DOB), _rf(SSN_LAST4)),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
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
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME), _rf(DOB), _rf(ITIN_LAST4))
        ),
        # Same 1.5e-12 drift as rule 04 above (first_name fuzzy u: 0.03, not the
        # v3.2.2-era 0.04 implicit assumption).
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME), _rf(DOB), _rf(ITIN_LAST4)),
            fuzzy_fields=frozenset({FIRST_NAME}),
        ),
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
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME), _rf(LAST_NAME, _F), _rf(DOB), _rf(ITIN_LAST4))
        ),
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME), _rf(LAST_NAME, _F), _rf(DOB), _rf(ITIN_LAST4)),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
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
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(DOB), _rf(MBI))),
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
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(DOB), _rf(LEGAL_ID))),
    ),
    MatchingRule(
        rule_id="10",
        description="Last Name* + DOB* + Legal ID",
        fields=(
            _rf(LAST_NAME, _F),
            _rf(DOB, _F),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=p_collision(
            (_rf(LAST_NAME, _F), _rf(DOB, _F), _rf(LEGAL_ID))
        ),
        # v3.4.0 DOB* addition - no numeric effect, see rule 01's comment above.
        p_collision_fuzzy=p_collision(
            (_rf(LAST_NAME, _F), _rf(DOB, _F), _rf(LEGAL_ID)),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
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
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(DOB), _rf(PHONE))),
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
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(DOB), _rf(EMAIL))),
    ),
    MatchingRule(
        rule_id="13",
        description="First Name + Phone Number + SSN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(PHONE),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(PHONE), _rf(SSN_LAST4))),
    ),
    MatchingRule(
        rule_id="14",
        description="First Name + Phone Number + ITIN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(PHONE),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(PHONE), _rf(ITIN_LAST4))),
    ),
    MatchingRule(
        rule_id="15",
        description="First Name + Email Address + SSN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(EMAIL),
            _rf(SSN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(EMAIL), _rf(SSN_LAST4))),
    ),
    MatchingRule(
        rule_id="16",
        description="First Name + Email Address + ITIN Last 4",
        fields=(
            _rf(FIRST_NAME),
            _rf(EMAIL),
            _rf(ITIN_LAST4),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(EMAIL), _rf(ITIN_LAST4))),
    ),
    MatchingRule(
        rule_id="17",
        description="Phone Number + MBI",
        fields=(
            _rf(PHONE),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(PHONE), _rf(MBI))),
    ),
    MatchingRule(
        rule_id="18",
        description="Phone Number + Legal ID (w/issuing-authority namespace)",
        fields=(
            _rf(PHONE),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(PHONE), _rf(LEGAL_ID))),
    ),
    MatchingRule(
        rule_id="19",
        description="Email Address + MBI",
        fields=(
            _rf(EMAIL),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(EMAIL), _rf(MBI))),
    ),
    MatchingRule(
        rule_id="20",
        description="Email Address + Legal ID (w/issuing-authority namespace)",
        fields=(
            _rf(EMAIL),
            _rf(LEGAL_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(EMAIL), _rf(LEGAL_ID))),
    ),
    MatchingRule(
        rule_id="21",
        description="Legal ID + MBI",
        fields=(
            _rf(LEGAL_ID),
            _rf(MBI),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(LEGAL_ID), _rf(MBI))),
    ),
    MatchingRule(
        rule_id="22",
        description="Namespace bound unique identifiers (EMPI, FHIR Patient ID, CSP UUID)",
        fields=(_rf(NAMESPACE_ID),),
        max_fuzzy_fields=0,
        # Computed as 1e-15, not literally 0.0 - see collision.FIELD_U_PROBS's
        # namespace_id entry for why a small nonzero float is used instead (avoids
        # masking other fields' probabilities in a product elsewhere).
        p_collision_exact=p_collision((_rf(NAMESPACE_ID),)),
    ),
    # --- CMS v3.3.0 base spec additions (session 6) ---
    MatchingRule(
        rule_id="23",
        description="First Name + DOB + Member ID (payer namespace)",
        fields=(
            _rf(FIRST_NAME),
            _rf(DOB),
            _rf(INSURANCE_MEMBER_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME), _rf(DOB), _rf(INSURANCE_MEMBER_ID))
        ),
    ),
    MatchingRule(
        rule_id="24",
        description="Last Name* + DOB* (+/-1 day) + Member ID (payer namespace)",
        fields=(
            _rf(LAST_NAME, _F),
            _rf(DOB, _F),
            _rf(INSURANCE_MEMBER_ID),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=p_collision(
            (_rf(LAST_NAME, _F), _rf(DOB, _F), _rf(INSURANCE_MEMBER_ID))
        ),
        # DOB's +/-1 day tolerance (session 6, field_comparator.dob_fuzzy_match) has
        # no separate u-probability in Table 3 (FIELD_U_PROBS["dob"] carries no
        # fuzzy variant) - CMS's own figures below only reconcile if the fuzzy
        # figure comes from Last Name going fuzzy (u 0.01, exactly 2x the exact
        # 0.005), not from DOB. See matching_engine.py's DOB-fuzzy dispatch note
        # for why DOB fuzzy-eligibility doesn't consume max_fuzzy_fields.
        p_collision_fuzzy=p_collision(
            (_rf(LAST_NAME, _F), _rf(DOB, _F), _rf(INSURANCE_MEMBER_ID)),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
    ),
    MatchingRule(
        rule_id="25",
        description="Phone Number + Member ID (payer namespace)",
        fields=(
            _rf(PHONE),
            _rf(INSURANCE_MEMBER_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(PHONE), _rf(INSURANCE_MEMBER_ID))),
    ),
    MatchingRule(
        rule_id="26",
        description="Email Address + Member ID (payer namespace)",
        fields=(
            _rf(EMAIL),
            _rf(INSURANCE_MEMBER_ID),
        ),
        max_fuzzy_fields=0,
        p_collision_exact=p_collision((_rf(EMAIL), _rf(INSURANCE_MEMBER_ID))),
    ),
    MatchingRule(
        rule_id="27",
        description="First Name* + Last Name + DOB + Subscriber ID (payer namespace)",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME),
            _rf(DOB),
            _rf(INSURANCE_SUBSCRIBER_ID),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=p_collision(
            (
                _rf(FIRST_NAME, _F),
                _rf(LAST_NAME),
                _rf(DOB),
                _rf(INSURANCE_SUBSCRIBER_ID),
            )
        ),
        # 1.5e-12, not 2e-12 - first_name fuzzy u is 0.03 (1.5x exact), same
        # correction already applied to rules 04/06 by session 5.
        p_collision_fuzzy=p_collision(
            (
                _rf(FIRST_NAME, _F),
                _rf(LAST_NAME),
                _rf(DOB),
                _rf(INSURANCE_SUBSCRIBER_ID),
            ),
            fuzzy_fields=frozenset({FIRST_NAME}),
        ),
    ),
    MatchingRule(
        rule_id="28",
        description="First Name + Last Name* + DOB + Subscriber ID (payer namespace)",
        fields=(
            _rf(FIRST_NAME),
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(INSURANCE_SUBSCRIBER_ID),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=p_collision(
            (
                _rf(FIRST_NAME),
                _rf(LAST_NAME, _F),
                _rf(DOB),
                _rf(INSURANCE_SUBSCRIBER_ID),
            )
        ),
        p_collision_fuzzy=p_collision(
            (
                _rf(FIRST_NAME),
                _rf(LAST_NAME, _F),
                _rf(DOB),
                _rf(INSURANCE_SUBSCRIBER_ID),
            ),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
    ),
    MatchingRule(
        rule_id="29",
        description="First Name* + Last Name* + Phone Number + ZIP Code",
        fields=(
            _rf(FIRST_NAME, _F),
            _rf(LAST_NAME, _F),
            _rf(PHONE),
            _rf(ZIP_CODE),
        ),
        max_fuzzy_fields=2,
        p_collision_exact=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(PHONE), _rf(ZIP_CODE))
        ),
        p_collision_fuzzy=p_collision(
            (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(PHONE), _rf(ZIP_CODE)),
            fuzzy_fields=frozenset({FIRST_NAME, LAST_NAME}),
        ),
    ),
    # --- v3.3.1 SS3.6: confirmed unaffected, retained as a flat "legacy exception"
    # with a multiple-birth caveat (no First Name field, can't disambiguate twins
    # sharing a household/DOB - twin handling itself is out of session 6's scope).
    MatchingRule(
        rule_id="30",
        description="Last Name* + DOB + Phone Number (legacy exception; no twin disambiguation)",
        fields=(
            _rf(LAST_NAME, _F),
            _rf(DOB),
            _rf(PHONE),
        ),
        max_fuzzy_fields=1,
        p_collision_exact=p_collision((_rf(LAST_NAME, _F), _rf(DOB), _rf(PHONE))),
        p_collision_fuzzy=p_collision(
            (_rf(LAST_NAME, _F), _rf(DOB), _rf(PHONE)),
            fuzzy_fields=frozenset({LAST_NAME}),
        ),
    ),
)
