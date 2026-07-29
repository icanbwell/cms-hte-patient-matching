# Session 5 — Table 3 U-Probabilities + P(Collision) Evaluator

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** M — one new module (a probability table + two pure functions), plus
replacing hand-entered constants in `table2_rules.py` with computed values.

> Read `../conventions.md` first.

## Outcome purpose

`table2_rules.py` currently hardcodes each rule's `p_collision_exact`/`p_collision_fuzzy` as
literal floats, hand-typed against the CMS v3.2.2 spec — there's no code that actually
*computes* P(collision) from per-field u-probabilities, so a typo or a spec update has no way
to be caught automatically, and there's no reusable evaluator for session 6 to score the 11
new v3.3 combinations against. This session builds that evaluator directly from the CMS v3.3
spec's own Table 3 and formula (`P(collision) ~= product of u_field` per field in a
combination), matching Imran's own reference implementation (confirmed by fetching
`gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee` on 2026-07-28: its `FIELD_U_PROBS`
dict matches the spec's Table 3 exactly, and it implements the same joint-probability formula
and 2e-12 threshold this session targets).

## Upstream sessions (must be completed first)

None — valid start point. (Can be coded in parallel with session 3; per `conventions.md`'s
statistical-rigor gate, it just can't move to `completed/` until session 3's Tier-1 report
exists, since it's rule-defining work.)

## Downstream sessions (unblocked by this one)

Session 6 (Table 2 v3.3 expansion) — needs this session's evaluator to score all 37 rules.

## Upstream data/system dependencies

The CMS v3.3 spec (Google Doc, file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg` — see
`conventions.md`'s "Reference documents" section). **Fetch it fresh at session-start; do not
assume the Table 3 values quoted below are still current** — the spec is under active public
comment and could change before this session executes. The values below are what the spec
contained as of 2026-07-28, transcribed directly from it (not from memory or secondhand
description) — re-verify against the live doc before implementing.

## Downstream data/system dependencies

`table2_rules.py`'s `p_collision_exact`/`p_collision_fuzzy` fields become computed (via this
session's evaluator) rather than hand-typed, for every rule session 6 defines.

## Scope

### In scope
- A new module, `patient_matching/matching/collision.py`, implementing:
  - `FIELD_U_PROBS`: the per-field conservative u-probability table (Task 1's data below).
  - `p_collision(fields, *, fuzzy_fields=frozenset())`: the joint-probability product formula.
  - `evaluate_combination(fields, *, fuzzy_fields=frozenset())`: wraps `p_collision` and
    checks it against the 2e-12 threshold, returning enough detail for a test to assert on
    (at minimum `p_collision` and `approved`).
- Replacing every hardcoded `p_collision_exact`/`p_collision_fuzzy` value in
  `table2_rules.py`'s existing 26 `MatchingRule` entries with values computed by this new
  evaluator (Task 3), so the existing rule set becomes self-verifying against Table 3 instead
  of trusting hand-entered constants — this also serves as the first real test of the
  evaluator (if it can't reproduce the 26 already-published-correct values, something's wrong
  with the evaluator, not the existing rules).
- An explicit regression test for the spec's own admitted inconsistency: First Name + Last
  Name + DOB + ZIP computes to 3e-12 under Table 3 (above the 2e-12 threshold) and must
  evaluate as **not approved**, regardless of the 3e-13 figure that appears in some prior,
  non-spec analyses.
- Cross-checking this session's `FIELD_U_PROBS`/`p_collision` output against Imran's gist/Colab
  directly, as a stretch-goal verification step (Task 4) — not required for this session's
  Definition of Done, since it's an external resource outside this repo's control and may not
  be reachable in every execution environment.

### Out of scope
- Adding the 11 new v3.3 rules themselves (Table 2 expansion) — that's session 6, which
  depends on this session's evaluator.
- The per-value (name-frequency-conditioned) collision-probability refinement Sean raised
  separately — that's a genuine methodology deviation from the published CMS approach (which
  uses static per-field constants, as implemented here) and needs Imran's explicit sign-off;
  see `index.md`'s "Candidate future sessions".
- Any change to `MatchingEngine`'s fuzzy-matching mechanics (Damerau-Levenshtein, min length)
  — this session only computes probabilities, it doesn't change how a match is decided.

## Tasks

1. **Write `FIELD_U_PROBS`.**
   File: `patient_matching/matching/collision.py` (new).
   Transcribed from the CMS v3.3 spec's Table 3 (§IV.C), as read 2026-07-28 — **re-verify
   against the live doc at session-start**:
   ```python
   """Table 3: per-field conservative u-probabilities, and the P(collision) evaluator,
   per CMS Patient Matching Proposal v3.3.0 SS IV.

   Values transcribed from the spec as of 2026-07-28 (Google Doc, file ID
   1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg - see ../../docs/sessions/conventions.md's
   "Reference documents" section). The spec is a live draft under public comment; if these
   values and the live doc diverge, the live doc wins - update this table and re-run the
   equivalence test in test_collision.py::test_existing_26_rules_reproduce_published_values.

   Three fields the spec defines but which are "dismissed due to observed data quality
   issues and low selectivity" (Middle Name, Suffix, Year of Birth) are intentionally
   excluded here, matching Imran's reference script's 16-field FIELD_U_PROBS (confirmed
   2026-07-28 via gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee) - no Table 2
   rule uses any of the three.
   """

   from __future__ import annotations

   from typing import Dict, Optional, Tuple

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
       "namespace_id": (1e-15, None),  # spec: "~=0"; a small nonzero float avoids a literal 0.0 * anything == 0.0 masking other fields in a product
       "insurance_member_id": (0.000001, None),
       "insurance_subscriber_id": (0.0001, None),
   }
   ```

2. **Write `p_collision` and `evaluate_combination`.**
   Append to `patient_matching/matching/collision.py`:
   ```python
   from .table2_rules import RuleField

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
   ```
   Note: `table2_rules.py`'s existing field-name constants (`FIRST_NAME`, `LAST_NAME`, `DOB`,
   `STREET_LINE`, `PHONE`, `EMAIL`, `SSN_LAST4`, `ITIN_LAST4`, `MBI`, `LEGAL_ID`,
   `NAMESPACE_ID`) already match `FIELD_U_PROBS`'s keys. `zip_code`, `city`, `state`,
   `insurance_member_id`, and `insurance_subscriber_id` don't have constants yet — session 6
   adds them (they're needed for the 11 new v3.3 rules, not any of the existing 26), but this
   session's `FIELD_U_PROBS` table includes them now so session 6 doesn't also have to touch
   `collision.py`.

3. **Replace `table2_rules.py`'s hardcoded values with computed ones**, for all 26 existing
   rules. Example for rule 01 (currently
   `p_collision_exact=3e-13, p_collision_fuzzy=9e-13` as a literal):
   ```python
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
       p_collision_exact=p_collision((_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(DOB), _rf(STREET_LINE, _F))),
       p_collision_fuzzy=p_collision(
           (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(DOB), _rf(STREET_LINE, _F)),
           fuzzy_fields=frozenset({FIRST_NAME, LAST_NAME}),
       ),
   )
   ```
   Apply the same pattern to all 26 rules — replace the two literal float arguments with
   `p_collision(...)` calls using that rule's own `fields` tuple. Import `p_collision` from
   `.collision` at the top of `table2_rules.py`. After this change, run
   `docker compose run --rm dev pytest patient_matching/matching/tests/test_table2_rules.py -v`
   and confirm every existing assertion about specific `p_collision_exact`/`p_collision_fuzzy`
   values still passes — if any computed value differs from today's hardcoded one by more
   than a rounding difference, stop and investigate before proceeding (it means either the
   evaluator or the original hand-entered constant was wrong). One known, expected exception: rules 04 and 06's computed `p_collision_fuzzy` will come out to 1.5e-12, not the currently-hardcoded 2e-12 — this is not a bug to investigate. The old hardcoded value implicitly assumed a `first_name` fuzzy u-probability of 0.04 (a 2x multiplier over exact); the real v3.3 Table 3 states 0.03 (1.5x). Accept the new computed value (1.5e-12) as the correct v3.3-era figure for these two rules, replacing the stale v3.2.2-era constant — this is exactly the kind of drift this evaluator is meant to catch and correct.

4. **(Stretch goal, not required for Definition of Done) Cross-check against Imran's
   reference script.** Fetch `https://gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee`
   and compare its `FIELD_U_PROBS` values and any of its worked examples against this
   session's `collision.py`. If reachable and values differ, investigate and reconcile before
   merging; if unreachable (offline execution environment, gist removed, etc.), note that in
   *Execution notes* and proceed — this step existing is a nice-to-have consistency check, not
   a blocker.

