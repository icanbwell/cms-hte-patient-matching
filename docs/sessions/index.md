# Session Index

The tracker for agent-executable sessions in `patient-matching`. See `conventions.md` for how
to run one. To begin, open a fresh agent conversation and say **"start the next session"** —
run whatever **Suggested Next Session** names below.

**Status of this set:** `APPROVED` (design reviewed and approved by the project lead, 2026-07-28 — see
`../superpowers/specs/2026-07-28-session-planning-playbook-design.md`).


---

## Suggested Next Session

> **2026-09-15 addendum (CMS v3.4.0 migration):** Imran shared the v3.4.0 spec diff and the
> full v3.4.0 doc directly, and asked for this repo to be brought into compliance. Four new
> sessions are queued for this: 16 (renumber Category 1 rules to v3.4.0's clean 01-30
> sequence + extend DOB fuzzy to rules 01/02/03/10), 17 (Relationship Linkage field + rules
> 39/40, guardian-verified minor / newborn-via-maternal-linkage — Imran decided: implement
> now, best-effort, with the spec's own unresolved caveats documented as known limitations),
> 18 (§VII audit record reconciliation — one real `NEEDS HUMAN DECISION` on what "query
> initiator" means for this repo), and 19 (§C.7 twin-handling + §C.9 defensive relationship-data
> flagging). This work is independent of session 8's Tier-3 harness below; both can proceed in
> parallel once session 8's `NEEDS HUMAN DECISION` items (in the moved repo) are answered.
>
> **2026-09-15 addendum (session 16 done):** session 16 executed same-day — PR
> [#51](https://github.com/icanbwell/cms-hte-patient-matching/pull/51), left open (merge is
> Imran's call), moved to `in_review/`. Found and resolved one real issue not anticipated when
> sessions 17-19 were scoped: v3.4.0's Category 1 renumbering collides with Category 2's
> legacy `13-16/34/35/37/38` IDs; resolved via a `C2-` prefix (see session_16.md's Execution
> notes) — sessions 17/19 should use the `C2-` form if they reference a Category 2 rule by ID.
>
> **2026-09-15 addendum (session 16, post-review fix):** an adversarial review of PR #51 found
> DOB fuzzy blocking was routed through Damerau-Levenshtein string edit distance rather than
> the engine's own calendar-day tolerance, silently dropping genuine +/-1-day matches at
> month/year boundaries and digit rollovers on the three highest-volume rules this PR extends
> DOB* to (01, 02, 03) - invisible to this session's own tests and to the ONC/NPPES regression
> suites, which bypass backend blocking entirely. Fixed with a new `MatchType.DOB_TOLERANCE`
> that expands to an exact `{value-1day, value, value+1day}` lookup on every backend, which
> also fixed a related Mongo Atlas token-explosion issue and a DuckDB full-scan issue the same
> review found. One open question flagged for Imran, not resolved unilaterally: whether rules
> 01/10's published `p_collision_fuzzy` figures should account for DOB*'s tolerance now that
> it's extended to high-volume rules - see session_16.md's "Post-review fixes" section.
>
> **Session 17 is the new Suggested Next Session.**
>
> **Session 8 — Legacy comparison harness (Tier 3).** Session 6 (below) is now `in_review/`
> (PR opened 2026-08-18) with its hard code dependency (session 5) satisfied. Session 8's
> remaining blockers are 3 `NEEDS HUMAN DECISION` items (eval-only dependency on
> `helix-personmatching`, adjudicator identity, replace-vs-alongside the labeled-set approach)
> — not code. Once those are answered, session 8 is the next session to run; session 6's
> merge is a soft/quality dependency for it, not a hard gate (see session_8.md).
>
> **2026-08-14 addendum:** session_9 (PR #27 merged 2026-08-14) resolved session_8's
> 2026-08-13 open question about the test-data simulation methodology (mutation-based fuzzy
> positives + mined real-record hard negatives). Session_8's session_9 dependency is now
> satisfied.
>
> **2026-08-18 addendum (session 4):** session 4 is now `completed/` (PR #22 merged
> 2026-08-14; live Databricks run completed 2026-08-18 after PR #36 fixed a real null-field
> bug the run surfaced — see session_4.md's Execution notes). Session_8's hard dependency on
> session 4 is satisfied. It still needs 3 `NEEDS HUMAN DECISION` items resolved (eval-only
> dependency on `helix-personmatching`, adjudicator identity, replace-vs-alongside — see
> session_8.md) before it can start.
>
> **2026-08-18 addendum (repo move, later same day):** the test-set generation code
> (`evaluation/`, its demo notebooks, and session docs 8/9/10/11) moved to
> [icanbwell/cms-hte-patient-matching-test-set](https://github.com/icanbwell/cms-hte-patient-matching-test-set)
> ([PR #1](https://github.com/icanbwell/cms-hte-patient-matching-test-set/pull/1)). Session 8's
> doc — including the dependency/`NEEDS HUMAN DECISION` state above — now lives there; check
> the new repo for its current status. Session 6 in this repo remains a hard dependency of the
> moved session 11.

## Up Next (execution order)

| # | Session | Thread | Depends on | Size | Status | One-line summary |
|---|---------|--------|-----------|------|--------|-------------------|
| 17 | [session_17](pending/session_17.md) | Line B: CMS v3.4.0 migration | 16 (soft, file-conflict avoidance only — 16 now `in_review/`, PR #51) | L | pending | Relationship Linkage field (Table 3) + Rules 39/40 (guardian-verified minor / newborn-via-maternal-linkage) — built best-effort with the spec's own unresolved caveats documented. |
| 18 | [session_18](pending/session_18.md) | Line B: CMS v3.4.0 migration | 16 (soft, ID-reference ordering only) | M | pending — blocked on 1 `NEEDS HUMAN DECISION` (what "query initiator" means for this repo) | §VII audit record reconciliation: confirm 6 of 7 required fields already present, add query initiator as the 7th. Path B aggregate metrics explicitly out of scope. |
| 19 | [session_19](pending/session_19.md) | Line B: CMS v3.4.0 migration | 17 (soft, avoid two sessions inventing different relationship-data FHIR conventions) | M | pending | §C.7 twin/multiple-birth handling (4 new operational rules, none exist yet) + §C.9 defensive relationship-data flagging (SHOULD-level, lower priority). |
| 8 | [session_8](https://github.com/icanbwell/cms-hte-patient-matching-test-set/blob/main/docs/sessions/pending/session_8.md) (moved) | Evaluation & Statistical Rigor | 3, 4, 9 (hard, all satisfied); 6 (soft, quality-of-result only) | L | pending — hard code dependencies satisfied (session 4: PR #22 merged, live run 2026-08-18 via PR #36; session 9: PR #27 merged); blocked on 3 `NEEDS HUMAN DECISION` items — see the moved session_8.md | Tier 3: legacy comparison harness, precision/recall-as-agreement, disagreement buckets, per-pair explanations |

Session 3 merged into `main` (PR [#11](https://github.com/icanbwell/patient-matching/pull/11),
2026-07-30) and session 5 merged into `main` (PR [#16](https://github.com/icanbwell/patient-matching/pull/16),
2026-08-02, doc in `completed/` as of 2026-08-03) — both of session 6's dependencies are
satisfied; session 6 itself moved to `in_review/` below on 2026-08-18.

## In Review

| # | Session | Thread | PR | One-line summary |
|---|---------|--------|----|--------------------|
| 16 | [session_16](in_review/session_16.md) | Line B: CMS v3.4.0 migration | [#51](https://github.com/icanbwell/cms-hte-patient-matching/pull/51) (open) | Renumbers Category 1 rules to v3.4.0's clean 01-30 sequence; extends DOB +/-1 day fuzzy to rules 01/02/03/10; prefixes Category 2's rule_ids with `C2-` after finding v3.4.0's renumbering collides with their legacy IDs (see doc's Execution notes). |
| 6 | [session_6](in_review/session_6.md) | Line B: CMS v3.3 migration | [#39](https://github.com/icanbwell/patient-matching/pull/39) (open) | Table 2 v3.3.0 base + v3.3.1/v3.3.3/v3.3.4/v3.3.6 addenda: 3 new fields, DOB +/-1 day fuzzy, Household/Individual two-step architecture (rules 13-16 amended, 34/35/37/38 new), 30 flat + 8 two-step = 38 rules total. Rules 39/40 and v3.3.6 institutional-address integration explicitly deferred. |
| 13 | [session_13](in_review/session_13.md) | Phase 2: production candidate-retrieval scaling | [#46](https://github.com/icanbwell/cms-hte-patient-matching/pull/46) (merged 2026-09-06) | Publish `cms-hte-patient-matching` to PyPI via OIDC Trusted Publishing. Packaging fixes done and verified locally (`[build-system]` added, stale `setup.py`/`setup.cfg` and stray `patientmatching/` dir removed, Makefile `dist`/`testpackage`/`package` targets added); pypi.org Trusted Publisher registered. |
| 14 | [session_14](in_review/session_14.md) | Phase 2: production candidate-retrieval scaling | [#48](https://github.com/icanbwell/cms-hte-patient-matching/pull/48) (open) | Converts `CacheBackend`/`MatchingBackend`/`MatchingEngine`/`CacheManager`/`PatientMatcherService`/`FhirClient`/`TokenVerifier`/`IAL2Extractor` to a uniform async interface so no I/O call blocks the event loop. `evaluate_pair()`/normalization stay sync (no I/O). 478 tests pass via `make tests`. |
| 15 | [session_15](in_review/session_15.md) | Phase 2: production candidate-retrieval scaling | [#48](https://github.com/icanbwell/cms-hte-patient-matching/pull/48) (open) — same branch/PR as #14 | Removes the FastAPI HTTP layer entirely (`cms-hte-patient-matching-service` is the intended HTTP layer, confirmed with Imran) and removes Docker/docker-compose entirely, matching `helix.personmatching`'s pure-`uv` pattern — `make tests` now runs `uv run pytest .` directly on the host, no container. |

## Completed (most recent 3)

| # | Session | Thread | One-line summary |
|---|---------|--------|-------------------|
| 12 | [session_12](completed/session_12.md) | Phase 2: production candidate-retrieval scaling | `MongoAtlasCache`: a MongoDB Atlas Search-backed `CacheBackend`, for the sibling `cms-hte-patient-matching-service`'s shared-cache/scaling needs. Merged via [#45](https://github.com/icanbwell/cms-hte-patient-matching/pull/45) (squash, 2026-09-06). |
| 4 | [session_4](completed/session_4.md) | Evaluation & Statistical Rigor | Real-world FHIR data source (`bronze.fhir_lake.patient_4_0_0` joined to `silver.fhir_lite.person_patient`) for `rule_eval.py`. Code merged via [#22](https://github.com/icanbwell/patient-matching/pull/22); live Databricks run completed 2026-08-18 (see session doc for full output/interpretation), after [#36](https://github.com/icanbwell/patient-matching/pull/36) fixed a real null-field crash the run surfaced. |
| 9 | [session_9](https://github.com/icanbwell/cms-hte-patient-matching-test-set/blob/main/docs/sessions/completed/session_9.md) (moved) | Evaluation & Statistical Rigor | Synthetic CMS test-dataset generation: single-edit-distance fuzzy mutations (true matches) + mined real-record hard negatives (true non-matches), resolving session_8's test-data simulation methodology question. Merged via [#27](https://github.com/icanbwell/patient-matching/pull/27). |

### Keeping this index current (do this when closing a session)
1. If the session's PR merged immediately: move the row from *Up Next* to the **top** of
   *Completed*. If it's still open: move the row to *In Review* instead, with a link to the PR.
2. When an *In Review* PR later merges (possibly in a different session): move its row from
   *In Review* to the **top** of *Completed*.
3. If *Completed* now has more than 3 rows, drop the oldest off the visible list — its doc
   stays in `completed/`, it's just no longer shown here.
4. Re-set **Suggested Next Session** above to whichever pending session is now the best next
   pick — usually, but not always, the new top row of *Up Next*. Say why, and double-check
   whether it has a hard code dependency on anything still in `in_review/` (if so, skip it).

## Rejected

_(none yet — see `rejected/README.md`)_

## Candidate future sessions (not yet authored)

- **Parent/child delegated access** ([full draft: `pending/session_7.md`](pending/session_7.md)
  — written up despite the "not yet authored" heading here because Jira `SD-1416` and a Slack
  design discussion with Imran/Alvin already exist and are worth capturing, but it is **not**
  in `Up Next` above and **confirmed not startable in this repo, period**). Prompted by
  Citizen's parent-account-to-child-records connection failures. As of 2026-08-07, Imran
  confirmed directly: **"Parent-guardian relationships are not patient matching. They are
  delegated access."** — a category rejection, not a qualification. There is no
  matching-side component to this at all (an earlier 2026-08-04 hypothesis that Imran's own
  proposed Rule 39 might partly answer this is now superseded — see `session_7.md`'s
  2026-08-07 update). The entire problem is authorizing a parent's account to access an
  already-matched child's record, and per Imran that's **jurisdiction-dependent** ("this is
  legal question and different in each state," "identity is different than control") — no
  existing internal or external framework answers it (the Cambia doc Imran shared covers
  identity-proofing only, not authorization, and is itself still unresolved, targeting a
  re-draft 2026-08-14). Confirmed out of scope for `patient-matching`,
  `helix.personmatching`, and `helix.personmatching-service` alike — see `session_7.md` for
  the full `NEEDS HUMAN DECISION` list, now centered on Legal/Compliance ownership and which
  service should hold the eventual access-control capability. Note per Matt Sables (Slack,
  2026-08-04): the 52.3%-failure number that escalated this was later found to be a
  client-side reporting misread, not an active production issue — the capability gap is still
  real, but the urgency has softened since the 2026-07-17 discussion.
- **P(collision) evaluator: per-value (name-frequency-conditioned) collision probability.**
  `NEEDS HUMAN DECISION`: a genuine methodology deviation from the published CMS
  approach (which uses static per-field constants), needs the engineering lead's sign-off as domain lead
  before implementation. Propose it alongside sessions 5/6's results.
- **"Project US@" address format compliance.** Smaller gap in the otherwise-complete
  normalization layer; not blocked, just not yet scoped in detail.
- **Automate the PHI guardrail** (a pre-commit check for hardcoded PHI-shaped literals in
  `notebooks/`) — currently enforced by review only.
- **Add a real indexed blocking key to `InMemoryBackend.search()`** (e.g. by
  `(soundex(last_name), dob_year)`), replacing its current O(n) linear-scan-per-query
  behavior. Not required by session 3, which evaluates rules via direct pairwise
  `evaluate_pair()` calls on precomputed pairs and never calls `InMemoryBackend.search()`;
  matters once actual `match()`/`match_batch()` calls need to scale against a large corpus
  (e.g. session 4 or eventual production-shaped batch runs).

## Dependency graph (at a glance)

```
session_1 (audit fields)         --+
session_2 (tiered uniqueness)    --+-- independent, no upstream
session_5 (P(collision) eval)    --+
                                    |
session_3 (ONC baseline) ----------+--> session_4 (completed 2026-08-18; real-world data source)
                                    |
session_5 --------------------------> session_6 (Table 2 v3.3 expansion, in_review as of 2026-08-18)

session_3 --------------------------> session_8 (legacy comparison harness, Tier 3)
session_4 (completed) ---------------> session_8 (hard, satisfied: reuses its real-batch query)
session_9 (completed) ---------------> session_8 (hard, satisfied: supplied the test-data
                                       simulation methodology - fuzzy mutations + mined hard
                                       negatives)
session_6 -----------------(soft)---> session_8 (session_8's own DoD doesn't need this; only
                                       the go-live-readiness of its numbers does)

session_3 --------------------------> session_9 (completed; reused onc_loader.py/rule_eval.py
                                       directly)

Merge gate (not a code dependency): session_3 must be in completed/ (PR merged into main,
not just in_review/) before session_5 or session_6 can move to completed/. session_4's
dependency on session_3 IS a code dependency, so it can't even start until then.
```
