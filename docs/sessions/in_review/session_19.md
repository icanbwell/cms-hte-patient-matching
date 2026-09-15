# Session 19 — CMS v3.4.0: §C.7 twin/multiple-birth handling + §C.9 defensive flagging

**Status:** pending
**Thread:** Line B: CMS v3.4.0 migration
**Estimated size:** M — corrects an initial "just verify" assumption: none of §C.7's four
operational behaviors exist yet (confirmed by grep, 2026-09-15 — only the base 1/2/3+
candidate-count tiering from session 2 exists). This is new logic on top of the existing
escalation path, not a verification pass.

> Read `../conventions.md` first. Independent of sessions 16/17/18 — no hard code dependency
> either direction, though it touches `matching_engine.py` (a hot file per session 6's own
> Category-2 work) so avoid running concurrently with a session that's mid-edit there.

## Outcome purpose

v3.4.0 §C.7 specifies four operational rules for twins/multiple-births sharing a household and
DOB — none built yet, only referenced as caveats on rule 30 (formerly 36) and I-01's gating
condition since session 6. §C.9 adds a new (SHOULD-level, not SHALL) category:
"Household/Relationship risk" — using existing relationship data (FHIR `RelatedPerson`,
`Patient.link`, emergency-contact fields) to flag same-household false positives before
finalizing a phone/email match. This session builds §C.7 in full and §C.9 as a lower-priority
addition if time allows within the session's sizing.

## Upstream sessions (must be completed first)

None with a hard dependency. Soft preference: land after session 17, since rule 39/40's
guardian/mother-linkage plumbing (session 17) and this session's relationship-data flagging
(§C.9) both touch "does this codebase understand a Patient's relationships" — landing session
17 first avoids two sessions independently inventing different FHIR-shape conventions for
similar data. Not a blocker if sequencing works out the other way; just flag the overlap
in Execution notes if it happens.

## Downstream sessions (unblocked by this one)

None currently authored.

## Upstream data/system dependencies

CMS Proposal v3.4.0 §C.7 and §C.9 (same live doc as sessions 16/17/18, file ID
`1NytpfZ05aokS-gD7uDIQE7gEyms9zMgoiaIah_w4VTE`) — fetch fresh at session-start, same rationale
as prior v3.4.0 sessions.

## Downstream data/system dependencies

None new.

## Scope

### In scope

