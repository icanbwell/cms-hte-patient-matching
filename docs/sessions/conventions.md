# Session Conventions — patient-matching

> **Read this file first, every session.**

These documents let a fresh agent conversation execute a scoped piece of work end-to-end from
"start the next session." PR #3 (`claude/cms-matching-v1`, "CMS matching v1: in-memory backend
+ demo notebook") merged into `main` on 2026-07-29 (commit `cf9b71b`); sessions now build
directly on `main`, which is the integration branch for this backlog. (Prior to that merge,
sessions built on `claude/cms-matching-v1` because `main` had no code yet — see git history if
that context is needed.) Sessions are submitted for the project lead's review (self-review during the DS author's
PTO, 2026-07-21 -> 2026-08-01); a rejected session moves to `rejected/` (kept, not
deleted — see `rejected/README.md`).

## Mode

**Files-only** — never both with a tracker; one authority per fact. State lives in this repo's
folders (`pending/ in_review/ completed/ rejected/` — the legacy layout name; the
`session-planning-setup` skill's tooling recognizes it as a permanently-supported variant, not a
migration target) plus `index.md`. See "Session lifecycle and folders" below for the exact
transition rules.

## People

- **Reviewer:** the project lead.
- **Backup reviewer:** the DS author — the normal reviewer; the project lead self-reviewed 2026-07-21 ->
  2026-08-01 during the DS author's PTO (see this file's intro above).
- **Reciprocal review:** not applicable — a two-person review model, not reciprocal.
- **Close notifications:** none formalized — the merged PR and the `index.md` update are the
  record.
- **WIP limit:** not enforced. `index.md` has carried more than one row in *In Review*
  simultaneously without issue so far; revisit if that starts causing actual collisions.

## The principles

This repo operates under the `session-planning-setup` skill's core principles — SELF-CONTAINED,
RATCHET, DECLARE, PRE-SETTLE, PARAMETERIZE, SCRATCH-EXIT — see that skill's
`references/principles.md` for full definitions rather than restating them here.

**SCRATCH-EXIT: applies.** See "Code exits scratch space as soon as it earns it" below —
`notebooks/` is the scratch layer; code exits into `patient_matching/<subpackage>/` once it's
general, reliable, and worth structuring, with `evaluation/rule_eval.py` as the one deliberate
exception (see that section for why).

## The "start the next session" protocol

When a human opens a fresh agent conversation and says **"start the next session,"** the agent
does exactly this, in order:

1. **Read the index.** Open `index.md`. Run whichever session its **Suggested Next Session**
   callout names — a human-curated pick that does not always match the top row of *Up Next*.
2. **Read this file (`conventions.md`) in full**, then read that session doc in full.
3. **Verify upstream dependencies.** Every session lists upstream sessions it depends on.
   Confirm each is already in `completed/` — meaning its PR has actually **merged into
   `main`**, not just that the doc says the work is finished. A dependency sitting in
   `in_review/` (PR open, not yet merged) does **not** satisfy this: branching from `main` now
   won't have that session's code. If the dependency isn't in `completed/`, **stop** and report
   which dependency is missing (and whether it's merely `in_review/` vs. not started at
   all), and ask whether to proceed anyway.
4. **Resolve open questions.** If any question in the session is still tagged
   `NEEDS HUMAN DECISION`, ask the project lead now, before writing any code.
5. **Set up an isolated workspace** — a feature branch cut from `main` (see
   "Workspace isolation" below) — never directly on `main` itself.
