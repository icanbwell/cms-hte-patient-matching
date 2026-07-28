# Design: Session-Planning Structure for `patient-matching`

**Date:** 2026-07-28
**Author:** Sean (via Claude Code)
**Status:** proposed

## Purpose

Adopt the `session-planning-playbook.md` structure (`docs/sessions/`) in this repo so the
remaining CMS v3.3 "Line B" build-out can be broken into self-contained, agent-executable
chunks — reviewed once as a plan, then run one at a time with "start the next session,"
without re-briefing context each time.

## Why now, and why this repo

Per `docs/handoff/README.md`, Sean is interim lead on the CMS v3.3 migration while Zack
Malone is out (2026-07-21 → 2026-08-01), targeting a mid-August live/shadow date. This repo
(`patient-matching`, backing open PR #3 "CMS matching v1: in-memory backend + demo notebook")
is where that v1 prototype lives. A code survey of `claude/cms-matching-v1` found concrete,
partially-ordered gaps against the CMS spec — exactly the shape the playbook targets.

**Survey findings (evidence-based, see conversation for file-level detail):**

| Item | Status |
|---|---|
| Normalization (§V) | Mostly done — placeholder detection is complete; "Project US@" address format compliance is the one gap |
| Table 3 u-probabilities + P(collision) evaluator | Missing — rules hardcode static collision floats, no evaluator |
| Table 2 combination engine | **26/37 rules** — repo implements CMS **v3.2.2**, not the target **v3.3** |
| Uniqueness/tiered response | Partial — 2-candidate and 3+-candidate cases both collapse into one `AMBIGUOUS` outcome; no 1e-6 stricter path for 3+ |
| Audit record (§VII) | Partial — missing `timestamp` and `version` fields |
| ONC precision/recall/FPR harness | Missing — `evaluation/rule_eval.py` is a solid generic framework but is never wired to `MatchingEngine`; no ONC dataset files in this repo |
| fhir_client / ial2_extraction | Done |

**Decisions made with the user:**
- Sessions build directly on `claude/cms-matching-v1` (PR #3) — not a new branch, not blocked
  on merging to `main` first, since `main` currently has no code to build on.
- Reviewer for session PRs: **Sean, self-review** — the handoff explicitly authorizes Sean to
  build ahead of Zack's return as long as work stays behind a feature flag / doesn't touch
  prod behavior.
- Sessions target **CMS v3.3 throughout** (gender dropped, DOB ±1 day, 2e-12 collision bar),
  even before the rule-set expansion itself lands, since v3.3 is the actual mid-August goal —
  not v3.2.2, which is what's currently in the repo.
- Sessions blocked on assets not present in this repo (v3.3 spec text, Imran's P(collision)
  reference script, ONC labeled dataset) are **not** authored as full session docs yet — they
  go in `index.md`'s "Candidate future sessions" list with a `NEEDS HUMAN DECISION` note on
  where each asset comes from.

## Directory structure

Per the playbook, under `docs/sessions/`:
```
docs/sessions/
  index.md         tracker: suggested next session, up-next queue, 3 most recent completed
  conventions.md   operating manual for this repo
  pending/         session_N.md not yet started
  completed/       session_N.md that met Definition of Done
  rejected/        session_N.md a human decided not to pursue
```

## `conventions.md` — filled-in values for this repo

- **Reviewer:** Sean (self-review during Zack's PTO; see handoff for the boundary of what
  Sean can decide alone vs. what waits for Zack/Imran).
- **Test command:** `make tests` (runs `pytest tests` in the dev Docker container). Targeted
  run: `docker compose run --rm dev pytest patient_matching/matching/tests/<file>.py`.
- **Gate command:** `make run-pre-commit` (ruff check --fix, ruff format, mypy, bandit via
  the pre-commit local hooks in `.pre-commit-config.yaml`, plus standard hygiene hooks).
- **Stack:** Python 3.12, `uv`/`pyproject.toml`, pytest, ruff, mypy, bandit — matches the
  workspace-wide convention for newer repos.
- **Test parameterization:** existing tests use plain pytest classes (e.g.
  `matching/tests/test_table2_rules.py::TestApprovedRules`), not `unittest.TestCase` — so
  `pytest.mark.parametrize` (playbook principle 4) applies directly; no adapter needed.
- **Scratch-space-exit target:** `notebooks/` and `evaluation/` are explicitly excluded from
  pre-commit hooks (see `.pre-commit-config.yaml` exclude line) — that's this repo's scratch
  layer. The real module structure is `patient_matching/<subpackage>/`. Note: `evaluation/`
  is scratch-space in the strict sense (rule_eval.py isn't wired to the engine yet) even
  though it's a mature standalone module — Session 3 below addresses that.
- **Workspace isolation per session:** a feature branch cut from `claude/cms-matching-v1`,
  merged back into `claude/cms-matching-v1` via PR (self-reviewed) — since `claude/cms-matching-v1`
  is not `main`, this satisfies "never directly on main branch" while keeping all Line B work
  in one place until PR #3 itself is ready to merge to `main`.
- **Project-specific guardrail:** WellSense/reconciliation data referenced in the handoff is
  PHI and must stay in governed environments (Databricks/Sigma) — never exported into this
  repo's notebooks or test fixtures. All matching/normalization test fixtures in this repo
  must use synthetic data. Enforced by review, not an automated check today (candidate future
  session: add a pre-commit check).
- **Security guardrail (per user request, ahead of any PR merge):** confirm this repo has
  b.well's standard security tooling wired up (Aikido scanning enabled on the GitHub repo,
  the existing bandit/detect-private-key/detect-aws-credentials pre-commit hooks staying
  active, no secrets in `docker.env`, `.gitignore` covering local env files) before any PR
  merges — this is verified as part of the separate PR-review pass, not a session itself.

## Proposed session backlog (Thread: "Line B — CMS v3.3 migration")

**pending/session_1.md — Audit record completeness (§VII)**
Add `timestamp` and `version` fields to `RuleEvaluation`/`MatchResult` in `match_result.py`,
populate them in `matching_engine.py`. Small, no external dependencies. Upstream: none.

**pending/session_2.md — Tiered uniqueness response (CMS step 6)**
Split the current single `AMBIGUOUS` outcome into 2-candidate (escalate/disambiguate) vs.
3+-candidate (stricter 1e-6 threshold or decline) per CMS v3.3. Touches `matching_engine.py`,
`match_result.py` (`MatchOutcome` enum gains a value), and their tests. Small-medium.
Upstream: none (session 1 not required, but doing 1 first keeps audit fields consistent
across the new outcome).

**pending/session_3.md — Wire evaluation harness to the real engine**
Connect `evaluation/rule_eval.py`'s `Matcher`/`compare()` framework to
`MatchingEngine`/`table2_rules`, using synthetic labeled pairs as a stand-in dataset until
real ONC data is available (candidate session 6). Produces a baseline `ComparisonReport` for
the current 26-rule v3.2.2 engine, which becomes the "prove we didn't regress" baseline once
v3.3 rules land. Medium. Upstream: none.

## Candidate future sessions (not yet authored — blocked on assets not in this repo)

- **Expand Table 2 to v3.3's 37 rules.** `NEEDS HUMAN DECISION — Sean`: needs
  `CMS_Patient_Matching_Proposal_v3.3.0 (1).md` (referenced in the handoff, not present in
  this repo — only v3.2.2's PDF/txt are). Recommended default: Sean pulls it from wherever
  the handoff sourced it (Imran, or the internal DS handoff doc) and adds it to `docs/`.
- **P(collision) evaluator validated against reference script.** `NEEDS HUMAN DECISION —
  Sean/Imran`: needs "Imran's gist/Colab" (handoff §IV.I) — not in this repo or findable via
  grep. Recommended default: ask Imran directly for the script or its output values.
- **Real ONC dataset wiring for precision/recall/FPR.** `NEEDS HUMAN DECISION — Sean`: needs
  the ONC labeled CSVs. Handoff says these live in `helix.personmatching/tests/cms_dataset/
  files/onc/*.csv` in a different repo. Recommended default: copy them into this repo (or
  point at them via a shared fixture path) once session 3's harness plumbing exists.
- **"Project US@" address format compliance.** Smaller gap in the otherwise-complete
  normalization layer; not blocked, just not yet scoped in detail. Candidate for session 4
  once 1-3 land.
- **Strategic architecture question (not a session, a policy call):** the handoff's own build
  plan (§4.4) targets `helix.personmatching` as the eventual home for this logic, calling
  `patient-matching` a "v1 demo." Whether this repo's proven logic later gets ported upstream,
  or `patient-matching` becomes the production engine outright, is `NEEDS HUMAN DECISION —
  Sean/Zack` and out of scope for this session set. Noted here so it isn't silently assumed
  either way.

## Out of scope for this design

- Any change to `helix.personmatching` or `person-matching-service` (different repos).
- The PR #1/#2/#3 review-and-merge pass the user separately requested — that happens after
  this scaffold and sessions 1-3 land, as its own piece of work.
- Automating the PHI guardrail (flagged above as a candidate future session, not part of this
  one).
