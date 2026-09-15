# Session 17 — CMS v3.4.0: Relationship Linkage field + Rules 39/40

**Status:** pending
**Thread:** Line B: CMS v3.4.0 migration
**Estimated size:** L — a genuinely new architectural concept (matching against an
*already-resolved, external* identity rather than fields on the same record pair), not an
extension of the existing flat or household/individual patterns. Both target rules carry
caveats the spec flags as unresolved in its own text — this session builds them anyway
(Imran, 2026-09-15: "implement now, best-effort"), with those caveats documented as known
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

### In scope

**1. Relationship Linkage field, Table 3.** File: `patient_matching/matching/collision.py`.
   Add two u-value entries (no existing pattern for "two u-values, no fuzzy variant, for the
   same logical field" — `FIELD_U_PROBS`'s shape may need a small extension; implementer's
   call whether that's two separate field-name keys, e.g. `relationship_linkage_clinical` /
   `relationship_linkage_self_reported`, or one field with a source-quality parameter. Two
   separate keys is simplest given nothing else in this repo has a "quality-conditioned"
   u-value):
   - `relationship_linkage_clinical` = 0.01 (source: clinical record, e.g. birth record,
     insurance dependent designation)
   - `relationship_linkage_self_reported` = 0.05 (source: patient/guardian self-report or
     intake form)
   Both rules 39/40 below use the clinical variant only — the self-reported variant exists in
   the spec's Table 3 but neither rule uses it; don't build a rule around it, per the same
   "define but leave unused" precedent as `household_rules.I_03`.

**2. A guardian/mother linked-identity representation.** However Task 1's dependency
   resolution comes out, this session needs some way to say "this query's guardian/mother has
   already been independently matched to Patient X" as an input the matching engine can
   consume — most naturally as a new, distinct field (analogous to `namespace_id`'s
   near-zero collision, since an already-verified Patient reference is about as unique an
   identifier as this system has). Implementer's call on the exact type/field-extraction
   shape; document the choice in Execution notes the way session 6 documented its FHIR
   identifier-type-code choice.

**3. Rule 39 (guardian-verified minor).** Fields: guardian's independently-matched identity +
   Street Line + Relationship Linkage (clinical, child-of) + First Name + DOB. Combined
   figure ≈6e-13 per the spec's own (flagged) math. **Known limitation, ship anyway, document
   in code and PR description — do not silently treat as resolved:** the spec's own text says
   *"Street Line is correlated with the relationship term (same household address), so this
   overstates the margin; needs a dependency discount or drop Street Line before adoption."*
   Build the rule exactly as specified (flat multiplication, no ad hoc discount invented by
   this session — inventing one would be a bigger methodology deviation than the spec's own
   flagged gap), and add a code comment plus an Execution-notes entry stating plainly that this
   rule's true collision margin is narrower than 6e-13 implies until CMS or an internal
   decision supplies a discount factor.

**4. Rule 40 (newborn via maternal linkage).** Fields: mother's independently-matched identity
   + Relationship Linkage (clinical, newborn-of) + DOB + a per-encounter, namespace-bound
   birth-encounter ID. Per the spec: clears with wide margin if the encounter ID is a true
   per-encounter unique identifier; **does not clear** with only a shared facility ID. Build
   the rule's logic to require a namespace-scoped encounter identifier (same pattern as
   `legal_id`/`insurance_subscriber_id`'s `f"{assigner}|{value}"` scoping) — this at least
   makes a shared facility-wide ID structurally distinguishable from a genuine per-encounter
   one *if* the source data tags them differently, but does not itself verify per-encounter
   uniqueness (that's a data-quality property of whatever feeds this field, outside this
   library's control). **`NEEDS HUMAN DECISION`** (carried over from session 6, still
   unresolved as of this session): is a genuinely per-encounter, namespace-bound birth
   identifier actually available anywhere in this system's real FHIR data? If not, rule 40 is
   built but practically unreachable until upstream data provides one — note this plainly in
   Execution notes rather than treating the rule's mere existence as proof the capability
   works end-to-end.

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

1. Add `relationship_linkage_clinical` / `relationship_linkage_self_reported` to
   `collision.py`'s `FIELD_U_PROBS` (or equivalent), values 0.01 / 0.05, no fuzzy variant.
