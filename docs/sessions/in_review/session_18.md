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

- [x] All 7 of v3.4.0 §VII's per-query audit fields are present and populated on
      `MatchResult`/`RuleEvaluation`.
- [x] `match_result.py`'s docstring correctly scopes Path A (covered) vs. Path B (not
      covered).
- [x] `uv run pytest .` green, full suite, no regressions (484 passed, up from 470; 21
      pre-existing Docker-dependent tests deselected, unrelated to this session).
- [x] `uv run pre-commit run` clean on touched files.
- [x] Not a rule-changing session (no Table 2/collision-probability change) — the statistical
      rigor gate does not apply per conventions.md's "Sessions that don't touch rule behavior
      are exempt entirely."

## Open questions

- **`NEEDS HUMAN DECISION`, resolved by the project lead (2026-09-15) before coding**: "query initiator"
  is an opaque, caller-supplied string with no validation or derivation by this library —
  deliberately *not* derived from the IAL2 token's issuer/CSP claim, since that identifies who
  verified the patient's identity, not who is asking for this match. See Execution notes for
  the implementation.
- **Resolved during execution, not anticipated when this doc was drafted**: "identifiers of
  records matched" (one of the 7 required fields) is genuinely ambiguous in the spec's own
  text — it could mean "which candidate record IDs matched" or "which identifying fields
  matched." Resolved as the latter: `RuleEvaluation.field_outcomes` already records which
  canonical fields (several of which are literally identifiers — SSN, ITIN, Legal ID, MBI,
  Namespace ID, Member ID, Subscriber ID) were compared and how. Documented as an
  interpretation in `match_result.py`'s module docstring, not silently assumed. Not escalated
  to the project lead as a second `NEEDS HUMAN DECISION` since it's a documentation/interpretation choice
  with no material behavior difference either way, not a design decision with real stakes.

## Execution notes

Executed 2026-09-15 on branch `claude/session-18-v340-audit-record-reconciliation`, cut from
`main` (session 16/PR #51 still open — soft dependency only, per this doc's own "Upstream
sessions" section; no `rule_id` values are referenced in this session's new fixtures in a way
that would need a second pass). `docs/sessions/pending/session_{18,19}.md` and the updated
`index.md`/`conventions.md` only existed on session 16's branch (never merged to `main`) - like
sessions 17/18 before it, pulled across via `git checkout claude/session-17-... -- <paths>`
(session 17's branch, since it already had the latest copies) as a separate commit, not part of
this session's own diff.

**Re-verified §VII's exact text against the raw v3.4.0 spec before implementing** (not just
this doc's paraphrase): the 7-field list, the Path A/B definitions, and the "SHOULD also retain
the applicable rules or software version" line all matched this doc's Outcome purpose exactly -
no surprises here, unlike sessions 16/17.

**Real, load-bearing gap found while doing the field-by-field mapping (Task 1), not anticipated
by this doc's "expect this to be small or empty" framing**: `RuleEvaluation.timestamp` exists,
but a query that matches zero rules (e.g. an empty query patient, or one missing every field
every enabled rule needs) produces an empty `rule_evaluations` list - meaning **no timestamp
existed anywhere on the result** for that case. Fixed by adding a query-level `timestamp` to
`MatchResult` itself, generated once per `MatchingEngine.match()` call, independent of how many
(if any) rule evaluations occur. Verified by a dedicated test
(`test_match_result.py::TestTimestamp::test_is_populated_even_with_zero_rule_evaluations`).

**`query_initiator` threading**: added as a keyword-only parameter on
`MatchingEngine.match()`, `PatientMatcherService.match_patient()`, and
`PatientMatcherService.match_from_token()`, flowing through `_build_result`'s 4
`MatchResult(...)` construction sites into `MatchResult.query_initiator`, then surfaced on the
service-layer `MatchResponse` too (alongside `timestamp`) so it's visible at both the engine and
service API levels, consistent with how `matched_rule_id`/`match_type` are already surfaced at
both.

**No structural changes needed for the other 5 fields** - confirmed by direct mapping, not
assumed: Table 2 combination evaluated -> `matched_rule_id`/`RuleEvaluation.rule_id`; match
type -> `match_type`; uniqueness-check result -> `is_unique`/`outcome`; final determination ->
`outcome`; identifiers of records matched -> `field_outcomes` (see Open Questions for why this
mapping, not a literal reading, was chosen).

Validation:
- `uv run pytest .`: 484 passed (up from 470), 0 regressions. New tests: 14 across
  `test_match_result.py` (a new file - one test class per SS VII field, 12 tests total,
  including the zero-rule-evaluations timestamp edge case) and `test_service.py` (3 tests:
  query-initiator echoed through both `match_patient()` and `match_from_token()`, and its
  absence defaulting to `None` without breaking existing callers).
- `uv run pre-commit run` on all touched files: clean (ruff, ruff-format, mypy, bandit,
  detect-secrets, standard hooks).
- Not a rule-changing session - statistical rigor gate exempt, per conventions.md.

Decision: PR opened from `claude/session-18-v340-audit-record-reconciliation` into `main`, left
**open** rather than merged - merging is the project lead's call, same as every prior session in this
repo. Doc moved to `in_review/` and `index.md` updated accordingly, in the same PR.

## Post-review fixes (adversarial review pass, 2026-09-15)

An adversarial review of this PR (executed against a live worktree, reproductions run and
verified, not by inspection) found two real defects, fixed here, and two real questions that
need the project lead's input rather than a unilateral code change:

**Fixed: `MatchingManager` - the other public entry point besides `MatchingEngine.match()` -
had no way to accept `query_initiator` at all.** `MatchingManager.match()`/`match_batch()`
still called `self._engine.match(query_patient)` with no initiator, verified to produce
`query_initiator=None` on every query routed through it regardless of what the caller
supplied. `MatchingManager` is exported in `patient_matching/matching/__init__.py` and its own
class docstring presents it as "a single entry point" - silently incomplete for SS VII. Fixed
by adding the same `query_initiator` keyword-only parameter to both methods
(`match_batch`'s applies to every patient in the batch, since a batch is one caller-issued
operation). New tests in `test_matching_manager.py` confirmed via `git stash` to fail
pre-fix.

**Fixed: a query with too few fields for ANY Table 2 rule to be attempted was
indistinguishable from a genuinely-evaluated-but-not-found query.** Both previously reported
`MatchOutcome.NO_MATCH` with an empty `rule_evaluations` - but "no Table 2 combination was even
evaluable" is not the same SS VII "final match determination" as "every evaluable combination
was checked and none matched," and this doc's own field-mapping treats "Table 2 combination
evaluated" and "final match determination" as two separate fields that can't both be
meaningfully populated from the same NO_MATCH value in the empty-evaluations case.
`MatchOutcome.INSUFFICIENT_FIELDS` was defined in `match_result.py` for exactly this and never
produced anywhere - confirmed by grep before fixing, not assumed. Fixed by tracking whether any
rule's (flat or household) field requirements were even satisfiable by the query, independent
of backend search, and returning `INSUFFICIENT_FIELDS` instead of `NO_MATCH` when none were.
One existing test (`test_service.py::test_match_patient_no_match`) turned out to be
accidentally exercising this exact case under a stale "no_match" assertion - its query's phone
number had an invalid US area code that normalization silently dropped, leaving it with too few
fields for any rule; fixed the phone number to restore the test's actual intent and added a
dedicated `test_match_patient_insufficient_fields` for the case it was accidentally covering.
Two more existing tests genuinely needed their expected outcome updated for the same reason
(both configured zero evaluable rules on purpose). All confirmed via `git stash` to
newly-fail/newly-pass correctly across the fix.

**Not fixed, flagged for the project lead instead of decided unilaterally:**

1. **No audit record is produced at all on error paths** (a raising backend, IAL2 token
   verification failure, or normalization failure all abort before any `MatchResult` is
   constructed - verified by tracing `matching_engine.py` and `service.py`'s exception
   surfaces). If SS VII requires a record per query *attempted*, a failed query is exactly the
   case an auditor would care about most. Not fixed here because catching exceptions to still
   emit a record is a real behavior change to this library's error-handling contract (do
   callers currently rely on exceptions propagating?), not a local correction - needs a
   decision on whether failed queries should produce a record at all, and if so, what
   "failure" outcome/fields it should carry.