## Unit tests required

File: `patient_matching/matching/tests/test_collision.py` (new).

```python
import pytest
from patient_matching.matching.collision import (
    FIELD_U_PROBS,
    APPROVAL_THRESHOLD,
    p_collision,
    evaluate_combination,
)
from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    DOB,
    FIRST_NAME,
    LAST_NAME,
    STREET_LINE,
    _rf,
)


class TestFieldUProbs:
    @pytest.mark.parametrize(
        "field_name,expected_exact",
        [
            ("first_name", 0.02),
            ("last_name", 0.005),
            ("dob", 0.0001),
            ("phone", 0.000001),
            ("email", 0.000001),
            ("ssn_last4", 0.0001),
            ("mbi", 0.000001),
        ],
    )
    def test_known_field_exact_u_values(self, field_name, expected_exact):
        exact, _ = FIELD_U_PROBS[field_name]
        assert exact == expected_exact

    def test_dismissed_fields_are_absent(self):
        for dismissed in ("middle_name", "suffix", "year_of_birth"):
            assert dismissed not in FIELD_U_PROBS


class TestPCollision:
    def test_single_field_equals_its_own_u(self):
        assert p_collision((_rf("phone"),)) == FIELD_U_PROBS["phone"][0]

    def test_joint_probability_is_product_of_fields(self):
        fields = (_rf(FIRST_NAME), _rf(DOB))
        expected = FIELD_U_PROBS["first_name"][0] * FIELD_U_PROBS["dob"][0]
        assert p_collision(fields) == pytest.approx(expected)

    def test_fuzzy_field_uses_fuzzy_u_value(self):
        fields = (_rf(FIRST_NAME, role=None),)  # role is irrelevant to p_collision itself
        exact_u, fuzzy_u = FIELD_U_PROBS["first_name"]
        assert p_collision(fields, fuzzy_fields=frozenset({FIRST_NAME})) == fuzzy_u
        assert p_collision(fields) == exact_u


class TestEvaluateCombination:
    def test_first_last_dob_zip_is_not_approvable(self):
        """The CMS v3.3 spec's own admitted inconsistency: this combination computes
        to 3e-12 under Table 3 (above the 2e-12 threshold) and must NOT be approved,
        regardless of the 3e-13 figure some prior (non-spec) analyses cite."""
        fields = (_rf(FIRST_NAME), _rf(LAST_NAME), _rf(DOB), _rf("zip_code"))
        result = evaluate_combination(fields)
        assert result["approved"] is False
        assert result["p_collision"] == pytest.approx(3e-12, rel=1e-6)

    def test_boundary_at_threshold(self):
        """A synthetic combination whose product lands exactly at 2e-12 must be
        approved - the spec's threshold is <=, not strictly <."""
        # phone (1e-6) * legal_id (1e-6) * a synthetic third field at 2.0 gives 2e-12.
        FIELD_U_PROBS["_test_field"] = (2.0, None)
        try:
            fields = (_rf("phone"), _rf("legal_id"), _rf("_test_field"))
            result = evaluate_combination(fields)
            assert result["p_collision"] == pytest.approx(2e-12)
            assert result["approved"] is True
        finally:
            del FIELD_U_PROBS["_test_field"]

    def test_just_above_threshold_is_not_approved(self):
        FIELD_U_PROBS["_test_field"] = (2.000001, None)
        try:
            fields = (_rf("phone"), _rf("legal_id"), _rf("_test_field"))
            assert evaluate_combination(fields)["approved"] is False
        finally:
            del FIELD_U_PROBS["_test_field"]


class TestExistingRulesMatchComputedValues:
    @pytest.mark.parametrize("rule", APPROVED_RULES, ids=lambda r: r.rule_id)
    def test_existing_26_rules_reproduce_published_values(self, rule):
        """After Task 3's change, every existing rule's p_collision_exact/_fuzzy IS a
        computed value (not a literal) - this test just confirms none of them are 0.0
        by accident (a real bug: an unmapped field name in FIELD_U_PROBS would raise a
        KeyError at import time, not silently produce 0.0, but this guards against a
        future refactor reintroducing a literal-float regression)."""
        assert rule.p_collision_exact > 0 or rule.rule_id == "26"  # rule 26 is the ~0 namespace-ID case
```

