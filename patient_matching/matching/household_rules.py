"""CMS Proposal v3.3.1 Household-then-Individual two-step matching (SS3-4).

Some fields (Phone, Email, SSN/ITIN Last 4, Subscriber ID, Street Line, ZIP) are
frequently shared by an entire household, not unique to one person - a match on
one of these Table 2-H combinations alone can only establish "same household,"
not "same person." This module defines the Household-tier rows (Table 2-H) and
Individual-tier rows (Table 2-I) v3.3.1 introduces, and pairs them into the 8
Category 2 rules that need this two-step treatment - see the `rule_id` note
below for their actual (prefixed) identifiers: legacy numbers 13, 14, 15, 16
(amending already-shipped v3.2.2 flat rules that used these household-shared
fields alone) and 34, 35, 37, 38 (new).

Every row's p_collision is computed via collision.p_collision(), the same
FIELD_U_PROBS table table2_rules.py's flat rules use - this is a sanity check
against the source-doc figures transcribed in
docs/sessions/completed/session_6.md, not a hardcoded literal.

**rule_id values carry a `C2-` prefix (session 16, v3.4.0) - this is the
authoritative form; the legacy bare numbers above are historical context
only, not live identifiers.** v3.4.0's Category 1 table renumbers to a clean,
gapless 01-30 sequence that happens to claim 13-16 for brand-new, unrelated
flat rules (see table2_rules.py). v3.4.0's own Category 2 material (SSA
C.2-C.5) never actually assigns these rules a live ID of their own - it only
describes them as Household-row + Individual-row pairings; "Rules 13, 14, 15,
16, 34, 35, 37, and 38" appears once, in SS C.8's prose, as a backward-reference
to the legacy v3.3.1 addendum numbering this module was originally built
against, not a v3.4.0 ID assignment. Keeping the bare numbers here would
silently collide with Category 1's new 13-16 in any audit record keyed on
`rule_id` alone (the "Table 2 combination evaluated" SS VII field) - the
`C2-` prefix preserves the historically-meaningful numbers while making that
collision structurally impossible. Decided by Imran, 2026-09-15 (see
docs/sessions/in_review/session_16.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from .collision import p_collision
from .table2_rules import (
    DOB,
    EMAIL,
    FIRST_NAME,
    INSURANCE_SUBSCRIBER_ID,
    ITIN_LAST4,
    LAST_NAME,
    PHONE,
    SSN_LAST4,
    STREET_LINE,
    ZIP_CODE,
    FieldRole,
    RuleField,
    _rf,
)

_F = FieldRole.FUZZY_ELIGIBLE


@dataclass(frozen=True)
class HouseholdRow:
    """A Table 2-H household-tier field combination.

    Household rows are exact-only (no starred/fuzzy fields in the spec).
    """

    row_id: str
    fields: tuple[RuleField, ...]
    p_collision: float


@dataclass(frozen=True)
class IndividualRow:
    """A Table 2-I individual-tier field combination, evaluated within an
    already-resolved household.

    p_collision_fuzzy defaults to p_collision_exact for rows with no
    fuzzy-eligible field (I-02, I-03) - there's nothing to fuzzy-match, so
    both figures are the same single value the spec publishes for them.
    """

    row_id: str
    fields: tuple[RuleField, ...]
    p_collision_exact: float
    p_collision_fuzzy: float


@dataclass(frozen=True)
class HouseholdIndividualRule:
    """A Category 2 (two-step) Table 2 rule: one household row + one
    individual row, evaluated sequentially and combined by multiplication.
    """

    rule_id: str
    description: str
    household_row: HouseholdRow
    individual_row: IndividualRow

    @property
    def p_collision_exact(self) -> float:
        return self.household_row.p_collision * self.individual_row.p_collision_exact

    @property
    def p_collision_fuzzy(self) -> float:
        return self.household_row.p_collision * self.individual_row.p_collision_fuzzy


# --- Table 2-H: household-tier rows ---------------------------------------

H_01 = HouseholdRow(
    "H-01", (_rf(SSN_LAST4), _rf(PHONE)), p_collision((_rf(SSN_LAST4), _rf(PHONE)))
)
H_02 = HouseholdRow(
    "H-02", (_rf(SSN_LAST4), _rf(EMAIL)), p_collision((_rf(SSN_LAST4), _rf(EMAIL)))
)
H_03 = HouseholdRow(
    "H-03",
    (_rf(SSN_LAST4), _rf(STREET_LINE)),
    p_collision((_rf(SSN_LAST4), _rf(STREET_LINE))),
)
H_04 = HouseholdRow(
    "H-04", (_rf(ITIN_LAST4), _rf(PHONE)), p_collision((_rf(ITIN_LAST4), _rf(PHONE)))
)
H_05 = HouseholdRow(
    "H-05", (_rf(ITIN_LAST4), _rf(EMAIL)), p_collision((_rf(ITIN_LAST4), _rf(EMAIL)))
)
H_06 = HouseholdRow(
    "H-06",
    (_rf(ITIN_LAST4), _rf(STREET_LINE)),
    p_collision((_rf(ITIN_LAST4), _rf(STREET_LINE))),
)
H_07 = HouseholdRow(
    "H-07",
    (_rf(INSURANCE_SUBSCRIBER_ID), _rf(PHONE)),
    p_collision((_rf(INSURANCE_SUBSCRIBER_ID), _rf(PHONE))),
)
H_08 = HouseholdRow(
    "H-08",
    (_rf(INSURANCE_SUBSCRIBER_ID), _rf(EMAIL)),
    p_collision((_rf(INSURANCE_SUBSCRIBER_ID), _rf(EMAIL))),
)
H_09 = HouseholdRow(
    "H-09",
    (_rf(INSURANCE_SUBSCRIBER_ID), _rf(STREET_LINE)),
    p_collision((_rf(INSURANCE_SUBSCRIBER_ID), _rf(STREET_LINE))),
)
H_10 = HouseholdRow(
    "H-10", (_rf(PHONE), _rf(EMAIL)), p_collision((_rf(PHONE), _rf(EMAIL)))
)
H_11 = HouseholdRow(
    # Weakest row (v3.3.1 SS3.3 correlation caveat) - still >=1e-8, well under
    # the 1e-7 structural floor each Table-A field independently clears.
    "H-11",
    (_rf(SSN_LAST4), _rf(INSURANCE_SUBSCRIBER_ID)),
    p_collision((_rf(SSN_LAST4), _rf(INSURANCE_SUBSCRIBER_ID))),
)
H_12 = HouseholdRow(
    "H-12", (_rf(PHONE), _rf(ZIP_CODE)), p_collision((_rf(PHONE), _rf(ZIP_CODE)))
)
H_13 = HouseholdRow(
    "H-13", (_rf(EMAIL), _rf(ZIP_CODE)), p_collision((_rf(EMAIL), _rf(ZIP_CODE)))
)
H_14 = HouseholdRow(
    "H-14", (_rf(PHONE), _rf(STREET_LINE)), p_collision((_rf(PHONE), _rf(STREET_LINE)))
)

HOUSEHOLD_ROWS: tuple[HouseholdRow, ...] = (
    H_01,
    H_02,
    H_03,
    H_04,
    H_05,
    H_06,
    H_07,
    H_08,
    H_09,
    H_10,
    H_11,
    H_12,
    H_13,
    H_14,
)

# --- Table 2-I: individual-tier rows ---------------------------------------

I_01 = IndividualRow(
    "I-01",
    (_rf(FIRST_NAME, _F), _rf(DOB)),
    p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(DOB))),
    p_collision_fuzzy=p_collision(
        (_rf(FIRST_NAME, _F), _rf(DOB)), fuzzy_fields=frozenset({FIRST_NAME})
    ),
)
I_02 = IndividualRow(
    "I-02",
    (_rf(FIRST_NAME), _rf(LAST_NAME), _rf(DOB)),
    p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(LAST_NAME), _rf(DOB))),
    p_collision_fuzzy=p_collision((_rf(FIRST_NAME), _rf(LAST_NAME), _rf(DOB))),
)
I_03 = IndividualRow(
    "I-03",
    (_rf(FIRST_NAME),),
    p_collision_exact=p_collision((_rf(FIRST_NAME),)),
    p_collision_fuzzy=p_collision((_rf(FIRST_NAME),)),
)

INDIVIDUAL_ROWS: tuple[IndividualRow, ...] = (I_01, I_02, I_03)

# --- Category 2 rules: 4 amended (13,14,15,16) + 4 new (34,35,37,38) -------
# All 8 pair with I-01 (First Name + DOB), not I-02/I-03 - I-02/I-03 are
# defined above as building blocks for a possible future rule, per session
# 6's scope, but unused by any rule this session builds.

CATEGORY_2_RULES: tuple[HouseholdIndividualRule, ...] = (
    HouseholdIndividualRule(
        rule_id="C2-13",
        description=(
            "SSN Last 4 + Phone (household) + First Name/DOB (individual); "
            "Last Name is non-blocking corroboration only, per v3.3.1 - amends "
            "the v3.2.2 flat rule of the same number"
        ),
        household_row=H_01,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-14",
        description=(
            "ITIN Last 4 + Phone (household) + First Name/DOB (individual); "
            "Last Name is non-blocking corroboration only - amends the v3.2.2 "
            "flat rule of the same number"
        ),
        household_row=H_04,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-15",
        description=(
            "SSN Last 4 + Email (household) + First Name/DOB (individual); "
            "Last Name* is non-blocking corroboration only - amends the v3.2.2 "
            "flat rule of the same number"
        ),
        household_row=H_02,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-16",
        description=(
            "ITIN Last 4 + Email (household) + First Name/DOB (individual); "
            "Last Name* is non-blocking corroboration only - amends the v3.2.2 "
            "flat rule of the same number"
        ),
        household_row=H_05,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-34",
        description="Phone + ZIP Code (household) + First Name/DOB (individual)",
        household_row=H_12,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-35",
        description="Email + ZIP Code (household) + First Name/DOB (individual)",
        household_row=H_13,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-37",
        description=(
            "Phone + Street Line (household) + First Name/DOB (individual); "
            "household leg gated on v3.3.6 institutional-address exclusion, "
            "not yet implemented - see session_6.md's Out of scope"
        ),
        household_row=H_14,
        individual_row=I_01,
    ),
    HouseholdIndividualRule(
        rule_id="C2-38",
        description=(
            "Subscriber ID + Phone (household) + First Name/DOB (individual) - "
            "recovers Table 4's previously-rejected Subscriber ID + DOB"
        ),
        household_row=H_07,
        individual_row=I_01,
    ),
)
