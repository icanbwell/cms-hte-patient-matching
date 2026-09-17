# Session 7 — Parent/Child Delegated Access (Proposed — Not Yet a Real Backlog Item)

**Status:** pending — **not ready to execute**; see "Why this session is unusual" below.
**Confirmed 2026-08-07 by the project lead: this is delegated access, not patient matching** — see
that dated update below. Title updated from "Identity Linking" to "Delegated Access" to match
his framing.
**Thread:** none yet. Proposed new thread ("Delegated access / relationship-based
authorization"), distinct from both existing threads (`Line B: CMS v3.3 migration`,
`Evaluation & Statistical Rigor`) — and, as of 2026-08-07, confirmed to need a home outside
this repo's Thread taxonomy entirely, since it isn't matching work. **`NEEDS HUMAN DECISION —
Sean`**: creating this thread at all is itself a decision this doc can't make (see Open
questions).
**Estimated size:** Unknown — can't be sized until the scope-anchor and consent-authority
questions below are resolved; a same-person-only linking layer (see Outcome purpose) is
plausibly S/M, but the actual hard part (identity-proofing/consent policy) isn't an engineering
estimate at all.

> Read `../conventions.md` first.

## Why this session is unusual

Every other session in this backlog traces to a specific line in `docs/handoff/README.md`
(Line A/Line B) or a specific CMS v3.3 spec section — `conventions.md`'s "Scope anchor" rule.
This one can't, yet: parent/child identity linking is **in neither document**. CMS v3.3's
Table 2 is exclusively a same-person uniqueness framework (per `docs/handoff/README.md` §2.3);
it has no "authorized relationship" combination. This doc exists to capture the design
discussion (Jira `SD-1416`; Slack DM with the project lead and Alvin Henrick, 2026-07-17) before
it's lost, **not** to claim this is scoped, sized, or ready for a feature branch. Do not start
this session via the normal "start the next session" protocol without first resolving every
`NEEDS HUMAN DECISION` below — several of them are more fundamental than a typical session's
(e.g., whether this even belongs in this repo).

## 2026-08-04 update — a candidate matching-side mechanism now exists (not yet adoption-ready)

A Google Drive folder (`13cRXYRcilcxrrg5yceKDZifub8I_dv3l`) of six companion proposals to the
base CMS v3.3.0 spec, all authored by the project lead (2026-07-15 through 2026-07-31 — i.e.,
mostly predating the 2026-07-17 DM this doc was originally based on), turned up while
investigating this ticket. Per `conventions.md`'s "Reference documents" section, these are live
Google Docs under active review — not copied into this repo; fetch fresh if this work proceeds.

**Proposal v3.3.3 ("Relationship-Based Matching for Minors and Newborns")**, authored
2026-07-15 — two days *before* the project lead told Sean in the DM "it's not a patient matching problem,
it is a linking minor to adult problem" and pointed at the external Cambia doc — proposes a new
Table 2 **Rule 39: guardian-verified minor match**. It lets a minor be matched using a
guardian's already-verified identity plus relationship data, without needing the minor's own
phone/email/SSN or even a shared last name — squarely the scenario where a child has thin
independent data and Citizen sends their demographics through a parent's account context.

**This only solves half the problem, and isn't ready even for that half:**
- Rule 39 answers "can we identify/match this child as a person," using the guardian
  relationship as a scoring input. It says nothing about whether the parent's *account* should
  then be granted access to that now-matched child's records — that's a separate
  access-authorization question, identical in kind to the one Aaron Madsen raises (as a
  reviewer on *both* this proposal and the external Cambia doc) about conflating
  identity-matching with proof-of-authority-to-act-on-behalf-of. **That question remains fully
  open** — Rule 39 doesn't touch it, and neither does anything else found so far.
- Rule 39's own math is flagged by the proposal itself as not yet sound: its stated P(collision)
  (≈6e-13) uses Street Line and the guardian-relationship term as if independent, but both are
  anchored to the same household address — a real correlation the base spec's own §IV.D
  Data Independence rule would flag. The proposal recommends dropping Street Line or applying
  an explicit dependency discount before this could be proposed for adoption; neither has
  happened yet. Its "Relationship Linkage" u-values (0.01 clinical / 0.05 self-reported) are
  also explicitly placeholder floors, not validated Table 3 figures.