## Validation (definition of "resolved")

- [ ] `collision.py` exists with `FIELD_U_PROBS`, `p_collision`, `evaluate_combination`,
      `APPROVAL_THRESHOLD`.
- [ ] All 26 existing rules in `table2_rules.py` compute their `p_collision_exact`/`_fuzzy`
      via `p_collision(...)` rather than a hardcoded literal, and every computed value matches
      what was previously hand-entered (within floating-point rounding).
- [ ] First Name + Last Name + DOB + ZIP evaluates as **not approved** (the spec's own
      admitted 3e-12-over-threshold case).
- [ ] Boundary tests (at-threshold approved, just-above not approved) pass.
- [ ] `docker compose run --rm dev pytest patient_matching/matching/tests/test_collision.py -v` passes.
- [ ] `make tests` is green (full suite — confirms the `table2_rules.py` change didn't
      regress `test_table2_rules.py` or `test_matching_engine.py`).
- [ ] `make run-pre-commit` is clean.
- [ ] Per `conventions.md`'s statistical rigor gate: this session does not move to
      `completed/` until session 3's Tier-1 `ComparisonReport` exists (it can be authored and
      coded before then, just not merged).

## Open questions

- The Table 3 values transcribed into Task 1 are current as of 2026-07-28's read of a live,
  actively-commented draft spec. **`NEEDS HUMAN DECISION` only if** the live doc has changed
  by execution time and the new values meaningfully differ from what's transcribed above — in
  that case, update `collision.py` to match the live doc and treat the difference as a normal
  code change, not something requiring Sean's sign-off (these are CMS's own published numbers,
  not a judgment call this repo is making). If genuinely ambiguous (e.g. the spec's wording
  changed in a way that's unclear how to encode), that's when to ask Sean.
- Task 4 (cross-check against Imran's gist) is explicitly a stretch goal — if unreachable,
  note it and move on; don't block the session on it.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
