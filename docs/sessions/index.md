# Session Index

The tracker for agent-executable sessions in `patient-matching`. See `conventions.md` for how
to run one. To begin, open a fresh agent conversation and say **"start the next session"** —
run whatever **Suggested Next Session** names below.

**Status of this set:** `APPROVED` (design reviewed and approved by Sean, 2026-07-28 — see
`../superpowers/specs/2026-07-28-session-planning-playbook-design.md`).

> **⚠ Concurrent-PR note (2026-08-01, remove once both merge):** this PR (#15, session 2
> closeout) and PR [#16](https://github.com/icanbwell/patient-matching/pull/16) (session 5)
> both branched from the same commit and both edit this file's *Suggested Next Session*, *Up
> Next*, and *In Review* sections independently — whichever merges second will hit a
> conflict here. When resolving it, don't just pick one side: the reconciled file should
> reflect **both** moves at once — session 2 in `completed/` (this PR) **and** session 5 in
> `in_review/` (PR #16) — plus an updated *Suggested Next Session* accounting for both (session
> 4 still blocked on its `NEEDS HUMAN DECISION`; session 6 still blocked on session 5 actually
> being in `completed/`, not just `in_review/`). PR #16's version of this file already has that
> combined reconciliation written out — use it as the template for the merged result.

---

## Suggested Next Session

> **Session 4 — Real-world FHIR data source for `rule_eval.py`.** Session 2 (tiered
> `ESCALATE`/`AMBIGUOUS` response) merged into `main` via PR #14 (2026-07-31), so it's done and
> off the board entirely. Of the remaining pending sessions, 4 and 5 are both genuinely
> startable (4's hard code dependency on session 3 is satisfied; 5 has no dependencies at all);
> 6 is not yet startable (depends on 5). Picking 4: it's the next Tier-2 statistical-rigor
> milestone per `conventions.md` and doesn't share Line B's CMS-v3.3-spec-fetch dependency that
> 5/6 both carry.

## Up Next (execution order)

| # | Session | Thread | Depends on | Size | Status | One-line summary |
|---|---------|--------|-----------|------|--------|-------------------|
| 4 | [session_4](pending/session_4.md) | Evaluation & Statistical Rigor | 3 | M | pending | Real-world FHIR data source for `rule_eval.py`, via reproducible queries |
| 5 | [session_5](pending/session_5.md) | Line B: CMS v3.3 migration | — | M | pending | Table 3 u-probabilities + P(collision) evaluator |
| 6 | [session_6](pending/session_6.md) | Line B: CMS v3.3 migration | 5 | M/L | pending | Expand Table 2 to v3.3's 37 rules |

Session 3 merged into `main` (PR [#11](https://github.com/icanbwell/patient-matching/pull/11),
2026-07-30) — session 4's hard code dependency and sessions 5/6's merge gate are both satisfied
now, all three remaining pending sessions above are genuinely startable except 6 (still gated
on 5).

## In Review

_(none currently — see `in_review/README.md` for what lands here.)_

## Completed (most recent 3)

| # | Session | Thread | One-line summary |
|---|---------|--------|-------------------|
| 2 | [session_2](completed/session_2.md) | Line B: CMS v3.3 migration | Split `AMBIGUOUS` into `ESCALATE` (exactly 2 candidates) vs. `AMBIGUOUS` (3+, stricter interim threshold). Merged via [#14](https://github.com/icanbwell/patient-matching/pull/14). |
| 1 | [session_1](completed/session_1.md) | Line B: CMS v3.3 migration | Add `timestamp`/`version` to the audit record (§VII) — audit plumbing only, no matching-behavior change. Merged via [#13](https://github.com/icanbwell/patient-matching/pull/13). |
| 3 | [session_3](completed/session_3.md) | Evaluation & Statistical Rigor | ONC self-match baseline wired to `rule_eval.py` (1M-record dataset, not the ~28K assumed); pairwise matcher + sampled negatives. Merged via [#11](https://github.com/icanbwell/patient-matching/pull/11). |

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