- It's the project lead's own proposal, still under open review (a comment thread as of 2026-07-31).
  It has not been adopted into any spec version this repo implements.

**Effect on this session's scope:** if Rule 39 stabilizes and is adopted, the *matching* half
of this problem gets a real home — it becomes CMS v3.3 Table 2 work, likely landing alongside
`session_6`'s rule expansion (see that session's own 2026-08-04 update, which has an
overlapping open question about whether the companion proposals are in scope for that
session). The *authorization* half stays exactly where it was — no scope anchor, no owner,
needs a policy decision — see Open questions below, updated accordingly.

**⚠️ SUPERSEDED on this specific point — see the 2026-08-07 update immediately below.** The project lead
rejected this framing outright rather than qualifying it: Rule 39 doesn't fold into anything
here because it was never applicable to `SD-1416` in the first place.

## 2026-08-07 update — the project lead confirmed: this is delegated access, not patient matching; Rule 39 does not apply

Asked the project lead directly (same Slack thread) whether Rule 39 — once its math is fixed — is the
answer to `SD-1416`. His answer: **"No. Parent-guardian relationships are not patient matching.
They are delegated access."** This is not "Rule 39 needs more work" — it's a category
rejection. Even a fully-adopted, fully-sound Rule 39 would not address what Citizen is actually
asking for, because identifying/matching the child as a person (what Rule 39 does) was never
the actual blocker. The 2026-08-04 update above is superseded on this point: there is no
"matching half" of this problem to fold into `session_6` or anywhere else in this repo.

On the consent-authority question, the project lead also confirmed there's no existing answer anywhere,
and added a fact this doc didn't have before — it's **jurisdiction-dependent**: *"This is legal
question and different in each state."* *"Identity is different than control."* *"The Portable
identity spec above is just allowing a minor to be identity verified. But whether a parent can
access their record is based on laws or explicit consent."* This independently confirms what
the Cambia doc's own reviewers argued (identity-proofing ≠ authorization) — and narrows it
further: there may be no single national answer to build toward, only a per-state one.

**Net effect:** this session is now confirmed to be **entirely a delegated-access /
consent-and-legal-compliance problem, with zero patient-matching content** — not just
provisionally out of scope per "Why this session is unusual" above, but confirmed by the
domain lead to have no home in `patient-matching`, `helix.personmatching`, or
`helix.personmatching-service`. Whatever solves this is an access-control/consent capability,
almost certainly requiring per-state legal input, not an algorithm or matching-rule decision.

## Outcome purpose

**Gap being addressed:** Jira `SD-1416` — a parent's Citizen account can connect to their
child's health records, but b.well's matching assumes the logged-in person *is* the patient, so
the connection fails to match. Sean confirmed to Sarah Jones (Slack, 2026-07-17): "we don't
currently support that. It's planned for the CMS algo implementation, but not implemented" —
but per the technical discussion below, that framing turned out to be imprecise: **this is not
actually a CMS Table 2 / matching-rule gap**, so "implement it as part of the CMS algo" is the
wrong home for it. See "Why this session is unusual" for the scope-anchor consequence of that.

