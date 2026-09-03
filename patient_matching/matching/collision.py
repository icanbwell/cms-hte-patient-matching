"""Table 3: per-field conservative u-probabilities, and the P(collision) evaluator,
per CMS Patient Matching Proposal v3.3.0 SS IV.

Values transcribed from the spec as of 2026-07-31 (Google Doc, file ID
1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg - see ../../docs/sessions/conventions.md's
"Reference documents" section). The spec is a live draft under public comment; if these
values and the live doc diverge, the live doc wins - update this table and re-run the
equivalence test in test_collision.py::test_existing_26_rules_reproduce_published_values.

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
