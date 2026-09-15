"""CMS Proposal v3.4.0 Relationship Linkage rules: guardian-verified minors
(Rule C2-39) and newborn-via-maternal-linkage (Rule C2-40) - session 17.

Structurally these are Category 2 (household+individual) rules, per v3.4.0
SS C.4's own table format ("Household leg | Individual leg | Combined
P(collision)"), reusing household_rules.py's HouseholdRow/IndividualRow/
HouseholdIndividualRule types directly rather than inventing a new dataclass
shape.

The key difference from household_rules.py's H-01..H-14/I-01..I-03 rows: this
module's "household leg" isn't a shared-PII-field grouping (SSN+Phone, etc.)
that narrows a search to one household - it's a reference to a DIFFERENT
person's identity, already independently matched by a separate Table 2 rule
entirely outside this module's scope. That identity's own uniqueness was
already bounded by whichever rule matched it, so it contributes u=1.0 (a
deliberate no-op multiplier) rather than a near-zero collision figure -
see collision.FIELD_U_PROBS's guardian_identity/mother_identity comment for
the full reasoning (verified directly against the spec's own math for rule
C2-39, which has no room for a 5th, near-zero factor).

Both rules carry caveats the spec itself flags as unresolved (see each
rule's own comment below) - built anyway per Imran's 2026-09-15 "implement
now, best-effort" decision (docs/sessions/pending/session_17.md).
"""

from __future__ import annotations

from .collision import p_collision
from .household_rules import HouseholdIndividualRule, HouseholdRow, IndividualRow
from .table2_rules import (
    BIRTH_ENCOUNTER_ID,
    DOB,
    FIRST_NAME,
    GUARDIAN_IDENTITY,
    MOTHER_IDENTITY,
    RELATIONSHIP_LINKAGE_CHILD_OF_CLINICAL,
    RELATIONSHIP_LINKAGE_NEWBORN_OF_CLINICAL,
    STREET_LINE,
    _rf,
)

# --- Household-leg rows: identity gates, not shared-field groupings --------

GUARDIAN_IDENTITY_ROW = HouseholdRow(
    "GUARDIAN-IDENTITY",
    (_rf(GUARDIAN_IDENTITY), _rf(STREET_LINE)),
    p_collision((_rf(GUARDIAN_IDENTITY), _rf(STREET_LINE))),
)

MOTHER_IDENTITY_ROW = HouseholdRow(
    "MOTHER-IDENTITY",
    (_rf(MOTHER_IDENTITY),),
    p_collision((_rf(MOTHER_IDENTITY),)),
)

# --- Individual-leg rows ----------------------------------------------------

_CHILD_RELATIONSHIP_FIELDS = (
    _rf(RELATIONSHIP_LINKAGE_CHILD_OF_CLINICAL),
    _rf(FIRST_NAME),
    _rf(DOB),
)
CHILD_RELATIONSHIP_ROW = IndividualRow(
    "CHILD-RELATIONSHIP",
    _CHILD_RELATIONSHIP_FIELDS,
    # No fuzzy variant anywhere in this combination per the spec's own math
    # (First Name is unstarred here, unlike I-01) - p_collision_fuzzy equals
    # p_collision_exact, same pattern as household_rules.I_02/I_03.
    p_collision_exact=p_collision(_CHILD_RELATIONSHIP_FIELDS),
    p_collision_fuzzy=p_collision(_CHILD_RELATIONSHIP_FIELDS),
)

_NEWBORN_RELATIONSHIP_FIELDS = (
    _rf(RELATIONSHIP_LINKAGE_NEWBORN_OF_CLINICAL),
    _rf(DOB),
    _rf(BIRTH_ENCOUNTER_ID),
)
NEWBORN_RELATIONSHIP_ROW = IndividualRow(
    "NEWBORN-RELATIONSHIP",
    _NEWBORN_RELATIONSHIP_FIELDS,
    p_collision_exact=p_collision(_NEWBORN_RELATIONSHIP_FIELDS),
    p_collision_fuzzy=p_collision(_NEWBORN_RELATIONSHIP_FIELDS),
)

# --- Category 2 rules: C2-39 (new), C2-40 (new) -----------------------------

RELATIONSHIP_LINKAGE_RULES: tuple[HouseholdIndividualRule, ...] = (
    HouseholdIndividualRule(
        rule_id="C2-39",
        description=(
            "Guardian-verified minor: guardian's independently-matched "
            "identity + Street Line (household leg) + Relationship Linkage "
            "clinical (child-of) + First Name + DOB (individual leg). "
            "KNOWN LIMITATION (spec's own flag, not resolved by this "
            "session): Street Line is correlated with the relationship term "
            "(same household address as the guardian), so the published "
            "6.0e-13 figure overstates the true margin until a dependency "
            "discount is applied or Street Line is dropped."
        ),
        household_row=GUARDIAN_IDENTITY_ROW,
        individual_row=CHILD_RELATIONSHIP_ROW,
    ),
    HouseholdIndividualRule(
        rule_id="C2-40",
        description=(
            "Newborn via maternal linkage: mother's independently-matched "
            "identity (household leg) + Relationship Linkage clinical "
            "(newborn-of) + DOB + a per-encounter, namespace-bound "
            "birth-encounter ID (individual leg). KNOWN LIMITATION (spec's "
            "own flag, not resolved by this session): this only clears with "
            "a wide margin if the encounter ID is genuinely per-encounter "
            "unique - a shared facility-wide ID does not qualify and would "
            "put the true collision risk far above the 2e-12 threshold. "
            "Whether such an identifier is actually available in this "
            "system's real data is unconfirmed (NEEDS HUMAN DECISION, "
            "carried over from session 6)."
        ),
        household_row=MOTHER_IDENTITY_ROW,
        individual_row=NEWBORN_RELATIONSHIP_ROW,
    ),
)