**Why matching (not linking) is the wrong lever:** this repo's own design already treats
parent/child confusion as the false-positive pattern to *avoid*, not enable —
`notebooks/wellsense_member_matching_analysis.py` (lines ~542, ~587) documents that the DOB
near-miss tolerance deliberately stops short of crediting a large single-digit-year typo
specifically "to avoid parent/child false links." Loosening name/DOB agreement to bridge
parent↔child would cut directly against that, and against the CMS methodology's core
false-positive constraint (`docs/handoff/README.md` §2.3: "Precision... a false positive is a
wrong-patient record release — the critical error").

**The actual technical shape (per the project lead, Slack DM, 2026-07-17): "it's not a patient
matching problem. It is a linking minor to adult problem."** Alvin Henrick's proposed design in
the same thread: resolve each side to its own canonical person via the *existing*,
unmodified `$match` (same-person-only, no rule changes) — parent's record matches the parent's
canonical person, child's record matches the child's canonical person — then draw a **new
link** between the two already-resolved canonical person IDs, sourced from `RelatedPerson`
records derived from payer eligibility/enrollment data (subscriber → dependent relationship),
which b.well already ingests for clients like WellSense.

**The unresolved hard part (the project lead, same thread):** *"Drawing the link between parent and child
is the hard part... someone has to look at a birth certificate or other proof of identity."*
And on Alvin's specific proposed evidence source: *"the subscriber id can define a household
relationship although not guaranteed to parent-child."* This is a policy/compliance question
(what counts as sufficient proof of guardianship before we grant one account access to another
person's clinical records?), not an engineering one — see Open questions.

## Upstream sessions (must be completed first)

None from this repo's existing sessions. This is architecturally independent of the CMS v3.3
Table 2/3 rule work (sessions 5/6) — per Alvin's design, matching itself is not modified.

## Downstream sessions (unblocked by this one)

None yet identified — this session has no code dependents in this backlog today.

## Upstream data/system dependencies

- `RelatedPerson` FHIR resources derived from payer eligibility/enrollment feeds (subscriber →
  dependent). Existence and location: **not confirmed** — Alvin referenced this as a plausible
  source, not a verified one. `NEEDS HUMAN DECISION — Sean/the project lead`: confirm whether this data
  exists in a queryable form today (which catalog/table, per client), and for which clients
  (WellSense only, or others).
- Whatever system of record would hold "authorized relationship" grants once proven (see next
  section) — does not exist yet in any repo this backlog touches.
- If the matching half proceeds via Rule 39 (see the 2026-08-04 update above): clinical
  "Relationship Linkage" data (FHIR `RelatedPerson`/`Patient.link`), scoped as "child-of an
  independently Table-2-matched guardian." Same not-yet-confirmed status as the bullet above —
  these may turn out to be the same underlying data source, or may not; not yet checked.

## Downstream data/system dependencies

**`NEEDS HUMAN DECISION — Sean`**: which service should own this capability at all. Candidates,
none confirmed:
- `patient-matching` (this repo) — **ruled out as of 2026-08-07**: the project lead confirmed this is
  delegated access, not patient matching, categorically, not just "unlikely to be the long-term
  home."
- `helix.personmatching-service` — **not ruled out**, corrected 2026-08-07: the project lead's rejection
  was of the matching *algorithm* as the mechanism, not of this *service* as a possible
  enforcement point. This is the actual production API surface a connection attempt hits today
  (per `docs/handoff/README.md` §2.1) — an access check plausibly needs to be enforced right
  there even though the policy logic behind it (what counts as sufficient authority) is new and
  not itself a matching concern. **Caveat:** per `docs/handoff/README.md`'s Line B framing,
  `helix.personmatching`/`helix.personmatching-service` are themselves slated to be replaced by
  whatever the CMS v3.3 migration produces — so "integration point" here means *today's*
  production surface, not necessarily the long-term home. Don't build a permanent bolt-on to
  the legacy service; build toward whatever replaces it.
- A new or existing identity/consent service (unnamed at authoring time) — most plausible owner
  of the *policy* logic itself: guardianship/authorization proofing needs its own auditable
  record, separate from matching, and per the project lead likely needs to encode per-state legal
  variation, which no repo in this backlog is built to hold. Likely paired with
  `helix.personmatching-service` as the enforcement point above, not a replacement for it.
This doc does not resolve this. It stays here as a placeholder until Sean/the project lead (and now,
per the consent-authority question above, Legal/Compliance) pick a home.

## Scope

### In scope (once the Open questions below are resolved — not yet)
- Confirming `RelatedPerson`/eligibility data actually exists and is reachable, for at least one
  client (likely WellSense, since it's the existing eligibility-feed pattern in
  `docs/handoff/README.md` §2.2).
- A design (not necessarily in this repo — see "Downstream data/system dependencies") for: (a)
  resolving parent and child each to their own canonical person via unmodified `$match`, (b)
  recording a link between the two canonical IDs, gated on whatever evidence-of-authority
  standard gets decided, (c) an audit trail for every such link (who/what authorized it, what
  evidence was used) — mirroring the CMS spec's own audit philosophy (`docs/handoff/README.md`
  §2.3 step 10) even though this isn't CMS-spec work.

### Out of scope
- Any change to matching *rules*, thresholds, or Table 2/3 values. This session's entire premise
  is that matching stays same-person-only and unmodified.
- Treating a payer subscriber/household relationship as sufficient proof of legal guardianship
  by default — the project lead explicitly flagged this as unreliable; any use of it needs an explicit,
  recorded risk acceptance from whoever owns that policy call.
- Building this in `patient-matching` if Sean/the project lead decide it belongs in a different repo (see
  "Downstream data/system dependencies") — this doc's design content is reusable regardless of
  where it's implemented, but the actual session execution should happen in whichever repo is
  chosen, following that repo's own conventions, not this one's.

## Tasks

**Not written yet.** Per `conventions.md`'s open-questions rule, tasks aren't authored until
the questions blocking them are resolved — writing implementation steps against an unresolved
consent-authority policy and an unconfirmed data source would be guessing, not planning. Once
the Open questions below are answered, come back and write Tasks 1..N the normal way (starting
with whichever repo is chosen, if not this one).

## Unit tests required

Not written yet — same reason as Tasks.

## Validation (definition of "resolved")

- [ ] Every `NEEDS HUMAN DECISION` below is answered and recorded in *Execution notes*.
- [ ] A Thread and scope anchor exist for this work (either a new handoff-doc line item, or an
      explicit decision that this doesn't need one because it's not part of the CMS
      handoff/backlog at all).
- [ ] The home repo/service is decided.
- [ ] The evidence-of-authority standard for parent/child (or any relationship) linking is
      decided and owned by someone accountable for that policy, not defaulted-to silently.
- [ ] Only once all of the above hold: this doc gets rewritten with real Tasks/Unit
      tests/Validation criteria, in whichever repo was chosen, following that repo's
      conventions.

## Open questions

- **ANSWERED 2026-08-07 by the project lead:** Does the project lead see Proposal v3.3.3's Rule 39 as the
  answer to `SD-1416`'s matching-side gap? **No** — "Parent-guardian relationships are not
  patient matching. They are delegated access." There is no matching-side gap to fix here;
  Rule 39 is not applicable to this problem regardless of whether its math gets fixed. See the
  2026-08-07 update above.
- **ANSWERED 2026-08-07 (by implication of the above), previously `NEEDS HUMAN DECISION —
  Sean/the project lead`**: Does this get a Thread and scope anchor in `patient-matching` at all? **No** —
  confirmed out of scope for this repo, and for `helix.personmatching`/
  `helix.personmatching-service` too, per the project lead's category rejection above. Whatever tracks this
  going forward needs a different home entirely (see the "which repo/service" item below, now
  the operative open question).
- **`NEEDS HUMAN DECISION — Sean/the project lead/Legal-Compliance`** (sharpened 2026-08-07): what counts
  as sufficient proof that an account holder is authorized to access another person's (e.g., a
  minor's) clinical records? The project lead confirmed directly: no existing answer, anywhere — "this is
  legal question and different in each state," and "whether a parent can access their record is
  based on laws or explicit consent." This is now known to be **jurisdiction-dependent**, not
  just undefined — the eventual answer may be a per-state policy matrix rather than one national
  rule. Payer-eligibility subscriber/dependent data alone is explicitly *not* sufficient (the project lead,
  2026-07-17). No recommended default — this needs Legal/Compliance ownership, not an
  engineering guess.
- **`NEEDS HUMAN DECISION — Sean`**: which repo/service/team owns this if it proceeds (see
  "Downstream data/system dependencies") — now sharpened to: almost certainly *not* a matching
  repo at all, per the project lead's 2026-08-07 answer. More likely an access-control/consent capability
  (identity/consent service, or a net-new one) paired with a Legal/Compliance-owned policy
  process, not an engineering algorithm decision.
- **Not a human-decision question, just unresolved administrivia**: whether the business
  urgency implied by Kristen Valdes's 2026-07-17 message ("we need to quickly support
  parent/child matches... this was a primary use case in the sales process") still holds as of
  2026-08-04 — Matt Sables's update the same day de-escalated Citizen's reported 52.3%
  match-failure number as a client-side reporting misread, not an active production problem,
  though the underlying capability gap (this session) is still real and still unaddressed. Sean
  should factor this into how urgently this gets prioritized against Line B's mid-August target
  (`docs/handoff/README.md`).

## Execution notes

_(empty at authoring time — 2026-08-04; this session is not startable yet, see "Why this
session is unusual")_