**1. §C.7, four operational rules**, applied only within the existing two-candidate escalation
   path (session 2) — this session does not introduce a new escalation mechanism, per the same
   "reuse, don't duplicate" principle session 6 used for the household/individual two-step:

   a. **Exact (not fuzzy) First Name whenever household-tier matching resolves more than one
      candidate sharing an identical DOB.** Before applying any fuzzy-First-Name rule, check
      whether the current candidate set has >1 member sharing DOB; if so, skip fuzzy/
      corroboration handling for First Name on that evaluation and require an exact match.

   b. **Fail closed on placeholder/identical first names.** If stripping newborn/NICU
      placeholders (existing `PlaceholderDetector`) leaves no discriminating First Name value,
      or the names are genuinely identical, the query SHALL produce the existing
      more-than-one-candidate escalation outcome — not a new mechanism, not a silent pick.

   c. **Middle name as last-resort tiebreaker**, used only inside the same two-candidate
      escalation flow, only when First Name is also tied. `household_rules.py`'s existing
      `IndividualRow` type doesn't reference middle name at all today — this task adds it as a
      tiebreak signal inside the escalation path, not as a new standing Table 2/Table 2-I row
      (consistent with v3.3.1's original framing of middle name as "not a standing field").

   d. **Anchor to a persistent identifier** (MRN/EMPI/FHIR `Patient.id`, i.e. the existing
      `namespace_id` field/rule 22) once a twin case is first resolved, so a subsequent query
      for the same person skips the name-tiebreak path entirely. Implementer's call on the
      exact mechanism (e.g., checking whether the candidate already carries a
      previously-recorded namespace ID match before re-running the tiebreak) — this is new
      state/lookup behavior this repo doesn't have an existing pattern for; keep it as narrow
      as the spec requires (skip re-tiebreaking a known-resolved case), not a general caching
      layer.

**2. §C.9 defensive relationship-data flagging (SHOULD, lower priority within this session).**
   Where relationship data exists (FHIR `RelatedPerson`, `Patient.link`, emergency-contact
   fields — or, once session 17 lands, whatever linked-identity representation it introduces),
   flag/log a same-household risk signal before finalizing a phone- or email-based match. Per
   the spec's own SHOULD (not SHALL) framing, this is advisory: log/flag only, never block or
   downgrade a match outcome. If this session's time budget is tight, this item may be
   deferred to a follow-up rather than compromising §C.7's quality — note that decision in
   Execution notes if it happens; don't silently drop it without a note.

### Out of scope

- Any change to the base 1/2/3+ candidate-count tiering itself (session 2) — this session adds
  twin-specific behavior *within* that existing tiering, not a replacement for it.
- A general match-outcome caching/lookup layer beyond the narrow "skip re-tiebreaking an
  already-resolved twin case" behavior in Task 1d.
- Sessions 16, 17, 18's scope.

## Tasks

1. Implement §C.7(a): DOB-shared-candidate check gating exact-vs-fuzzy First Name, in
   `matching_engine.py`'s field-verification path.
2. Implement §C.7(b): placeholder/identical-name fail-closed routing to the existing
   escalation outcome (reuse `MatchOutcome.ESCALATE`/`AMBIGUOUS`, no new outcome type).
3. Implement §C.7(c): middle name as last-resort tiebreaker inside the escalation path only.
4. Implement §C.7(d): persistent-identifier anchoring to skip re-tiebreaking a previously
   resolved twin case.
5. If time allows: implement §C.9's advisory relationship-data flagging, log/flag only.

## Unit tests required

- New test module (e.g. `test_twin_handling.py`): one test per §C.7 sub-rule (a-d), each
  constructed as a same-household, shared-DOB scenario per conventions.md's "cover decision
  boundaries" guidance (e.g. for (a): DOB shared by exactly 2 vs. exactly 1 candidate; for (b):
  placeholder-stripped-to-empty vs. genuinely-identical vs. genuinely-different First Name; for
  (c): middle name present-and-distinguishing vs. absent vs. also tied; for (d): first
  resolution vs. a repeat query for the same already-resolved pair).
- If §C.9 is built this session: a test confirming the flag is advisory only — an otherwise-
  valid match is never blocked or downgraded by a relationship-risk flag, only logged.

## Validation (definition of "resolved")

- [x] All four §C.7 behaviors implemented and independently tested.
- [x] §C.9 explicitly deferred, not silently dropped - see Execution notes for why.
- [x] No existing test regresses - confirmed by the full suite (481 passed, up from 470 on
      this branch; 21 pre-existing Docker-dependent tests deselected, unrelated).
- [x] `uv run pytest .` green, full suite.
- [x] `uv run pre-commit run` clean on touched files.
- [x] Statistical rigor gate: `tests/test_onc_population_regression.py`/`test_onc_regression.py`
      (this repo's current Tier-1-equivalent tooling, per sessions 17/18's same finding) both
      pass with the twin-handling changes active in `MatchingEngine()`'s default behavior,
      confirming no regression. As expected, the ONC dataset has no labeled true-twin cases, so
      this doesn't produce meaningful precision/recall for the twin-specific behavior itself -
      exercised instead by this session's own dedicated `test_twin_handling.py`.

## Open questions

None requiring a human decision - §C.7's four rules were specified concretely enough to
implement directly, and no case arose needing new infrastructure beyond what this session
already built. §C.9 (see Execution notes) is deferred, not blocked on a decision - resolving it
is future scoping work, not something requiring Imran's input right now.

## Execution notes

Executed 2026-09-15 on branch `claude/session-19-v340-twin-handling`, cut from `main` (sessions
16-18/PRs #51-#53 all still open - no hard dependency either direction, per this doc's own
"Upstream sessions" section). `docs/sessions/pending/session_19.md` and the updated
`index.md`/`conventions.md` only existed on session 16's unmerged branch; pulled across via
`git checkout claude/session-18-... -- <paths>` as a separate commit, same as sessions 17/18.