6. **Execute the tasks in order**, test-first, per the TDD validation loop below.
7. **Close the session**: fill in *Execution notes*, commit the bookkeeping, **open a PR from
   the feature branch into `main`** (see "Every session ends with a PR" below — a session is
   never closed by merging or fast-forwarding without one), then either:
   - **merged now** (self-reviewed clean, no reason to wait): move the doc to `completed/` and
     update `index.md`'s *Completed* table; or
   - **PR left open** (e.g. waiting on the project lead's explicit go-ahead, since merging is their call to
     make): move the doc to `in_review/` instead (see that folder's README), update `index.md`
     to reflect that, and record the decision in *Execution notes*. Come back and move it from
     `in_review/` to `completed/` once the PR actually merges — that move can happen in a later,
     unrelated session/conversation; it doesn't need to be the one that opened the PR.

If told "start session N" specifically, skip step 1's queue lookup and go straight to that
session (still doing steps 2-7).

## Session lifecycle and folders

```
docs/sessions/
  index.md         the tracker: suggested next session, the up-next queue, the 3 most
                   recently completed, one-line summaries
  conventions.md   this file
  pending/         session_N.md files not yet started (the queue; order = suggested execution order)
  in_review/       session_N.md files whose work is done and PR is open, but not yet merged
  completed/       session_N.md files that met their Definition of Done (PR merged into main)
  rejected/        session_N.md files the project lead decided not to pursue (kept, not deleted)
```

A session moves **pending -> in_review** once its own work is done and its PR is open but not
yet merged, then **in_review -> completed** once that PR merges (these two moves can happen in
different sessions/conversations — see the "start the next session" protocol's step 7). A
session that merges immediately (no reason to wait) can skip `in_review/` and go straight
**pending -> completed**. A session moves **pending -> rejected** at any point before
`completed/` when the project lead decides against it. Sessions are never edited in place after execution
starts; if the plan turns out wrong mid-execution, finish or cleanly abandon, note it in
*Execution notes*, and author a follow-up session rather than rewriting history.

## Anatomy of a session doc

Every session doc follows this skeleton, in order: title/status/thread/size header, Outcome
purpose, Upstream sessions, Downstream sessions, Upstream data/system dependencies, Downstream
data/system dependencies, Scope (In scope / Out of scope), Tasks, Unit tests required,
Validation, Open questions, Execution notes. See any `pending/session_N.md` for a filled-in
example.

**Scope anchor (part of Outcome purpose):** every session's Outcome purpose must name the
specific `docs/handoff/README.md` line item or CMS spec section (e.g. "§VII audit record",
"Table 3 u-probabilities", "the mid-August Line B target") it addresses — not just a `Thread`
tag. This is what keeps the backlog from drifting into unrelated work over many sessions
authored at different times: every session traces back to one of the two canonical sources
(the handoff doc's Line A/Line B strategy, or the CMS spec itself), not to another session doc
or to freeform judgment. `Thread` alone doesn't do this — it's just a coarse label with no
registry, so nothing stops a typo'd or genuinely new thread from drifting in unnoticed.

## Sizing

Inferred from observed session sizes to date (sessions 1-9), not a rubric the project lead has explicitly
calibrated — treat as a draft to correct, not a settled answer:

- **S:** under 2 hours — a single function/fix, one sitting (e.g. session 1's audit-field
  addition).
- **M:** half a day — 2-4 new files or one new module plus tests (e.g. session 4, session 9).
- **L:** up to a full day — a new cross-cutting subsystem, multiple modules, or a dependency on
  another repo's code (e.g. session 8).
- **XL:** split before authoring; if genuinely irreducible, queue as XL with the no-split reason
  recorded in the doc.

Second-party size check: solo — self-graded (the project lead, or whoever authors the session).

## Hot files

Shared files multiple sessions are likely to touch, where footprint collisions concentrate:

- `patient_matching/matching/table2_rules.py` — the Table 2 rule set; sessions 5 and 6 both
  touch it, and any future rule-adding session will too.
- `docs/sessions/index.md` — every session's close-out writes here; two sessions closing at
  the same time can collide on this file.
- `evaluation/rule_eval.py` — the shared comparison harness every rule-changing session's Tier 1
  statistical-rigor gate (see below) depends on.

## PR labels

**Not yet adopted in this repo.** GitHub labels here are the generic repo defaults (`bug`,
`enhancement`, `dependencies`, `Major`/`Minor`/`Patch` for semver bumps) — no `type:*`/`risk:*`
scheme exists, unlike the `session-planning-setup` skill's default recommendation
(`references/integration.md`). `NEEDS HUMAN DECISION`: adopt that scheme, or continue
without it. No recommended default given — this is a process-overhead-vs-value call for a
solo/two-person review model, not a technical one.

## Reference documents (intentionally NOT copied into this repo)

- **CMS v3.3 spec** (Google Doc, "Draft for Technical Validation," open public-comment
  period, unresolved reviewer comments): `https://docs.google.com/document/d/1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg/edit`
  (file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg`). This is a live, actively-commented
  draft this repo doesn't own — sessions that need its content (5, 6) fetch it fresh via
  Google Drive access as their first task, rather than trusting a committed copy that could
  silently go stale while the comment period is open. (A full copy was tried and reverted
  2026-07-28 because it created two things to keep in sync — see git history on this branch.)
- **v3.2.2 spec** (finalized/superseded version): `docs/CMS_Patient_Matching_Proposal_v3.2.2.{pdf,txt}`
  — this one IS committed, because it's a frozen prior version, not a live draft.
- **ONC patient-matching test dataset**: a public, de-identified, versioned benchmark (the
  2017 ONC Patient Matching Algorithm Challenge dataset) — copied into this repo as test
  fixtures (session 3) because it's static and published, unlike the two documents above.

## Centralized docs

**None — this repo's docs are its own Markdown files** (`docs/sessions/`, `docs/handoff/`, the
committed spec copies above). Draft inference, not externally confirmed.

- Space/root: none.
- Company-wide initiative guide: none, with one nuance worth flagging — session 9's CMS-
  compliance work also references a cross-org workgroup Google Doc (a shared test-dataset
  proposal, not an internal Confluence page). Treat that the same way this section treats
  a company-wide initiative doc if a future session needs to update it.
- Which pages correlate with which paths: `docs/sessions/confluence-links.md` (added by this
  update, starts empty — that's the expected steady state for a repo with no centralized docs,
  not a gap to fill).

## Capturing friction as you go

Durable, project-wide facts go straight into this repo's `CLAUDE.md` as found (none exists yet
for `patient-matching` specifically — a candidate future session) or directly into this file;
thread-specific context goes into each session's own *Execution notes* at close, not the other
way around. No company-wide initiative doc exists to also update (see "Centralized docs" above).

## Testing structure: parameterization over duplication

One behavior, one test body, many named cases — not the same test copy-pasted with one input
changed. Use `pytest.mark.parametrize`.

- Test runner / framework: `pytest`, via `docker compose run --rm dev pytest ...` (or
  `make tests` for the full suite).
- Parameterization mechanism: `pytest.mark.parametrize`. Existing tests use plain pytest
  classes (e.g. `patient_matching/matching/tests/test_table2_rules.py::TestApprovedRules`),
  not `unittest.TestCase` — this applies directly, no adapter needed.
- Where shared test fixtures live: colocated per subpackage, e.g.
  `patient_matching/matching/tests/`. New ONC fixtures (session 3) live at
  `evaluation/fixtures/onc/` (sibling to `evaluation/rule_eval.py`, the module they support).
- Gotcha: `evaluation/` and `notebooks/` are excluded from pre-commit hooks (see the
  `exclude:` line in `.pre-commit-config.yaml`) — don't assume ruff/mypy/bandit ran on files
  there; run them manually (`ruff check evaluation/`, etc.) if a session touches those dirs.

Cover **decision boundaries**, not every value: for a threshold (the 2e-12 P(collision) bar,
a fuzzy-match edit-distance limit, the DOB +/-1-day tolerance), test just-below, at, and
just-above.

## TDD validation approach

1. Red — write the failing tests from the session's test table first; confirm they fail for
   the *right* reason.
2. Green — minimal code to pass.
3. Refactor while green.
4. Regression gate — the whole suite, not just the new tests.

## The validation loop (loop until resolved)

```
loop:
  1. Run the full test suite:   make tests
  2. If anything fails: diagnose the root cause, fix, go to 1.
  3. Run the project's gate:    make run-pre-commit
     If it modifies files or fails, address it, go to 1.
  4. Check the session's Validation criteria one by one; anything not objectively met -> do the
     work, go to 1.
  5. All green + gate clean + every criterion met -> DONE.
```

Never claim done without having actually run `make tests` and `make run-pre-commit` and seen
them pass. Evidence before assertion.

### Exact commands for this project

```bash
make devsetup                                                                              # one-time local setup
make tests                                                                                 # full suite (pytest tests, in Docker)
docker compose run --rm dev pytest patient_matching/matching/tests/test_table2_rules.py    # targeted example
make run-pre-commit                                                                        # ruff check --fix, ruff format, mypy, bandit
```

## Code exits scratch space as soon as it earns it

Exploratory environments — `notebooks/`, one-off scripts — are where logic is born and proven,
not where it should live. Once logic is general, reliable, reusable, and worthy of structure,
it moves into `patient_matching/<subpackage>/`, with tests. What legitimately stays in
`notebooks/` is environment glue (Databricks widgets, credential/config wiring, top-to-bottom
orchestration that calls the real modules) — see `notebooks/wellsense_member_matching_analysis.py`
for the pattern session 4 extends. `evaluation/` is a partial exception: `rule_eval.py` is a
mature, tested, reusable module that happens to sit outside `patient_matching/` — sessions
should wire to it in place, not duplicate it into `patient_matching/`, since moving it isn't
in scope for this backlog.

## Every session ends stable and at least as capable

- The system still runs end-to-end after the session, not just "the new part works."
- No capability is silently removed. Retiring something on purpose requires explicit sign-off
  from the project lead, recorded in the session's *Execution notes*.
- A behavior-preserving change (refactor, optimization) carries an **equivalence test** —
  proof the new path produces the same result as the old one.
- **No half-migrations land.** If a session can't reach a clean, green, at-least-as-capable
  state, it does not merge. Revert to the prior stable state and write up the blocker as a new
  session.

## Statistical rigor gate (Definition of Done for rule-changing sessions)

This matching methodology is built on statistical uniqueness-quantification principles
(Fellegi-Sunter P(collision)), not a labeled ground truth we can check answers against — so
statistical rigor is the guiding philosophy for any session that adds or modifies matching
*behavior* (a fuzzy-match allowance, a DOB tolerance, nickname handling, u-probability/
collision values, a new Table 2 rule, a blocking key). This is tiered, mirroring the CMS
spec's own phased-adoption/safe-harbor structure, so it shapes sessions without blocking early
development:

- **Tier 1 — required before a rule-changing session reaches `completed/`:** an ONC
  self-match `ComparisonReport` from `evaluation/rule_eval.py` (baseline vs. candidate,
  Beta-posterior credible intervals on precision/recall/FPR). Achievable entirely on synthetic
  labeled data (session 3) — never blocked on infra access.
- **Tier 2 — encouraged, not required:** validate the change's effect on P(collision)/
  collision-*rate* against real population data (session 4). Well-posed without match/
  non-match labels, unlike precision.
- **Tier 3 — explicitly not a near-term blocker:** full empirical precision/recall/FPR at
  population scale (>=1M records) on real data. Track as a pre-production-cutover milestone,
  not a gate on any session in this backlog.
- **Sessions can be authored and coded in any order** — the gate applies at merge time, not
  start time. Sessions 5 and 6 (rule-defining) can be developed in parallel with session 3,
  but shouldn't move to `completed/` until session 3 itself is in `completed/` (merged into
  `main`) and its Tier-1 report is actually there to diff against — session 3 sitting in
  `in_review/` isn't enough, since 5/6 would need to branch from a `main` that has the report.
- Sessions that don't touch rule behavior (1, 2) are exempt entirely, at every tier.

## PHI / data-handling guardrail

Payer client/reconciliation data and any real FHIR Patient/Person data from Databricks or Mongo
is PHI and must stay in governed environments — never exported into this repo's notebooks,
test fixtures, or committed queries' *output*. All matching/normalization test fixtures in
this repo must use synthetic or public data (the ONC dataset qualifies; payer client data does
not). Real-data sessions (4) commit only parameterized query *definitions*
(`notebooks/wellsense_member_matching_analysis.py`'s pattern: Databricks widgets, SQL-identifier
validation helpers), never query output or raw records. Enforced by review today, not an
automated check (candidate future session: a pre-commit check for hardcoded PHI-shaped
literals in `notebooks/`).

## Security guardrail (ahead of any PR merge)

Confirm the standard security tooling is active before any session's PR merges: Aikido
scanning enabled on the GitHub repo, the existing bandit/detect-private-key/
detect-aws-credentials pre-commit hooks staying active, no secrets in `docker.env`,
`.gitignore` covering local env files. Verified as part of the separate PR-review pass, not
per-session.

## Workspace isolation per session

A feature branch cut from `main`, merged back into `main` via PR (self-reviewed by the project lead) —
this satisfies "never directly on the base branch." (Before PR #3 merged on 2026-07-29, this
section pointed at `claude/cms-matching-v1` instead of `main`, back when `main` had no code.)

## Every session ends with a PR

**Every session, no exceptions, ends by opening a PR from its feature branch into
`main`** — never a direct merge, fast-forward, or push straight to `main` without one, even
during self-review periods. The PR is what makes a session's diff visible
and reviewable as a single unit, gives Aikido/Gecko's automated scans a checkpoint to run
against (per the Security guardrail above) before the change lands, and gives *Execution
notes* a natural home (the PR description) alongside the session doc's own copy. A session is
not done until its PR is merged — see Definition of Done below. If a PR is intentionally left
open past a session's other criteria being met (e.g. waiting on the project lead's explicit go-ahead to
merge), that's a valid stopping point, but it must be recorded as such in *Execution notes*
(not silently skipped) and the doc moved to `in_review/`, not `completed/` — see "Session
lifecycle and folders" above.

## Dependency and ordering rules

- Don't start a session whose upstream sessions aren't in `completed/` (merged into `main`,
  not just `in_review/`) without explicit sign-off from the project lead.
- `index.md`'s Up Next order reflects dependencies but isn't the only valid order —
  independent sessions may be reordered.
- A session with only a *merge-gate* dependency (see the statistical rigor gate) rather than a
  hard code dependency can still be coded while the gating session is `in_review/` — it just
  can't move to `completed/` first.
- A missing prerequisite discovered mid-session becomes a new session with a re-sequenced
  index, not silent scope expansion of the current one.

## Definition of Done

A session is done when **all** hold:
1. Every criterion in its Validation section is objectively met.
1a. Its Outcome purpose names the specific handoff-doc line item or CMS spec section it
    addresses (see "Anatomy of a session doc"'s scope anchor) — if it doesn't, add that
    sentence now, before closing out; don't let a session merge without it.
2. `make tests` is green.
3. `make run-pre-commit` is clean.
4. For rule-changing sessions, the statistical rigor gate's Tier 1 requirement is met.
5. The end state is stable and at least as capable as the start state — if not, the session
   does not merge; revert and write up the blocker instead.
6. Work is committed on its feature branch, a PR from that branch into `main`
   is open, and it has been merged (see "Every session ends with a PR" above) — or, if the project lead has
   explicitly said to leave it open rather than merge yet, that decision is recorded in
   *Execution notes* and the doc lives in `in_review/`, not `completed/`, until it does merge.

Then: fill in *Execution notes*, and either:
- **merged**: move `pending/session_N.md` -> `completed/session_N.md`, update `index.md`
  (move the row to the top of *Completed*, trim that list back to 3 if needed, re-set
  *Suggested Next Session*), commit the bookkeeping; or
- **PR open, not yet merged**: move `pending/session_N.md` -> `in_review/session_N.md`, add it
  to `index.md`'s *In Review* section, commit the bookkeeping. Later, once the PR merges (in
  this session or a future one), move `in_review/session_N.md` -> `completed/session_N.md` and
  update `index.md` the same way the "merged" case above does.

## Open-questions handling

The project lead (or whoever authors a session) resolves every question that's genuinely their call —
naming, file layout, which existing helper to reuse, algorithm choice — and writes the answer
into the session as a decision, not a question. What's left as an **Open Question** is only
what requires information or authority the author doesn't have. Every open question gets a
recommended default; only when the work genuinely cannot proceed safely without a human call
does it get a **`NEEDS HUMAN DECISION`** tag naming who should decide. The executing agent
resolves every `NEEDS HUMAN DECISION` item before writing any code.
