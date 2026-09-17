# Design: Session-Planning Structure for `patient-matching`

**Date:** 2026-07-28
**Author:** Sean (via Claude Code)
**Status:** proposed

> **Post-execution note (2026-07-30):** kept as-authored, per this repo's own "never rewrite
> history" principle — see `docs/sessions/conventions.md` for what's actually current. Two
> things below are now stale: (1) PR #3 (`claude/cms-matching-v1`) merged into `main` on
> 2026-07-29, so "sessions build on `claude/cms-matching-v1`, not `main`" (below) now reads the
> other way around — sessions build on `main`. (2) The lifecycle this design proposes
> (`pending/completed/rejected`) gained a fourth-ish state, `docs/sessions/in_review/`, for
> work that's done with an open-but-unmerged PR — added while session 3 was awaiting merge.

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
- Sessions blocked on assets not present in this repo are **not** authored as full session
  docs — they go in `index.md`'s "Candidate future sessions" list with a `NEEDS HUMAN
  DECISION` note on where each asset comes from. (Two items originally blocked this way — the
  v3.3 spec text and the project lead's P(collision) reference script — were resolved mid-design when
  Sean shared the spec doc directly; see "Back to Thread A — now unblocked" below. The ONC
  dataset was separately resolved once it was confirmed to be public, non-PHI data.)

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
  Sean can decide alone vs. what waits for Zack/the project lead).
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
- **Reference documents (intentionally NOT copied into this repo):** the CMS v3.3 spec is a
  live Google Doc still in "Draft for Technical Validation" status with an open public-comment
  period and unresolved reviewer comments — it is actively changing and this repo doesn't own
  it, so it is referenced by link, not mirrored as a file. **Sean's Google Doc:**
  `https://docs.google.com/document/d/1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg/edit`
  (file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg`). Any session that needs its content
  (5, 6 below) fetches it fresh via Google Drive access as its first task, rather than trusting
  a point-in-time copy that could silently go stale while the comment period is still open —
  the opposite was tried mid-design (a full copy was committed, then deleted per Sean's
  feedback: "now we have two things that need to be kept up to date," 2026-07-28). This is
  different from the ONC dataset (Thread B session 3), which *is* copied in, because that's a
  static, versioned, published benchmark that isn't changing — the distinction is mutability
  and ownership, not size or source.
- **Statistical rigor gate (Definition of Done, tiered — see below).** Per Sean (2026-07-28):
  this matching methodology is built on statistical uniqueness-quantification principles
  (Fellegi-Sunter-style P(collision)), not a labeled ground truth we can check answers against,
  so statistical rigor is the guiding philosophy — but per Sean's follow-up (also 2026-07-28),
  it should shape the sessions **without blocking early development**. The CMS v3.3 spec itself
  (see the reference-documents bullet above) endorses exactly this kind of phased rigor —
  a 12-month grace period for empirical P(collision) validation at population scale, and a
  "safe harbor" for self-attested performance against standardized datasets — so this gate
  mirrors the spec's own structure rather than inventing a stricter one:
  - **Tier 1 — required before a rule-changing session reaches `completed/`:** an ONC
    self-match `ComparisonReport` from `rule_eval.py` (baseline vs. candidate, Beta-posterior
    credible intervals on precision/recall/FPR). Achievable entirely on synthetic labeled data
    (Thread B session 3) — no real-data dependency, so this is never blocked on infra access.
  - **Tier 2 — encouraged, not required:** validate the change's effect on P(collision)/
    collision-*rate* against real population data (Thread B session 4). This is well-posed
    without match/non-match labels — per the spec, "responding entities are encouraged to
    validate collision probabilities against their own patient populations" — unlike
    precision, which real unlabeled data structurally can't certify (see the conversation's
    precision-measurability discussion; real links are also confounded by the current
    production algorithm, per Sean).
  - **Tier 3 — explicitly not a near-term blocker:** full empirical precision/recall/FPR at
    population scale (≥1M records) on real data, matching the spec's own 12-month grace
    period. Track as a pre-production-cutover milestone (the handoff's own "validate before
    go-live" step), not a gate on any session in this backlog.
  - **Sessions can be authored and coded in any order** — the gate applies at merge time, not
    at start time. In practice this means Thread A's rule-changing sessions (5, 6 below) can
    be developed in parallel with Thread B, but shouldn't move to `completed/` until Thread B
    session 3 exists and produces their required Tier-1 report.
  - Sessions that don't touch rule behavior (audit fields, tiered-response plumbing) are
    exempt entirely, at every tier.

## Guiding philosophy: why there's a second thread of work

Sean's framing (2026-07-28): because there is no independent "these two records are/aren't
the same person" ground truth beyond the statistical framework itself, every rule change must
be evaluated for its effect on **false-positive rate and recall**, not shipped on judgment
alone — but, per Sean's follow-up, that shouldn't block early development. The tiered gate
above resolves this: the harness (Thread B) needs to exist before a rule-changing session can
be marked `completed/`, but nothing stops Thread A's rule work (sessions 5, 6) from being
authored and coded in parallel with it.

**What already exists vs. what's genuinely new**, checked directly against
`helix.personmatching` (the sibling repo's own ONC-based test harness) so this isn't built on
guesswork:
- `evaluation/rule_eval.py`/`DESIGN.md` in *this* repo already implements Beta-posterior
  credible intervals, `P(better)`, paired-McNemar recall churn, and a SHIP/REJECT verdict —
  genuinely more statistically rigorous than anything in `helix.personmatching`, which has
  **no Bayesian/statistical layer at all**: its ONC-dataset tests (`tests/cms_dataset/
  test_cms_dataset.py`, `test_cms_performance.py`) only compute flat pass/fail/no-match counts
  with lenient `< 1.0`-style asserts. So the "minimalist reporting framework" Sean asked for is
  mostly **wiring existing machinery to real data**, not building a new one from scratch.
- `helix.personmatching`'s self-match-integrity design (match a labeled set against itself;
  a record whose top match isn't itself is either a false negative — no match found — or a
  false positive — matched to a verifiably different real record) is exactly right and worth
  reusing, and it maps directly onto `rule_eval.py`'s `Confusion`/`RatePosterior` types: no
  separate "these are definitely different people" negative set is needed, because ONC assigns
  every row a distinct ground-truth identity.
- `helix.personmatching` has **no real blocking strategy** — `Matcher.score_inputs` is a plain
  nested loop, and the only mitigation for the resulting O(n²) cost was lowering a hard record
  cap from 1000 to 200 (`helix_personmatching`, commit `4953cf7`) and processing one alphabetic
  shard at a time. **Our own `InMemoryBackend.search()` has the identical problem** — it's a
  linear scan per query with no field-indexed blocking key, so we are not automatically ahead
  here. This session should fix it properly (an indexed blocking key, e.g. by `(soundex(last_name),
  dob_year)`) rather than inherit the sibling repo's cap-and-shrink workaround.
- The ONC dataset itself is a **public, de-identified benchmark** (the 2017 ONC Patient
  Matching Algorithm Challenge dataset) — not PHI. Its 9 alphabetic shards
  (`tests/cms_dataset/files/onc/*.csv` in `helix.personmatching`) are the dataset's native,
  real distribution, not a demo artifact either repo invented. Recommended default: copy those
  CSVs directly into this repo's test fixtures (same public data, no new licensing/download
  question) rather than re-sourcing them.
- Real-world FHIR data (Databricks/Mongo) is different: it **is** PHI-adjacent, and per Sean,
  any matches already present in it are confounded by having been produced by the *current*
  production algorithm — so it can inform realistic input distributions and adversarial edge
  cases, but its existing matches can't be treated as independent ground truth. Per the PHI
  guardrail above, **no raw data may be committed to this repo** — only the query definitions
  that reproduce an analysis. This repo already has a working precedent for that exact pattern:
  `notebooks/wellsense_member_matching_analysis.py` (Databricks widgets for catalog/schema,
  `_validate_sql_identifier`/`_sql_string_literal` safety helpers, reads `bronze.*` tables at
  runtime, nothing persisted) — extend it, don't reinvent it.

## Proposed session backlog

### Thread A — "Line B: CMS v3.3 migration"

**pending/session_1.md — Audit record completeness (§VII)**
Add `timestamp` and `version` fields to `RuleEvaluation`/`MatchResult` in `match_result.py`,
populate them in `matching_engine.py`. Small, no external dependencies. Upstream: none.
Not a rule change — exempt from the statistical rigor gate.

**pending/session_2.md — Tiered uniqueness response (CMS step 6)**
Split the current single `AMBIGUOUS` outcome into 2-candidate (escalate/disambiguate) vs.
3+-candidate (stricter 1e-6 threshold or decline) per CMS v3.3. Touches `matching_engine.py`,
`match_result.py` (`MatchOutcome` enum gains a value), and their tests. Small-medium.
Upstream: none (session 1 not required, but doing 1 first keeps audit fields consistent
across the new outcome). The 1e-6 threshold is CMS-mandated, not tuned, so this is also
exempt from the gate — but its behavior should be exercised by Thread B's harness once that
exists, as a sanity check rather than a hard requirement.

### Thread B — "Evaluation & Statistical Rigor Framework"

**pending/session_3.md — ONC self-match baseline wired to `rule_eval.py`**
Copy the public ONC CSV shards from `helix.personmatching/tests/cms_dataset/files/onc/` into
this repo's test fixtures; port a `create_patient_resource`-equivalent transform (same column
mapping and SAS-date-offset decoding `helix.personmatching` uses, extended to also populate
fields our `FieldExtractor` supports that theirs doesn't map — e.g. `MOTHERS_MAIDEN_NAME`,
`ALIAS`); add an indexed blocking key to `InMemoryBackend` so the self-match run doesn't
require `helix.personmatching`'s record-count cap; wire the self-match results (self-found /
found-other / not-found) into `rule_eval.py`'s `Confusion`/`compare()` as a real baseline
`ComparisonReport` for the current 26-rule v3.2.2 engine. This *is* how Thread A's future rule
changes (v3.3 expansion, P(collision) tuning) will be evaluated once it exists. Medium-large.
Upstream: none, but should land before any further Table 2 rule changes.

**pending/session_4.md — Real-world FHIR data source for `rule_eval.py`, via reproducible queries**
Extend `wellsense_member_matching_analysis.py`'s query pattern to pull FHIR Patient/Person
match data from the Databricks/Mongo sources Sean has access to, producing `rule_eval.py`-
compatible labeled pairs (`strata` tagging the fact that existing links came from the current
production algorithm, so downstream reports can separate "does the new rule agree with the
old one" from "is the new rule correct"). No data or query *output* is committed — only the
parameterized query file(s), matching the existing PHI guardrail. `NEEDS HUMAN DECISION —
Sean`: the exact catalog/schema/table names for the FHIR Patient/Person match tables — not
yet known to this design; resolve at session-start per the playbook protocol, before writing
code. Medium. Upstream: session 3 (shares the `rule_eval.py` wiring and report format).

### Back to Thread A — now unblocked

Both items previously listed below as blocked candidates are now unblocked: Sean shared the
CMS v3.3 spec (Google Doc, file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg` — see the
reference-documents bullet above; not copied into this repo), and that document itself
contains the project lead's P(collision) reference script links (§IV.I:
`gist.github.com/imranq2/b5cc7a534a37dfa26922a83e69c686ee` and a companion Colab notebook) —
fetched and confirmed directly: the gist's `FIELD_U_PROBS` dict matches the spec's Table 3
exactly, implements the same `∏ u_field_k` joint-probability formula and 2e-12 threshold, and
already flags 2 of the 37 proposed combinations as failing or administratively concerning —
consistent with what the spec's own Table 4 and open review comments say (see below). Three
independent sources agree as of 2026-07-28, so sessions 5-6 are scoped from firsthand spec
text, not secondhand description — but since the doc is a live, still-commented-on draft,
whoever executes those sessions should re-fetch it rather than trust this scoping to still
match exactly (e.g. rule numbering, exact u-values, or the two flagged concerns could shift if
CMS revises the draft before then).

**pending/session_5.md — Table 3 u-probabilities + P(collision) evaluator**
First task: fetch the current spec via Google Drive (file ID above) — do not assume a local
copy exists or is current. Implement `FIELD_U_PROBS` (17 fields, exact/fuzzy values, per §IV.C
as of this scoping) and a `p_collision()`/`evaluate_combination()` module, mirroring the project lead's
reference script's function shape for consistency with his established implementation. Replace
`table2_rules.py`'s hardcoded `p_collision_exact`/`p_collision_fuzzy` floats with values
computed by this evaluator (catches drift/typos against the spec automatically instead of
trusting hand-entered constants). Include the spec's own admitted inconsistency as an explicit
test: First Name + Last Name + DOB + ZIP computed to 3e-12 (above threshold) under this
scoping's Table 3 values and **must not** be approvable by this evaluator, regardless of the
3e-13 figure that appears in some prior (non-spec) analyses — re-verify this against whatever
Table 3 values the live doc has at execution time. Cross-checking output against the project lead's
gist/Colab directly is a stretch goal, not a blocker, since it's an external resource outside
this repo's control. Medium. Upstream: none — this is a rule-defining session, so it needs
Thread B's Tier-1 report before `completed/`, per the gate above.

**pending/session_6.md — Expand Table 2 to v3.3's 37 rules**
First task: fetch the current spec via Google Drive (same file ID) for its Table 2. Replace
`table2_rules.py`'s 26 v3.2.2 rules with the (as of this scoping) 37 v3.3 rules, scored via
session 5's evaluator. Two explicit exclusions/flags carried over from this scoping's read of
the spec and its still-open review comments (re-verify both still apply at execution time,
since the doc is under active comment): (1) First Name + Last Name + DOB + ZIP **must not** be
added — the spec says so outright pending an undefined geographic-dependency-discount
methodology; (2) the phone+ZIP+name-anchored cluster (rules in the 33-37 range as of this
scoping) has open, unresolved reviewer concern about false positives among co-resident
family/household members — implement them, but behind a distinct, default-off flag (e.g.
`enable_household_risk_rules`) until Thread B's harness can run a dedicated adversarial
family-sharing test case against them. `NEEDS HUMAN DECISION — Sean/the project lead`: whether to enable
that cluster by default before the spec's comment period resolves — recommended default is to
ship them off-by-default, matching the spec's own "necessary but not sufficient" framing for
threshold-only approval. Medium-large. Upstream: session 5 (needs the evaluator); needs Thread
B's Tier-1 report before `completed/`.

## Candidate future sessions (not yet authored)

- **P(collision) evaluator: per-value (name-frequency-conditioned) collision probability.**
  No longer blocked on a missing asset (session 5 has the reference script and spec values in
  hand) — what remains is a genuine **methodology deviation** from the published CMS approach,
  which uses static per-field constants, not per-value frequency weighting. `NEEDS HUMAN
  DECISION — Sean/the project lead`: this needs the project lead's explicit sign-off as domain lead before
  implementation, since it goes beyond what the spec itself prescribes, not just his reference
  values. Recommended default: propose it to the project lead alongside session 5/6's results once they
  exist, as a concrete "here's what the spec says vs. what we think could be more precise."
- **"Project US@" address format compliance.** Smaller gap in the otherwise-complete
  normalization layer; not blocked, just not yet scoped in detail. Candidate once Threads A/B's
  pending sessions land.

## Resolved: this repo stays self-contained

**Decided (2026-07-28):** `patient-matching` does **not** get ported to
`helix.personmatching`. It is its own self-contained implementation, despite the handoff
doc's §4.4 framing of `patient-matching` as a "v1 demo" and `helix.personmatching` as the
eventual build target — that framing is superseded. All future sessions build here.

**The project lead is the domain lead** for the CMS proposal and the P(collision) methodology
(confirmed: he authored commit `3abc37e`, the foundational normalization/matching/cache/
fhir_client/ial2_extraction implementation — PR #2 `add-patient-matching-code` is that same
commit, verified via `git merge-base --is-ancestor` to be a direct ancestor of
`claude/cms-matching-v1`, not a divergent parallel design). Practical implications:
- New code (sessions 1-6 and the still-blocked candidate session) should follow the
  conventions the project lead already established — `table2_rules.py`'s `RuleField`/`MatchingRule`
  dataclass shape, docstrings citing exact CMS spec sections, the normalization module split —
  rather than introduce new patterns.
- For the one remaining domain-specific open item (per-value collision probability), the project lead is
  the specific person to consult, not a generic "ask around" — he authored the v3.3 proposal
  itself and the P(collision) reference script now confirmed at the spec doc's §IV.I (see the
  reference-documents bullet above for the link).

## Out of scope for this design

- Any change to `helix.personmatching` or `person-matching-service` (different repos) —
  this repo does not port to or depend on either.
- The PR #1/#2/#3 review-and-merge pass the user separately requested — that happens after
  this scaffold and sessions 1-6 land, as its own piece of work.
- Automating the PHI guardrail (flagged above as a candidate future session, not part of this
  one).
