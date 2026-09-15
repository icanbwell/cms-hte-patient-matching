# Session 18 — CMS v3.4.0: §VII audit record reconciliation

**Status:** pending
**Thread:** Line B: CMS v3.4.0 migration
**Estimated size:** M — mostly additive to existing audit types
(`RuleEvaluation`/`MatchResult`), plus one real API-surface question (query initiator) that
needs a human call before coding.

> Read `../conventions.md` first. Independent of sessions 16/17's rule-set changes — can run
> before, after, or in parallel with either, but should land after session 16 if `rule_id`
> values are cross-referenced in any new audit test fixtures, to avoid re-doing them.

## Outcome purpose

v3.4.0 §VII splits audit into **Path A** (rules-engine integrity — did the engine apply Table
2 correctly) and **Path B** (outcomes/performance — match rate, correction rate, appeal rate,
trend over time), and specifies a 7-field per-query audit record: query initiator, Table 2
combination evaluated, match type (exact/fuzzy), identifiers matched, uniqueness-check result,
final determination, timestamp. This repo already has 6 of those 7 fields (session 1's
audit-field addition plus what session 2/5/6 added along the way) via
`RuleEvaluation`/`MatchResult` in `patient_matching/matching/match_result.py`. The one missing
field is **query initiator** — no such concept exists anywhere in this codebase today
(confirmed by grep, 2026-09-15: zero hits for "initiator"/"requester"/"caller"/"client_id" across
`patient_matching/api/` and `patient_matching/matching/`).

## Upstream sessions (must be completed first)

None with a hard code dependency. Soft ordering preference: after session 16, so any new test
fixtures referencing `rule_id` use the post-renumbering IDs rather than needing a second pass.

## Downstream sessions (unblocked by this one)

Path B's aggregate outcome metrics (match/no-candidate/ambiguous rate, correction rate, appeal
rate, trend) are explicitly **out of scope** for this session (see below) — a future session,
once someone owns compliance reporting, would build on this session's per-query record to
compute them.

## Upstream data/system dependencies

CMS Proposal v3.4.0 §VII (same live doc as sessions 16/17, file ID
`1NytpfZ05aokS-gD7uDIQE7gEyms9zMgoiaIah_w4VTE`) — re-verify the exact 7-field list and Path
A/B definitions against the live doc at session-start, same rationale as sessions 16/17.

## Downstream data/system dependencies

None new.

## Scope

### In scope

**1. Confirm the 6 already-covered fields map cleanly to v3.4.0's list**, updating field names
   or docstrings only if the spec's wording has shifted since v3.2.2/v3.3 (session 1's original
   basis): Table 2 combination evaluated (`RuleEvaluation.rule_id`), match type
   (`match_type`), identifiers matched (`field_outcomes`), uniqueness-check result
   (`MatchResult.is_unique`/`outcome`), final determination (`MatchResult.outcome`), timestamp
   (`RuleEvaluation.timestamp`). No structural change expected here — this is a verification
   task, not a build task; only touch code where the spec's wording genuinely doesn't match
   what exists.

**2. Add "query initiator" as a 7th audit field.** This needs a human decision before coding —
   see Open Questions. Once decided, the mechanical shape is: a new parameter on
   `PatientMatcherService.match_patient`/`match_from_token` (both currently lack any
   caller-identity parameter), threaded down into `RuleEvaluation`/`MatchResult` alongside the
   existing `version`/`timestamp` fields.

**3. Note Path A vs. Path B in the audit record's docstring/module comment** (currently
   `match_result.py`'s docstring cites "Section VII" generically) — Path A is fully satisfied
   by the per-query record this session completes; Path B is explicitly out of scope (below),
   so the docstring should say so rather than implying full §VII coverage.

### Out of scope

- **Path B aggregate metrics** (match/no-candidate/ambiguous rate, correction rate, appeal
  rate, trend over time). These are population-level statistics computed *over* per-query
  records, not a per-query field — this repo has no reporting/analytics layer to compute or
  store them (same disposition as v3.3.2/v3.3.5 in session 6: "relevant to whoever owns
  compliance reporting," likely `evaluation/` or the sibling `cms-hte-patient-matching-service`
  repo, not this session).
- Any change to how `MatchResult`/`RuleEvaluation` are persisted/exported — this session only
  ensures the *fields* exist; wiring them to an actual audit log/database is Phase 2
  production-infrastructure scope, not yet chartered anywhere in this repo per
  `docs/PROJECT_MAP.md`.
- Sessions 16, 17, 19's scope.

## Tasks

1. Diff v3.4.0 §VII's 7-field list, fetched fresh, against `match_result.py`'s current fields
   field-by-field; fix only genuine mismatches (expect this to be small or empty per the
   Outcome purpose's pre-check).
2. Once Open Questions' `NEEDS HUMAN DECISION` is resolved, add the query-initiator field:
   new parameter on the public service methods, new field on `RuleEvaluation` (and/or
   `MatchResult`, implementer's call on which level it belongs at — likely `MatchResult`, since
   it's per-query, not per-rule-evaluation), plumbed through `_match_and_respond`.
3. Update `match_result.py`'s module docstring to distinguish Path A (covered) from Path B
   (not covered, see Out of scope) rather than citing "Section VII" unqualified.

## Unit tests required

- Extend `test_service.py` / wherever `PatientMatcherService`'s tests live: a case passing a
  query initiator through to the resulting `MatchResult`/`RuleEvaluation`, and a case
  confirming its absence doesn't break existing callers (a sensible default — implementer's
  call, e.g. `None` or an empty string — once the Open Question is resolved).
- A test asserting the 7-field mapping directly (one assertion per field, parametrized), so a
  future spec revision touching §VII trips an obvious, named test rather than a generic
  regression.

## Validation (definition of "resolved")

- [ ] All 7 of v3.4.0 §VII's per-query audit fields are present and populated on
      `MatchResult`/`RuleEvaluation`.
- [ ] `match_result.py`'s docstring correctly scopes Path A (covered) vs. Path B (not
      covered).
- [ ] `uv run pytest .` green, full suite, no regressions.
- [ ] `uv run pre-commit run` clean on touched files.
- [ ] Not a rule-changing session (no Table 2/collision-probability change) — the statistical
      rigor gate does not apply per conventions.md's "Sessions that don't touch rule behavior
      are exempt entirely."

## Open questions

- **`NEEDS HUMAN DECISION`**: what does "query initiator" concretely mean for this repo, and
  who supplies it? Candidates: an opaque caller-supplied string (e.g. the calling service's
  name/client ID, passed as a new parameter with no validation by this library); something
  derived from the IAL2 token's issuer/CSP claim when the query came via
  `match_from_token`; or something Phase 2's production service (not this repo) is expected to
  populate, in which case this session should add the *field* but leave it caller-optional
  with no derivation logic here. This shapes Task 2's actual implementation — resolve before
  writing code, per conventions.md's open-questions handling.

## Execution notes

_(filled in at close)_
