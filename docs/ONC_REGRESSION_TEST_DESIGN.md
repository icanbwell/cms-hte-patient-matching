# Design: ONC-Dataset Regression Test for the Table 2 Matching Engine

**Status:** Implemented, pending review | **Date:** 2026-09-04 | **Author:** Imran Qureshi (with Claude) | **Reviewer:** project lead

---

## Summary

`tests/test_onc_regression.py` runs every labeled pair from the sibling
`cms-hte-patient-matching-test-set` repo's ONC-derived dataset through this engine's real
normalize → extract → `evaluate_pair` pipeline, and asserts recall ≥ 0.95 and FPR ≤ 0.01 as
regression guards. It's written, passing (measured: recall 0.9710, FPR 0.0069, 0 extraction
errors on 6,290 pairs), and clean under ruff/mypy. It does **not** yet run in CI — see
Limitations. No practitioner/NPPES-style test was built; see "Alternatives Considered" for why
that's not a gap.

## Problem

This repo has unit tests for individual Table 2 rules (`patient_matching/matching/tests/`) but,
until now, nothing that validated the engine end-to-end against a real labeled dataset — the
equivalent of what `helix.personmatching`'s `tests/cms_dataset/test_cms_dataset.py` does for the
legacy scoring engine.

This repo actually had that once. `docs/PROJECT_MAP.md` records session 3 as having built an ONC
eval harness and produced a baseline: **95.08% recall, 0.11% FPR** on ONC self-matches, 26 rules.
That code no longer lives here — it was extracted into a sibling repo,
`../cms-hte-patient-matching-test-set`, which (per that repo's own `CLAUDE.md`) now has **zero
runtime dependency on any matching engine**; it only generates and exports portable, algorithm-
agnostic ONC-derived FHIR `Patient` test data. `MatchingEngine.evaluate_pair()` in this repo still
carries a docstring pointing at a never-rebuilt `evaluation/onc_baseline.py` as its intended
consumer — the hook was left in place, nothing was ever wired to it.

Net effect: the data exists, the engine has the right factored-out method for it
(`evaluate_pair(query_fields, candidate_fields) -> bool`, pure pairwise, no backend needed), and
nothing connects them.

## Design

### Data source

`../cms-hte-patient-matching-test-set/evaluation/cases/sample_labeled_pairs.jsonl` — 6,290
labeled `(source, target, expected_match, rationale)` records, each an ONC 2017 Patient Matching
Algorithm Challenge record (public, synthetic, non-PHI) or a same-record mutation/mined
hard-negative of one. Categories: `fuzzy_variant` (single-edit typo/nickname/transposition
variants), `normalization_edge_case` (diacritic/punctuation folding), `hard_negative` (mined
coincidental ZIP+DOB collisions between distinct real people), `special_population` (mined
multi-generational households + constructed institutional-address collisions).

This repo's own `.claude/skills/test-matching-rule/SKILL.md` already assumes this sibling repo is
cloned alongside `cms-hte-patient-matching` — the test follows that same convention rather than
inventing a new one.

### Pipeline

For each pair: `NormalizationManager().normalize()` → `FieldExtractor().extract()` →
`MatchingEngine.evaluate_pair(source_fields, target_fields)`. `evaluate_pair` is a pure decision
over two `PatientFields` objects (all 30 Category 1 rules + all 8 Category 2 household/individual
rules), no backend search involved — exactly the shape the engine's own docstring says it was
factored out for.

The test constructs `MatchingEngine` with a no-op `_NullBackend` (its `search()` is never called
by `evaluate_pair`, but the constructor requires a backend instance).

### What's asserted, and why only that

Only **recall** (`tp / (tp + fn)`) and **FPR** (`fp / (fp + tn)`) are asserted — not precision,
F1, or accuracy. This follows the sibling repo's own documented methodology
(`evaluation/cases/README.md`, "Frequency and real-world representativeness"): this per-provision
pairs file deliberately over-samples rare/high-risk categories (e.g. `normalization_edge_case` is
64% of the file by construction, not because accented/punctuated names are that common) for
statistical power. Recall and FPR are valid on it as-is because both are computed *within* the
true-match or true-non-match population respectively, not across the mixed base rate — but
precision/F1/accuracy would be computed over a should-match ratio that's a generation-parameter
artifact, not a real base rate, and would have no real-world interpretation. The sibling repo's
separate population-query tier (`population_queries.jsonl` + `population_candidates.jsonl` — one
query against a realistic 40-candidate pool per query) is designed for exactly that, and is **not**
wired up by this test. See "Limitations."

The test also asserts **zero extraction errors** across all 6,290 pairs (raises are tallied and
fail the test, not silently dropped) — per the sibling repo's own Option A guidance: an algorithm
that silently skips its hardest cases and reports metrics only over what it attempted can look
stronger than one that honestly attempted everything.

### Measured values and thresholds

Run against the current engine (30 Category 1 rules + 8 household rules):

| Metric | Measured | Threshold | Headroom |
|---|---|---|---|
| Recall | 0.9710 (tp=5826, fn=174) | ≥ 0.95 | ~2 points below measured; still above the historical 26-rule baseline (0.9508) |
| FPR | 0.0069 (fp=2, tn=288) | ≤ 0.01 | ~0.3 points above measured — deliberately tight; a false positive here is a wrong-patient record link, the error this whole engine exists to prevent |
| Extraction errors | 0 | must be 0 | none — any error is a bug, not a case to skip |

Both false positives are in the `special_population` category (mined/constructed institutional
and household collisions) — the category built specifically to stress-test this exact risk.

Per-category breakdown (for diagnosability, not separately asserted):

| Category | tp | fp | tn | fn | recall | fpr |
|---|---|---|---|---|---|---|
| fuzzy_variant | 1848 | 0 | 0 | 152 | 0.9240 | n/a |
| normalization_edge_case | 3978 | 0 | 0 | 22 | 0.9945 | n/a |
| hard_negative | 0 | 0 | 4 | 0 | n/a | 0.0000 |
| special_population | 0 | 2 | 284 | 0 | n/a | 0.0070 |

These thresholds are **regression guards with headroom**, not a re-derivation of the sibling
repo's checked-in `evaluation/baselines/v3_2_2_onc_baseline.txt` (26 rules, ~2,000,936 pairs from
a much larger, uncommitted generated set) — that file isn't a valid direct comparison point for a
30-rule engine evaluated on the smaller, committed 6,290-pair file.

