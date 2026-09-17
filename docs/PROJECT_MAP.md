# Project Map — Orientation for Anyone Picking This Up

Read this before `docs/sessions/conventions.md` if you're new to the project entirely; read
`conventions.md` before actually executing a session. This doc answers "what is this and why,"
not "how do I run a session" (that's `conventions.md`'s job).

## 1. What this repo is for

The platform's **current production patient-matching** (`helix.personmatching` +
`person-matching-service`) is a weighted-score algorithm: 26 rules,
each scores 0-1, highest score wins, match if ≥0.955. It works today — match errors with a payer client
are down ~80% and the remainder is bad upstream data, not the algorithm.

CMS has a **draft proposal (v3.3)** requiring a different approach: instead of scoring fields,
check whether an incoming record's fields match one of ~38 CMS-pre-approved "combinations"
(Table 2). If it does, and it resolves to exactly one candidate in your system, you are
*required* to return that record. Each combination is approved because the odds of two
*different* people sharing all those field values by coincidence is ≤ 1-in-500-billion (computed
from per-field "collision probabilities," Table 3).

**This repo is a from-scratch build of that CMS v3.3 engine**, done in isolation — no production
traffic, no deploy target — so it can be validated against labeled data before touching
production. It has **no code path into `helix.personmatching`/`person-matching-service` today**.
Connecting it to production ("Phase 2") is a separate, currently unscoped effort in those other
repos.

**2026-09-04 update:** Phase 2 is no longer *entirely* unscoped. A new sibling repo,
`cms-hte-patient-matching-service`, is being built to wrap this package's
`PatientMatcherService`/`MatchingEngine` as a production HTTP microservice. The project lead decided this
repo's charter now extends to the production-backend infrastructure work that sibling service's
design surfaces (see `docs/sessions/pending/session_12.md`: a `MongoAtlasCache` `CacheBackend`,
motivated by that service's scaling/shared-state needs rather than by the CMS spec itself).
This repo's own matching-algorithm work (Table 2/3, ONC validation) is unaffected — this is an
addition to scope, not a redirection of it.

## 2. Data — what exists and where

| Dataset | Where | Used for |
|---|---|---|
| ONC 2017 Patient Matching Challenge (public, labeled, 1,000,000 records) | `evaluation/fixtures/onc/*.csv` | The only dataset with known right answers — real precision/recall/FPR. **Tier 1.** |
| CMS v3.3 spec + 6 addenda | `docs/CMS_Patient_Matching_Proposal_v3.3.0.txt`, `docs/Proposal v3.3.1-3.3.6*.txt` | The rulebook: Table 2 (approved combinations) and Table 3 (collision probabilities). A live-drafting Google Doc — re-verify against the live doc before any session that changes rules. |
| Real FHIR data, prod Databricks: `bronze.fhir_lake.patient_4_0_0` joined to `silver.fhir_lite.person_patient` | Queried by `notebooks/fhir_match_data_source.py` | Real-population sanity check on Table 3's assumed collision rates. **Tier 2.** |
| Synthetic labeled pairs (mutations + mined hard negatives, in-memory only, not persisted) | `evaluation/mutations.py`, `evaluation/hard_negatives.py`, `evaluation/labeled_pairs.py` | Fills the gap where there's no large hand-labeled real dataset. |
| Legacy engine (`helix.personmatching`, separate repo) | Not yet wired in | Comparison baseline for a go/no-go cutover decision. **Tier 3.** |

## 3. Session map — what each one actually does

| # | Status | What it does |
|---|---|---|
| 1 | done | Adds `timestamp`/`version` to every match decision's audit record. Logging only, no behavior change. |
| 2 | done | 2-candidate results become `ESCALATE` (ask for more info); 3+-candidate results stay `AMBIGUOUS` (stricter threshold). CMS's tiered-uniqueness requirement. |
| 3 | done | Built the eval harness: loaded the 1M-record ONC dataset, added `MatchingEngine.evaluate_pair()`, produced the first baseline report — **95.08% recall, 0.11% FPR** on ONC self-matches. Every later rule change is diffed against this. |
| 5 | done | `patient_matching/matching/collision.py`: 16-field collision-probability table (Table 3) + a function that multiplies the relevant fields together to score a combination. Replaced 26 hand-typed probability constants with computed ones. |
| 9 | done | Synthetic test-data generator: true-matches = typo'd/mutated real ONC records; true-non-matches = two distinct real ONC people who happen to collide on several fields (mined, not invented). |
| 4 | code merged (PR #22, 2026-08-14); doc not yet closed | Live query against real prod FHIR data → real per-field collision rates + agreement-rate vs. the current algorithm. **Tier 2, now actually run successfully** (2026-08-18) — the session doc's Execution notes and DoD checkbox need updating to reflect it, and the doc needs to move `in_review/` → `completed/`. |
| 6 | not started | Expands 26 rules → 38: adds ZIP/insurance-ID rules (27-33), adds ±1-day DOB tolerance, builds a new **two-step "Household then Individual"** architecture for 8 rules where a field (phone, SSN-last-4, subscriber ID) is often shared by a whole family and can only prove "same household," not "same person." Also amends 4 already-merged rules (13,14,15,16) into that architecture. Largest remaining session. |
| 8 | not started | Runs both the current production algorithm and this new engine against the same batch, buckets every disagreement into 6 categories (nickname, typo, DOB conflict, etc.), produces the evidence report for a cutover decision. |

## 4. Blockers and open decisions (as of 2026-08-18)

- **Session 4's doc is stale**: says "not yet run" but the live run succeeded. Needs its
  Execution notes updated and the doc moved to `completed/`.
- **Session 6 is NOT actually blocked**, despite `index.md`'s current text claiming it's
  "blocked on fetching the live CMS v3.3 spec content" — all 6 addenda are already committed
  under `docs/`. Its only upstream dependency (session 5) is done. **Ready to start.** Its two
  explicitly-deferred sub-parts (Rules 39/40, and v3.3.6's institutional-address lookup) don't
  block the rest of it.
- **Session 8 has 4 real blockers**: (a) session 4 needs to actually reach `completed/`; (b) a
  decision on whether this repo may take an eval-only dependency on `helix-personmatching`; (c)
  naming who adjudicates a 25-50 pair hand-review sample; (d) whether the session-9 synthetic
  labeled-set approach replaces or runs alongside the original legacy-vs-new comparison design.
- **Phase 2 (production deployment) has zero scoping** — no session docs, no owner, in different
  repos (`helix.personmatching`, `person-matching-service`) with no scaffolding for this engine.

## 5. The plan, in order

1. Close session 4: update Execution notes with the live-run output, check its last DoD box,
   move the doc to `completed/`, fix `index.md`'s stale "blocked" framing on session 6.
2. Run session 6 (see `docs/sessions/pending/session_6.md` for the full task list). Done looks
   like: 38 rules total in `table2_rules.py`, 3 new extractable fields, a `dob_fuzzy_match()`
   comparator, a `HouseholdIndividualRule` type with 14 household-rows + 3 individual-rows,
   rules 13-16 amended in place, full test suite green, session_6.md's checklist fully checked.
3. Get the project lead's and engineering lead's decisions on the open items in parallel, not serialized after session 6.
4. Run session 8 once session 4 is `completed/` and the human decisions land. Done looks like:
   `evaluation/legacy_comparison.py` producing a disagreement-bucketed comparison report.
5. Only after that: scope Phase 2 (production deployment) — currently nothing exists for this.
