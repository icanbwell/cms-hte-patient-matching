"""Table 3: per-field conservative u-probabilities, and the P(collision) evaluator,
per CMS Patient Matching Proposal v3.4.0 SS IV.

Values transcribed from the spec as of 2026-07-31 (Google Doc, file ID
1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg) and re-confirmed unchanged against v3.4.0
(Google Doc, file ID 1NytpfZ05aokS-gD7uDIQE7gEyms9zMgoiaIah_w4VTE, 2026-09-15) - see
../../docs/sessions/conventions.md's "Reference documents" section. The spec is a live
draft under public comment; if these values and the live doc diverge, the live doc wins -
update this table and re-run the equivalence test in
test_collision.py::test_existing_category1_rules_reproduce_published_values.

Three fields the spec defines but which are "dismissed due to observed data quality
issues and low selectivity" (Middle Name, Suffix, Year of Birth) are intentionally
excluded here, matching the CMS reference implementation's 16-field FIELD_U_PROBS - no Table 2
rule uses any of the three.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    # table2_rules.py imports p_collision back from this module (Task 3) - a
    # runtime import here would be circular. RuleField is only used for type
    # hints below, and `from __future__ import annotations` means annotations
    # are never evaluated at runtime, so a TYPE_CHECKING-only import is safe.
    from .table2_rules import RuleField

# field_name -> (conservative u, exact; conservative u, fuzzy or None if fuzzy isn't used)
FIELD_U_PROBS: Dict[str, Tuple[float, Optional[float]]] = {
    "first_name": (0.02, 0.03),
    "last_name": (0.005, 0.01),
    "dob": (0.0001, None),
    "zip_code": (0.0003, None),
    "city": (0.01, None),
    "state": (0.06, None),
    "street_line": (0.00003, 0.00006),
    "phone": (0.000001, None),
    "email": (0.000001, None),
    "ssn_last4": (0.0001, None),
    "itin_last4": (0.0001, None),
    "legal_id": (0.000001, None),
    "mbi": (0.000001, None),
    "namespace_id": (
        1e-15,
        None,
    ),  # spec: "~=0"; a small nonzero float avoids a literal 0.0 * anything == 0.0 masking other fields in a product
    "insurance_member_id": (0.000001, None),
    "insurance_subscriber_id": (0.0001, None),
    # v3.4.0 additions (session 17):
    "relationship_linkage_clinical": (0.01, None),
    # Self-reported/intake variant: defined per Table 3, deliberately unused by
    # any rule this session builds (same "define but leave unused" precedent
    # as household_rules.I_03) - both rules C2-39/C2-40 require the clinical
    # variant only.
    "relationship_linkage_self_reported": (0.05, None),
    # Post-review fix: type-narrowed variants actually used by C2-39/C2-40
    # (see table2_rules.py's definition comment). Each has a strictly SMALLER
    # value space than the un-narrowed "relationship_linkage_clinical" above
    # (one specific code vs. any code), so its true collision probability is
    # at most 0.01, not more - reusing the spec's published 0.01 keeps the
    # rules' P(collision) figures matching v3.4.0's stated math exactly
    # rather than inventing a new, unpublished number; the narrowing can only
    # make the true risk lower than what's priced, never higher.
    "relationship_linkage_child_of_clinical": (0.01, None),
    "relationship_linkage_newborn_of_clinical": (0.01, None),
    # Identity-gate fields: NOT a discriminating probabilistic factor. These
    # represent "this record references a guardian/mother identity that was
    # already independently matched by a separate Table 2 rule" - u=1.0 is a
    # deliberate no-op multiplier, not a placeholder. The spec's own math for
    # rule 39 ("flat product: 0.02 x 0.0001 x 0.01 x 0.00003") has exactly 4
    # factors and no room for a 5th, near-zero one - the guardian/mother's own
    # uniqueness was already bounded by whichever rule matched THEM, so this
    # rule's P(collision) is conditional on that gate already holding, not
    # compounded with it. Using namespace_id's near-zero tier here instead
    # would misreport rule 39/40's collision risk by ~15 orders of magnitude.
    "guardian_identity": (1.0, None),
    "mother_identity": (1.0, None),
    # Not given an explicit figure anywhere in Table 3 - the spec only says a
    # true per-encounter ID "clears with wide margin" and a shared facility ID
    # "is far above the threshold." Reuses namespace_id's 1e-15 tier as the
    # closest existing analogue (both represent a namespace-bound,
    # per-entity-unique identifier) - an interpretation, not a spec-given
    # number; re-verify against the live doc if it's ever clarified.
    "birth_encounter_id": (1e-15, None),
}

APPROVAL_THRESHOLD = 2e-12


def p_collision(
    fields: Tuple[RuleField, ...], *, fuzzy_fields: frozenset[str] = frozenset()
) -> float:
    """Joint collision probability: product of each field's u-probability.

    fuzzy_fields names which of the given fields should use their fuzzy
    u-probability instead of exact (only meaningful for fields that have one).
    """
    result = 1.0
    for rf in fields:
        exact_u, fuzzy_u = FIELD_U_PROBS[rf.name]
        if rf.name in fuzzy_fields and fuzzy_u is not None:
            result *= fuzzy_u
        else:
            result *= exact_u
    return result


def evaluate_combination(
    fields: Tuple[RuleField, ...], *, fuzzy_fields: frozenset[str] = frozenset()
) -> Dict[str, object]:
    """Evaluate a Table 2 candidate combination against the 2e-12 threshold."""
    p = p_collision(fields, fuzzy_fields=fuzzy_fields)
    return {
        "p_collision": p,
        "approved": p <= APPROVAL_THRESHOLD,
        "fields": tuple(rf.name for rf in fields),
        "fuzzy_fields": tuple(sorted(fuzzy_fields)),
    }
