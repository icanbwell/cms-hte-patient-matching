# Session 2 — Tiered Uniqueness Response

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** S/M — one new enum value, one method's branching logic, tests for the new
boundary.

> Read `../conventions.md` first.

## Outcome purpose

CMS v3.3 requires tiered handling of ambiguous matches, not a single bucket: exactly 1
candidate returns; exactly 2 candidates *may* escalate to MFA/disambiguation; 3 or more
candidates must clear a stricter 1-in-a-million (1e-6) collision threshold or the responder
declines. Today, `MatchingEngine._build_result` collapses every non-unique outcome (2
candidates or 20) into one `MatchOutcome.AMBIGUOUS` bucket with no distinction — so a caller
can't tell "this is a 2-candidate disambiguation case" from "this is a 5-candidate case that
should almost always be declined." This session adds that distinction.

## Upstream sessions (must be completed first)

None — valid start point. (Doing session 1 first is a nice-to-have, not a requirement — it
keeps the new evaluations' audit fields consistent across the new outcome value, but nothing
in this session depends on session 1's code.)

## Downstream sessions (unblocked by this one)

Session 6 (Table 2 v3.3 expansion) will exercise this tiered logic against the full 37-rule
set, including cases where the 3+-candidate stricter threshold actually matters.

## Upstream data/system dependencies

None.

## Downstream data/system dependencies

None new — same `MatchResult` consumers as today, now seeing a new possible
`outcome` value.

## Scope

### In scope
- Add `MatchOutcome.ESCALATE` to the enum in `patient_matching/matching/match_result.py`,
  for the exactly-2-candidates case.
- Redefine what `MatchOutcome.AMBIGUOUS` means: 3 or more candidates, evaluated against a
  stricter 1e-6 collision threshold (see Task 2 below for exactly how "the stricter threshold"
  is applied given today's engine has no live P(collision) computation yet — session 5 adds
  that; this session adds the *branching structure*, using a placeholder-free interim
  comparison described in Task 2).
- Update `MatchingEngine._build_result` in `patient_matching/matching/matching_engine.py` to
  branch on `len(all_matched)`: `== 1` -> `MATCH` (unchanged), `== 2` -> `ESCALATE` (new),
  `>= 3` -> `AMBIGUOUS` (same enum value as today, but now specifically meaning "3+, stricter
  threshold applies").

### Out of scope
- Actually computing P(collision) for the 3+-candidate stricter-threshold check — that
  requires session 5's evaluator. This session's interim behavior (Task 2) is deliberately
  simple and explicitly documented as interim, so session 5/6 can wire in the real
  P(collision) check later without changing `_build_result`'s branching structure.
- Any MFA/disambiguation implementation for the `ESCALATE` case — this repo has no
  auth/session layer; `ESCALATE` is a signal for a caller (e.g. a future API layer) to act on,
  not something this engine implements itself.
- The 1e-6 threshold value itself is CMS-mandated (see the v3.3 spec, §III — fetch it live per
  `../conventions.md`'s "Reference documents" section if you need the exact wording), not
  tuned, so this session is exempt from the statistical-rigor gate.

## Tasks

1. **Add the new enum value.**
   File: `patient_matching/matching/match_result.py`.
   Current:
   ```python
   class MatchOutcome(Enum):
       """Outcome of a matching operation."""

       MATCH = "match"
       NO_MATCH = "no_match"
       AMBIGUOUS = "ambiguous"
       INSUFFICIENT_FIELDS = "insufficient_fields"
   ```
   Change to:
   ```python
   class MatchOutcome(Enum):
       """Outcome of a matching operation."""

       MATCH = "match"
       NO_MATCH = "no_match"
       ESCALATE = "escalate"  # exactly 2 candidates; may escalate to MFA/disambiguation
       AMBIGUOUS = "ambiguous"  # 3+ candidates; stricter 1e-6 threshold applies
       INSUFFICIENT_FIELDS = "insufficient_fields"
   ```
   Update the class docstring to note the tiering (1 -> MATCH, 2 -> ESCALATE, 3+ -> AMBIGUOUS).

2. **Branch `_build_result` on candidate count.**
   File: `patient_matching/matching/matching_engine.py`, method `_build_result` (currently
   ends with an `if len(all_matched) == 1: ... else: # Ambiguous: 2+ candidates matched ...`).
   Replace the trailing `if/else` with a three-way branch:
   ```python
   # Uniqueness check: tiered per CMS v3.3 - 1 unique / 2 escalate / 3+ stricter threshold
   if len(all_matched) == 1:
       return MatchResult(
           outcome=MatchOutcome.MATCH,
           matched_patients=all_matched,
           matched_rule_id=first_rule_id,
           match_type=first_match_type,
           is_unique=True,
           rule_evaluations=evaluations,
           candidate_count=len(all_matched),
       )
   elif len(all_matched) == 2:
       return MatchResult(
           outcome=MatchOutcome.ESCALATE,
           matched_patients=all_matched,
           matched_rule_id=first_rule_id,
           match_type=first_match_type,
           is_unique=False,
           rule_evaluations=evaluations,
           candidate_count=len(all_matched),
       )
   else:
       # 3+ candidates: CMS v3.3 requires a stricter 1e-6 threshold here. This engine
       # doesn't yet compute live P(collision) (see session 5) - until it does, every
       # 3+-candidate case is conservatively treated as failing that stricter bar
       # (i.e. always AMBIGUOUS/decline), which is the safe default: it can only ever
       # cause an under-return, never a wrong-patient release. Session 5/6 should
       # replace this comment and wire in a real check without changing the branch
       # structure above.
       return MatchResult(
           outcome=MatchOutcome.AMBIGUOUS,
           matched_patients=all_matched,
           matched_rule_id=first_rule_id,
           match_type=first_match_type,
           is_unique=False,
           rule_evaluations=evaluations,
           candidate_count=len(all_matched),
       )
   ```

## Unit tests required

File: `patient_matching/matching/tests/test_matching_engine.py` (existing file — add a new
test class; the file already has `TestMatchingEngineAmbiguous` for the old 2-candidate case,
per `test_ambiguous_multiple_candidates` — update that existing test's expected outcome from
`MatchOutcome.AMBIGUOUS` to `MatchOutcome.ESCALATE` if it uses exactly 2 candidates, since its
meaning has changed; add the table below alongside it).

```python
import pytest

class TestTieredUniquenessResponse:
    """Boundary behavior across 1 / 2 / 3+ matched candidates (CMS v3.3 step 6)."""

    @pytest.mark.parametrize(
        "n_candidates,expected_outcome,expected_unique",
        [
            (1, MatchOutcome.MATCH, True),
            (2, MatchOutcome.ESCALATE, False),
            (3, MatchOutcome.AMBIGUOUS, False),
            (5, MatchOutcome.AMBIGUOUS, False),
        ],
    )
    def test_outcome_by_candidate_count(
        self, n_candidates, expected_outcome, expected_unique
    ):
        # Build n_candidates distinct patients that all satisfy the same rule
        # (e.g. rule 08: First Name + DOB + MBI), each with a unique "id".
        candidates = [
            _make_patient(first="john", dob="1990-01-15", mbi=f"1mbi{i:03d}mbi1")
            for i in range(n_candidates)
        ]
        for i, c in enumerate(candidates):
            c["id"] = f"patient-{i}"
        backend = InMemoryBackend(candidates)
        engine = MatchingEngine(backend=backend)
        query = _make_patient(first="john", dob="1990-01-15", mbi=candidates[0]["identifier"][-1]["value"])

        result = engine.match(query)

        assert result.outcome == expected_outcome
        assert result.is_unique == expected_unique
        assert result.candidate_count == n_candidates
```

Adjust the exact `_make_patient(...)` call to whatever combination of fields this test file's
existing helper supports for triggering a specific rule with N distinct candidates (the
pattern above assumes an MBI-based rule like rule 08, since MBI needs no fuzzy handling and
is trivial to make unique per candidate — check `_make_patient`'s actual signature in
`test_matching_engine.py` before finalizing field names).

## Validation (definition of "resolved")

- [x] `MatchOutcome.ESCALATE` exists and is used for exactly-2-candidate results.
- [x] `MatchOutcome.AMBIGUOUS` is used only for 3+-candidate results (never for exactly 2).
- [x] The existing `TestMatchingEngineAmbiguous` test (or its 2-candidate case) is updated to
      expect `ESCALATE`, not `AMBIGUOUS`, if it exercises exactly 2 candidates — grep the test
      file for `AMBIGUOUS` and confirm every remaining reference is a genuine 3+-candidate
      case.
- [x] All four parametrized boundary cases (1/2/3/5 candidates) pass.
- [x] `make tests` is green (full suite, no regressions from the `AMBIGUOUS` meaning change).
- [x] `make run-pre-commit` is clean.

## Open questions

None requiring a human decision. The interim "always treat 3+ as failing the stricter
threshold" behavior (Task 2) is a deliberate, safe default chosen at authoring time — it can
only cause under-return (a missed match), never a wrong-patient release, so it doesn't need
Sean's sign-off to ship as an interim state ahead of session 5/6.

## Execution notes

Executed 2026-07-30 on feature branch `claude/session-2-tiered-uniqueness`, cut from
`origin/main` at `c752873` (session 1's merge commit).

- Added `MatchOutcome.ESCALATE` to `patient_matching/matching/match_result.py`, per the
  session doc's exact snippet; updated the enum's class docstring and `MatchResult.
  matched_patients`'s attribute docstring (also said "2+ for AMBIGUOUS", now stale — updated
  to "2 for ESCALATE, 3+ for AMBIGUOUS").
- Replaced `MatchingEngine._build_result`'s trailing `if/else` with the three-way branch from
  the session doc verbatim (`== 1` MATCH, `== 2` ESCALATE, `>= 3` AMBIGUOUS with the documented
  interim-conservative comment).
- Test file `patient_matching/matching/tests/test_matching_engine.py`: renamed
  `test_ambiguous_multiple_candidates` to `test_escalate_two_candidates` and updated its
  assertion to `MatchOutcome.ESCALATE` (it exercises exactly 2 candidates); tightened its
  `candidate_count >= 2` assertion to `== 2` since the count is now deterministic. Added
  `TestTieredUniquenessResponse` with the doc's parametrized 1/2/3/5-candidate table, using
  rule 08 (First Name + DOB + MBI, all-exact) with a distinct MBI per candidate, per the
  doc's suggested pattern — `_make_patient`'s actual signature matched the doc's assumption
  directly, no field-name adjustment needed.
- Found and fixed a second, doc-unlisted regression: `patient_matching/matching/tests/
  test_in_memory_backend.py::test_engine_ambiguous_is_not_released` also exercises exactly 2
  candidates (via `MatchingManager`, which wraps `MatchingEngine` directly) and asserted
  `MatchOutcome.AMBIGUOUS` — this would have failed after the branching change. Renamed to
  `test_engine_escalate_is_not_released` and updated the assertion to `ESCALATE`. Confirmed via
  grep that no other production or test code references `MatchOutcome.AMBIGUOUS`/`ESCALATE` in
  a way requiring a change (`patient_matching/api/service.py::_compute_confidence` already
  branches on `!= MatchOutcome.MATCH`, so it's outcome-agnostic and needed no update).

Validation:
- `uv run pytest` (full local suite, outside Docker): 332 passed, 2 skipped, no regressions.
- `docker compose run --rm dev pytest patient_matching/matching/tests/`: 82 passed (78
  pre-existing + 4 new parametrized cases), no regressions.
- `docker compose run --rm dev pytest patient_matching/api/tests/`: pre-existing, unrelated
  failure — `ImportError: Error loading shared library libstdc++.so.6` from `duckdb` in the
  Alpine/musl dev image, on code this session never touched (`patient_matching/cache/
  duckdb_cache.py`). Not a regression from this change; not investigated further (out of
  scope). The equivalent tests pass locally outside Docker (`uv run pytest`, full suite above),
  confirming this is a container/native-lib issue, not a logic issue.
- `make tests`: 1 passed — as session 1 documented, this target only runs the top-level
  `tests/` dir (`test_basic.py`), not `patient_matching/matching/tests/`. Pre-existing Makefile
  gap, out of this session's scope; noted again here since the direct `docker compose run
  --rm dev pytest patient_matching/matching/tests/` run above is the stronger evidence.
- `make run-pre-commit`: clean (ruff, ruff format, mypy, bandit, secrets, etc.).
- No P(collision) computation was added (out of scope per the doc); the 3+-candidate branch's
  interim always-AMBIGUOUS behavior is exactly what session 5/6 are expected to replace.
- Statistical rigor gate: does not apply — the 1e-6 threshold is CMS-mandated, not tuned, and
  this session adds no new value judgment beyond the doc's explicit interim default (safe by
  construction: can only under-return, never mis-release).

Decision: PR [#14](https://github.com/icanbwell/patient-matching/pull/14) opened from
`claude/session-2-tiered-uniqueness` into `main`, left **open** rather than merged — per
`conventions.md`'s Definition of Done, merging is Sean's call, not the executing agent's. Doc
moved to `in_review/` accordingly.

PR #14 merged into `main` 2026-07-31 (Sean's merge decision). Doc moved from `in_review/` to
`completed/` in a later session (2026-08-01), which also updated `index.md` to reflect the
merge — this bookkeeping-only move was itself out of date until then.