2. Resolve and implement the guardian/mother linked-identity representation (Task 1/2 above) —
   `FieldExtractor` extraction logic, a new canonical field constant, and whatever dataclass
   shape best represents "an already-resolved external identity + a relationship claim" as one
   leg of a two-leg rule (a new type, or an extension of `HouseholdIndividualRule` if the
   existing shape genuinely fits — implementer's call, but note the semantic difference in
   whichever docstring lands: a household row groups by *shared* fields, this groups by an
   *external, already-verified* reference).
3. Build rule 39: guardian-identity leg × (Street Line + Relationship Linkage(clinical) +
   First Name + DOB) leg, computed via `p_collision()`, verified against the spec's ≈6e-13
   figure. Add the correlation-caveat comment per Scope Task 3 above.
4. Build rule 40: mother-identity leg × (Relationship Linkage(clinical) + DOB + birth-encounter
   ID) leg, same verification approach. Add the per-encounter-uniqueness caveat comment per
   Scope Task 4 above.
5. Wire both rules into `MatchingEngine` following whichever existing dispatch pattern (flat
   vs. two-step) the Task 2 design ends up closest to.

## Unit tests required

- `test_collision.py`: both new u-value entries present with correct values.
- New test file (e.g. `test_relationship_linkage_rules.py`): rule 39 and rule 40 each
  computing their stated `p_collision` figure; a case where the guardian/mother identity leg
  fails to resolve (zero or multiple candidates) short-circuits to no-match/escalate per the
  existing candidate-count convention; a case distinguishing a namespace-scoped
  per-encounter ID from an unscoped/shared-looking one for rule 40 (даже though this session
  can't verify real-world uniqueness, the *format* handling should be tested).
- A test confirming rules 39/40 do not affect any other rule's evaluation (no accidental
  cross-talk introduced into `MatchingEngine`'s shared candidate-resolution path).

## Validation (definition of "resolved")

- [ ] `relationship_linkage_clinical`/`_self_reported` exist in `collision.py` with correct
      values; self-reported variant confirmed unused by any rule (matches
      `household_rules.I_03`'s "defined but unused" precedent, not an oversight).
- [ ] Rules 39 and 40 exist, each computing the spec's stated `p_collision` figure via
      `p_collision()` (not hardcoded).
- [ ] Rule 39's code comment and this doc's Execution notes both state the Street Line
      correlation caveat plainly — a future reader should not mistake the 6e-13 figure for a
      fully-resolved margin.
- [ ] Rule 40's code comment and Execution notes both state the per-encounter-ID
      availability caveat plainly.
- [ ] `uv run pytest .` green, full suite, no regressions.
- [ ] `uv run pre-commit run` clean on touched files.
- [ ] Statistical rigor gate: these are genuinely new matching rules (not a rename), so per
      conventions.md's Tier 1 requirement, run `evaluation/rule_eval.py`'s ONC self-match
      `ComparisonReport` (baseline vs. candidate with rules 39/40 enabled) before this session
      reaches `completed/` — note in Execution notes that the ONC dataset likely has zero or
      near-zero real guardian/newborn-linkage test cases, so this Tier 1 report mainly confirms
      "no regression to the other 38 rules," not meaningful precision/recall for 39/40
      specifically; that gap is expected and acceptable per the caveats already documented
      above, not a blocker.

## Open questions

- **`NEEDS HUMAN DECISION`** (carried over from session 6, still open): is a genuinely
  per-encounter, namespace-bound birth-encounter identifier available anywhere in this
  system's real data? Affects whether rule 40 is reachable in practice, not whether it should
  be built (Imran already decided: build it regardless).
- The exact FHIR shape for guardian/mother linked-identity (Task 2) is left for implementation
  time per the "Upstream data/system dependencies" section above — a legitimate implementation
  detail, not a `NEEDS HUMAN DECISION`.
- Whether rule 39's Street Line correlation should eventually get a real discount factor is
  CMS's/the engineering lead's call, tracked as a future candidate session, not blocking this
  one (per Imran's "implement now, best-effort" decision).

## Execution notes

_(filled in at close)_
