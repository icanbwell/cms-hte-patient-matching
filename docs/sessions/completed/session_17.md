# Session 17 — CMS v3.4.0: Relationship Linkage field + Rules 39/40

**Status:** completed ([PR #52](https://github.com/icanbwell/cms-hte-patient-matching/pull/52),
merged 2026-09-15)
**Thread:** Line B: CMS v3.4.0 migration
**Estimated size:** L — a genuinely new architectural concept (matching against an
*already-resolved, external* identity rather than fields on the same record pair), not an
extension of the existing flat or household/individual patterns. Both target rules carry
caveats the spec flags as unresolved in its own text — this session builds them anyway
(the project lead, 2026-09-15: "implement now, best-effort"), with those caveats documented as known
limitations rather than silently resolved.

> Read `../conventions.md` first. Depends on session 16 landing first (see below) — don't
> start this session until session 16 is in `completed/`.

## Outcome purpose

v3.4.0 adds a new Table 3 field, **Relationship Linkage** (two u-value variants: clinical
source 0.01, self-reported/intake 0.05, no fuzzy variant), and two new Category 2-style rules
that use it: **Rule 39** (guardian-verified minor) and **Rule 40** (newborn via maternal
linkage). Unlike every existing Category 2 rule (13-16, 34, 35, 37, 38), which resolves a
*household* from shared fields on the same incoming record, rules 39/40 require a *different*
person's identity to already be independently matched (a guardian, or a mother) and use that
resolved identity plus a relationship claim as one "leg" of the combination. This session adds
the field and builds both rules against v3.4.0's text as currently drafted.

## Upstream sessions (must be completed first)

Session 16 — renumbers Category 1 and is a hot-file (`table2_rules.py`) change; branching
before it merges risks a rename conflict on the same file this session also touches (adding
new field constants). No hard *code* dependency otherwise — rules 39/40 are new IDs, untouched
by session 16's renumbering.

## Downstream sessions (unblocked by this one)

None currently. A future session revisiting rule 39's Street Line correlation discount (once
CMS or an internal decision resolves it) or rule 40's per-encounter-ID data availability would
build on this session's field/plumbing rather than redo it.

## Upstream data/system dependencies

CMS Proposal v3.4.0 (same live Google Doc as session 16 — file ID
`1NytpfZ05aokS-gD7uDIQE7gEyms9zMgoiaIah_w4VTE`), §C.4's rule 39/40 rows specifically. **Fetch
fresh at session-start**, same rationale as session 16.

**New dependency this session did not have before:** rules 39/40 both require a
*relationship* signal (guardian-of, newborn-of) and, for rule 39, a reference to a guardian's
own already-matched identity. This repo's `FieldExtractor` only ever sees a single FHIR
`Patient` dict (per its own docstring) — there is no existing convention here for representing
"this patient's guardian/mother, already resolved to Patient X." Resolve at implementation
time by checking what shape is actually available: FHIR `Patient.link` (`type: seealso` or
similar), a `RelatedPerson` resource with an HL7 relationship code (`MTH` for mother, a
guardian code), or an extension — grep `patient_matching/fhir_client/` and
`patient_matching/ial2_extraction/` first for any existing convention before inventing one
(same instruction pattern session 6 used for Task 1's identifier codes).

## Downstream data/system dependencies

None new.

## Scope

**Correction, found during execution by re-verifying the raw §C.4 table before writing any
code (not guessed):** the spec's own math for rule 39 — *"≈6e-13 (flat product: 0.02 × 0.0001
× 0.01 × 0.00003)"* — only has 4 factors: First Name exact (0.02), DOB exact (0.0001),
Relationship Linkage clinical (0.01), Street Line exact (0.00003). **"Guardian's identity
(independently matched under Table 2)" contributes no factor of its own** — there is no room
in that product for a 5th, near-zero term. This repo's original scoping (Task 2, below)
assumed the guardian/mother identity would be a `namespace_id`-style near-zero-collision
*field* multiplied into the product, the same way `household_rules.py`'s H-rows work — that
would be wrong by many orders of magnitude (multiplying by ~1e-15 on top of the published
6e-13 would misreport the rule's actual collision risk to regulators/auditors). The correct
reading: **the guardian/mother identity match is a zero-cost gate, not a probabilistic
factor** — its own uniqueness was already fully accounted for by whatever separate Table 2
rule matched the guardian/mother in the first place, so rule 39/40's own P(collision) is
*conditional* on that gate already holding, not compounded with it. §C.4's own table literally
presents rules 39/40 in its "Household leg | Individual leg | Combined P(collision)" format —
so the *existing* `HouseholdRow`/`IndividualRow`/`HouseholdIndividualRule` two-step machinery
(`household_rules.py`) is exactly the right shape, provided the "household row" for the
identity-gate component uses a u-value of **1.0** (not near-zero) to make it a true no-op
multiplier. Per session 16's precedent, these get `C2-` prefixed rule_ids too (`C2-39`,
`C2-40`) — same audit-fidelity reasoning, and they're structurally Category 2 rules per the
spec's own table.