### Skip behavior

`@pytest.mark.skipif(not ONC_PAIRS_PATH.exists(), ...)` — skips with an actionable reason
(clone-the-sibling-repo instructions) rather than failing when the sibling repo isn't present.
This matches how `test-matching-rule` already treats that dependency, but means the test provides
**zero protection in an environment where the sibling repo isn't checked out** — see Limitations.

## Alternatives Considered

### A practitioner/NPPES-style test — rejected

The original framing was "the same [Table 2] rules should work for practitioners that work for
patients." Investigation showed this doesn't hold, for two independent reasons:

1. **`helix.personmatching`'s NPPES tests aren't testing the same kind of algorithm.**
   `tests/provider_merging/test_independent_practitioner.py` and its siblings test
   `PractitionerMerger` — a source-priority field-merge tool (`MergeConfig`/
   `MergeRule.Exclusive`, e.g. "prefer NPPES over Healthgrades for this field") that assumes
   identity is *already resolved* and only decides which data source's field values win. There is
   no probabilistic "are these two records the same person" decision anywhere in it — it's not
   the CMS Table 2 problem at all.
2. **Table 2/Table 3 don't transfer to NPPES data even if you wanted them to.** The public NPPES
   NPI Registry file has no DOB, SSN, or email — only name, credential, taxonomy, license numbers,
   and practice address/phone — so most Table 2 rule combinations have no fields to evaluate
   against. More fundamentally, Table 3's collision probabilities (the ≤1-in-500-billion safety
   guarantee the whole engine exists to provide) are calibrated to the *patient* population's
   field-value distributions; reusing them for the much smaller (~8M NPI) provider population
   would produce a number that looks precise but was never validated for that population.

This repo also has zero practitioner/provider code today — it's patient-only per `README.md` and
the `patient_matching/` package layout, consistent with `docs/PROJECT_MAP.md` §1's statement that
this repo has "no code path into `helix.personmatching`/`person-matching-service` today."
Practitioner/provider matching is already owned by those two repos. **No practitioner test was
built, and none should be, in this repo.**

### Exact tp/fp/tn/fn pinning instead of floor/ceiling — rejected

The pipeline is fully deterministic (no randomness at eval time), so byte-exact pinning of the
four confusion-matrix counts was technically viable and would catch literally any behavior change.
Rejected because it would force a test-file edit on every legitimate rule improvement (e.g. a new
rule that recovers a few more true positives), which doesn't match this codebase's own regression
philosophy — `.claude/skills/test-matching-rule` already frames verdicts as SHIP / REJECT /
NEEDS-MORE-DATA relative to "did it get worse," not "did anything change." Floor/ceiling
thresholds let genuine improvements pass silently while still catching regressions.

### Asserting against the sibling repo's committed baseline file — rejected

`evaluation/baselines/v3_2_2_onc_baseline.txt` reports 26-rule metrics over a ~2,000,936-pair
generated set, not the 6,290-pair file this test reads. Different rule count, different sample
size — not a valid comparison basis. This test establishes its own thresholds instead (see above).

## Limitations / Non-Goals

- **Does not run in CI today.** `.github/workflows/build_and_test.yml` only checks out this repo;
  the sibling `cms-hte-patient-matching-test-set` repo is never present, so the test always skips
  in CI as currently configured. It only runs when a developer has both repos cloned locally.
- **Precision/F1/accuracy are not measured.** Would require wiring up the sibling repo's
  population-query tier (`population_queries.jsonl`/`population_candidates.jsonl`) instead —
  not done here.
- **No practitioner/provider coverage** — see Alternatives Considered. Out of scope for this repo.

## Open Questions

| # | Question | Needed From | Impact on Proposal |
|---|---|---|---|
| 1 | Should CI check out the sibling repo so this test actually gates PRs, instead of perpetually skipping? (Second `actions/checkout`? Submodule? Something else?) This is a cross-repo test-only dependency — the same category of question `docs/PROJECT_MAP.md` §4 already flags (there, for an eval-only dependency on `helix.personmatching`) and reserves for the project lead. | Project lead | If no: test remains local-only/advisory. If yes: needs a CI workflow change + a decision on checkout mechanism. |
| 2 | Should this test also cover the population-query tier for precision/F1/accuracy, or is recall/FPR-only sufficient for now? | Project lead | If yes: separate follow-up test + likely a separate design note (candidate pool scoring is a different shape than pairwise evaluation). |
| 3 | Are 0.95 recall / 0.01 FPR the right thresholds, or should they track closer to the currently-measured 0.9710/0.0069 for tighter regression sensitivity? | Project lead | Tighter thresholds catch smaller regressions but risk more false alarms on noise-level fluctuations from legitimate rule tuning. |