**Real, load-bearing correction found empirically while writing the tests for SS C.7(4), not
assumed in advance:** this doc's own text speculated that anchoring to a persistent identifier
might turn out to need "new state/lookup behavior this repo doesn't have an existing pattern
for." The actual finding is different and more specific: it isn't a *missing* capability, it's
a *wrong assumption about existing architecture*. A first attempt at implementing (4) relied on
`MatchingEngine`'s ordinary cross-rule aggregation to do the work for free - reasoning that a
query carrying a resolved `namespace_id` would independently match the standing `namespace_id`
flat rule, and that this would somehow narrow the twin household/individual rule's own
ambiguous result. A dedicated test (`TestPersistentIdentifierAnchor`) disproved this
immediately: `_build_result` **unions** every contributing rule's matches rather than letting a
more-specific rule suppress a less-specific one, so the twin-ambiguous rule still independently
contributed both candidates regardless of what the `namespace_id` rule separately resolved,
producing `ESCALATE` where `MATCH` was expected. Fixed properly by applying the `namespace_id`
anchor *inside* the household/individual tie-resolution itself
(`_break_twin_tie_with_namespace_id`, checked before the middle-name tiebreak, since it's a
near-zero-collision signal rather than a last-resort one) - not by adding any new state or
lookup mechanism, and not by relying on aggregation. This is exactly the kind of
plausible-but-wrong architectural assumption the "write the test before trusting the theory"
discipline exists to catch.

**SS C.7(1)** (exact First Name when DOB shared): implemented as a field-composition rewrite
(`_force_exact_first_name`) applied only when `_household_matches_share_a_dob` detects 2+
household-tier matches sharing an identical DOB - the common, non-twin, single-household-match
case is entirely unaffected (confirmed by a dedicated control test and the full suite's zero
regressions).

**SS C.7(2)** (placeholder/identical-name fail-closed): needed no new code, confirmed by
writing the tests first rather than assuming - the existing per-candidate exact/missing-field
checks already produce `NO_MATCH` (placeholder-stripped-to-empty case) or `ESCALATE`
(genuinely-identical-names case) without any twin-specific branch.

**SS C.7(3)** (middle name tiebreaker): added `middle_names` to `PatientFields` as given names
beyond the first (FHIR positional convention), additive to the existing `first_names` set (which
already collects *every* given name per Core Principle 10 - unchanged). Deliberately **not**
added to `get_values()`'s mapping or `collision.FIELD_U_PROBS`, since CMS dismisses Middle Name
from the collision-probability tables entirely (data quality/low selectivity) - `middle_names`
is accessed directly by the tiebreak logic, never through a `RuleField`, so it can never be
mistakenly used in a `p_collision()` call.

**SS C.9** (defensive relationship-data flagging): deferred, not built this session. Confirmed
this is a real API-surface question, not a quick addition: `FieldExtractor.extract()` only ever
sees a single FHIR `Patient` dict (per its own docstring), but FHIR `RelatedPerson` is a
*separate* resource type entirely - flagging same-household risk from relationship data would
require deciding how a caller supplies that data to the engine at all (a new parameter? read
from a `Patient.link`/extension already on the dict, like session 17's linked-identity
convention once it lands?), which is a real design decision this session's remaining time
budget shouldn't rush past. Per this doc's own explicit permission to defer rather than
compromise §C.7's quality.

Validation:
- `uv run pytest .`: 481 passed (up from 470), 0 regressions. New tests: 9 in
  `test_twin_handling.py` (one test class per SS C.7 sub-rule, including the namespace-id-vs-
  middle-name priority case that caught the aggregation-assumption bug) + 2 in
  `test_field_extractor.py` (`middle_names` extraction).
- `uv run pre-commit run` on all touched files: clean (ruff, ruff-format, mypy, bandit,
  detect-secrets, standard hooks) - one real mypy error caught and fixed (a test helper's
  `identifiers` list needed an explicit `List[Dict[str, Any]]` annotation once it held
  non-uniform dict shapes).
- Statistical rigor gate: see corrected checklist item above.

Decision: PR opened from `claude/session-19-v340-twin-handling` into `main`, left **open**
rather than merged - merging is Imran's call, same as every prior session in this repo. Doc
moved to `in_review/` and `index.md` updated accordingly, in the same PR.