### In scope

**1. Relationship Linkage field, Table 3.** File: `patient_matching/matching/collision.py`.
   Add two u-value entries — separate field-name keys, since nothing else in this repo has a
   "source-quality-conditioned" u-value and `FIELD_U_PROBS`'s shape doesn't need to change:
   - `relationship_linkage_clinical` = 0.01
   - `relationship_linkage_self_reported` = 0.05 (defined but unused by any rule this session
     builds — both rules 39/40 use the clinical variant only — matching the "define but leave
     unused" precedent `household_rules.I_03` already sets).
   **Also add a 1.0 "identity gate" u-value** (e.g. `guardian_identity` / `mother_identity`,
   or one shared key if the executor judges the semantics are close enough — see Task 2) — a
   deliberate no-op multiplier representing an already-independently-verified identity, per
   the correction above. Document inline exactly why this is 1.0 and not near-zero, since a
   future reader's first instinct (this session's own original assumption) will be wrong.
   **`birth_encounter_id`'s u-value is not given explicitly anywhere in Table 3** — the spec
   only says a true per-encounter ID "clears with wide margin" and a shared facility ID "is
   far above the threshold." Reuse `namespace_id`'s existing 1e-15 tier (both represent a
   namespace-bound, per-entity-unique identifier) rather than inventing a new number, and
   document this as an interpretation, not a spec-given figure.

