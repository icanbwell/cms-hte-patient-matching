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
- **Statistical rigor gate (Definition of Done, applies to every future session):** per Sean
  (2026-07-28) — this matching methodology is built on statistical uniqueness-quantification
  principles (Fellegi-Sunter-style P(collision)), not a labeled ground truth we can check
  answers against. **Statistical rigor is therefore the guiding philosophy, not a nice-to-have.**
  Any session that adds or modifies a matching rule (a fuzzy-match allowance, a DOB tolerance,
  nickname handling, u-probability/collision values, a new Table 2 rule, a blocking key) is
  **not done** until its PR includes a `rule_eval.py`-produced `ComparisonReport` — baseline
  vs. candidate, with Beta-posterior credible intervals on precision/recall/FPR — showing the
  change's actual effect. Sessions that don't touch rule behavior (e.g. session 1's audit
  fields) are exempt.

## Guiding philosophy: why there's a second thread of work

Sean's framing (2026-07-28): because there is no independent "these two records are/aren't
the same person" ground truth beyond the statistical framework itself, every rule change must
be evaluated for its effect on **false-positive rate and recall**, not shipped on judgment
alone. That's a standing requirement on all *future* rule work, which means the harness that
produces those numbers has to exist and be trustworthy *before* Line B's remaining rule
changes (v3.3 rule expansion, the P(collision) evaluator) land — not after.

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

## Candidate future sessions (not yet authored — blocked on assets not in this repo)

- **Expand Table 2 to v3.3's 37 rules.** `NEEDS HUMAN DECISION — Sean`: needs
  `CMS_Patient_Matching_Proposal_v3.3.0 (1).md` (referenced in the handoff, not present in
  this repo — only v3.2.2's PDF/txt are). Recommended default: Sean pulls it from wherever
  the handoff sourced it (Imran, or the internal DS handoff doc) and adds it to `docs/`.
  Blocked on the statistical rigor gate too: this is a rule change, so it needs Thread B done
  first, and its `ComparisonReport` needs Sean/Imran sign-off before merge.
- **P(collision) evaluator, including per-value (name-frequency-conditioned) collision
  probability.** `NEEDS HUMAN DECISION — Sean/Imran`: needs "Imran's gist/Colab" (handoff
  §IV.I) — not in this repo or findable via grep. Sean separately raised a specific
  methodology refinement worth carrying into this session's scope once it's unblocked: using
  per-value collision probability (e.g. surname-frequency-weighted, "Smith" vs. "Qureshi")
  rather than CMS's static per-field constant — a real change to the P(collision) methodology
  that needs Imran's sign-off as domain lead, not something to implement unilaterally.
  Recommended default: ask Imran directly for the reference script/values and his read on the
  per-value refinement.
- **"Project US@" address format compliance.** Smaller gap in the otherwise-complete
  normalization layer; not blocked, just not yet scoped in detail. Candidate once Threads A/B's
  pending sessions land.

## Resolved: this repo stays self-contained

**Decided (2026-07-28):** `patient-matching` does **not** get ported to
`helix.personmatching`. It is its own self-contained implementation, despite the handoff
doc's §4.4 framing of `patient-matching` as a "v1 demo" and `helix.personmatching` as the
eventual build target — that framing is superseded. All future sessions build here.

**Imran Qureshi is the domain lead** for the CMS proposal and the P(collision) methodology
(confirmed: he authored commit `3abc37e`, the foundational normalization/matching/cache/
fhir_client/ial2_extraction implementation — PR #2 `add-patient-matching-code` is that same
commit, verified via `git merge-base --is-ancestor` to be a direct ancestor of
`claude/cms-matching-v1`, not a divergent parallel design). Practical implications:
- New code (sessions 1-4 and the still-blocked candidate sessions) should follow the
  conventions Imran already established — `table2_rules.py`'s `RuleField`/`MatchingRule`
  dataclass shape, docstrings citing exact CMS spec sections, the normalization module split —
  rather than introduce new patterns.
- For the domain-specific blocked items above (v3.3's 37 rules, the P(collision) evaluator),
  Imran is the specific person to consult, not a generic "ask around" — he authored the v3.3
  proposal itself and the P(collision) reference script the handoff references.

## Out of scope for this design

- Any change to `helix.personmatching` or `person-matching-service` (different repos) —
  this repo does not port to or depend on either.
- The PR #1/#2/#3 review-and-merge pass the user separately requested — that happens after
  this scaffold and sessions 1-4 land, as its own piece of work.
- Automating the PHI guardrail (flagged above as a candidate future session, not part of this
  one).
