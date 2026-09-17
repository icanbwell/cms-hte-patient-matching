# Project Map — Orientation for Anyone Picking This Up

Read this before `docs/sessions/conventions.md` if you're new to the project entirely; read
`conventions.md` before actually executing a session. This doc answers "what is this and why,"
not "how do I run a session" (that's `conventions.md`'s job).

## 1. What this repo is for

The platform's **current production patient-matching** (`helix.personmatching` +
`person-matching-service`) is a weighted-score algorithm: 26 rules,
each scores 0-1, highest score wins, match if ≥0.955. It works today — match errors with a payer client
are down ~80% and the remainder is bad upstream data, not the algorithm.

CMS has a **draft proposal (v3.4.0, superseding v3.3 as of 2026-09-15)** requiring a different
approach: instead of scoring fields, check whether an incoming record's fields match one of
~40 CMS-pre-approved "combinations" (Table 2). If it does, and it resolves to exactly one
candidate in your system, you are *required* to return that record. Each combination is
approved because the odds of two *different* people sharing all those field values by
coincidence is ≤ 1-in-500-billion (computed from per-field "collision probabilities," Table 3).

**This repo is a from-scratch build of that CMS engine**, done in isolation — no production
traffic, no deploy target — so it can be validated against labeled data before touching
production. It has **no code path into `helix.personmatching`/`person-matching-service` today**.
Connecting it to production ("Phase 2") is a separate, currently unscoped effort in those other
repos.

**2026-09-04 update:** Phase 2 is no longer *entirely* unscoped. A new sibling repo,
`cms-hte-patient-matching-service`, is being built to wrap this package's
`PatientMatcherService`/`MatchingEngine` as a production HTTP microservice. Imran decided this
repo's charter now extends to the production-backend infrastructure work that sibling service's
design surfaces (see `docs/sessions/pending/session_12.md`: a `MongoAtlasCache` `CacheBackend`,
motivated by that service's scaling/shared-state needs rather than by the CMS spec itself).
This repo's own matching-algorithm work (Table 2/3, ONC validation) is unaffected — this is an
addition to scope, not a redirection of it.

## 2. Data — what exists and where

| Dataset | Where | Used for |
|---|---|---|
| ONC 2017 Patient Matching Challenge (public, labeled, 1,000,000 records) | `evaluation/fixtures/onc/*.csv` | The only dataset with known right answers — real precision/recall/FPR. **Tier 1.** |
| CMS v3.4.0 spec ("Final Consolidated Draft", supersedes v3.3) | Live Google Doc only, not committed here (see `docs/sessions/conventions.md`'s "Reference documents") | The rulebook: Table 2 (approved combinations) and Table 3 (collision probabilities). A live-drafting Google Doc, still unfinalized as of 2026-09-15 (`Comment Period Ends`/`Effective Date` unfilled) — re-verify against the live doc before any session that changes rules. |
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
| 4 | `completed/` (PR #22 merged 2026-08-14; live run 2026-08-18) | Live query against real prod FHIR data → real per-field collision rates + agreement-rate vs. the current algorithm. **Tier 2**, run successfully. |
| 6 | merged (PR #39) | Expanded 26 rules → 38 (CMS v3.3): added ZIP/insurance-ID rules (27-33), ±1-day DOB tolerance, a **two-step "Household then Individual"** architecture for 8 rules where a field (phone, SSN-last-4, subscriber ID) is often shared by a whole family and can only prove "same household," not "same person." Also amended 4 already-merged rules (13,14,15,16) into that architecture. |
| 16-19 | merged (PRs #51-#54) | CMS v3.4.0 migration: renumbered Category 1 rules to a clean 01-30 sequence and extended DOB fuzzy to rules 01/02/03/10 (16); added Relationship Linkage rules `C2-39`/`C2-40` for guardian-verified minors and newborn-via-maternal-linkage (17); reconciled §VII audit records — `query_initiator` and a query-level timestamp (18); built §C.7 twin/multiple-birth tie-resolution (19). §C.9 defensive relationship-data flagging explicitly deferred (see `docs/sessions/index.md`'s "Candidate future sessions"). Current rule count: 30 Category 1 + 10 Category 2 (8 household + 2 relationship-linkage) = 40. |
| 8 | pending, moved to `cms-hte-patient-matching-test-set` | Runs both the current production algorithm and this new engine against the same batch, buckets every disagreement into 6 categories (nickname, typo, DOB conflict, etc.), produces the evidence report for a cutover decision. |

## 4. Blockers and open decisions (as of 2026-09-17)

- **Sessions 4, 6, and 16-19 are all merged into `main`** — the v3.4.0 migration described
  above is code-complete. `docs/sessions/index.md` is the source of truth for exact PR numbers
  and per-session execution notes; keep it current as work continues.
- **§C.9 (defensive relationship-data flagging)** from the v3.4.0 spec is deferred, not built —
  it needs a decision on how a caller supplies `RelatedPerson` data to the engine at all before
  it can be scoped (see `index.md`'s "Candidate future sessions").
- **Session 8 has 3 real blockers** (now tracked in `cms-hte-patient-matching-test-set`): (a) a
  decision on whether this repo may take an eval-only dependency on `helix-personmatching`; (b)
  naming who adjudicates a 25-50 pair hand-review sample; (c) whether the session-9 synthetic
  labeled-set approach replaces or runs alongside the original legacy-vs-new comparison design.
- **Phase 2 (production deployment)** now has real scope: the sibling
  `cms-hte-patient-matching-service` repo wraps this package's `PatientMatcherService`/
  `MatchingEngine` as a production HTTP microservice; this repo's own production-backend
  infrastructure work (e.g. `MongoAtlasCache`, session 12, merged) supports that.

## 5. The plan, in order

1. Confirm the v3.4.0 migration (sessions 16-19) is fully reflected in `index.md` and each
   session doc has moved to `completed/` once its PR is verified merged.
2. Scope and resolve §C.9 (defensive relationship-data flagging) once the `RelatedPerson`
   input-surface question has an answer.
3. Run session 8 (in `cms-hte-patient-matching-test-set`) once its 3 `NEEDS HUMAN DECISION`
   items are resolved. Done looks like: a disagreement-bucketed comparison report against the
   legacy algorithm.
4. Continue Phase 2 production-backend work as `cms-hte-patient-matching-service` surfaces
   further needs.
