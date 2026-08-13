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
> session 5's evaluator per the merge-gate rule. Session 4 is also startable but remains
> blocked on its `NEEDS HUMAN DECISION` (exact Databricks/Mongo table names for FHIR Patient
> resources and Person-Patient match links — see `pending/session_4.md`'s "Upstream data/system
> dependencies"), unresolved since it was first deferred on 2026-07-31. Session 6 has no such
> blocker, so it's the pick unless Sean resolves session 4's open question first.

## Up Next (execution order)

| # | Session | Thread | Depends on | Size | Status | One-line summary |
|---|---------|--------|-----------|------|--------|-------------------|
| 6 | [session_6](pending/session_6.md) | Line B: CMS v3.3 migration | 5 | L | pending — ready to start | Expand Table 2 to CMS v3.3 base + v3.3.1/v3.3.3/v3.3.4/v3.3.6 addenda |
| 4 | [session_4](pending/session_4.md) | Evaluation & Statistical Rigor | 3 | M | pending — blocked on `NEEDS HUMAN DECISION` | Real-world FHIR data source for `rule_eval.py`, via reproducible queries |

Session 3 merged into `main` (PR [#11](https://github.com/icanbwell/patient-matching/pull/11),
2026-07-30) and session 5 merged into `main` (PR [#16](https://github.com/icanbwell/patient-matching/pull/16),
2026-08-02, doc in `completed/` as of 2026-08-03) — session 4's hard code dependency and
session 6's merge gate are both satisfied. Session 4 itself is blocked only on Sean answering
its `NEEDS HUMAN DECISION`.

## In Review

_(none currently)_

## Completed (most recent 3)

| # | Session | Thread | One-line summary |
|---|---------|--------|-------------------|
| 5 | [session_5](completed/session_5.md) | Line B: CMS v3.3 migration | Table 3 u-probabilities + P(collision) evaluator; replaces `table2_rules.py`'s 26 hand-typed constants with computed values. Merged via [#16](https://github.com/icanbwell/patient-matching/pull/16). |
| 2 | [session_2](completed/session_2.md) | Line B: CMS v3.3 migration | Split `AMBIGUOUS` into `ESCALATE` (exactly 2 candidates) vs. `AMBIGUOUS` (3+, stricter interim threshold). Merged via [#14](https://github.com/icanbwell/patient-matching/pull/14). |
| 1 | [session_1](completed/session_1.md) | Line B: CMS v3.3 migration | Add `timestamp`/`version` to the audit record (§VII) — audit plumbing only, no matching-behavior change. Merged via [#13](https://github.com/icanbwell/patient-matching/pull/13). |

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
session_3 (ONC baseline) ----------+--> session_4 (real-world data source)
                                    |
session_5 --------------------------> session_6 (Table 2 v3.3 expansion)

Merge gate (not a code dependency): session_3 must be in completed/ (PR merged into main,
not just in_review/) before session_5 or session_6 can move to completed/. session_4's
dependency on session_3 IS a code dependency, so it can't even start until then.
```
