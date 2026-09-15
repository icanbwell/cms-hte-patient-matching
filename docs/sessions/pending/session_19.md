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

- [ ] All four §C.7 behaviors implemented and independently tested.
- [ ] §C.9 implemented and tested, or explicitly deferred with a note in Execution notes (not
      silently dropped).
- [ ] No existing test regresses — in particular, confirm the base 1/2/3+ tiering (session 2)
      and rules 13-16/34/35/37/38 (session 6/17) still pass unchanged.
- [ ] `uv run pytest .` green, full suite.
- [ ] `uv run pre-commit run` clean on touched files.
- [ ] This session changes matching *behavior* for twin/shared-DOB cases specifically — per
      conventions.md's statistical rigor gate, run the Tier 1 ONC `ComparisonReport` (baseline
      vs. candidate) before this session reaches `completed/`; note in Execution notes whether
      the ONC dataset contains enough true-twin cases to meaningfully exercise this change (if
      not, same "no regression confirmed, not meaningful precision/recall for this specific
      behavior" caveat as session 17's Tier 1 note applies here too).

## Open questions

None requiring a human decision identified so far — §C.7's four rules are specified concretely
enough to implement directly. If persistent-identifier anchoring (Task 4/1d) turns out to
require infrastructure this repo doesn't have (e.g., a durable store of prior resolutions
beyond a single `MatchingEngine` call's lifetime), that becomes a new open question to raise at
execution time, not guessed at here.

## Execution notes

_(filled in at close)_
