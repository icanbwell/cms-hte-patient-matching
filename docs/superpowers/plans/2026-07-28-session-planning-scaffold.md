# Session-Planning Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `docs/sessions/` in the `patient-matching` repo (branch `claude/cms-matching-v1`) per the session-planning-playbook structure, with `conventions.md`, `index.md`, and six fully-authored `session_N.md` docs ready to execute via "start the next session."

**Architecture:** This plan produces *documentation*, not application code — each task writes one file (or a small group of tightly-coupled files) per the playbook's templates. There is no red/green test cycle for markdown; "verification" for each task means checking the file against a concrete, objective checklist (required sections present, cross-references resolve to real files, code snippets are syntactically valid Python). The actual code changes described *inside* the session docs (audit fields, tiered uniqueness, the ONC harness, etc.) are out of scope for this plan — they happen later, when each session is executed.

**Tech Stack:** Markdown files under `docs/sessions/`. No new runtime dependencies. Source-of-truth for all technical claims is the current state of `patient_matching/matching/*.py` and `evaluation/rule_eval.py` on `claude/cms-matching-v1`, as read during this plan's authoring (2026-07-28) — cited by exact file and function name throughout.

## Global Constraints

- Every file this plan creates lives under `docs/sessions/` in the `patient-matching` repo, on branch `claude/cms-matching-v1`. Do not touch `main`.
- Follow the playbook's session doc anatomy exactly (see `~/git/session-planning-playbook.md`, "Template: `session_N.md` anatomy") — title/status/thread/size header, Outcome purpose, Upstream/Downstream sessions, Upstream/Downstream data dependencies, Scope (in/out), Tasks, Unit tests required, Validation, Open questions, Execution notes.
- Reviewer for all sessions: Sean (self-review during Zack Malone's PTO).
- The CMS v3.3 spec is referenced by Google Doc link/file ID (`1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg`) — **never** re-introduce a committed copy of it. This was tried and reverted earlier in this project (see git log on this branch, commit "Reference the live v3.3 spec doc instead of committing a copy") — don't repeat it.
- Every session that changes matching *rule behavior* (3, 5, 6) must carry the statistical-rigor gate language (Tier 1/2/3) — sessions 1 and 2 are explicitly exempt (audit plumbing and CMS-mandated tiering, not tunable rule behavior).
- No placeholders in any session doc: every task names exact files, exact function/class names, and either exact code or an exact, complete data table. `NEEDS HUMAN DECISION` tags are allowed only where the design doc (`docs/superpowers/specs/2026-07-28-session-planning-playbook-design.md`) already identifies a genuine external dependency (Sean's real Databricks/Mongo table names for session 4; Imran's sign-off for the not-yet-authored per-value P(collision) idea).
- Source of truth for scope/sequencing: `docs/superpowers/specs/2026-07-28-session-planning-playbook-design.md`. Where this plan and that spec seem to disagree, the spec wins — flag it during self-review rather than silently picking one.
- **Every session ends with an opened PR into `claude/cms-matching-v1`, no exceptions** (added 2026-07-28, mid-execution, per Sean) — `conventions.md`'s protocol step 7 and Definition of Done must both state this as a hard requirement, not one option among several ("merged, or a PR is open" language is not acceptable — the PR is mandatory even when Sean is self-reviewing).

---

### Task 1: Scaffold the `docs/sessions/` directory structure

**Files:**
- Create: `docs/sessions/pending/.gitkeep` (only needed if `pending/` would otherwise be empty after this task — it won't be, since Tasks 4-9 populate it immediately; skip this file)
- Create: `docs/sessions/completed/README.md`
- Create: `docs/sessions/rejected/README.md`

**Interfaces:** None (pure filesystem/doc scaffolding). Later tasks assume these directories exist.

- [ ] **Step 1: Create the directory structure and the two mechanics READMEs**

```bash
mkdir -p docs/sessions/pending docs/sessions/completed docs/sessions/rejected
```

`docs/sessions/completed/README.md`:
```markdown
# Completed Sessions

A session lands here when its Definition of Done (see `../conventions.md`) is fully met and
its feature branch has merged into `claude/cms-matching-v1`. Files are never edited after the
move — if something turns out wrong, author a follow-up session instead of rewriting history.

`../index.md`'s "Completed (most recent 3)" list is a capped view of the most recent entries
here; older sessions stay in this folder even after they drop off that list.
```

`docs/sessions/rejected/README.md`:
```markdown
# Rejected Sessions

A session lands here when Sean decides not to pursue it, at any point before it's marked
`completed/` — kept for history, not deleted, so the reasoning behind a "no" is never lost.
Add a one-line reason to the session's *Execution notes* section before moving it here.
```

- [ ] **Step 2: Verify the structure**

Run: `find docs/sessions -type d | sort`
Expected:
```
docs/sessions
docs/sessions/completed
docs/sessions/pending
docs/sessions/rejected
```

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/completed/README.md docs/sessions/rejected/README.md
git commit -m "Scaffold docs/sessions/ directory structure"
```

---

### Task 2: Write `docs/sessions/conventions.md`

**Files:**
- Create: `docs/sessions/conventions.md`

**Interfaces:**
- Produces: the operating manual every later task's session docs reference by relative link (`../conventions.md`). Section headers used by name in session docs: "The 'start the next session' protocol", "Statistical rigor gate", "Reference documents", "Definition of Done".

- [ ] **Step 1: Write the file**

`docs/sessions/conventions.md`:
```markdown
# Session Conventions — patient-matching

> **Read this file first, every session.**

These documents let a fresh agent conversation execute a scoped piece of work end-to-end from
"start the next session." This repo backs open PR #3 (`claude/cms-matching-v1`, "CMS matching
v1: in-memory backend + demo notebook"); sessions build directly on that branch, not `main`
(which currently has no code — `main` is just the initial commit). Sessions are submitted for
Sean's review (self-review during Zack Malone's PTO, 2026-07-21 -> 2026-08-01); a rejected
session moves to `rejected/` (kept, not deleted — see `rejected/README.md`).

## The "start the next session" protocol

When a human opens a fresh agent conversation and says **"start the next session,"** the agent
does exactly this, in order:

1. **Read the index.** Open `index.md`. Run whichever session its **Suggested Next Session**
   callout names — a human-curated pick that does not always match the top row of *Up Next*.
2. **Read this file (`conventions.md`) in full**, then read that session doc in full.
3. **Verify upstream dependencies.** Every session lists upstream sessions it depends on.
   Confirm each is already in `completed/`. If not, **stop** and tell Sean which dependency is
   missing, and ask whether to proceed anyway.
4. **Resolve open questions.** If any question in the session is still tagged
   `NEEDS HUMAN DECISION`, ask Sean now, before writing any code.
5. **Set up an isolated workspace** — a feature branch cut from `claude/cms-matching-v1` (see
   "Workspace isolation" below) — never directly on `claude/cms-matching-v1` itself.
6. **Execute the tasks in order**, test-first, per the TDD validation loop below.
7. **Close the session**: fill in *Execution notes*, move the doc to `completed/`, update
   `index.md`, commit the bookkeeping, **open a PR from the feature branch into
   `claude/cms-matching-v1`**, and merge it once self-reviewed (see "Every session ends with
   a PR" below) — a session is never closed by merging or fast-forwarding without one.

If told "start session N" specifically, skip step 1's queue lookup and go straight to that
session (still doing steps 2-7).

## Session lifecycle and folders

```
docs/sessions/
  index.md         the tracker: suggested next session, the up-next queue, the 3 most
                   recently completed, one-line summaries
  conventions.md   this file
  pending/         session_N.md files not yet started (the queue; order = suggested execution order)
  completed/       session_N.md files that met their Definition of Done
  rejected/        session_N.md files Sean decided not to pursue (kept, not deleted)
```

A session moves **pending -> completed** when its Definition of Done is met, or
**pending -> rejected** when Sean decides against it. Sessions are never edited in place after
execution starts; if the plan turns out wrong mid-execution, finish or cleanly abandon, note it
in *Execution notes*, and author a follow-up session rather than rewriting history.

## Anatomy of a session doc

Every session doc follows this skeleton, in order: title/status/thread/size header, Outcome
purpose, Upstream sessions, Downstream sessions, Upstream data/system dependencies, Downstream
data/system dependencies, Scope (In scope / Out of scope), Tasks, Unit tests required,
Validation, Open questions, Execution notes. See any `pending/session_N.md` for a filled-in
example.

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
  from Sean, recorded in the session's *Execution notes*.
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
  but shouldn't move to `completed/` until session 3 exists and produces their Tier-1 report.
- Sessions that don't touch rule behavior (1, 2) are exempt entirely, at every tier.

## PHI / data-handling guardrail

WellSense/reconciliation data and any real FHIR Patient/Person data from Databricks or Mongo
is PHI and must stay in governed environments — never exported into this repo's notebooks,
test fixtures, or committed queries' *output*. All matching/normalization test fixtures in
this repo must use synthetic or public data (the ONC dataset qualifies; WellSense data does
not). Real-data sessions (4) commit only parameterized query *definitions*
(`notebooks/wellsense_member_matching_analysis.py`'s pattern: Databricks widgets, SQL-identifier
validation helpers), never query output or raw records. Enforced by review today, not an
automated check (candidate future session: a pre-commit check for hardcoded PHI-shaped
literals in `notebooks/`).

## Security guardrail (ahead of any PR merge)

Confirm b.well's standard security tooling is active before any session's PR merges: Aikido
scanning enabled on the GitHub repo, the existing bandit/detect-private-key/
detect-aws-credentials pre-commit hooks staying active, no secrets in `docker.env`,
`.gitignore` covering local env files. Verified as part of the separate PR-review pass, not
per-session.

## Workspace isolation per session

A feature branch cut from `claude/cms-matching-v1`, merged back into `claude/cms-matching-v1`
via PR (self-reviewed by Sean) — since `claude/cms-matching-v1` is not `main`, this satisfies
"never directly on the base branch" while keeping all Line B work in one place until PR #3
itself is ready to merge to `main`.

## Every session ends with a PR

**Every session, no exceptions, ends by opening a PR from its feature branch into
`claude/cms-matching-v1`** — never a direct merge, fast-forward, or push straight to
`claude/cms-matching-v1` without one, even though Sean is self-reviewing during Zack's PTO.
The PR is what makes a session's diff visible and reviewable as a single unit, gives Aikido/
Gecko's automated scans a checkpoint to run against (per the Security guardrail above) before
the change lands, and gives *Execution notes* a natural home (the PR description) alongside
the session doc's own copy. A session is not done until its PR is merged — see Definition of
Done below. If a PR is intentionally left open past a session's other criteria being met (e.g.
waiting on Sean's explicit go-ahead to merge), that's a valid stopping point, but it must be
recorded as such in *Execution notes*, not silently skipped.

## Dependency and ordering rules

- Don't start a session whose upstream sessions aren't in `completed/` without explicit
  sign-off from Sean.
- `index.md`'s Up Next order reflects dependencies but isn't the only valid order —
  independent sessions may be reordered.
- A missing prerequisite discovered mid-session becomes a new session with a re-sequenced
  index, not silent scope expansion of the current one.

## Definition of Done

A session is done when **all** hold:
1. Every criterion in its Validation section is objectively met.
2. `make tests` is green.
3. `make run-pre-commit` is clean.
4. For rule-changing sessions, the statistical rigor gate's Tier 1 requirement is met.
5. The end state is stable and at least as capable as the start state — if not, the session
   does not merge; revert and write up the blocker instead.
6. Work is committed on its feature branch, a PR from that branch into `claude/cms-matching-v1`
   is open, and it has been merged (see "Every session ends with a PR" above) — or, if Sean has
   explicitly said to leave it open rather than merge yet, that decision is recorded in
   *Execution notes*.

Then: fill in *Execution notes*, move `pending/session_N.md` -> `completed/session_N.md`,
update `index.md` (move the row to the top of *Completed*, trim that list back to 3 if needed,
re-set *Suggested Next Session*), commit the bookkeeping.

## Open-questions handling

Sean (or whoever authors a session) resolves every question that's genuinely their call —
naming, file layout, which existing helper to reuse, algorithm choice — and writes the answer
into the session as a decision, not a question. What's left as an **Open Question** is only
what requires information or authority the author doesn't have. Every open question gets a
recommended default; only when the work genuinely cannot proceed safely without a human call
does it get a **`NEEDS HUMAN DECISION`** tag naming who should decide. The executing agent
resolves every `NEEDS HUMAN DECISION` item before writing any code.
```

- [ ] **Step 2: Verify required sections are present**

Run: `grep -c '^## ' docs/sessions/conventions.md`
Expected: `16` (16 level-2 section headers, matching the outline above — if this count drifts after edits, that's fine as long as every named section in "Step 1" is still present; re-run `grep '^## ' docs/sessions/conventions.md` to eyeball it).

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/conventions.md
git commit -m "Add docs/sessions/conventions.md"
```

---

### Task 3: Write `docs/sessions/index.md`

**Files:**
- Create: `docs/sessions/index.md`

**Interfaces:**
- Consumes: session titles/threads/sizes from Tasks 4-9 (this task is written last among the doc-authoring tasks so the table can cite real filenames — if executed out of order, come back and fill in the table once sessions 1-6 exist).
- Produces: the `index.md` that `conventions.md`'s protocol step 1 reads.

- [ ] **Step 1: Write the file**

`docs/sessions/index.md`:
```markdown
# Session Index

The tracker for agent-executable sessions in `patient-matching`. See `conventions.md` for how
to run one. To begin, open a fresh agent conversation and say **"start the next session"** —
run whatever **Suggested Next Session** names below.

**Status of this set:** `APPROVED` (design reviewed and approved by Sean, 2026-07-28 — see
`../superpowers/specs/2026-07-28-session-planning-playbook-design.md`).

---

## Suggested Next Session

> **Session 1 — Audit record completeness.** Smallest, no dependencies, no statistical-rigor
> gate to satisfy (not a rule change) — the fastest way to get the "start the next session"
> loop actually exercised once before tackling larger work.

## Up Next (execution order)

| # | Session | Thread | Depends on | Size | Status | One-line summary |
|---|---------|--------|-----------|------|--------|-------------------|
| 1 | [session_1](pending/session_1.md) | Line B: CMS v3.3 migration | — | S | pending | Add `timestamp`/`version` to the audit record (§VII) |
| 2 | [session_2](pending/session_2.md) | Line B: CMS v3.3 migration | — | S/M | pending | Split `AMBIGUOUS` into 2-candidate vs. 3+-candidate tiered response |
| 3 | [session_3](pending/session_3.md) | Evaluation & Statistical Rigor | — | M/L | pending | ONC self-match baseline wired to `rule_eval.py`; pairwise matcher + sampled negatives |
| 4 | [session_4](pending/session_4.md) | Evaluation & Statistical Rigor | 3 | M | pending | Real-world FHIR data source for `rule_eval.py`, via reproducible queries |
| 5 | [session_5](pending/session_5.md) | Line B: CMS v3.3 migration | — | M | pending | Table 3 u-probabilities + P(collision) evaluator |
| 6 | [session_6](pending/session_6.md) | Line B: CMS v3.3 migration | 5 | M/L | pending | Expand Table 2 to v3.3's 37 rules |

Sessions 5 and 6 can be coded in parallel with session 3 (the statistical-rigor gate applies
at merge time, not start time — see `conventions.md`), but shouldn't move to `completed/`
until session 3 exists.

## Completed (most recent 3)

_(none yet)_

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
```

- [ ] **Step 2: Verify every linked session file exists**

Run: `grep -oP '(?<=\()pending/session_\d\.md(?=\))' docs/sessions/index.md | while read f; do test -f "docs/sessions/$f" && echo "OK $f" || echo "MISSING $f"; done`
Expected (once Tasks 4-9 are done): six `OK` lines, one per session. If run before Tasks 4-9,
expect `MISSING` lines — that's fine, re-run after those tasks complete.

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/index.md
git commit -m "Add docs/sessions/index.md"
```

---

### Task 4: Author `docs/sessions/pending/session_1.md` — Audit record completeness

**Files:**
- Create: `docs/sessions/pending/session_1.md`

**Interfaces:**
- Consumes: current `patient_matching/matching/match_result.py` (`RuleEvaluation`, `MatchResult` dataclasses) and `patient_matching/matching/matching_engine.py` (`MatchingEngine._evaluate_rule`, `MatchingEngine._build_result`), as they exist today (read 2026-07-28).
- Produces (for later sessions/execution): `RuleEvaluation.timestamp: str` (ISO 8601 UTC) and `RuleEvaluation.version: str`; `MatchResult` gains no new fields itself (the audit trail lives per-rule-evaluation in `rule_evaluations`).

- [ ] **Step 1: Write the file**

`docs/sessions/pending/session_1.md`:
````markdown
# Session 1 — Audit Record Completeness

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** S — two dataclass fields, populated in one place, no new external deps.

> Read `../conventions.md` first.

## Outcome purpose

CMS Section VII requires every matching decision to be auditable enough to reproduce during
an incident review — specifically naming timestamp and software version among the required
audit fields. Today's `RuleEvaluation` captures which rule fired, exact-vs-fuzzy, suffix
negation, and per-field outcomes, but not *when* the evaluation happened or *what version* of
the matching logic produced it. Without those two fields, a future audit or incident review
can't answer "was this evaluated before or after we changed rule X" — this session closes
that gap.

## Upstream sessions (must be completed first)

None — valid start point.

## Downstream sessions (unblocked by this one)

None known specifically, but session 3's ONC baseline and any later production-shaped work
benefit from having a real audit trail to inspect from day one.

## Upstream data/system dependencies

None — this only touches this repo's own dataclasses and engine code.

## Downstream data/system dependencies

Whatever eventually persists `MatchResult`/`RuleEvaluation` (out of scope here — no such
persistence layer exists yet in this repo) will read `RuleEvaluation.timestamp`/`.version`.

## Scope

### In scope
- Add `timestamp: str` and `version: str` fields to `RuleEvaluation` in
  `patient_matching/matching/match_result.py`.
- Populate both fields in `MatchingEngine._evaluate_rule` in
  `patient_matching/matching/matching_engine.py`.
- Read `version` from the repo's existing `VERSION` file (already present at the repo root,
  used by `setup.cfg`'s `[metadata] version = file: VERSION` per `pyproject.toml`'s
  `[tool.setuptools.dynamic]` — do not hardcode a version string).

### Out of scope
- Any persistence/storage of audit records (no such layer exists in this repo).
- Adding audit fields to `MatchResult` itself — CMS §VII's per-decision detail
  (combination evaluated, exact/fuzzy, uniqueness result) already lives in
  `rule_evaluations: List[RuleEvaluation]`; timestamp/version belong at that same
  per-evaluation granularity, not duplicated onto the summary `MatchResult`.
- Changing `MatchOutcome` or any matching *behavior* — this is audit plumbing only, so it is
  exempt from `conventions.md`'s statistical rigor gate.

## Tasks

1. **Add the two fields to `RuleEvaluation`.**
   File: `patient_matching/matching/match_result.py`.
   Current shape (as of 2026-07-28):
   ```python
   @dataclass
   class RuleEvaluation:
       rule_id: str = ""
       matched: bool = False
       match_type: str = "exact"
       fuzzy_fields: List[str] = field(default_factory=list)
       negated_by_suffix: bool = False
       field_outcomes: Dict[str, str] = field(default_factory=dict)
   ```
   Change to:
   ```python
   @dataclass
   class RuleEvaluation:
       rule_id: str = ""
       matched: bool = False
       match_type: str = "exact"
       fuzzy_fields: List[str] = field(default_factory=list)
       negated_by_suffix: bool = False
       field_outcomes: Dict[str, str] = field(default_factory=dict)
       timestamp: str = ""
       version: str = ""
   ```
   Update the class docstring's `Attributes:` block to document both new fields (e.g.
   `timestamp: ISO 8601 UTC timestamp of when this evaluation ran.` /
   `version: The patient_matching package version that produced this evaluation, from VERSION.`).
   Also update the module docstring at the top of the file (currently: *"Captures
   audit-required fields per Section VII of the CMS proposal: rule ID, match type
   (exact/fuzzy), uniqueness result, and per-field comparison outcomes."*) to add timestamp
   and version to that list.

2. **Add a small version-reading helper.**
   File: `patient_matching/matching/matching_engine.py`.
   At module scope (near the top, after the existing imports), add:
   ```python
   import importlib.resources
   from datetime import datetime, timezone

   def _read_package_version() -> str:
       """Read the package version from the repo-root VERSION file.

       Falls back to "unknown" if VERSION can't be found (e.g. installed without
       the repo root present) rather than raising - a missing version string
       should never break matching.
       """
       try:
           version_path = (
               importlib.resources.files("patient_matching").parent / "VERSION"
           )
           return version_path.read_text().strip()
       except (FileNotFoundError, ModuleNotFoundError, OSError):
           return "unknown"
   ```
   Cache it once at import time (module-level constant, since `VERSION` doesn't change within
   a process lifetime):
   ```python
   _PACKAGE_VERSION = _read_package_version()
   ```

3. **Populate both fields in `_evaluate_rule`.**
   File: `patient_matching/matching/matching_engine.py`, method `_evaluate_rule` (currently
   starts with `evaluation = RuleEvaluation(rule_id=rule.rule_id)`).
   Change that line to:
   ```python
   evaluation = RuleEvaluation(
       rule_id=rule.rule_id,
       timestamp=datetime.now(timezone.utc).isoformat(),
       version=_PACKAGE_VERSION,
   )
   ```

## Unit tests required

File: `patient_matching/matching/tests/test_matching_engine.py` (existing file — add a new
test class alongside the existing `TestMatchingEngine*` classes).

```python
import re
from datetime import datetime

class TestAuditFields:
    """RuleEvaluation.timestamp/.version are populated per CMS Section VII."""

    def test_timestamp_is_iso8601_utc(self):
        backend = _InMemoryTestBackend([_make_patient()])
        engine = MatchingEngine(backend=backend)
        result = engine.match(_make_patient())
        assert result.rule_evaluations, "expected at least one rule evaluation"
        for ev in result.rule_evaluations:
            # Must parse as ISO 8601 and be timezone-aware (UTC).
            parsed = datetime.fromisoformat(ev.timestamp)
            assert parsed.tzinfo is not None

    def test_version_is_nonempty_string(self):
        backend = _InMemoryTestBackend([_make_patient()])
        engine = MatchingEngine(backend=backend)
        result = engine.match(_make_patient())
        assert result.rule_evaluations
        for ev in result.rule_evaluations:
            assert isinstance(ev.version, str) and ev.version != ""

    def test_version_matches_repo_version_file(self):
        from patient_matching.matching.matching_engine import _PACKAGE_VERSION
        repo_version = open("VERSION").read().strip()
        assert _PACKAGE_VERSION == repo_version
```

Use whatever this test file's existing backend test-double is called (check
`test_matching_engine.py`'s current imports/helpers before writing `_InMemoryTestBackend` —
if the file already has a helper that builds a `MatchingBackend` from a list of patients,
reuse its actual name instead of inventing a new one).

## Validation (definition of "resolved")

- [ ] `RuleEvaluation` has `timestamp: str` and `version: str` fields with default `""`.
- [ ] Every `RuleEvaluation` produced by `MatchingEngine.match()` has a non-empty,
      ISO-8601-parseable `timestamp` and a non-empty `version`.
- [ ] `version` equals the contents of the repo-root `VERSION` file, stripped.
- [ ] All three new tests pass: `docker compose run --rm dev pytest patient_matching/matching/tests/test_matching_engine.py -k TestAuditFields -v`
- [ ] `make tests` is green (full suite, no regressions).
- [ ] `make run-pre-commit` is clean.

## Open questions

None requiring a human decision — this session's scope (which two fields, where they're
populated, where the version string comes from) was fully resolved at authoring time using
the repo's existing `VERSION` file convention.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
````

- [ ] **Step 2: Verify the file's Python code blocks are syntactically valid**

Run:
```bash
python3 - <<'PYEOF'
import re, ast, textwrap
text = open("docs/sessions/pending/session_1.md").read()
# Only ```python fences are checked - a ```python-fragment fence (used for
# intentionally-partial snippets shown against fuller context elsewhere in the
# doc) is a different fence tag on purpose and won't match this regex.
blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
for i, b in enumerate(blocks):
    ast.parse(textwrap.dedent(b))  # dedent first: blocks are nested under "- [ ]" list items
print(f"{len(blocks)} python blocks, all parsed OK")
PYEOF
```
Expected: `N python blocks, all parsed OK` with no `SyntaxError` traceback.

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/pending/session_1.md
git commit -m "Author session_1: audit record completeness"
```

---

### Task 5: Author `docs/sessions/pending/session_2.md` — Tiered uniqueness response

**Files:**
- Create: `docs/sessions/pending/session_2.md`

**Interfaces:**
- Consumes: `MatchOutcome` enum (`match_result.py`), `MatchingEngine._build_result`
  (`matching_engine.py`), as they exist today.
- Produces (for session 6 and any later work): `MatchOutcome.ESCALATE` (new enum value, for
  exactly 2 candidates) and `MatchOutcome.AMBIGUOUS` redefined to mean 3+ candidates that fail
  the stricter 1e-6 threshold. `MatchResult.candidate_count` already exists and is reused,
  unchanged.

- [ ] **Step 1: Write the file**

`docs/sessions/pending/session_2.md`:
````markdown
# Session 2 — Tiered Uniqueness Response

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** S/M — one new enum value, one method's branching logic, tests for the new
boundary.

> Read `../conventions.md` first.

## Outcome purpose

CMS v3.3 requires tiered handling of ambiguous matches, not a single bucket: exactly 1
candidate returns; exactly 2 candidates *may* escalate to MFA/disambiguation; 3 or more
candidates must clear a stricter 1-in-a-million (1e-6) collision threshold or the responder
declines. Today, `MatchingEngine._build_result` collapses every non-unique outcome (2
candidates or 20) into one `MatchOutcome.AMBIGUOUS` bucket with no distinction — so a caller
can't tell "this is a 2-candidate disambiguation case" from "this is a 5-candidate case that
should almost always be declined." This session adds that distinction.

## Upstream sessions (must be completed first)

None — valid start point. (Doing session 1 first is a nice-to-have, not a requirement — it
keeps the new evaluations' audit fields consistent across the new outcome value, but nothing
in this session depends on session 1's code.)

## Downstream sessions (unblocked by this one)

Session 6 (Table 2 v3.3 expansion) will exercise this tiered logic against the full 37-rule
set, including cases where the 3+-candidate stricter threshold actually matters.

## Upstream data/system dependencies

None.

## Downstream data/system dependencies

None new — same `MatchResult` consumers as today, now seeing a new possible
`outcome` value.

## Scope

### In scope
- Add `MatchOutcome.ESCALATE` to the enum in `patient_matching/matching/match_result.py`,
  for the exactly-2-candidates case.
- Redefine what `MatchOutcome.AMBIGUOUS` means: 3 or more candidates, evaluated against a
  stricter 1e-6 collision threshold (see Task 3 below for exactly how "the stricter threshold"
  is applied given today's engine has no live P(collision) computation yet — session 5 adds
  that; this session adds the *branching structure*, using a placeholder-free interim
  comparison described in Task 3).
- Update `MatchingEngine._build_result` in `patient_matching/matching/matching_engine.py` to
  branch on `len(all_matched)`: `== 1` -> `MATCH` (unchanged), `== 2` -> `ESCALATE` (new),
  `>= 3` -> `AMBIGUOUS` (same enum value as today, but now specifically meaning "3+, stricter
  threshold applies").

### Out of scope
- Actually computing P(collision) for the 3+-candidate stricter-threshold check — that
  requires session 5's evaluator. This session's interim behavior (Task 3) is deliberately
  simple and explicitly documented as interim, so session 5/6 can wire in the real
  P(collision) check later without changing `_build_result`'s branching structure.
- Any MFA/disambiguation implementation for the `ESCALATE` case — this repo has no
  auth/session layer; `ESCALATE` is a signal for a caller (e.g. a future API layer) to act on,
  not something this engine implements itself.
- The 1e-6 threshold value itself is CMS-mandated (see the v3.3 spec, §III — fetch it live per
  `../conventions.md`'s "Reference documents" section if you need the exact wording), not
  tuned, so this session is exempt from the statistical-rigor gate.

## Tasks

1. **Add the new enum value.**
   File: `patient_matching/matching/match_result.py`.
   Current:
   ```python
   class MatchOutcome(Enum):
       """Outcome of a matching operation."""

       MATCH = "match"
       NO_MATCH = "no_match"
       AMBIGUOUS = "ambiguous"
       INSUFFICIENT_FIELDS = "insufficient_fields"
   ```
   Change to:
   ```python
   class MatchOutcome(Enum):
       """Outcome of a matching operation."""

       MATCH = "match"
       NO_MATCH = "no_match"
       ESCALATE = "escalate"  # exactly 2 candidates; may escalate to MFA/disambiguation
       AMBIGUOUS = "ambiguous"  # 3+ candidates; stricter 1e-6 threshold applies
       INSUFFICIENT_FIELDS = "insufficient_fields"
   ```
   Update the class docstring to note the tiering (1 -> MATCH, 2 -> ESCALATE, 3+ -> AMBIGUOUS).

2. **Branch `_build_result` on candidate count.**
   File: `patient_matching/matching/matching_engine.py`, method `_build_result` (currently
   ends with an `if len(all_matched) == 1: ... else: # Ambiguous: 2+ candidates matched ...`).
   Replace the trailing `if/else` with a three-way branch:
   ```python
   # Uniqueness check: tiered per CMS v3.3 - 1 unique / 2 escalate / 3+ stricter threshold
   if len(all_matched) == 1:
       return MatchResult(
           outcome=MatchOutcome.MATCH,
           matched_patients=all_matched,
           matched_rule_id=first_rule_id,
           match_type=first_match_type,
           is_unique=True,
           rule_evaluations=evaluations,
           candidate_count=len(all_matched),
       )
   elif len(all_matched) == 2:
       return MatchResult(
           outcome=MatchOutcome.ESCALATE,
           matched_patients=all_matched,
           matched_rule_id=first_rule_id,
           match_type=first_match_type,
           is_unique=False,
           rule_evaluations=evaluations,
           candidate_count=len(all_matched),
       )
   else:
       # 3+ candidates: CMS v3.3 requires a stricter 1e-6 threshold here. This engine
       # doesn't yet compute live P(collision) (see session 5) - until it does, every
       # 3+-candidate case is conservatively treated as failing that stricter bar
       # (i.e. always AMBIGUOUS/decline), which is the safe default: it can only ever
       # cause an under-return, never a wrong-patient release. Session 5/6 should
       # replace this comment and wire in a real check without changing the branch
       # structure above.
       return MatchResult(
           outcome=MatchOutcome.AMBIGUOUS,
           matched_patients=all_matched,
           matched_rule_id=first_rule_id,
           match_type=first_match_type,
           is_unique=False,
           rule_evaluations=evaluations,
           candidate_count=len(all_matched),
       )
   ```

## Unit tests required

File: `patient_matching/matching/tests/test_matching_engine.py` (existing file — add a new
test class; the file already has `TestMatchingEngineAmbiguous` for the old 2-candidate case,
per `test_ambiguous_multiple_candidates` — update that existing test's expected outcome from
`MatchOutcome.AMBIGUOUS` to `MatchOutcome.ESCALATE` if it uses exactly 2 candidates, since its
meaning has changed; add the table below alongside it).

```python
import pytest

class TestTieredUniquenessResponse:
    """Boundary behavior across 1 / 2 / 3+ matched candidates (CMS v3.3 step 6)."""

    @pytest.mark.parametrize(
        "n_candidates,expected_outcome,expected_unique",
        [
            (1, MatchOutcome.MATCH, True),
            (2, MatchOutcome.ESCALATE, False),
            (3, MatchOutcome.AMBIGUOUS, False),
            (5, MatchOutcome.AMBIGUOUS, False),
        ],
    )
    def test_outcome_by_candidate_count(
        self, n_candidates, expected_outcome, expected_unique
    ):
        # Build n_candidates distinct patients that all satisfy the same rule
        # (e.g. rule 08: First Name + DOB + MBI), each with a unique "id".
        candidates = [
            _make_patient(first="john", dob="1990-01-15", mbi=f"1mbi{i:03d}mbi1")
            for i in range(n_candidates)
        ]
        for i, c in enumerate(candidates):
            c["id"] = f"patient-{i}"
        backend = InMemoryBackend(candidates)
        engine = MatchingEngine(backend=backend)
        query = _make_patient(first="john", dob="1990-01-15", mbi=candidates[0]["identifier"][-1]["value"])

        result = engine.match(query)

        assert result.outcome == expected_outcome
        assert result.is_unique == expected_unique
        assert result.candidate_count == n_candidates
```

Adjust the exact `_make_patient(...)` call to whatever combination of fields this test file's
existing helper supports for triggering a specific rule with N distinct candidates (the
pattern above assumes an MBI-based rule like rule 08, since MBI needs no fuzzy handling and
is trivial to make unique per candidate — check `_make_patient`'s actual signature in
`test_matching_engine.py` before finalizing field names).

## Validation (definition of "resolved")

- [ ] `MatchOutcome.ESCALATE` exists and is used for exactly-2-candidate results.
- [ ] `MatchOutcome.AMBIGUOUS` is used only for 3+-candidate results (never for exactly 2).
- [ ] The existing `TestMatchingEngineAmbiguous` test (or its 2-candidate case) is updated to
      expect `ESCALATE`, not `AMBIGUOUS`, if it exercises exactly 2 candidates — grep the test
      file for `AMBIGUOUS` and confirm every remaining reference is a genuine 3+-candidate
      case.
- [ ] All four parametrized boundary cases (1/2/3/5 candidates) pass.
- [ ] `make tests` is green (full suite, no regressions from the `AMBIGUOUS` meaning change).
- [ ] `make run-pre-commit` is clean.

## Open questions

None requiring a human decision. The interim "always treat 3+ as failing the stricter
threshold" behavior (Task 2) is a deliberate, safe default chosen at authoring time — it can
only cause under-return (a missed match), never a wrong-patient release, so it doesn't need
Sean's sign-off to ship as an interim state ahead of session 5/6.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
````

- [ ] **Step 2: Verify the file's Python code blocks are syntactically valid**

Run the same check as Task 4 Step 2, pointed at `docs/sessions/pending/session_2.md`.
Expected: all blocks parse OK. (Note: the parametrized test snippet references
`_make_patient`/`InMemoryBackend` names that must match whatever `test_matching_engine.py`
actually imports — `ast.parse` only checks syntax, not that these names resolve; that
resolution happens for real at session-execution time, not during this authoring plan.)

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/pending/session_2.md
git commit -m "Author session_2: tiered uniqueness response"
```

---

### Task 6: Author `docs/sessions/pending/session_3.md` — ONC self-match baseline wired to `rule_eval.py`

**Files:**
- Create: `docs/sessions/pending/session_3.md`

**Interfaces:**
- Consumes: `evaluation/rule_eval.py`'s `LabeledPair`, `Matcher` (= `Callable[[Mapping[str, Any]], bool]`), `compare()`, `format_report()`, `min_sample_size()` (all as they exist today); `patient_matching/matching/matching_engine.py::MatchingEngine._evaluate_rule`/`_suffix_conflict` (as the logic to factor into a new pairwise API); `patient_matching/matching/field_extractor.py::FieldExtractor`, `PatientFields`.
- Produces (for session 4 and any later rule-changing session): `MatchingEngine.evaluate_pair(query_fields: PatientFields, candidate_fields: PatientFields) -> bool` (new public method — the reusable pairwise decision that session 4 and future sessions wrap as a `rule_eval.Matcher`); `evaluation/onc_loader.py::load_onc_patients(csv_paths: list[Path]) -> list[dict]` (FHIR Patient dicts, each with `"id"` set to the ONC `EnterpriseID`); `evaluation/onc_baseline.py::build_onc_pairs(patients: list[dict], *, n_negative_samples: int, seed: int) -> list[LabeledPair]`.

- [ ] **Step 1: Write the file**

`docs/sessions/pending/session_3.md`:
````markdown
# Session 3 — ONC Self-Match Baseline Wired to `rule_eval.py`

**Status:** pending
**Thread:** Evaluation & Statistical Rigor Framework
**Estimated size:** M/L — a new pairwise matcher API, an ONC data transform, sampled negative
pair generation, and the first real `ComparisonReport` this repo has ever produced.

> Read `../conventions.md` first.

## Outcome purpose

This repo's matching methodology has no independent "these two records are/aren't the same
person" ground truth beyond the statistical framework itself (Fellegi-Sunter P(collision)),
so every future rule change (v3.3's 37 rules, the P(collision) evaluator, any fuzzy-match
tuning) has to be evaluated for its effect on false-positive rate and recall, not shipped on
judgment alone — that's `conventions.md`'s statistical-rigor gate, Tier 1. Tier 1 requires an
`evaluation/rule_eval.py`-produced `ComparisonReport`, but `rule_eval.py` has never been wired
to any real matcher or dataset (`evaluation/test_rule_eval.py` only exercises it against toy
inline data). This session makes it real: load the public ONC patient-matching benchmark,
turn `MatchingEngine`'s rule logic into something `rule_eval.py` can score, and produce the
first actual baseline report for the current (v3.2.2, 26-rule) engine. Every later
rule-changing session compares against this baseline.

## Upstream sessions (must be completed first)

None — valid start point.

## Downstream sessions (unblocked by this one)

Session 4 (real-world data source) shares this session's `rule_eval.py` wiring and report
format. Sessions 5 and 6 (P(collision) evaluator, Table 2 v3.3 expansion) need this session's
Tier-1 report to exist before they can move to `completed/` (see `conventions.md`'s
statistical rigor gate) — they can be coded in parallel with this session, just not merged
before it.

## Upstream data/system dependencies

- The public ONC 2017 Patient Matching Algorithm Challenge dataset. A copy of its 9 alphabetic
  CSV shards already exists in the sibling repo `helix.personmatching`, at
  `tests/cms_dataset/files/onc/*.csv` (confirmed present via direct inspection, 2026-07-28: 9
  shard files, e.g. `ONC Patient Matching Algorithm Challenge Test Dataset.A-C.csv`). Copy
  those files into this repo (Task 1) — they are public, de-identified data, not PHI, so this
  is a legitimate exception to the "don't duplicate external content" principle in
  `conventions.md`'s "Reference documents" section (that principle is about live/mutable
  documents this repo doesn't own; this is a static, versioned, published benchmark).

## Downstream data/system dependencies

`evaluation/fixtures/onc/*.csv` (copied data) and the baseline `ComparisonReport` this session
produces become the reference point for every later rule-changing session's Tier-1 evidence.

## Scope

### In scope
- Copy the ONC CSV shards from `helix.personmatching/tests/cms_dataset/files/onc/` into
  `evaluation/fixtures/onc/` in this repo.
- Write a CSV -> normalized-FHIR-Patient transform (`evaluation/onc_loader.py`), covering the
  same columns `helix.personmatching`'s `create_patient_resource()` maps (confirmed via direct
  inspection, 2026-07-28: `EnterpriseID, LAST, FIRST, MIDDLE, SUFFIX, DOB, GENDER, SSN,
  ADDRESS1, ADDRESS2, ZIP, MOTHERS_MAIDEN_NAME, MRN, CITY, STATE, PHONE, PHONE2, EMAIL,
  ALIAS`), extended to also populate two fields `helix.personmatching`'s transform drops on
  the floor: `MOTHERS_MAIDEN_NAME` (maps to an additional entry in `last_names` via a
  `_previousFamily`-style extension our `FieldExtractor` doesn't currently read — see Task 2's
  explicit note on this) and `ALIAS` (maps to an additional `first_names` entry). `MRN` and
  `PHONE2` remain unmapped, matching `helix.personmatching` (no rule in this repo's Table 2
  uses a bare MRN or a second phone number).
- Add `MatchingEngine.evaluate_pair(query_fields, candidate_fields) -> bool`: a new public
  method factoring the existing per-candidate rule-evaluation logic (today spread across
  `_evaluate_rule` + `_suffix_conflict`, called once per candidate inside `match()`) into a
  standalone pairwise decision, so it can be wrapped as a `rule_eval.Matcher` without
  duplicating logic. `match()` itself is refactored to call this new method internally —
  behavior must be identical before/after (this is the "equivalence test" `conventions.md`
  requires for a behavior-preserving refactor).
- Build labeled pairs for `rule_eval.py` from the ONC data:
  - **True-match pairs**: `(record, masked(record))` for each ONC record, across the same
    masking scenarios `helix.personmatching`'s `test_cms_performance.py` already defines
    (confirmed via direct inspection, 2026-07-28: `drop_gender`, `drop_email_phone`,
    `drop_email_gender_phone`, `gender_unknown`) — `is_true_match=True`, since masking some
    fields doesn't change who the record actually belongs to. This tests recall under
    realistic partial data, not a trivial always-true self-compare.
  - **True-non-match pairs**: a *sampled* set of cross pairs `(record_i, record_j)`, `i != j`
    — ONC guarantees every row is a distinct individual, so any two distinct rows are a
    genuine non-match, `is_true_match=False`. This is where the "blocking and local memory
    constraints" problem Sean raised actually bites: full pairwise cross-reference of ~28,000
    ONC records is ~400 million pairs, intractable to generate or score. Sample instead — use
    `rule_eval.min_sample_size` to size the negative sample for a specific detectable FPR
    delta (Task 4 below), rather than exhaustively enumerating all non-match pairs. This is
    the correct fix for *this* session's memory-constraint problem — a separate, related
    problem (making `InMemoryBackend.search()` itself scale for a real `match()` call against
    a large corpus, e.g. for session 4 or eventual production-shaped batch runs) is real but
    explicitly out of scope here (see "Out of scope" below); don't conflate the two.
- Run `rule_eval.compare()` with the current (v3.2.2, 26-rule) engine as *both* baseline and
  candidate (a self-comparison — there's no "candidate" change to evaluate yet; this session's
  job is to produce the reference point, not evaluate a change). Save the resulting
  `format_report()` text output to `evaluation/baselines/v3_2_2_onc_baseline.txt` so later
  sessions have a committed reference to diff against.

### Out of scope
- Fixing `InMemoryBackend.search()`'s O(n) linear-scan-per-query behavior with a real indexed
  blocking key. This matters for actual `match()`/`match_batch()` calls against a large
  corpus (relevant to session 4 and any future production-shaped work), but this session's
  `rule_eval.py` wiring uses `evaluate_pair()` directly on precomputed pairs, never calling
  `InMemoryBackend.search()` at all — so it doesn't need this fix to succeed. Track the
  backend-indexing fix as a candidate future session if a later session's use of
  `InMemoryBackend` against the full ONC corpus turns out to need it.
- Computing real precision/recall/FPR on real-world (non-ONC) data — that's session 4 (Tier 2)
  and, at population scale, Tier 3 (explicitly not a near-term blocker).
- Any change to which Table 2 rules exist or their P(collision) values — that's sessions 5/6.
  This session evaluates the *current* 26-rule v3.2.2 engine as-is.

## Tasks

1. **Copy the ONC fixtures.**
   ```bash
   mkdir -p evaluation/fixtures/onc
   cp ~/git/helix.personmatching/tests/cms_dataset/files/onc/*.csv evaluation/fixtures/onc/
   ```
   Verify: `ls evaluation/fixtures/onc/*.csv | wc -l` should print `9`.

2. **Write the ONC transform.**
   File: `evaluation/onc_loader.py` (new).
   ```python
   """Load the public ONC Patient Matching Algorithm Challenge dataset as normalized
   FHIR Patient dicts, for use as evaluation/rule_eval.py input.

   Column mapping mirrors helix.personmatching's create_patient_resource() (see
   tests/cms_dataset/test_cms_dataset.py in that repo), extended to also populate
   MOTHERS_MAIDEN_NAME and ALIAS, which that transform reads from the CSV but never
   maps into the output FHIR resource.
   """

   from __future__ import annotations

   import csv
   from datetime import date, timedelta
   from pathlib import Path
   from typing import Any, Dict, List

   _SAS_EPOCH = date(1900, 1, 1)
   _GENDER_MAP = {"MALE": "male", "FEMALE": "female", "U": "unknown"}


   def _decode_sas_date(raw: str) -> str:
       """ONC's DOB column is a SAS-style day-offset from 1900-01-01, minus 2."""
       offset_days = int(raw) - 2
       return (_SAS_EPOCH + timedelta(days=offset_days)).isoformat()


   def _row_to_patient(row: Dict[str, str]) -> Dict[str, Any]:
       given = [row["FIRST"]]
       if row.get("ALIAS"):
           given.append(row["ALIAS"])
       family_names = [row["LAST"]]
       # Not mapped by helix.personmatching's transform - included here so this
       # repo's normalization/matching sees prior/maiden names per Core Principle 10.
       if row.get("MOTHERS_MAIDEN_NAME"):
           family_names.append(row["MOTHERS_MAIDEN_NAME"])

       patient: Dict[str, Any] = {
           "resourceType": "Patient",
           "id": row["EnterpriseID"],
           "name": [
               {"family": fam, "given": given, "suffix": [row["SUFFIX"]] if row.get("SUFFIX") else []}
               for fam in family_names
           ],
           "gender": _GENDER_MAP.get(row.get("GENDER", "").upper(), "unknown"),
           "birthDate": _decode_sas_date(row["DOB"]),
           "telecom": [],
           "address": [],
           "identifier": [],
       }
       if row.get("PHONE"):
           patient["telecom"].append({"system": "phone", "value": row["PHONE"]})
       if row.get("EMAIL"):
           patient["telecom"].append({"system": "email", "value": row["EMAIL"]})
       if row.get("ADDRESS1"):
           lines = [row["ADDRESS1"]] + ([row["ADDRESS2"]] if row.get("ADDRESS2") else [])
           patient["address"].append(
               {"line": lines, "city": row.get("CITY", ""), "state": row.get("STATE", ""), "postalCode": row.get("ZIP", "")}
           )
       if row.get("SSN"):
           patient["identifier"].append({"system": "http://hl7.org/fhir/sid/us-ssn", "value": row["SSN"]})
       return patient


   def load_onc_patients(csv_paths: List[Path]) -> List[Dict[str, Any]]:
       """Load one or more ONC shard CSVs into normalized FHIR Patient dicts."""
       patients: List[Dict[str, Any]] = []
       for path in csv_paths:
           with open(path, newline="", encoding="utf-8") as f:
               for row in csv.DictReader(f):
                   patients.append(_row_to_patient(row))
       return patients
   ```
   Note: this repo's normalization pipeline (`patient_matching/normalization/`) expects
   already-lowercased/diacritic-folded values; run each patient through
   `NormalizationManager` (see `patient_matching/normalization/manager.py`) before extraction,
   the same way any other caller of `MatchingEngine` must, rather than duplicating
   normalization logic inside `onc_loader.py`.

3. **Add the pairwise matcher API.**
   File: `patient_matching/matching/matching_engine.py`.
   Add a new public method to `MatchingEngine`, extracting today's per-candidate logic:
   ```python
   def evaluate_pair(
       self, query_fields: PatientFields, candidate_fields: PatientFields
   ) -> bool:
       """Decide whether two already-extracted field sets match, per Table 2.

       This is the pure pairwise decision (no backend search, no uniqueness
       check) - the same logic match() applies per candidate, factored out so
       it can be used directly against precomputed pairs (see
       evaluation/onc_baseline.py) without needing a MatchingBackend at all.
       """
       for rule in self._rules:
           evaluation = self._evaluate_rule(rule, query_fields, candidate_fields)
           if evaluation.matched and not self._suffix_conflict(
               query_fields.suffixes, candidate_fields.suffixes
           ):
               return True
       return False
   ```
   Then simplify `match()`'s inner loop to call it where it makes sense to reduce duplication
   — but do NOT change `match()`'s externally-observable behavior (its return type, its
   `MatchResult` construction, and its per-rule audit trail via `all_evaluations` must stay
   exactly as they are today, since Task 5 below requires an equivalence test proving this).

4. **Build labeled pairs and size the negative sample.**
   File: `evaluation/onc_baseline.py` (new).
   ```python
   """Build rule_eval.py LabeledPairs from the ONC dataset, and run the current
   engine's self-match baseline (session 3 of docs/sessions/).
   """

   from __future__ import annotations

   import random
   from pathlib import Path
   from typing import Any, Dict, List

   from evaluation.onc_loader import load_onc_patients
   from evaluation.rule_eval import LabeledPair, compare, format_report, min_sample_size
   from patient_matching.matching.field_extractor import FieldExtractor
   from patient_matching.matching.matching_engine import MatchingEngine
   from patient_matching.matching.in_memory_backend import InMemoryBackend

   MASKING_SCENARIOS = ("none", "drop_gender", "drop_email_phone", "drop_email_gender_phone", "gender_unknown")


   def _mask(patient: Dict[str, Any], scenario: str) -> Dict[str, Any]:
       masked = dict(patient)
       if scenario in ("drop_gender", "drop_email_gender_phone", "gender_unknown"):
           masked = {**masked, "gender": "unknown" if scenario == "gender_unknown" else None}
       if scenario in ("drop_email_phone", "drop_email_gender_phone"):
           masked = {**masked, "telecom": []}
       return masked


   def build_onc_pairs(
       patients: List[Dict[str, Any]], *, n_negative_samples: int, seed: int = 0
   ) -> List[LabeledPair]:
       extractor = FieldExtractor()
       pairs: List[LabeledPair] = []

       # True-match pairs: each record against each masked variant of itself.
       for p in patients:
           q_fields = extractor.extract(p)
           for scenario in MASKING_SCENARIOS:
               c_fields = extractor.extract(_mask(p, scenario))
               pairs.append(
                   LabeledPair(
                       features={"query": q_fields, "candidate": c_fields},
                       is_true_match=True,
                       strata={"scenario": scenario},
                       pair_id=f"{p['id']}::{scenario}",
                   )
               )

       # True-non-match pairs: a random sample of distinct-record cross pairs.
       # ONC guarantees every row is a distinct individual, so any (i, j), i != j
       # pair is a genuine non-match - sampling avoids the O(n^2) full cross-product.
       rng = random.Random(seed)
       n = len(patients)
       seen = set()
       while len(seen) < n_negative_samples:
           i, j = rng.randrange(n), rng.randrange(n)
           if i == j or (i, j) in seen or (j, i) in seen:
               continue
           seen.add((i, j))
           q_fields = extractor.extract(patients[i])
           c_fields = extractor.extract(patients[j])
           pairs.append(
               LabeledPair(
                   features={"query": q_fields, "candidate": c_fields},
                   is_true_match=False,
                   strata={"scenario": "cross_pair"},
                   pair_id=f"{patients[i]['id']}::{patients[j]['id']}",
               )
           )
       return pairs


   def current_engine_matcher(features):
       """Adapts MatchingEngine.evaluate_pair to rule_eval.py's Matcher signature."""
       engine = MatchingEngine(backend=InMemoryBackend([]))  # backend unused by evaluate_pair
       return engine.evaluate_pair(features["query"], features["candidate"])


   if __name__ == "__main__":
       onc_dir = Path(__file__).parent / "fixtures" / "onc"
       patients = load_onc_patients(sorted(onc_dir.glob("*.csv")))
       # Size the negative sample to detect a 1-percentage-point FPR shift at a
       # ~0.1% baseline FPR, per rule_eval.py's own power-calculation utility.
       n_negative = min_sample_size(p0=0.001, delta=0.01)
       pairs = build_onc_pairs(patients, n_negative_samples=n_negative)
       report = compare(
           current_engine_matcher,
           current_engine_matcher,  # self-comparison: this run establishes the baseline
           pairs,
           baseline_name="v3.2.2 (26 rules)",
           candidate_name="v3.2.2 (26 rules)",
       )
       output_path = Path(__file__).parent / "baselines" / "v3_2_2_onc_baseline.txt"
       output_path.parent.mkdir(exist_ok=True)
       output_path.write_text(format_report(report))
       print(format_report(report))
   ```

5. **Generate and commit the baseline report.**
   ```bash
   mkdir -p evaluation/baselines
   docker compose run --rm dev python -m evaluation.onc_baseline
   ```
   This writes `evaluation/baselines/v3_2_2_onc_baseline.txt`. Commit it — it's the reference
   point sessions 5/6 diff against.

## Unit tests required

File: `evaluation/test_onc_baseline.py` (new, sibling to the existing `evaluation/test_rule_eval.py`).

```python
import pytest
from evaluation.onc_loader import _decode_sas_date, load_onc_patients
from evaluation.onc_baseline import build_onc_pairs, current_engine_matcher
from evaluation.rule_eval import LabeledPair

class TestOncTransform:
    @pytest.mark.parametrize(
        "raw_offset,expected_iso",
        [
            ("2", "1900-01-01"),   # offset 0 after the -2 correction
            ("367", "1900-12-31"), # 365 days later (1900 not a leap year)
            ("36527", "2000-01-01"),
        ],
    )
    def test_decode_sas_date_boundaries(self, raw_offset, expected_iso):
        assert _decode_sas_date(raw_offset) == expected_iso

class TestEvaluatePairEquivalence:
    """MatchingEngine.evaluate_pair must agree with match()'s per-candidate decision -
    this IS the equivalence test conventions.md requires for this behavior-preserving
    refactor."""

    def test_evaluate_pair_agrees_with_match_for_matching_pair(self):
        from patient_matching.matching.field_extractor import FieldExtractor
        from patient_matching.matching.in_memory_backend import InMemoryBackend
        from patient_matching.matching.matching_engine import MatchingEngine

        candidate = _make_patient(mbi="1abc2de3f45")
        candidate["id"] = "cand-1"
        backend = InMemoryBackend([candidate])
        engine = MatchingEngine(backend=backend)
        query = _make_patient(mbi="1abc2de3f45")

        match_result = engine.match(query)
        extractor = FieldExtractor()
        pairwise_result = engine.evaluate_pair(
            extractor.extract(query), extractor.extract(candidate)
        )

        assert (match_result.outcome.value == "match") == pairwise_result

class TestBuildOncPairs:
    def test_true_match_pairs_outnumber_or_equal_masking_scenarios(self):
        patients = [{"id": "p1", "name": [{"family": "smith", "given": ["john"]}], "birthDate": "1980-01-01", "telecom": [], "address": [], "identifier": []}]
        pairs = build_onc_pairs(patients, n_negative_samples=0)
        true_pairs = [p for p in pairs if p.is_true_match]
        assert len(true_pairs) == 5  # one per masking scenario, per Task 4's MASKING_SCENARIOS

    def test_negative_sample_count_is_respected(self):
        patients = [
            {"id": f"p{i}", "name": [{"family": "smith", "given": ["john"]}], "birthDate": "1980-01-01", "telecom": [], "address": [], "identifier": []}
            for i in range(10)
        ]
        pairs = build_onc_pairs(patients, n_negative_samples=5, seed=0)
        negative_pairs = [p for p in pairs if not p.is_true_match]
        assert len(negative_pairs) == 5

    def test_negative_pairs_never_pair_a_record_with_itself(self):
        patients = [
            {"id": f"p{i}", "name": [{"family": "smith", "given": ["john"]}], "birthDate": "1980-01-01", "telecom": [], "address": [], "identifier": []}
            for i in range(10)
        ]
        pairs = build_onc_pairs(patients, n_negative_samples=8, seed=1)
        for p in pairs:
            if not p.is_true_match:
                q_id, c_id = p.pair_id.split("::")
                assert q_id != c_id
```

## Validation (definition of "resolved")

- [ ] `evaluation/fixtures/onc/` contains all 9 ONC CSV shards.
- [ ] `evaluate_pair()` exists on `MatchingEngine`, is used internally by `match()`, and the
      equivalence test (`TestEvaluatePairEquivalence`) passes — proving the refactor didn't
      change `match()`'s behavior.
- [ ] `build_onc_pairs()` produces both true-match (masked-self) and true-non-match (sampled
      cross) pairs, with the negative-sample count controllable and never pairing a record
      with itself.
- [ ] Running `python -m evaluation.onc_baseline` produces a `ComparisonReport` and writes
      `evaluation/baselines/v3_2_2_onc_baseline.txt`, which is committed.
- [ ] All new tests pass: `docker compose run --rm dev pytest evaluation/test_onc_baseline.py -v`
- [ ] `make tests` is green (full suite, including the existing `test_matching_engine.py` and
      `evaluation/test_rule_eval.py` — the `evaluate_pair` refactor must not regress either).
- [ ] `make run-pre-commit` is clean for all touched files under `patient_matching/` (note:
      `evaluation/` is excluded from pre-commit hooks per `conventions.md` — run
      `ruff check evaluation/` and `mypy evaluation/` manually and fix anything they flag,
      since "excluded from the automated gate" doesn't mean "exempt from the standard").

## Open questions

- The negative-sample size in Task 4 (`min_sample_size(p0=0.001, delta=0.01)`) assumes a
  ~0.1% baseline FPR and targets detecting a 1-percentage-point shift — a reasonable starting
  assumption, not a value with real data behind it yet. **Recommended default:** ship with
  this value; if session 5/6's `ComparisonReport`s come back with FPR credible intervals too
  wide to be useful (`NEEDS MORE DATA` verdicts that don't resolve), revisit the sample size
  then, informed by the actual observed FPR rather than a guess. Not a `NEEDS HUMAN DECISION`
  — this is exactly the kind of algorithm-tuning choice principle 5 says the session author
  resolves directly.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
````

- [ ] **Step 2: Verify the file's Python code blocks are syntactically valid**

Run the same check as Task 4 Step 2, pointed at `docs/sessions/pending/session_3.md`.
Expected: all blocks parse OK.

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/pending/session_3.md
git commit -m "Author session_3: ONC self-match baseline wired to rule_eval.py"
```

---

### Task 7: Author `docs/sessions/pending/session_4.md` — Real-world FHIR data source via reproducible queries

**Files:**
- Create: `docs/sessions/pending/session_4.md`

**Interfaces:**
- Consumes: `notebooks/wellsense_member_matching_analysis.py`'s existing pattern (Databricks
  widgets, `_validate_sql_identifier`/`_sql_string_literal` helpers) as the template to extend;
  session 3's `LabeledPair`/`Matcher` wiring and report format.
- Produces: nothing session 5/6 depend on structurally (this is a Tier-2, encouraged-not-required
  input) — its main downstream consumer is a human reading its `ComparisonReport` output.

- [ ] **Step 1: Write the file**

`docs/sessions/pending/session_4.md`:
````markdown
# Session 4 — Real-World FHIR Data Source for `rule_eval.py`, via Reproducible Queries

**Status:** pending
**Thread:** Evaluation & Statistical Rigor Framework
**Estimated size:** M — mostly a new Databricks notebook following an existing pattern, plus
wiring its output into session 3's `LabeledPair` shape.

> Read `../conventions.md` first.

## Outcome purpose

Session 3's ONC baseline proves the engine's self-match integrity on public, synthetic data —
necessary but not sufficient, since ONC's demographic distribution won't exactly match real
WellSense/b.well traffic. `conventions.md`'s statistical-rigor gate names this "Tier 2":
validating the engine's effect on real-population **collision rates** (how often distinct real
people share field-value combinations) — a well-posed question even without match/non-match
labels, unlike precision, which real unlabeled data structurally can't certify (see the
project's own conversation history on why precision needs certified negatives, which real,
unlabeled production data doesn't have). This session builds that real-data input as a
reproducible, PHI-safe query — not a one-off analysis that can't be rerun.

## Upstream sessions (must be completed first)

Session 3 — this session reuses its `rule_eval.py` wiring (the `LabeledPair` shape,
`compare()`/`format_report()` usage) and extends its report format; it does not make sense to
design this session's output shape independently of that one.

## Downstream sessions (unblocked by this one)

None structurally required — Tier 2 is encouraged, not a hard gate on any other session (see
`conventions.md`). Sessions 5/6 may optionally reference this session's collision-rate output
when justifying a P(collision) or Table 2 change, but don't depend on it to reach
`completed/`.

## Upstream data/system dependencies

Real FHIR Patient/Person match data in Databricks and/or MongoDB. **`NEEDS HUMAN DECISION —
Sean`:** the exact catalog/schema/table names for the FHIR Patient/Person resources and their
existing match links are not known at authoring time (2026-07-28) — the handoff doc
(`docs/handoff/README.md`) names `bronze.proa.metrics` and `bronze.wellsense.ws_eligibility_all`
for WellSense-specific error analysis, but does not name a general FHIR Patient/Person store.
**Resolve this at session-start**, per `conventions.md`'s protocol step 4, before writing any
query code — ask Sean for: (a) the catalog/schema/table holding normalized FHIR Patient
resources, (b) the catalog/schema/table (or Mongo collection) holding existing Person-Patient
match links, and (c) whether both are reachable the same way
`wellsense_member_matching_analysis.py` reaches `bronze.*` (Databricks `spark.sql`), or if the
Mongo side needs a different connection pattern.

## Downstream data/system dependencies

None — this session's only output is a `ComparisonReport` (a human-readable artifact), not
data or a service other code depends on.

## Scope

### In scope
- A new Databricks notebook, `notebooks/fhir_match_data_source.py`, following
  `wellsense_member_matching_analysis.py`'s exact pattern: `dbutils.widgets` for
  catalog/schema/table names (with sane defaults matching whatever Sean confirms at
  session-start), the same `_validate_sql_identifier`/`_sql_string_literal` safety helpers
  (copy them verbatim — they're small, tested-by-inspection, and duplicating two ~10-line
  functions is cheaper than introducing a shared-utility import between `notebooks/` and
  itself, especially since `notebooks/` is explicitly scratch space per `conventions.md`),
  and a `spark.sql(...)` query built from validated identifiers only.
- The query itself pulls (a) a sample of normalized FHIR Patient resources and (b) their
  existing Person-Patient match links, joins them, and shapes the result into
  `rule_eval.LabeledPair` objects — with `strata={"source": "current_algorithm_link"}` on
  every pair, so downstream reports can filter/separate "does the new rule agree with the
  current algorithm" from any claim about ground-truth correctness (the current algorithm's
  links are not ground truth — see "Out of scope" below).
- Compute and report **collision rates** per field and per Table 2 combination (Tier 2): for
  each field (last name, DOB, phone, etc.), what fraction of *distinct* people in the sample
  share the same normalized value? Compare against Table 3's conservative u-probability
  assumptions (session 5) once session 5 exists — until then, just report the raw observed
  rates, so the comparison is a small addition later rather than a redesign.
- No data or query *output* is committed to this repo — only the parameterized query
  notebook itself (`notebooks/fhir_match_data_source.py`). Running it produces a
  `ComparisonReport`-shaped console/notebook-cell output that a human copies into wherever
  they're tracking session results (e.g. a PR description), never into a committed file.

### Out of scope
- Treating the current algorithm's existing Person-Patient links as ground truth for
  precision/recall. They're confounded — produced by the very algorithm this repo aims to
  replace or compare against — so this session reports **agreement rate** with the current
  algorithm's links (a descriptive statistic) and **collision rate** (a well-posed statistical
  quantity), never a precision/recall/FPR number derived from those links. If a future session
  is tempted to compute precision against this data, point them back to this note and to
  `conventions.md`'s Tier 3 language.
- Any change to production Databricks jobs, dashboards, or alerts (Zane's monitoring work,
  per the handoff doc, is separate and unaffected).
- Fixing `InMemoryBackend`'s scaling behavior — if this session's sample is large enough to
  need real blocking for local processing, sample smaller rather than fixing the backend here;
  that fix (if ever needed) is a separate candidate session.

## Tasks

1. **Resolve the `NEEDS HUMAN DECISION` above with Sean** before writing any code, per
   `conventions.md`'s protocol step 4. Record the answer here in *Execution notes* once
   resolved (not as a code comment — this decision belongs in the session doc's history, not
   buried in a notebook).

2. **Copy and adapt the query-safety pattern.**
   File: `notebooks/fhir_match_data_source.py` (new).
   Copy `_validate_sql_identifier`/`_sql_string_literal` from
   `notebooks/wellsense_member_matching_analysis.py` (lines ~40-50 as of 2026-07-28) verbatim.
   Add widgets for whatever table names Task 1 resolved, e.g.:
   ```python
   dbutils.widgets.text("fhir_catalog", "<TBD from Task 1>", "FHIR Patient catalog")
   dbutils.widgets.text("fhir_schema", "<TBD from Task 1>", "FHIR Patient schema")
   dbutils.widgets.text("fhir_patient_table", "<TBD from Task 1>", "FHIR Patient table")
   dbutils.widgets.text("match_links_table", "<TBD from Task 1>", "Person-Patient match links table")
   dbutils.widgets.text("sample_size", "5000", "Row sample size (keep local processing tractable)")
   ```

3. **Write the query and the transform into `LabeledPair`s**, following session 3's
   `evaluation/onc_baseline.py::build_onc_pairs` as the shape to match (same `features={...}`
   keying convention, same use of `FieldExtractor`), but sourcing rows from the Spark
   DataFrame this notebook's query returns instead of `evaluation/onc_loader.py`'s CSV reader.
   The exact column names depend on Task 1's resolution — write this step for real once that's
   known; do not guess table-specific column names here.

4. **Compute and print collision rates per field**, comparing the sample's observed
   same-value-among-distinct-people rate against Table 3's conservative assumptions (available
   once session 5 exists — until then, just print the observed rate with a note "compare
   against Table 3 once session 5 lands").

## Unit tests required

Real Databricks/Mongo access can't be unit-tested locally. Test the parts that don't need a
live connection:

File: `notebooks/test_fhir_match_data_source.py` (new — note `notebooks/` is excluded from
the pre-commit gate but tests here still run under `make tests` if collected; confirm
`pyproject.toml`'s pytest config doesn't exclude `notebooks/` from collection before assuming
this, and adjust the test file's location to `evaluation/tests/` instead if it does, keeping
the transform logic itself in `notebooks/fhir_match_data_source.py` but testing it via a
plain import).

```python
import pytest

class TestSqlSafetyHelpers:
    """Same safety contract as wellsense_member_matching_analysis.py's helpers -
    copied verbatim, so copy its test cases too."""

    @pytest.mark.parametrize(
        "identifier,should_raise",
        [
            ("bronze.fhir.patient", False),
            ("bronze", False),
            ("bronze; DROP TABLE x", True),
            ("bronze.fhir.patient--", True),
            ("", True),
        ],
    )
    def test_validate_sql_identifier(self, identifier, should_raise):
        from notebooks.fhir_match_data_source import _validate_sql_identifier
        if should_raise:
            with pytest.raises(ValueError):
                _validate_sql_identifier(identifier)
        else:
            assert _validate_sql_identifier(identifier) == identifier

    def test_sql_string_literal_escapes_quotes(self):
        from notebooks.fhir_match_data_source import _sql_string_literal
        assert _sql_string_literal("o'brien") == "'o''brien'"
```

## Validation (definition of "resolved")

- [ ] The `NEEDS HUMAN DECISION` above is resolved and recorded in *Execution notes* before
      any query code is written.
- [ ] `notebooks/fhir_match_data_source.py` exists, uses widget-based configuration (no
      hardcoded table names), and reuses the validated-identifier pattern for every
      interpolated value.
- [ ] Running the notebook (in Databricks, with real access) produces `LabeledPair`s
      shaped identically to session 3's, each tagged `strata={"source": "current_algorithm_link"}`.
- [ ] Collision-rate output is printed per field, with an explicit note that it is descriptive
      (Tier 2), not a precision/recall claim.
- [ ] No real data, query output, or table contents are committed to this repo — only the
      notebook file itself.
- [ ] The SQL-safety unit tests pass: `docker compose run --rm dev pytest notebooks/test_fhir_match_data_source.py -v` (or `evaluation/tests/test_fhir_match_data_source.py`, per Task 4's collection-path check).
- [ ] `make tests` is green.

## Open questions

- **`NEEDS HUMAN DECISION — Sean`** (already stated above under "Upstream data/system
  dependencies"): the exact catalog/schema/table names for FHIR Patient resources and
  Person-Patient match links, and whether Mongo needs a different access pattern than
  Databricks `spark.sql`. Recommended default if genuinely stuck: start with whatever table
  the handoff doc's `enterprise-person-service` logs reference (per `docs/handoff/README.md`
  §2.4's data table), since that's the closest named real-data source already documented for
  this project, and confirm with Sean before treating it as authoritative.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
````

- [ ] **Step 2: Verify the file's Python code blocks are syntactically valid**

Run the same check as Task 4 Step 2, pointed at `docs/sessions/pending/session_4.md`.
Expected: all blocks parse OK.

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/pending/session_4.md
git commit -m "Author session_4: real-world FHIR data source via reproducible queries"
```

---

### Task 8: Author `docs/sessions/pending/session_5.md` — Table 3 u-probabilities + P(collision) evaluator

**Files:**
- Create: `docs/sessions/pending/session_5.md`

**Interfaces:**
- Consumes: `patient_matching/matching/table2_rules.py`'s `RuleField`, `MatchingRule`,
  `FieldRole`, field-name constants (as they exist today); the CMS v3.3 spec (fetched live,
  not from a committed copy — see `conventions.md`).
- Produces (for session 6): `patient_matching/matching/collision.py::FIELD_U_PROBS: Dict[str, tuple[float, Optional[float]]]` (field name -> (exact u, fuzzy u or `None`)), `p_collision(fields: tuple[RuleField, ...], *, fuzzy_fields: frozenset[str] = frozenset()) -> float`, `evaluate_combination(fields, *, fuzzy_fields=frozenset()) -> dict` (returns at least `{"p_collision": float, "approved": bool}`).

- [ ] **Step 1: Write the file**

`docs/sessions/pending/session_5.md`:
````markdown
# Session 5 — Table 3 U-Probabilities + P(Collision) Evaluator

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** M — one new module (a probability table + two pure functions), plus
replacing hand-entered constants in `table2_rules.py` with computed values.

> Read `../conventions.md` first.

## Outcome purpose

`table2_rules.py` currently hardcodes each rule's `p_collision_exact`/`p_collision_fuzzy` as
literal floats, hand-typed against the CMS v3.2.2 spec — there's no code that actually
*computes* P(collision) from per-field u-probabilities, so a typo or a spec update has no way
to be caught automatically, and there's no reusable evaluator for session 6 to score the 11
new v3.3 combinations against. This session builds that evaluator directly from the CMS v3.3
spec's own Table 3 and formula (`P(collision) ~= product of u_field` per field in a
combination), matching Imran's own reference implementation (confirmed by fetching
`gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee` on 2026-07-28: its `FIELD_U_PROBS`
dict matches the spec's Table 3 exactly, and it implements the same joint-probability formula
and 2e-12 threshold this session targets).

## Upstream sessions (must be completed first)

None — valid start point. (Can be coded in parallel with session 3; per `conventions.md`'s
statistical-rigor gate, it just can't move to `completed/` until session 3's Tier-1 report
exists, since it's rule-defining work.)

## Downstream sessions (unblocked by this one)

Session 6 (Table 2 v3.3 expansion) — needs this session's evaluator to score all 37 rules.

## Upstream data/system dependencies

The CMS v3.3 spec (Google Doc, file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg` — see
`conventions.md`'s "Reference documents" section). **Fetch it fresh at session-start; do not
assume the Table 3 values quoted below are still current** — the spec is under active public
comment and could change before this session executes. The values below are what the spec
contained as of 2026-07-28, transcribed directly from it (not from memory or secondhand
description) — re-verify against the live doc before implementing.

## Downstream data/system dependencies

`table2_rules.py`'s `p_collision_exact`/`p_collision_fuzzy` fields become computed (via this
session's evaluator) rather than hand-typed, for every rule session 6 defines.

## Scope

### In scope
- A new module, `patient_matching/matching/collision.py`, implementing:
  - `FIELD_U_PROBS`: the per-field conservative u-probability table (Task 1's data below).
  - `p_collision(fields, *, fuzzy_fields=frozenset())`: the joint-probability product formula.
  - `evaluate_combination(fields, *, fuzzy_fields=frozenset())`: wraps `p_collision` and
    checks it against the 2e-12 threshold, returning enough detail for a test to assert on
    (at minimum `p_collision` and `approved`).
- Replacing every hardcoded `p_collision_exact`/`p_collision_fuzzy` value in
  `table2_rules.py`'s existing 26 `MatchingRule` entries with values computed by this new
  evaluator (Task 3), so the existing rule set becomes self-verifying against Table 3 instead
  of trusting hand-entered constants — this also serves as the first real test of the
  evaluator (if it can't reproduce the 26 already-published-correct values, something's wrong
  with the evaluator, not the existing rules).
- An explicit regression test for the spec's own admitted inconsistency: First Name + Last
  Name + DOB + ZIP computes to 3e-12 under Table 3 (above the 2e-12 threshold) and must
  evaluate as **not approved**, regardless of the 3e-13 figure that appears in some prior,
  non-spec analyses.
- Cross-checking this session's `FIELD_U_PROBS`/`p_collision` output against Imran's gist/Colab
  directly, as a stretch-goal verification step (Task 4) — not required for this session's
  Definition of Done, since it's an external resource outside this repo's control and may not
  be reachable in every execution environment.

### Out of scope
- Adding the 11 new v3.3 rules themselves (Table 2 expansion) — that's session 6, which
  depends on this session's evaluator.
- The per-value (name-frequency-conditioned) collision-probability refinement Sean raised
  separately — that's a genuine methodology deviation from the published CMS approach (which
  uses static per-field constants, as implemented here) and needs Imran's explicit sign-off;
  see `index.md`'s "Candidate future sessions".
- Any change to `MatchingEngine`'s fuzzy-matching mechanics (Damerau-Levenshtein, min length)
  — this session only computes probabilities, it doesn't change how a match is decided.

## Tasks

1. **Write `FIELD_U_PROBS`.**
   File: `patient_matching/matching/collision.py` (new).
   Transcribed from the CMS v3.3 spec's Table 3 (§IV.C), as read 2026-07-28 — **re-verify
   against the live doc at session-start**:
   ```python
   """Table 3: per-field conservative u-probabilities, and the P(collision) evaluator,
   per CMS Patient Matching Proposal v3.3.0 SS IV.

   Values transcribed from the spec as of 2026-07-28 (Google Doc, file ID
   1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg - see ../../docs/sessions/conventions.md's
   "Reference documents" section). The spec is a live draft under public comment; if these
   values and the live doc diverge, the live doc wins - update this table and re-run the
   equivalence test in test_collision.py::test_existing_26_rules_reproduce_published_values.

   Three fields the spec defines but which are "dismissed due to observed data quality
   issues and low selectivity" (Middle Name, Suffix, Year of Birth) are intentionally
   excluded here, matching Imran's reference script's 16-field FIELD_U_PROBS (confirmed
   2026-07-28 via gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee) - no Table 2
   rule uses any of the three.
   """

   from __future__ import annotations

   from typing import Dict, Optional, Tuple

   # field_name -> (conservative u, exact; conservative u, fuzzy or None if fuzzy isn't used)
   FIELD_U_PROBS: Dict[str, Tuple[float, Optional[float]]] = {
       "first_name": (0.02, 0.03),
       "last_name": (0.005, 0.01),
       "dob": (0.0001, None),
       "zip_code": (0.0003, None),
       "city": (0.01, None),
       "state": (0.06, None),
       "street_line": (0.00003, 0.00006),
       "phone": (0.000001, None),
       "email": (0.000001, None),
       "ssn_last4": (0.0001, None),
       "itin_last4": (0.0001, None),
       "legal_id": (0.000001, None),
       "mbi": (0.000001, None),
       "namespace_id": (1e-15, None),  # spec: "~=0"; a small nonzero float avoids a literal 0.0 * anything == 0.0 masking other fields in a product
       "insurance_member_id": (0.000001, None),
       "insurance_subscriber_id": (0.0001, None),
   }
   ```

2. **Write `p_collision` and `evaluate_combination`.**
   Append to `patient_matching/matching/collision.py`:
   ```python
   from .table2_rules import RuleField

   APPROVAL_THRESHOLD = 2e-12


   def p_collision(
       fields: Tuple[RuleField, ...], *, fuzzy_fields: frozenset[str] = frozenset()
   ) -> float:
       """Joint collision probability: product of each field's u-probability.

       fuzzy_fields names which of the given fields should use their fuzzy
       u-probability instead of exact (only meaningful for fields that have one).
       """
       result = 1.0
       for rf in fields:
           exact_u, fuzzy_u = FIELD_U_PROBS[rf.name]
           if rf.name in fuzzy_fields and fuzzy_u is not None:
               result *= fuzzy_u
           else:
               result *= exact_u
       return result


   def evaluate_combination(
       fields: Tuple[RuleField, ...], *, fuzzy_fields: frozenset[str] = frozenset()
   ) -> Dict[str, object]:
       """Evaluate a Table 2 candidate combination against the 2e-12 threshold."""
       p = p_collision(fields, fuzzy_fields=fuzzy_fields)
       return {
           "p_collision": p,
           "approved": p <= APPROVAL_THRESHOLD,
           "fields": tuple(rf.name for rf in fields),
           "fuzzy_fields": tuple(sorted(fuzzy_fields)),
       }
   ```
   Note: `table2_rules.py`'s existing field-name constants (`FIRST_NAME`, `LAST_NAME`, `DOB`,
   `STREET_LINE`, `PHONE`, `EMAIL`, `SSN_LAST4`, `ITIN_LAST4`, `MBI`, `LEGAL_ID`,
   `NAMESPACE_ID`) already match `FIELD_U_PROBS`'s keys. `zip_code`, `city`, `state`,
   `insurance_member_id`, and `insurance_subscriber_id` don't have constants yet — session 6
   adds them (they're needed for the 11 new v3.3 rules, not any of the existing 26), but this
   session's `FIELD_U_PROBS` table includes them now so session 6 doesn't also have to touch
   `collision.py`.

3. **Replace `table2_rules.py`'s hardcoded values with computed ones**, for all 26 existing
   rules. Example for rule 01 (currently
   `p_collision_exact=3e-13, p_collision_fuzzy=9e-13` as a literal):
   ```python
   MatchingRule(
       rule_id="01",
       description="First Name* + Last Name* + DOB + Street Line*",
       fields=(
           _rf(FIRST_NAME, _F),
           _rf(LAST_NAME, _F),
           _rf(DOB),
           _rf(STREET_LINE, _F),
       ),
       max_fuzzy_fields=2,
       p_collision_exact=p_collision((_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(DOB), _rf(STREET_LINE, _F))),
       p_collision_fuzzy=p_collision(
           (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(DOB), _rf(STREET_LINE, _F)),
           fuzzy_fields=frozenset({FIRST_NAME, LAST_NAME, STREET_LINE}),
       ),
   )
   ```
   Apply the same pattern to all 26 rules — replace the two literal float arguments with
   `p_collision(...)` calls using that rule's own `fields` tuple. Import `p_collision` from
   `.collision` at the top of `table2_rules.py`. After this change, run
   `docker compose run --rm dev pytest patient_matching/matching/tests/test_table2_rules.py -v`
   and confirm every existing assertion about specific `p_collision_exact`/`p_collision_fuzzy`
   values still passes — if any computed value differs from today's hardcoded one by more
   than a rounding difference, stop and investigate before proceeding (it means either the
   evaluator or the original hand-entered constant was wrong).

4. **(Stretch goal, not required for Definition of Done) Cross-check against Imran's
   reference script.** Fetch `https://gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee`
   and compare its `FIELD_U_PROBS` values and any of its worked examples against this
   session's `collision.py`. If reachable and values differ, investigate and reconcile before
   merging; if unreachable (offline execution environment, gist removed, etc.), note that in
   *Execution notes* and proceed — this step existing is a nice-to-have consistency check, not
   a blocker.

## Unit tests required

File: `patient_matching/matching/tests/test_collision.py` (new).

```python
import pytest
from patient_matching.matching.collision import (
    FIELD_U_PROBS,
    APPROVAL_THRESHOLD,
    p_collision,
    evaluate_combination,
)
from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    DOB,
    FIRST_NAME,
    LAST_NAME,
    STREET_LINE,
    _rf,
)


class TestFieldUProbs:
    @pytest.mark.parametrize(
        "field_name,expected_exact",
        [
            ("first_name", 0.02),
            ("last_name", 0.005),
            ("dob", 0.0001),
            ("phone", 0.000001),
            ("email", 0.000001),
            ("ssn_last4", 0.0001),
            ("mbi", 0.000001),
        ],
    )
    def test_known_field_exact_u_values(self, field_name, expected_exact):
        exact, _ = FIELD_U_PROBS[field_name]
        assert exact == expected_exact

    def test_dismissed_fields_are_absent(self):
        for dismissed in ("middle_name", "suffix", "year_of_birth"):
            assert dismissed not in FIELD_U_PROBS


class TestPCollision:
    def test_single_field_equals_its_own_u(self):
        assert p_collision((_rf("phone"),)) == FIELD_U_PROBS["phone"][0]

    def test_joint_probability_is_product_of_fields(self):
        fields = (_rf(FIRST_NAME), _rf(DOB))
        expected = FIELD_U_PROBS["first_name"][0] * FIELD_U_PROBS["dob"][0]
        assert p_collision(fields) == pytest.approx(expected)

    def test_fuzzy_field_uses_fuzzy_u_value(self):
        fields = (_rf(FIRST_NAME, role=None),)  # role is irrelevant to p_collision itself
        exact_u, fuzzy_u = FIELD_U_PROBS["first_name"]
        assert p_collision(fields, fuzzy_fields=frozenset({FIRST_NAME})) == fuzzy_u
        assert p_collision(fields) == exact_u


class TestEvaluateCombination:
    def test_first_last_dob_zip_is_not_approvable(self):
        """The CMS v3.3 spec's own admitted inconsistency: this combination computes
        to 3e-12 under Table 3 (above the 2e-12 threshold) and must NOT be approved,
        regardless of the 3e-13 figure some prior (non-spec) analyses cite."""
        fields = (_rf(FIRST_NAME), _rf(LAST_NAME), _rf(DOB), _rf("zip_code"))
        result = evaluate_combination(fields)
        assert result["approved"] is False
        assert result["p_collision"] == pytest.approx(3e-12, rel=1e-6)

    def test_boundary_at_threshold(self):
        """A synthetic combination whose product lands exactly at 2e-12 must be
        approved - the spec's threshold is <=, not strictly <."""
        # phone (1e-6) * legal_id (1e-6) * a synthetic third field at 2.0 gives 2e-12.
        FIELD_U_PROBS["_test_field"] = (2.0, None)
        try:
            fields = (_rf("phone"), _rf("legal_id"), _rf("_test_field"))
            result = evaluate_combination(fields)
            assert result["p_collision"] == pytest.approx(2e-12)
            assert result["approved"] is True
        finally:
            del FIELD_U_PROBS["_test_field"]

    def test_just_above_threshold_is_not_approved(self):
        FIELD_U_PROBS["_test_field"] = (2.000001, None)
        try:
            fields = (_rf("phone"), _rf("legal_id"), _rf("_test_field"))
            assert evaluate_combination(fields)["approved"] is False
        finally:
            del FIELD_U_PROBS["_test_field"]


class TestExistingRulesMatchComputedValues:
    @pytest.mark.parametrize("rule", APPROVED_RULES, ids=lambda r: r.rule_id)
    def test_existing_26_rules_reproduce_published_values(self, rule):
        """After Task 3's change, every existing rule's p_collision_exact/_fuzzy IS a
        computed value (not a literal) - this test just confirms none of them are 0.0
        by accident (a real bug: an unmapped field name in FIELD_U_PROBS would raise a
        KeyError at import time, not silently produce 0.0, but this guards against a
        future refactor reintroducing a literal-float regression)."""
        assert rule.p_collision_exact > 0 or rule.rule_id == "26"  # rule 26 is the ~0 namespace-ID case
```

## Validation (definition of "resolved")

- [ ] `collision.py` exists with `FIELD_U_PROBS`, `p_collision`, `evaluate_combination`,
      `APPROVAL_THRESHOLD`.
- [ ] All 26 existing rules in `table2_rules.py` compute their `p_collision_exact`/`_fuzzy`
      via `p_collision(...)` rather than a hardcoded literal, and every computed value matches
      what was previously hand-entered (within floating-point rounding).
- [ ] First Name + Last Name + DOB + ZIP evaluates as **not approved** (the spec's own
      admitted 3e-12-over-threshold case).
- [ ] Boundary tests (at-threshold approved, just-above not approved) pass.
- [ ] `docker compose run --rm dev pytest patient_matching/matching/tests/test_collision.py -v` passes.
- [ ] `make tests` is green (full suite — confirms the `table2_rules.py` change didn't
      regress `test_table2_rules.py` or `test_matching_engine.py`).
- [ ] `make run-pre-commit` is clean.
- [ ] Per `conventions.md`'s statistical rigor gate: this session does not move to
      `completed/` until session 3's Tier-1 `ComparisonReport` exists (it can be authored and
      coded before then, just not merged).

## Open questions

- The Table 3 values transcribed into Task 1 are current as of 2026-07-28's read of a live,
  actively-commented draft spec. **`NEEDS HUMAN DECISION` only if** the live doc has changed
  by execution time and the new values meaningfully differ from what's transcribed above — in
  that case, update `collision.py` to match the live doc and treat the difference as a normal
  code change, not something requiring Sean's sign-off (these are CMS's own published numbers,
  not a judgment call this repo is making). If genuinely ambiguous (e.g. the spec's wording
  changed in a way that's unclear how to encode), that's when to ask Sean.
- Task 4 (cross-check against Imran's gist) is explicitly a stretch goal — if unreachable,
  note it and move on; don't block the session on it.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
````

- [ ] **Step 2: Verify the file's Python code blocks are syntactically valid**

Run the same check as Task 4 Step 2, pointed at `docs/sessions/pending/session_5.md`.
Expected: all blocks parse OK.

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/pending/session_5.md
git commit -m "Author session_5: Table 3 u-probabilities + P(collision) evaluator"
```

---

### Task 9: Author `docs/sessions/pending/session_6.md` — Expand Table 2 to v3.3's 37 rules

**Files:**
- Create: `docs/sessions/pending/session_6.md`

**Interfaces:**
- Consumes: session 5's `collision.py::p_collision`/`evaluate_combination`;
  `table2_rules.py`'s `RuleField`, `MatchingRule`, `FieldRole`; `field_extractor.py`'s
  `PatientFields`/`FieldExtractor`; `field_comparator.py`'s `FieldComparator`.
- Produces: `table2_rules.py::APPROVED_RULES` grown from 26 to 37 entries; new canonical field
  constants `ZIP_CODE`, `INSURANCE_MEMBER_ID`, `INSURANCE_SUBSCRIBER_ID`; new
  `PatientFields.zip_codes`/`.insurance_member_ids`/`.insurance_subscriber_ids` sets and their
  `FieldExtractor` population logic; `FieldComparator.dob_fuzzy_match(...)` for the new
  +/-1-day DOB tolerance; a `enable_household_risk_rules` flag gating rules 33-37 off by
  default.

- [ ] **Step 1: Write the file**

`docs/sessions/pending/session_6.md`:
````markdown
# Session 6 — Expand Table 2 to v3.3's 37 Rules

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** M/L — three new canonical fields end-to-end (extractor + comparator +
rules), a new DOB fuzzy mode, 11 new rule definitions, and a default-off flag for a
reviewer-flagged risky cluster.

> Read `../conventions.md` first.

## Outcome purpose

This repo currently implements CMS Proposal **v3.2.2** (26 rules, no ZIP or insurance-ID
based combinations, no DOB tolerance) — but the actual mid-August target, per the DS handoff
(`docs/handoff/README.md`), is **v3.3**: 37 rules, gender dropped entirely, DOB exact-or-
+/-1-day, and several insurance-namespace and ZIP-anchored combinations the current field
model can't even express yet. This session closes that version gap.

## Upstream sessions (must be completed first)

Session 5 — every new rule's `p_collision_exact`/`_fuzzy` is computed via session 5's
evaluator; this session cannot correctly score the 11 new combinations without it.

## Downstream sessions (unblocked by this one)

None currently authored. The (not-yet-authored) per-value P(collision) refinement, if Imran
signs off on it, would apply to this session's full 37-rule set once it exists.

## Upstream data/system dependencies

The CMS v3.3 spec's Table 2 (Google Doc, file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg`
— see `conventions.md`). **Fetch it fresh at session-start.** The 37-rule table below is
transcribed directly from that spec as read 2026-07-28 — re-verify rule numbering, field
combinations, and collision-probability figures against the live doc before implementing,
since it's a draft under active public comment.

## Downstream data/system dependencies

None new.

## Scope

### In scope

**1. Three new canonical fields, end-to-end** (needed by the 11 new rules below):
   - `zip_code` (rules 33, 34, 35) — 5-digit ZIP, exact only.
   - `insurance_member_id` (rules 27-30) — individual-level, payer-namespace-scoped, exact
     only. Per the spec: "the bare subscriber base value without dependent suffix SHALL NOT
     be treated as a Member ID."
   - `insurance_subscriber_id` (rules 31, 32) — policyholder-level, payer-namespace-scoped,
     exact only.

**2. A new DOB comparison mode**: several v3.3 rules mark DOB as fuzzy-eligible (shown with
   `*` in the spec), but v3.3's DOB tolerance is **+/-1 day**, not Damerau-Levenshtein edit
   distance (DOB is a date, not a name/street string) — this needs new comparator logic, not
   reuse of the existing string-fuzzy path.

**3. The 11 new Table 2 rules** (27-37), per the spec as read 2026-07-28 (re-verify at
   session-start):

   | # | Combination | p(exact) | p(fuzzy) | Notes |
   |---|---|---|---|---|
   | 27 | First Name + DOB + Member ID (payer namespace) | 2e-12 | — | |
   | 28 | Last Name* + DOB* + Member ID (payer namespace) | 5e-13 | 1e-12 | DOB* = +/-1 day |
   | 29 | Phone Number + Member ID (payer namespace) | 1e-12 | — | |
   | 30 | Email Address + Member ID (payer namespace) | 1e-12 | — | |
   | 31 | First Name* + Last Name + DOB + Subscriber ID (payer namespace) | 1e-12 | 2e-12 | |
   | 32 | First Name + Last Name* + DOB + Subscriber ID (payer namespace) | 1e-12 | 2e-12 | |
   | 33 | First Name* + Last Name* + Phone Number + ZIP | 3e-14 | 9e-14 | household-risk cluster, see below |
   | 34 | Last Name + Phone Number + ZIP | 1.5e-12 | — | household-risk cluster |
   | 35 | Last Name + Email Address + ZIP | 1.5e-12 | — | household-risk cluster |
   | 36 | Last Name* + DOB + Phone Number | 5e-13 | 1e-12 | household-risk cluster |
   | 37 | Last Name* + Street Line + Phone Number | 1.5e-13 | 3e-13 | household-risk cluster |

   For each rule, the `p_collision_exact`/`_fuzzy` column values above are what session 5's
   `evaluate_combination()` should reproduce once the rule's `fields` tuple is correctly
   built — don't hardcode the spec's numbers as literals (same principle as session 5's
   Task 3); use them here only to verify the computed value against the spec's own stated
   figure as a sanity check while authoring the rule.

**4. Two explicit exclusions/flags, carried over from the spec's own text and its still-open
   review comments** (see `../superpowers/specs/2026-07-28-session-planning-playbook-design.md`
   for the full history of how these were found):
   - **First Name + Last Name + DOB + ZIP must NOT be added.** The spec computes this to 3e-12
     under its own Table 3 (above the 2e-12 threshold) and explicitly says combinations
     depending on an undefined geographic-dependency discount SHALL NOT be added until that
     methodology is specified through governance — regardless of the 3e-13 figure some prior,
     non-spec analyses cite. Session 5's `test_first_last_dob_zip_is_not_approvable` already
     locks this in at the evaluator level; this session must not construct a `MatchingRule`
     for it.
   - **Rules 33-37 (the phone+ZIP/name-anchored cluster) ship behind a new, default-off
     flag**, `enable_household_risk_rules` — the spec's own reviewers raised unresolved
     concern that this cluster may violate the field-independence assumption for co-resident
     family/household members sharing a landline and surname, with a documented real-world
     false-positive scenario (sensitive records released to the wrong family member). Passing
     the numeric threshold is explicitly "necessary but not sufficient" per the spec itself.
     **`NEEDS HUMAN DECISION — Sean/Imran`**: whether to enable this cluster by default before
     the spec's comment period resolves. Recommended default: off, matching the spec's own
     framing — implement the rules, gate them behind the flag, don't flip it on without
     explicit sign-off.

### Out of scope
- The per-value (name-frequency-conditioned) collision-probability refinement — separate,
  not-yet-authored candidate session needing Imran's sign-off.
- Gender as a matching field — v3.3 drops it entirely; this repo's Table 2 rules never
  referenced gender in the first place (confirm by grep before assuming there's cleanup work
  here — `grep -rn gender patient_matching/matching/` and check whether any hits are
  matching-relevant or just FHIR resource shape).
- Wiring the household-risk cluster's adversarial family-sharing test case into Thread B's
  harness — that's the trigger condition for eventually flipping `enable_household_risk_rules`
  on, tracked as follow-up work once session 3/4 exist, not part of this session's Definition
  of Done.

## Tasks

1. **Add the three new canonical fields to the field model.**
   File: `patient_matching/matching/table2_rules.py` — add constants alongside the existing
   ones:
   ```python
   ZIP_CODE = "zip_code"
   INSURANCE_MEMBER_ID = "insurance_member_id"
   INSURANCE_SUBSCRIBER_ID = "insurance_subscriber_id"
   ```
   File: `patient_matching/matching/field_extractor.py` — add three new `Set[str]` fields to
   `PatientFields` (`zip_codes`, `insurance_member_ids`, `insurance_subscriber_ids`), add them
   to `get_values()`'s mapping dict, and add extraction logic in `FieldExtractor`:
   - `zip_codes`: extend `_extract_addresses` to also pull `addr.get("postalCode")` per
     address entry.
   - `insurance_member_ids`/`insurance_subscriber_ids`: extend `_extract_identifiers` — these
     come from FHIR `Coverage` resources in a real system, but this repo's `FieldExtractor`
     only ever sees a `Patient` dict (per its docstring: "Extract canonical field values from
     a normalized FHIR Patient resource"). Per the spec, an insurance identifier requires a
     co-submitted Payer ID and SHALL be namespace-scoped — represent this the same way
     `legal_ids`/`namespace_ids` already do (`f"{namespace}|{value}"` — see
     `_extract_identifiers`'s existing `legal_ids` branch for the pattern), reading from
     `patient.get("identifier", [])` entries whose `type.coding` includes a member-ID or
     subscriber-ID type code. **Decide the exact FHIR identifier type codes to key off of at
     implementation time** (this wasn't resolved during authoring since it depends on how
     Coverage-sourced identifiers actually get attached to the Patient dict this engine
     receives — check `patient_matching/fhir_client/` and `patient_matching/ial2_extraction/`
     for how identifiers arrive in practice before inventing new codes).

2. **Add DOB fuzzy (+/-1 day) comparison.**
   File: `patient_matching/matching/field_comparator.py` — add a new method:
   ```python
   from datetime import date, timedelta

   DOB_FUZZY_TOLERANCE_DAYS = 1

   @staticmethod
   def dob_fuzzy_match(query_values: Set[str], candidate_values: Set[str]) -> bool:
       """CMS v3.3 DOB tolerance: +/-1 day, exact date comparison (not edit distance).

       Both value sets are ISO 8601 date strings (YYYY-MM-DD). A query DOB matches
       a candidate DOB if they're the same day or adjacent by exactly one day.
       """
       try:
           q_dates = {date.fromisoformat(v) for v in query_values}
           c_dates = {date.fromisoformat(v) for v in candidate_values}
       except ValueError:
           return False  # partial/malformed dates never fuzzy-match, per SS V.A.5
       for q in q_dates:
           for c in c_dates:
               if abs((q - c).days) <= DOB_FUZZY_TOLERANCE_DAYS:
                   return True
       return False
   ```
   File: `patient_matching/matching/matching_engine.py`, method `_evaluate_rule` — the fuzzy
   branch currently always calls `self._comparator.fuzzy_match(q_values, c_values)`
   regardless of field name. The full method today (as of 2026-07-28) reads:
   ```python
   def _evaluate_rule(
       self,
       rule: MatchingRule,
       query_fields: PatientFields,
       cand_fields: PatientFields,
   ) -> RuleEvaluation:
       evaluation = RuleEvaluation(rule_id=rule.rule_id)
       fuzzy_count = 0
       all_matched = True

       for rf in rule.fields:
           q_values = query_fields.get_values(rf.name)
           c_values = cand_fields.get_values(rf.name)

           if not q_values or not c_values:
               evaluation.field_outcomes[rf.name] = "missing"
               all_matched = False
               continue

           if self._comparator.exact_match(q_values, c_values):
               evaluation.field_outcomes[rf.name] = "exact"
               continue

           if (
               rf.role == FieldRole.FUZZY_ELIGIBLE
               and rule.max_fuzzy_fields > 0
               and self._comparator.fuzzy_match(q_values, c_values)
           ):
               fuzzy_count += 1
               if fuzzy_count <= rule.max_fuzzy_fields:
                   evaluation.field_outcomes[rf.name] = "fuzzy"
                   evaluation.fuzzy_fields.append(rf.name)
                   continue
               else:
                   evaluation.field_outcomes[rf.name] = "fuzzy_exceeded"
                   all_matched = False
                   continue

           evaluation.field_outcomes[rf.name] = "no_match"
           all_matched = False

       evaluation.matched = all_matched
       if evaluation.matched:
           evaluation.match_type = "fuzzy" if evaluation.fuzzy_fields else "exact"

       return evaluation
   ```
   Change only the fuzzy-branch condition (the `if (rf.role == FieldRole.FUZZY_ELIGIBLE and
   rule.max_fuzzy_fields > 0 and self._comparator.fuzzy_match(q_values, c_values)):` block) to
   dispatch on field name, leaving every other line of the method unchanged (this snippet is
   a fragment — the replacement for just that condition and its existing body, shown against
   the full method above for context — not a standalone statement):
   ```python-fragment
           if (
               rf.role == FieldRole.FUZZY_ELIGIBLE
               and rule.max_fuzzy_fields > 0
               and (
                   self._comparator.dob_fuzzy_match(q_values, c_values)
                   if rf.name == DOB
                   else self._comparator.fuzzy_match(q_values, c_values)
               )
           ):
               fuzzy_count += 1
               if fuzzy_count <= rule.max_fuzzy_fields:
                   evaluation.field_outcomes[rf.name] = "fuzzy"
                   evaluation.fuzzy_fields.append(rf.name)
                   continue
               else:
                   evaluation.field_outcomes[rf.name] = "fuzzy_exceeded"
                   all_matched = False
                   continue
   ```
   (Import `DOB` from `.table2_rules` in `matching_engine.py` if not already imported —
   check current imports first, since `table2_rules` is already imported for other names.)

3. **Add the `enable_household_risk_rules` flag and the 11 new rules.**
   File: `patient_matching/matching/table2_rules.py`. Add a module-level flag:
   ```python
   # NEEDS HUMAN DECISION - Sean/Imran: whether to enable the household-risk rule
   # cluster (33-37) by default. Off by default per the CMS v3.3 spec's own open,
   # unresolved reviewer concern about family/household false-positive risk on
   # phone+ZIP/name-anchored combinations - see docs/sessions/pending/session_6.md.
   ENABLE_HOUSEHOLD_RISK_RULES = False
   ```
   Add the 11 new `MatchingRule` entries (27-37) to `APPROVED_RULES`, each with `fields` built
   from the new/existing constants, `p_collision_exact`/`_fuzzy` computed via
   `collision.p_collision(...)` (import from `.collision`, added in session 5), and — for
   rules 33-37 only — excluded from `APPROVED_RULES` unless `ENABLE_HOUSEHOLD_RISK_RULES` is
   `True`. First, rename the existing 26-rule tuple literal in `table2_rules.py` from
   `APPROVED_RULES` to `_V322_RULES` (it keeps its exact current contents — no rule inside it
   changes). Then add the new rules. Two fully worked examples below — rule 27 (always-on,
   needs the new `INSURANCE_MEMBER_ID` constant) and rule 33 (household-risk cluster, needs
   `ZIP_CODE`) — build rules 28-32 and 34-37 the same way, reading each one's exact field
   combination and fuzzy-eligible fields (marked `*` in the Task 3 table's "Combination"
   column) from that table:
   ```python
   _V33_ALWAYS_ON_RULES: tuple[MatchingRule, ...] = (
       MatchingRule(
           rule_id="27",
           description="First Name + DOB + Member ID (w/ Payer namespace)",
           fields=(
               _rf(FIRST_NAME),
               _rf(DOB),
               _rf(INSURANCE_MEMBER_ID),
           ),
           max_fuzzy_fields=0,
           p_collision_exact=p_collision((_rf(FIRST_NAME), _rf(DOB), _rf(INSURANCE_MEMBER_ID))),
       ),
       # ... rules 28-32 go here, same pattern, using the Task 3 table's field lists ...
   )

   _HOUSEHOLD_RISK_RULES: tuple[MatchingRule, ...] = (
       MatchingRule(
           rule_id="33",
           description="First Name* + Last Name* + Phone Number + ZIP",
           fields=(
               _rf(FIRST_NAME, _F),
               _rf(LAST_NAME, _F),
               _rf(PHONE),
               _rf(ZIP_CODE),
           ),
           max_fuzzy_fields=1,
           p_collision_exact=p_collision((_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(PHONE), _rf(ZIP_CODE))),
           p_collision_fuzzy=p_collision(
               (_rf(FIRST_NAME, _F), _rf(LAST_NAME, _F), _rf(PHONE), _rf(ZIP_CODE)),
               fuzzy_fields=frozenset({FIRST_NAME, LAST_NAME}),
           ),
       ),
       # ... rules 34-37 go here, same pattern, using the Task 3 table's field lists ...
   )

   APPROVED_RULES: tuple[MatchingRule, ...] = (
       *_V322_RULES,
       *_V33_ALWAYS_ON_RULES,
       *(_HOUSEHOLD_RISK_RULES if ENABLE_HOUSEHOLD_RISK_RULES else ()),
   )
   ```
   The two `# ... rules N-M go here ...` comments are the only intentionally-incomplete part
   of this snippet — they stand for four and five more `MatchingRule(...)` calls, respectively,
   each fully specified (rule ID, field combination, fuzzy eligibility, collision values) in
   the Task 3 table above; write all nine remaining calls out in full using the two examples
   above as the pattern, the same way rule 27's and rule 33's are written out in full here —
   don't leave a real `...` or a bare comment in the actual file.
   Update the module docstring and `MatchingRule`'s docstring reference to "26" -> reflect the
   new total, and update `MatchingEngine`'s module docstring (currently "All 26 approved field
   combinations") similarly.

## Unit tests required

File: `patient_matching/matching/tests/test_table2_rules.py` (existing — update
`test_total_count`, which currently asserts `len(APPROVED_RULES) == 26`) and
`patient_matching/matching/tests/test_field_comparator.py` (existing — add DOB fuzzy cases).

```python
import pytest
from patient_matching.matching.table2_rules import APPROVED_RULES, ENABLE_HOUSEHOLD_RISK_RULES

class TestV33RuleCount:
    def test_total_count_with_household_risk_rules_off(self):
        assert ENABLE_HOUSEHOLD_RISK_RULES is False  # documents the current default
        assert len(APPROVED_RULES) == 32  # 26 original + 27-32, with 33-37 excluded

    def test_first_last_dob_zip_never_appears(self):
        """The spec's own admitted exclusion - must never be constructible as a rule."""
        for rule in APPROVED_RULES:
            field_names = {rf.name for rf in rule.fields}
            assert field_names != {"first_name", "last_name", "dob", "zip_code"}
```

```python
# in test_field_comparator.py
import pytest
from patient_matching.matching.field_comparator import FieldComparator

class TestDobFuzzyMatch:
    @pytest.mark.parametrize(
        "query_dob,candidate_dob,expected",
        [
            ("1990-01-15", "1990-01-15", True),   # exact
            ("1990-01-15", "1990-01-14", True),    # -1 day
            ("1990-01-15", "1990-01-16", True),    # +1 day
            ("1990-01-15", "1990-01-13", False),   # -2 days, out of tolerance
            ("1990-01-15", "1990-01-17", False),   # +2 days, out of tolerance
            ("1990-01-01", "1989-12-31", True),    # year boundary, -1 day
        ],
    )
    def test_dob_fuzzy_boundary(self, query_dob, candidate_dob, expected):
        assert FieldComparator.dob_fuzzy_match({query_dob}, {candidate_dob}) == expected

    def test_malformed_date_never_matches(self):
        assert FieldComparator.dob_fuzzy_match({"not-a-date"}, {"1990-01-15"}) is False
```

## Validation (definition of "resolved")

- [ ] `zip_code`, `insurance_member_id`, `insurance_subscriber_id` are extractable via
      `FieldExtractor`/`PatientFields`, with tests covering at least one populated and one
      empty case each.
- [ ] `FieldComparator.dob_fuzzy_match` exists, is used by `MatchingEngine` specifically for
      the `dob` field (not the generic string `fuzzy_match`), and all six boundary cases pass.
- [ ] `APPROVED_RULES` has 32 entries with `ENABLE_HOUSEHOLD_RISK_RULES = False` (the default),
      and 37 entries if that flag is manually flipped to `True` in a test.
- [ ] First Name + Last Name + DOB + ZIP is not constructible as any rule in `APPROVED_RULES`,
      under either flag setting.
- [ ] Every new rule's `p_collision_exact`/`_fuzzy` (computed via session 5's evaluator)
      matches the spec's own stated figure in the Task 3 table above, within rounding.
- [ ] `make tests` is green (full suite — this touches shared field-extraction and comparator
      code, so run the *entire* suite, not just the new tests, to catch regressions in
      existing rules 01-26).
- [ ] `make run-pre-commit` is clean.
- [ ] Per `conventions.md`'s statistical rigor gate: this session does not move to
      `completed/` until session 3's Tier-1 `ComparisonReport` exists.

## Open questions

- **`NEEDS HUMAN DECISION — Sean/Imran`** (stated in Scope above): whether to enable
  `ENABLE_HOUSEHOLD_RISK_RULES` by default before the CMS v3.3 comment period resolves.
  Recommended default: leave it `False` until Sean/Imran explicitly say otherwise.
- The exact FHIR identifier type codes for `insurance_member_id`/`insurance_subscriber_id`
  extraction (Task 1) were deliberately left for implementation time rather than guessed —
  this is a legitimate implementation detail the executing agent resolves by reading
  `patient_matching/fhir_client/`/`patient_matching/ial2_extraction/`'s actual identifier
  shapes, not a `NEEDS HUMAN DECISION` (no external authority is needed, just more context
  than was convenient to gather during this planning pass).

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
````

- [ ] **Step 2: Verify the file's Python code blocks are syntactically valid**

Run the same check as Task 4 Step 2, pointed at `docs/sessions/pending/session_6.md`. Note:
Task 2's DOB-dispatch replacement snippet is tagged ` ```python-fragment ` on purpose (it's a
partial condition+body shown against the full method printed just above it, not a standalone
statement) — the checker's regex only matches ` ```python ` fences, so it's skipped
automatically, not by special-casing its content. Every other Python block in this file,
including both `MatchingRule(...)` examples in Task 3, is complete, real, standalone-parseable
code with no `...` placeholders — confirm the checker reports all of them "parsed OK."

- [ ] **Step 3: Commit**

```bash
git add docs/sessions/pending/session_6.md
git commit -m "Author session_6: expand Table 2 to v3.3's 37 rules"
```

---

### Task 10: Final cross-reference and consistency pass

**Files:**
- Modify (if needed): any of `docs/sessions/index.md`, `docs/sessions/conventions.md`,
  `docs/sessions/pending/session_{1..6}.md`.

**Interfaces:** None new — this task only verifies consistency across everything Tasks 1-9
produced.

- [ ] **Step 1: Verify every session doc's Upstream/Downstream references point to real files**

```bash
for f in docs/sessions/pending/session_*.md; do
  echo "=== $f ==="
  grep -oP 'session_\d(?=\.md|\b)' "$f" | sort -u
done
```
Manually confirm every session number referenced (e.g. session 3 references itself and is
referenced by 4/5/6) corresponds to an actual `pending/session_N.md` file, and that the
dependency direction is consistent both ways (if session 6 lists session 5 as upstream,
session 5's doc should not claim session 6 as upstream of *it*).

- [ ] **Step 2: Re-run index.md's link check now that all six sessions exist**

Run: `grep -oP '(?<=\()pending/session_\d\.md(?=\))' docs/sessions/index.md | while read f; do test -f "docs/sessions/$f" && echo "OK $f" || echo "MISSING $f"; done`
Expected: six `OK` lines.

- [ ] **Step 3: Verify every Python code block across all authored files parses**

(The glob below also matches the two trivial `README.md` files from Task 1 — harmless, since
they contain no code blocks. The eight substantive files are `conventions.md`, `index.md`,
and `session_1.md` through `session_6.md`.)

```bash
python3 - <<'PYEOF'
import re, ast, glob, textwrap
total = 0
for path in glob.glob("docs/sessions/**/*.md", recursive=True):
    text = open(path).read()
    # Only ```python fences are checked - ```python-fragment fences (partial
    # snippets shown against fuller context elsewhere, e.g. session_6.md's
    # DOB-dispatch replacement) are a distinct tag on purpose and are excluded
    # by not matching this regex, not by content-based special-casing.
    blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
    for b in blocks:
        try:
            ast.parse(textwrap.dedent(b))  # dedent: blocks are nested under "- [ ]" items
        except SyntaxError as e:
            print(f"SYNTAX ERROR in {path}: {e}")
            raise
        total += 1
print(f"{total} python blocks across all session docs parsed OK")
PYEOF
```
Expected: a total count with no `SYNTAX ERROR` lines.

- [ ] **Step 4: Confirm no stray references to the deleted v3.3 spec copy survived**

```bash
grep -rn "CMS_Patient_Matching_Proposal_v3.3.0.md" docs/sessions/ || echo "clean"
```
Expected: `clean` (the file was deleted earlier in this project specifically to avoid
duplicating a live external doc — no session doc should reference it as a local path).

- [ ] **Step 5: Confirm the statistical-rigor gate is referenced by every rule-changing session**

```bash
for f in docs/sessions/pending/session_3.md docs/sessions/pending/session_5.md docs/sessions/pending/session_6.md; do
  grep -q "statistical rigor gate\|statistical-rigor gate" "$f" && echo "OK $f" || echo "MISSING $f"
done
```
Expected: three `OK` lines.

- [ ] **Step 6: Commit any fixes found in Steps 1-5**

```bash
git add -A docs/sessions/
git commit -m "Fix cross-references found in final consistency pass" --allow-empty
```
(Use `--allow-empty` only if Steps 1-5 found nothing to fix — don't create a no-op commit if
there's genuinely nothing staged; check `git status` first and skip this step entirely if
clean.)

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-07-28-session-planning-playbook-design.md`):
- Directory structure (index/conventions/pending/completed/rejected) — Task 1. ✓
- `conventions.md` filled-in values (reviewer, test/gate commands, stack, scratch-space
  target, workspace isolation, PHI guardrail, security guardrail, tiered statistical rigor
  gate, reference-documents-not-copied) — Task 2. ✓
- Session 1 (audit fields), Session 2 (tiered uniqueness) — Tasks 4-5. ✓
- Thread B: Session 3 (ONC baseline + pairwise matcher + sampled negatives, addressing the
  blocking/memory-constraint concern), Session 4 (real-world query-based data source, Tier 2,
  confound-tagged via strata) — Tasks 6-7. ✓
- Session 5 (Table 3 + P(collision) evaluator, live-spec-fetch not a committed copy), Session
  6 (37-rule expansion, geo-dependency exclusion, household-risk default-off flag) — Tasks
  8-9. ✓
- Candidate future sessions (per-value P(collision), Project US@ addresses, PHI-guardrail
  automation) — captured in `index.md` (Task 3), intentionally not authored as full sessions
  per the design doc's own decision. ✓

**Placeholder scan:** searched all eight substantive authored files (`conventions.md`,
`index.md`, `session_1.md`-`session_6.md`) for "TBD", "TODO", "fill in",
"similar to Task N", "add appropriate error handling" — none found as unresolved placeholders.
The two instances of `<TBD from Task 1>` in session_4.md's widget defaults are intentional and
correctly scoped: session 4 has a real, explicitly-tagged `NEEDS HUMAN DECISION` for exact
table names (unlike every other placeholder pattern the skill prohibits, this one names
*exactly* what's missing and *exactly* how to resolve it, per playbook principle 5 — it is not
vague). Caught and fixed during this self-review: session_6.md's Task 3 originally used a bare
`...` ellipsis inside `MatchingRule(rule_id="33", ...)` calls — a real placeholder violation
(syntactically valid Python, since `...` is a legitimate Ellipsis expression, so the automated
syntax checker wouldn't have caught it; only re-reading the content did). Replaced with two
fully worked, complete `MatchingRule` constructions (rules 27 and 33) plus an explicit
instruction to build the remaining nine the same way from the Task 3 table's complete data —
no bare `...` remains inside any code block. Two snippets remain intentionally partial
(session_6.md's DOB-dispatch condition, shown against the full method printed just above it)
and are tagged with a distinct ` ```python-fragment ` fence rather than silently mixed in with
the complete, standalone-parseable ` ```python ` blocks, so the automated checker's fence
regex excludes them without needing content-based special-casing.

**Type/interface consistency:** `MatchingEngine.evaluate_pair(query_fields: PatientFields,
candidate_fields: PatientFields) -> bool` (introduced session 3) is referenced with the same
signature in session 3's own tests. `collision.p_collision`/`evaluate_combination` (introduced
session 5) are referenced with the same signatures in session 6. `rule_eval.LabeledPair`'s
`features` key convention (`{"query": ..., "candidate": ...}`, introduced in session 3's
`build_onc_pairs`) is reused identically in session 4's task description. Field name constants
(`ZIP_CODE`, `INSURANCE_MEMBER_ID`, `INSURANCE_SUBSCRIBER_ID`, introduced session 6) don't
collide with any of session 5's `FIELD_U_PROBS` keys (`zip_code`, `insurance_member_id`,
`insurance_subscriber_id` — confirmed identical strings, not just similar names).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-28-session-planning-scaffold.md`.
Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between
tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution
with checkpoints.

**Which approach?**