2. **`query_initiator` is untrusted, unvalidated input written verbatim into an audit
   field.** Verified a forged value containing control characters/newlines passes through
   unmodified and gets persisted. `MatchResult.query_initiator`'s own docstring already
   documents "this library does not validate, derive, or require it" as an explicit decision
   made with the project lead on 2026-09-15 (the same day this session ran) - re-litigating that via a
   silent validation change would override a decision already made on this exact field without
   new authorization. Flagging instead: was "opaque, unvalidated" meant to include tolerating
   literal control characters (a log-injection vector once this record reaches any
   line-oriented sink) and PHI smuggled into a field documented as non-PHI provenance metadata,
   or does the existing decision need a narrower amendment (e.g. reject control characters/cap
   length, without deriving or requiring semantic content)?

A related, smaller documentation gap also flagged, not changed: `match_result.py`'s module
docstring now frames `MatchResult` as "the SS VII per-query audit record," but the dataclass
still carries full FHIR Patient dicts in `matched_patients` - a consumer following that framing
literally could persist/export the whole object as its audit record, writing complete PHI
(name, DOB, address) into a store that needs only identifiers and outcomes. Worth a docstring
warning or a PHI-free projection method in a follow-up, not blocking this fix pass.

Also added, closing test-coverage gaps the same review found: `TestQueryInitiatorAndTimestampOnEveryOutcomeBranch`
(query_initiator/timestamp were only tested on the NO_MATCH/MATCH branches of `_build_result`'s
4 hand-duplicated construction sites - ESCALATE/AMBIGUOUS were unverified), a timestamp
ISO-8601-UTC well-formedness test (prior tests only checked `!= ""`), and a fuzzy `match_type`
test (only "exact" was covered).

Validation after fixes: `uv run pytest .` - 485 passed (up from 478), 0 regressions.
`uv run pre-commit run` clean; the one remaining mypy failure (`mongo_atlas_cache.py:264`)
confirmed via `git stash` to pre-exist on this branch independent of this fix.