**2. Guardian/mother linked-identity + relationship-linkage extraction.** However the FHIR-shape
   research comes out (see "Upstream data/system dependencies"), this session needs
   `FieldExtractor` to pull: (a) a reference to the guardian's/mother's own already-matched
   identity, (b) a Relationship Linkage claim (type: child-of/newborn-of; source:
   clinical/self-reported), and (c) for rule 40, a namespace-scoped birth-encounter ID.
   Represent (a) and (c) as `identifier`-array entries (this repo's existing pattern for
   `legal_id`/`insurance_subscriber_id` — reuse `_extract_identifiers`, don't invent a second
   extraction mechanism) with new custom type codes (document the choice, same as session 6's
   `MB`/`SN` codes). Represent (b) as a Patient `extension` (it describes a relationship claim,
   not an identity) with a documented, self-defined extension URL. New `PatientFields` fields:
   `guardian_identity`/`mother_identity` (or one shared field, executor's call),
   `relationship_linkage_clinical`/`_self_reported`, `birth_encounter_id`.

**3. Rule `C2-39` (guardian-verified minor).** Household row: guardian-identity gate (u=1.0)
   × Street Line (u=0.00003) = 3e-5. Individual row: Relationship Linkage clinical (0.01) ×
   First Name exact (0.02) × DOB exact (0.0001) = 2e-8. Combined: 6e-13, matching the spec's
   own stated figure exactly. **Known limitation, ship anyway, document in code and PR
   description — do not silently treat as resolved:** the spec's own text says *"Street Line
   is correlated with the relationship term (same household address), so this overstates the
   margin; needs a dependency discount or drop Street Line before adoption."* Build the rule
   exactly as specified (no ad hoc discount invented by this session), and add a code comment
   plus an Execution-notes entry stating plainly that the true collision margin is narrower
   than 6e-13 implies until CMS or an internal decision supplies a discount factor.

**4. Rule `C2-40` (newborn via maternal linkage).** Household row: mother-identity gate
   (u=1.0) alone (no Street Line component in the spec's table for this row) = 1.0.
   Individual row: Relationship Linkage clinical (0.01) × DOB exact (0.0001) ×
   birth-encounter-id (1e-15, per Task 1's interpretation) = 1e-21. Combined: 1e-21 — clears
   2e-12 with the "wide margin" the spec describes. Build the rule's birth-encounter-id
   extraction to require a namespace-scoped identifier (same pattern as
   `legal_id`/`insurance_subscriber_id`'s `f"{assigner}|{value}"` scoping) — this makes a
   shared facility-wide ID *structurally distinguishable* from a genuine per-encounter one
   *if* the source data tags them differently, but does not itself verify per-encounter
   uniqueness (a data-quality property of whatever feeds this field, outside this library's
   control). **`NEEDS HUMAN DECISION`** (carried over from session 6, still unresolved as of
   this session): is a genuinely per-encounter, namespace-bound birth identifier actually
   available anywhere in this system's real FHIR data? If not, rule `C2-40` is built but
   practically unreachable until upstream data provides one — note this plainly in Execution
   notes rather than treating the rule's mere existence as proof the capability works
   end-to-end.

### Out of scope

- Resolving rule 39's Street Line correlation discount with an actual statistical method —
  that's CMS's or the engineering lead's call (per session 6's original flagging), not
  something this session invents.
- Confirming real per-encounter birth-encounter ID availability in production FHIR data — a
  data/infrastructure question for whoever owns the upstream feeds, not resolvable from inside
  this repo.
- Any UI/API-level way for a caller to *submit* a guardian/mother linkage claim — this session
  builds the matching-engine side (Task 2) using whatever representation Task 1 lands on;
  wiring an actual production caller (e.g. `cms-hte-patient-matching-service`) to populate it
  is Phase 2 scope, not this repo's.
- Sessions 16, 18, 19's scope (see their own docs).

## Tasks

1. Add `relationship_linkage_clinical` / `relationship_linkage_self_reported` (0.01 / 0.05)
   and the identity-gate u-value(s) (1.0) and `birth_encounter_id` (1e-15) to `collision.py`'s
   `FIELD_U_PROBS`, per Scope Task 1's corrected figures above.
2. Implement the guardian/mother linked-identity + relationship-linkage extraction (Scope Task
   2) — new `FieldExtractor` logic, new `PatientFields` fields, new canonical field constants.
3. Build rule `C2-39` as a `HouseholdIndividualRule` (reusing `household_rules.py`'s existing
   types): household row = identity-gate (u=1.0) + Street Line; individual row = Relationship
   Linkage clinical + First Name + DOB. Verify the combined figure equals the spec's 6e-13.
   Add the correlation-caveat comment per Scope Task 3.
4. Build rule `C2-40` the same way: household row = identity-gate (u=1.0) alone; individual row
   = Relationship Linkage clinical + DOB + birth-encounter ID. Verify against 1e-21. Add the
   per-encounter-uniqueness caveat comment per Scope Task 4.
5. Wire both into `MatchingEngine` via the existing `household_individual_rules` parameter —
   no new dispatch path needed if Tasks 3/4 genuinely reuse `HouseholdIndividualRule`.

## Unit tests required

- `test_collision.py`: all new u-value entries (relationship linkage x2, identity gate(s),
  birth_encounter_id) present with correct values.
- New test file (e.g. `test_relationship_linkage_rules.py`): rules `C2-39`/`C2-40` each
  computing their stated `p_collision` figure (6e-13 / 1e-21) via `p_collision()`, not
  hardcoded; a case where the guardian/mother identity-gate field fails to resolve (zero or
  multiple candidates) short-circuits to no-match/escalate per the existing
  household/individual two-step convention; a case distinguishing a namespace-scoped
  per-encounter ID from an unscoped/shared-looking one for rule `C2-40` (even though this
  session can't verify real-world uniqueness, the *format* handling should be tested).
- A test confirming rules `C2-39`/`C2-40` don't collide with any existing Category 1 or
  Category 2 rule_id (extend session 16's `test_rule_ids_disjoint_from_category_2`-style
  guard, or add `C2-39`/`C2-40` to `household_rules.py`'s own `test_all_8_rules_present`-style
  set check, updated to 10 rules).
- A test confirming rules `C2-39`/`C2-40` do not affect any other rule's evaluation (no
  accidental cross-talk introduced into `MatchingEngine`'s shared candidate-resolution path).

## Validation (definition of "resolved")

- [x] `relationship_linkage_clinical`/`_self_reported`, the identity-gate u-value(s), and
      `birth_encounter_id` all exist in `collision.py` with correct values; self-reported
      variant confirmed unused by any rule (matches `household_rules.I_03`'s "defined but
      unused" precedent, not an oversight).
- [x] Rules `C2-39` and `C2-40` exist, each computing the spec's stated `p_collision` figure
      (6e-13 / 1e-21) via `p_collision()` (not hardcoded), and neither collides with any
      existing Category 1 or Category 2 rule_id.
- [x] Rule `C2-39`'s code comment and this doc's Execution notes both state the Street Line
      correlation caveat plainly — a future reader should not mistake the 6e-13 figure for a
      fully-resolved margin.
- [x] Rule `C2-40`'s code comment and Execution notes both state the per-encounter-ID
      availability caveat plainly.
- [x] `uv run pytest .` green, full suite, no regressions (499 passed, up from 470; 21
      pre-existing Docker-dependent tests deselected, unrelated to this session).
- [x] `uv run pre-commit run` clean on touched files.
- [x] **Correction to this checklist item, found during execution:** `evaluation/rule_eval.py`
      no longer exists in this repo - it moved to `cms-hte-patient-matching-test-set` per
      `index.md`'s 2026-08-18 addendum, before this doc was even authored (this doc's original
      text was already stale on this point). This repo's actual Tier-1-equivalent check today
      is `tests/test_onc_population_regression.py`/`test_onc_regression.py`, which run as part
      of the standard suite against `MatchingEngine()`'s defaults - and its defaults now
      include `C2-39`/`C2-40` (see matching_engine.py's `_ALL_CATEGORY_2_RULES`). Both passed
      with no floor/ceiling violations, confirming no regression to the other 38 rules. As
      anticipated, the ONC dataset has no real guardian/newborn-linkage cases, so this doesn't
      produce meaningful precision/recall for `C2-39`/`C2-40` specifically - expected and
      acceptable per the caveats already documented above, not a blocker.

## Open questions

- **`NEEDS HUMAN DECISION`** (carried over from session 6, still open): is a genuinely
  per-encounter, namespace-bound birth-encounter identifier available anywhere in this
  system's real data? Affects whether rule `C2-40` is reachable in practice, not whether it
  should be built (the project lead already decided: build it regardless).
- **Resolved during execution, no longer open**: the exact FHIR shape for guardian/mother
  linked-identity and the Relationship Linkage claim (Task 2) - see Execution notes for the
  chosen representation (identifier entries with repo-defined type codes; a repo-defined
  Patient extension) and why no standard FHIR element fit either.
- Whether rule `C2-39`'s Street Line correlation should eventually get a real discount factor
  is CMS's/the engineering lead's call, tracked as a future candidate session, not blocking
  this one (per the project lead's "implement now, best-effort" decision).

## Execution notes

Executed 2026-09-15 on branch `claude/session-17-v340-relationship-linkage-rules-39-40`, cut
from `main` (per the project lead's explicit go-ahead to proceed before session 16/PR #51 merges - see
this doc's original "don't start until session 16 is completed/" note, overridden by direct
instruction). `docs/sessions/pending/session_{17,18,19}.md` and the updated `index.md`/
`conventions.md` only existed on session 16's branch (never merged to `main`), so those files
were pulled across via `git checkout claude/session-16-... -- <paths>` rather than merging
session 16's code changes - a separate commit on this branch, not part of session 17's own
diff.

**The single most important finding this session:** re-verified the raw v3.4.0 §C.4 table
before writing any code, per conventions.md's own instruction to re-verify figures against the
live doc rather than trusting a transcription. This doc's original Scope section (Tasks 2-4)
assumed "guardian's independently-matched identity" would be a `namespace_id`-style near-zero
collision *field*, multiplied into rule 39's product alongside Street Line/Relationship
Linkage/First Name/DOB. The spec's own stated math - *"≈6e-13 (flat product: 0.02 × 0.0001 ×
0.01 × 0.00003)"* - has exactly 4 factors, with no room for a 5th near-zero term. Multiplying
by ~1e-15 as originally planned would have misreported the rule's collision risk by roughly 15
orders of magnitude in the direction of appearing *safer* than actually justified - precisely
the kind of error the statistical rigor gate exists to catch, caught here by re-deriving the
number by hand before implementing rather than after. Corrected: guardian/mother identity
match is a u=1.0 "no-op gate," not a probabilistic field - its own uniqueness was already
bounded by whichever separate rule matched the guardian/mother in the first place. This maps
directly onto the existing `HouseholdRow`/`IndividualRow`/`HouseholdIndividualRule` machinery
(household leg's `p_collision` = 1.0 × Street Line where applicable; individual leg carries the
real discriminating factors) - no new dataclass was needed. Verified by direct computation:
C2-39 = 3e-5 × 2e-8 = 6.0e-13 (exact match to spec); C2-40 = 1.0 × 1e-21 = 1.0e-21 (the
session's own initial estimate of 1e-19 was also an arithmetic slip - 0.01 × 0.0001 × 1e-15 is
1e-21, not 1e-19 - caught by the same direct-computation check before finalizing the doc).

**FHIR shape decisions (implementation-time, per this doc's own instruction - grepped
`fhir_client/`/`ial2_extraction/` first, found no existing convention for either an identity
cross-reference or a relationship claim):**
- Guardian identity, mother identity, and the birth-encounter ID: represented as `identifier`
  array entries, reusing `_extract_identifiers`'s existing namespace-scoping pattern
  (`f"{system}|{value}"`, same as `legal_id`/`insurance_subscriber_id`) rather than inventing a
  second extraction mechanism. Custom type codes `CMS-GRDN`/`CMS-MTHR`/`CMS-BEID` - no standard
  HL7 v2-0203 code exists for "a reference to a different person's already-matched identity"
  (unlike `MB`/`SN`, which are real codes session 6 could reuse), so these are repo-defined and
  documented as such in `field_extractor.py`, not silently passed off as standard.
- Relationship Linkage (type: child-of/newborn-of; source: clinical/self-reported): represented
  as a Patient `extension`, not an identifier - it describes a claim, not an identity. FHIR's
  `Patient.link.type` enum (replaced-by/replaces/refer/seealso) has no family-relationship
  semantics and `Patient.contact` isn't a `Reference` to another Patient resource, so neither
  standard element fits. Not a published/registered FHIR extension - a repo-internal
  convention, documented as such at its URL constant's definition.

**Real bug caught before it shipped, not by the test suite:** `patient_matching/api/
service.py`'s confidence-scoring lookup only searched `household_rules.CATEGORY_2_RULES` (the
original 8), not the new `RELATIONSHIP_LINKAGE_RULES`. A match resolved via `C2-39`/`C2-40`
would have silently fallen through to that function's final `return 0.0` - reporting *zero
confidence* for a real, correctly-resolved match. Caught by tracing every consumer of
`CATEGORY_2_RULES` before considering the session done (`matching_engine.py`'s default and
`service.py`'s two separate usages), not by any test failing - no existing test exercises
`PatientMatcherService`'s confidence scoring against a `C2-39`/`C2-40` match, since that would
require wiring the full IAL2/cache pipeline. Fixed by searching
`CATEGORY_2_RULES + RELATIONSHIP_LINKAGE_RULES` together in that lookup. Flagged here rather
than silently fixed, since it's exactly the class of bug an adversarial review would look for -
worth specifically re-checking in review.

**Avoided a circular import**: `relationship_linkage_rules.py` imports
`HouseholdRow`/`IndividualRow`/`HouseholdIndividualRule` from `household_rules.py` (one-way).
Rather than having `household_rules.py` import back from `relationship_linkage_rules.py` to
build a combined `CATEGORY_2_RULES` (which would cycle), the combination
(`_ALL_CATEGORY_2_RULES = CATEGORY_2_RULES + RELATIONSHIP_LINKAGE_RULES`) lives in
`matching_engine.py`, the one place that already needs both. `household_rules.py` itself is
untouched by this session - reduces conflict risk with session 16's still-unmerged renumbering
work, which also touches that file's sibling `table2_rules.py` but not `household_rules.py`.

Validation:
- `uv run pytest .`: 499 passed (up from 470), 0 regressions. New tests: 13 in
  `test_relationship_linkage_rules.py` (rule figures, ID-collision guard, end-to-end
  guardian/newborn matching via `MatchingEngine.match()`, cross-talk guard, default-inclusion
  guard) + 13 in `test_field_extractor.py`'s new `TestFieldExtractorCmsV340Fields` (extraction
  correctness for all 5 new fields, unscoped-identifier exclusion, malformed-extension
  handling) + 6 in `test_collision.py` (new u-value entries, identity-gate fuzzy-variant guard).
- Direct numeric verification (not just test-pass): `C2-39` = 6.0e-13, `C2-40` = 1.0e-21,
  both matching hand-derived figures from the spec's own stated math.
- `uv run pre-commit run` on all touched files: clean (ruff, ruff-format, mypy, bandit,
  detect-secrets, standard hooks).
- Statistical rigor gate: see the corrected Validation checklist item above -
  `tests/test_onc_population_regression.py`/`test_onc_regression.py` (this repo's actual
  current Tier-1-equivalent tooling, `evaluation/rule_eval.py` having moved to a sibling repo
  before this doc was authored) both pass with `C2-39`/`C2-40` now part of
  `MatchingEngine()`'s default rule set, confirming no regression to the other 38 rules.

Decision: PR opened from `claude/session-17-v340-relationship-linkage-rules-39-40` into
`main`, left **open** rather than merged - merging is the project lead's call, same as every prior
session in this repo. Doc moved to `in_review/` and `index.md` updated accordingly, in the
same PR.

## Post-review fixes (adversarial review pass, 2026-09-15)

An adversarial review of this PR (executed against a live worktree, reproductions run and
verified, not by inspection) found two real defects:

1. **The relationship `type` code was never constrained - both rules matched on ANY code.**
   `relationship_linkage_clinical` is a set-of-values field matched by ordinary
   Core-Principle-10 overlap semantics. Nothing checked that the specific claimed type was
   `"child-of"` for C2-39 or `"newborn-of"` for C2-40 - verified empirically that C2-39 fired
   on a `"newborn-of"` claim, C2-40 fired on a `"child-of"` claim, and both fired on an
   arbitrary/unrecognized code like `"spouse-of"`. **Fix:** added two type-narrowed derived
   fields to `PatientFields`
   (`relationship_linkage_child_of_clinical`/`relationship_linkage_newborn_of_clinical`,
   computed by filtering the existing raw `relationship_linkage_clinical` set down to the one
   specific type each rule requires) and pointed each rule's individual row at the
   type-specific field instead of the generic one. Since each narrowed field's value space is
   a strict subset of the un-narrowed one, its true collision probability is at most what's
   already published (0.01) - reused that figure directly in `collision.py` rather than
   inventing a new number. Also fixed, found in the same code path: `_extract_relationship_linkage`
   wrote through whatever `PatientFields.get_values()` happened to return for the raw field
   rather than assigning to the named attribute directly - fragile if `get_values()`'s
   read-only contract were ever tightened (e.g. to return a copy). Now assigns explicitly.

2. **Rule C2-40 has no field that discriminates between twins/siblings from the same
   delivery.** `NEWBORN-RELATIONSHIP`'s individual leg is relationship-type + DOB +
   birth-encounter-ID - no name field at all - and per this doc's own already-flagged
   caveat, a birth-encounter ID is realistically assigned per-delivery, not per-infant.
   Verified empirically: with only ONE twin registered in the backend, a query for the
   *other*, unregistered twin resolves as a confident, unique MATCH at confidence >0.99
   against the wrong sibling's record. **Not fixed** - this doc's own C2-40 description
   already carried a "NEEDS HUMAN DECISION, carried over from session 6" flag on exactly this
   uniqueness assumption, and closing it means either adding a discriminating field (changes
   the CMS-published P(collision) figure) or gating on FHIR's
   `multipleBirthBoolean`/`multipleBirthInteger` and failing closed when a multiple birth is
   known or unconfirmed (a product decision on how much of the rule's real-world utility to
   trade for that safety margin, since most source systems rarely populate that field).
   Documented and locked in with an explicit `test_KNOWN_LIMITATION_...` test (asserts today's
   actual, risky behavior, with instructions to update it once the limitation is actually
   closed) rather than left as an unverified prose caveat. When both twins ARE present as
   candidates, the rule does correctly escalate (also now covered by a dedicated test) - the
   risk is specifically the single-candidate case.

A related but smaller gap the same review raised, also not fixed: the household-leg identity
gates (`GUARDIAN_IDENTITY_ROW`/`MOTHER_IDENTITY_ROW`, priced at u=1.0 on the stated reasoning
that "the guardian/mother's own uniqueness was already bounded by whichever rule matched
them") never actually verify that the referenced guardian/mother identity resolves to exactly
one backend record - the u=1.0 pricing's entire justification is currently unenforced by code.
Flagging for a future session rather than folding an identity-resolution redesign into this
fix pass: the fix would mean resolving the guardian/mother identity to a specific candidate
set size (0, 1, or 2+) before the individual leg runs at all, which is a genuine structural
change to how this rule category retrieves candidates, not a local correction.

Validation after fixes: `uv run pytest .` - 501 passed (up from 499), 0 regressions. 7 new
tests in `test_relationship_linkage_rules.py` (twin escalation when both present, the
documented known-limitation case, 4 relationship-type-enforcement cases) + 2 in
`test_service.py` (`_compute_confidence` for C2-39/C2-40 - this PR's own headline
`service.py` fix had no direct regression test until now). 3 of the 4 type-enforcement tests
confirmed via `git stash` to fail against the pre-fix code. `uv run pre-commit run` clean; the
one remaining mypy failure (`mongo_atlas_cache.py:264`) confirmed via `git stash` to pre-exist
on this branch independent of this fix.
