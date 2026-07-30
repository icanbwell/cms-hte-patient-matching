# Session Index

The tracker for agent-executable sessions in `patient-matching`. See `conventions.md` for how
to run one. To begin, open a fresh agent conversation and say **"start the next session"** —
run whatever **Suggested Next Session** names below.

**Status of this set:** `APPROVED` (design reviewed and approved by Sean, 2026-07-28 — see
`../superpowers/specs/2026-07-28-session-planning-playbook-design.md`).

---

## Suggested Next Session

> **Session 1 — Audit record completeness.** Smallest, no dependencies, no statistical-rigor
> gate to satisfy (not a rule change) — a quick, low-risk pick while session 3's PR is out for
> review. (Sessions 5/6 are also unblocked now that session 3's Tier-1 report exists, but they're
> larger — session 1 is the fastest next win.)

## Up Next (execution order)

| # | Session | Thread | Depends on | Size | Status | One-line summary |
|---|---------|--------|-----------|------|--------|-------------------|
| 1 | [session_1](pending/session_1.md) | Line B: CMS v3.3 migration | — | S | pending | Add `timestamp`/`version` to the audit record (§VII) |
| 2 | [session_2](pending/session_2.md) | Line B: CMS v3.3 migration | — | S/M | pending | Split `AMBIGUOUS` into 2-candidate vs. 3+-candidate tiered response |
| 4 | [session_4](pending/session_4.md) | Evaluation & Statistical Rigor | 3 | M | pending | Real-world FHIR data source for `rule_eval.py`, via reproducible queries |
| 5 | [session_5](pending/session_5.md) | Line B: CMS v3.3 migration | — | M | pending | Table 3 u-probabilities + P(collision) evaluator |
| 6 | [session_6](pending/session_6.md) | Line B: CMS v3.3 migration | 5 | M/L | pending | Expand Table 2 to v3.3's 37 rules |

Sessions 5 and 6's merge gate (session 3's Tier-1 report) is now satisfied — see Completed
below — so they're unblocked, pending Sean's review of session 3's PR.

## Completed (most recent 3)

| # | Session | Thread | One-line summary |
|---|---------|--------|-------------------|
| 3 | [session_3](completed/session_3.md) | Evaluation & Statistical Rigor | ONC self-match baseline wired to `rule_eval.py` (1M-record dataset, not the ~28K assumed); pairwise matcher + sampled negatives. PR open, not yet merged. |

### Keeping this index current (do this when closing a session)
1. Move the row from *Up Next* to the **top** of *Completed*.
2. If *Completed* now has more than 3 rows, drop the oldest off the visible list — its doc
   stays in `completed/`, it's just no longer shown here.
3. Re-set **Suggested Next Session** above to whichever pending session is now the best next
   pick — usually, but not always, the new top row of *Up Next*. Say why.

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

Merge gate (not a code dependency): session_3's Tier-1 report must exist before
session_5 or session_6 can move to completed/.
```
