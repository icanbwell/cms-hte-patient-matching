# Session Index

The tracker for agent-executable sessions in `patient-matching`. See `conventions.md` for how
to run one. To begin, open a fresh agent conversation and say **"start the next session"** —
run whatever **Suggested Next Session** names below.

**Status of this set:** `APPROVED` (design reviewed and approved by Sean, 2026-07-28 — see
`../superpowers/specs/2026-07-28-session-planning-playbook-design.md`).


---

## Suggested Next Session

> **Session 6 — Expand Table 2 to CMS v3.3 (base + v3.3.1/v3.3.3/v3.3.4/v3.3.6 addenda).**
> Re-scoped 2026-08-12 — see the doc's "Re-scope note"; it's larger than the original
> "37 rules" framing (household/individual two-tier architecture, 4 already-merged rules
> amended, 2 rules explicitly deferred). Session 5's doc moved to `completed/` on
> 2026-08-03 (PR #16 merged 2026-08-02), which satisfies session 6's hard code dependency on
> session 5's evaluator per the merge-gate rule. Session 6 remains blocked only on fetching
> the live CMS v3.3 spec content (Google Doc; see `conventions.md`'s "Reference documents"),
> which the executing environment on 2026-08-06/07 had no Google Drive access to fetch.
> Unblocks as soon as either Drive access is authorized or someone pastes the relevant
> Table 2/DOB-tolerance sections directly into the session.
>
> **2026-08-14 addendum:** session_9 (`completed/session_9.md`, PR #27 merged 2026-08-14)
> resolved session_8's 2026-08-13 open question about the test-data simulation methodology
> (mutation-based fuzzy positives + mined real-record hard negatives). Session_8's session_9
> dependency is now satisfied; it still needs session 4 in `completed/` (PR #22 open) and the
> `NEEDS HUMAN DECISION` on replace-vs-alongside — see session_8.md's 2026-08-14 update.

## Up Next (execution order)

| # | Session | Thread | Depends on | Size | Status | One-line summary |
|---|---------|--------|-----------|------|--------|-------------------|
| 6 | [session_6](pending/session_6.md) | Line B: CMS v3.3 migration | 5 | L | pending — blocked on fetching the live CMS v3.3 spec content | Expand Table 2 to CMS v3.3 base + v3.3.1/v3.3.3/v3.3.4/v3.3.6 addenda |
| 8 | [session_8](pending/session_8.md) | Evaluation & Statistical Rigor | 3, 4, 9 (hard); 6 (soft, quality-of-result only) | L | pending — session 9 dependency now satisfied (`completed/`, PR #27 merged 2026-08-14); still blocked on session 4 (`in_review/`, PR #22 open) and 1 `NEEDS HUMAN DECISION` (replace-vs-alongside, see session_8.md) | Tier 3: legacy comparison harness, precision/recall-as-agreement, disagreement buckets, per-pair explanations |

Session 3 merged into `main` (PR [#11](https://github.com/icanbwell/patient-matching/pull/11),
2026-07-30) and session 5 merged into `main` (PR [#16](https://github.com/icanbwell/patient-matching/pull/16),
2026-08-02, doc in `completed/` as of 2026-08-03) — session 6's merge gate is satisfied; it
just needs the live spec content, not more code dependencies.

## In Review

| # | Session | Thread | PR | One-line summary |
|---|---------|--------|----|--------------------|
| 4 | [session_4](in_review/session_4.md) | Evaluation & Statistical Rigor | [#22](https://github.com/icanbwell/patient-matching/pull/22) (open) | Real-world FHIR data source (`bronze.fhir_lake.patient_4_0_0` joined to `silver.fhir_lite.person_patient`) for `rule_eval.py`, via reproducible queries; per-field collision rates vs. session 5's Table 3 |

## Completed (most recent 3)

| # | Session | Thread | One-line summary |
|---|---------|--------|-------------------|
| 9 | [session_9](completed/session_9.md) | Evaluation & Statistical Rigor | Synthetic CMS test-dataset generation: single-edit-distance fuzzy mutations (true matches) + mined real-record hard negatives (true non-matches), resolving session_8's test-data simulation methodology question. Merged via [#27](https://github.com/icanbwell/patient-matching/pull/27). |
| 5 | [session_5](completed/session_5.md) | Line B: CMS v3.3 migration | Table 3 u-probabilities + P(collision) evaluator; replaces `table2_rules.py`'s 26 hand-typed constants with computed values. Merged via [#16](https://github.com/icanbwell/patient-matching/pull/16). |
| 2 | [session_2](completed/session_2.md) | Line B: CMS v3.3 migration | Split `AMBIGUOUS` into `ESCALATE` (exactly 2 candidates) vs. `AMBIGUOUS` (3+, stricter interim threshold). Merged via [#14](https://github.com/icanbwell/patient-matching/pull/14). |

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

- **P(collision) evaluator: per-value (name-frequency-conditioned) collision probability.**
  `NEEDS HUMAN DECISION — Sean/Imran`: a genuine methodology deviation from the published CMS
  approach (which uses static per-field constants), needs Imran's sign-off as domain lead
  before implementation. Propose it to him alongside sessions 5/6's results.
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
session_3 (ONC baseline) ----------+--> session_4 (real-world data source, in_review as of 2026-08-06)
                                    |
session_5 --------------------------> session_6 (Table 2 v3.3 expansion)

session_3 --------------------------> session_8 (legacy comparison harness, Tier 3)
session_4 --------------------------> session_8 (hard: reuses its real-batch query)
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
