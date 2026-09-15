# Design: ONC-Dataset Regression Test for the Table 2 Matching Engine

**Status:** Implemented, all open questions resolved | **Date:** 2026-09-04 | **Author:** Imran Qureshi (with Claude) | **Reviewer:** project lead

---

## Summary

Two tests run ONC-derived data through this engine's real normalize → extract → `evaluate_pair`
pipeline:

- `tests/test_onc_regression.py` (pairs tier) — asserts recall ≥ 0.95 and FPR ≤ 0.01.
- `tests/test_onc_population_regression.py` (population tier) — asserts precision ≥ 0.99,
  recall ≥ 0.95, FPR ≤ 0.001, and F1 ≥ 0.97.

The data itself is **vendored into this repo** at `tests/fixtures/onc/` (copied from the sibling
`cms-hte-patient-matching-test-set` repo — see "Vendoring decision" below) — this repo is
standalone and does not require a second repo checked out to run these tests, including in CI.

Both are written, passing, and clean under ruff/mypy. Measured live: pairs tier — recall 0.9717,
FPR 0.0069, 0 extraction errors on 6,290 pairs; population tier — precision 0.9990, recall 0.9717,
FPR 0.0001, accuracy 0.9978, F1 0.9851, 0 extraction errors on 80,000 query-candidate evaluations
(2,000 queries × ~40-candidate pools, 8,016 unique candidates).

No practitioner/NPPES *compliance* test was built — see "Alternatives Considered" for why that's
not a gap. A narrower, valid NPPES-based test was added instead: `tests/test_nppes_matching.py`,
checking both directions of the one approved rule that *can* evaluate against NPPES-shaped data
(rule 29) — recall 1.0000 on exact-duplicate/single-edit true-match cases, FPR 0.0000 on 307
real distinct-provider collisions — data vendored at `tests/fixtures/nppes/`. See the "Update
(2026-09-04)" note under "Alternatives Considered" for the full rationale.

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

### Vendoring decision (2026-09-04)

**This repo now vendors a copy of the ONC-derived test data at `tests/fixtures/onc/`** — copied
from `cms-hte-patient-matching-test-set`'s `evaluation/cases/{sample_labeled_pairs,
population_queries,population_candidates}.jsonl` (provenance, source commit, and refresh
instructions in `tests/fixtures/onc/README.md`). This reverses the original design in this doc,
which read the data live from a sibling repo checkout.

**Why:** explicit direction that this repo should be standalone for testing — a second repo
should not need to be cloned alongside this one (or checked out in CI) for its test suite to run
and gate PRs. Vendoring solves the CI-visibility gap flagged in this doc's Limitations/Open
Questions without any CI workflow change: the data is just here now.

**Tradeoff accepted:** this copy will not update automatically if the sibling repo regenerates its
dataset. `tests/fixtures/onc/README.md` documents the refresh procedure and records the source
commit hash so drift is at least detectable, not silent-forever — but keeping it current is now a
manual, deliberate act rather than always-current-by-construction. This was the reason the earlier
design didn't vendor in the first place (see the original Problem/Design rationale below, which
still explains why the *generation* code and the raw ~1M-row ONC CSVs stay in the sibling repo —
only the three already-generated output files are duplicated here, not the mutation/mining
pipeline that produces them).

### Data source (pairs tier)

`tests/fixtures/onc/sample_labeled_pairs.jsonl` — 6,290 labeled `(source, target, expected_match,
rationale)` records, each an ONC 2017 Patient Matching Algorithm Challenge record (public,
synthetic, non-PHI) or a same-record mutation/mined hard-negative of one. Categories:
`fuzzy_variant` (single-edit typo/nickname/transposition variants), `normalization_edge_case`
(diacritic/punctuation folding), `hard_negative` (mined coincidental ZIP+DOB collisions between
distinct real people), `special_population` (mined multi-generational households + constructed
institutional-address collisions).

### Pipeline

For each pair: `NormalizationManager().normalize()` → `FieldExtractor().extract()` →
`MatchingEngine.evaluate_pair(source_fields, target_fields)`. `evaluate_pair` is a pure decision
over two `PatientFields` objects (all 30 Category 1 rules + all 8 Category 2 household/individual
rules), no backend search involved — exactly the shape the engine's own docstring says it was
factored out for.

The test constructs `MatchingEngine` with a no-op `NullBackend` (its `search()` is never called
by `evaluate_pair`, but the constructor requires a backend instance) — shared with the population
tier via `tests/_onc_test_set.py`, along with the fixture path constants and the skip-reason
helper, so both tests stay in sync rather than duplicating this bookkeeping.

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
| Recall | 0.9717 (tp=5830, fn=170) | ≥ 0.95 | ~2 points below measured; still above the historical 26-rule baseline (0.9508) |
| FPR | 0.0069 (fp=2, tn=288) | ≤ 0.01 | ~0.3 points above measured — deliberately tight; a false positive here is a wrong-patient record link, the error this whole engine exists to prevent |
| Extraction errors | 0 | must be 0 | none — any error is a bug, not a case to skip |

Both false positives are in the `special_population` category (mined/constructed institutional
and household collisions) — the category built specifically to stress-test this exact risk.

Per-category breakdown (for diagnosability, not separately asserted):

| Category | tp | fp | tn | fn | recall | fpr |
|---|---|---|---|---|---|---|
| fuzzy_variant | 1852 | 0 | 0 | 148 | 0.9260 | n/a |
| normalization_edge_case | 3978 | 0 | 0 | 22 | 0.9945 | n/a |
| hard_negative | 0 | 0 | 4 | 0 | n/a | 0.0000 |
| special_population | 0 | 2 | 284 | 0 | n/a | 0.0070 |

These thresholds are **regression guards with headroom**, not a re-derivation of the sibling
repo's checked-in `evaluation/baselines/v3_2_2_onc_baseline.txt` (26 rules, ~2,000,936 pairs from
a much larger, uncommitted generated set) — that file isn't a valid direct comparison point for a
30-rule engine evaluated on the smaller, committed 6,290-pair file.

### Population tier (`tests/test_onc_population_regression.py`)

The pairs tier above deliberately can't validate precision/F1/accuracy (see previous section).
The second, vendored tier — `tests/fixtures/onc/population_queries.jsonl` (2,000 query patients) +
`tests/fixtures/onc/population_candidates.jsonl` (8,016 unique candidates, shared across queries'
pools) — is built to be naturally representative instead: each query's pool (~40 candidates)
mixes its real duplicate cluster into mostly-random distractors, rather than curating rare cases.
That representativeness is exactly what makes precision/F1/accuracy valid to compute here, per
the sibling repo's `evaluation/cases/README.md` "Option B" (the generation methodology, still
documented only in that repo — not duplicated here, see "Vendoring decision" above).

Same pipeline as the pairs tier, with one efficiency difference: each of the 8,016 candidates is
normalized/extracted **once** (candidates are shared across many queries' pools) rather than
once per query-candidate pair, then every `(query, candidate_id)` in every pool is flattened into
one confusion matrix — 80,000 evaluations total, ~10-20s locally.

This roughly mirrors what `helix.personmatching`'s `tests/cms_dataset/test_cms_performance.py`
does for the legacy engine (a query patient matched against the rest of a population), but uses
the vendored pre-built pools — which include real mined/constructed non-matches — rather than
self-matching a masked patient against an otherwise-unmasked baseline bundle. It does not
replicate that file's masking-scenario sweep (drop phone/email/gender) or its persisted
per-scenario JSON metrics report; this test evaluates the one vendored dataset and reports its
breakdown in the assertion message on failure, matching this repo's existing test style rather
than helix's file-based tracking.

| Metric | Measured | Threshold | Headroom |
|---|---|---|---|
| Precision | 0.9990 (tp=5830, fp=6) | ≥ 0.99 | matches the pairs-tier tp/fn since true matches are counted the same way; fp differs (6 vs. 2) because the population tier's much larger candidate pool surfaces more near-miss distractors |
| Recall | 0.9717 | ≥ 0.95 | same as pairs tier |
| FPR | 0.0001 (fp=6, tn=73,994) | ≤ 0.001 | 10x headroom; naturally tiny here because tn dominates the pool, but still a tight absolute ceiling — same false-positive-is-critical reasoning as the pairs tier |
| F1 | 0.9851 | ≥ 0.97 | ~1.5 points below measured |
| Accuracy | 0.9978 | not asserted | reported in the failure-message summary only; dominated by the huge tn count so less sensitive to a real regression than the other four metrics |

### Skip behavior

`@pytest.mark.skipif(not ONC_PAIRS_PATH.exists(), ...)` — skips with an actionable reason
(pointing at `tests/fixtures/onc/README.md`) rather than failing outright. Now that the data is
vendored and committed, this should never actually trigger in a normal checkout — it's
defense-in-depth for a corrupted/partial clone, not the expected path it was when the data lived
in a sibling repo that might not be cloned.

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
Practitioner/provider matching is already owned by those two repos. **No practitioner
*compliance* test was built, and none should be, in this repo** — that conclusion still holds.

**Update (2026-09-04): a narrower, valid NPPES-based test was added anyway** —
`tests/test_nppes_matching.py`, data vendored at `tests/fixtures/nppes/` (copied from
`helix.personmatching`'s own NPPES sample, provenance in that directory's README). It is **not** a
reversal of the conclusion above: it doesn't claim this engine matches practitioners in general.
Exactly one approved Table 2 rule can evaluate at all against NPPES-shaped data — Rule 29, `First
Name* + Last Name* + Phone Number + ZIP Code`, the only approved rule requiring none of
DOB/SSN/MBI/email — and the test checks that rule both directions, the same way the ONC pairs test
checks recall and FPR for patients:

- **Recall:** exact duplicates and single-edit (Damerau-Levenshtein ≤1) typo variants of a
  provider's name should all still match (phone/ZIP held fixed) — measured **1.0000** (17,299/
  17,299 true-match cases, 0 false negatives), gated at ≥ 0.99. 27 of 4,943 providers are excluded
  from this measurement (tracked, not hidden) because their practice phone didn't survive
  normalization at all (a placeholder like `000-000-0000`, or a non-US/APO number) — rule 29 can't
  evaluate without phone present, even against an identical copy of itself.
- **FPR:** real group practices commonly share one practice phone+ZIP across multiple distinct
  providers (130 such (phone, ZIP) collisions found in the vendored sample, 307 distinct-NPI pairs
  evaluated, several sharing a last name too — likely colleagues or family). Measured **0.0000**
  (0/307), gated at an exact zero — a cross-provider false positive is a wrong-person record link,
  not a rate to tolerate any of.

See that test's own module docstring for the full rationale — not duplicated here.

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

## Comparison to `helix.personmatching` (2026-09-04)

### First pass: each engine's own test suite (superseded by the apples-to-apples comparison below)

`helix.personmatching`'s own ONC/NPPES integration tests (`tests/cms_dataset/test_cms_dataset.py`,
`test_cms_performance.py`, `tests/nppes_dataset/test_nppes_dataset.py`) self-match 200 unmodified
records against an identical copy of themselves in a small bundle - no synthetic fuzzy variants,
no distinct-record negative sample, and they report pass/wrong/not-matched buckets rather than a
confusion matrix. Comparing those numbers directly against this repo's own tests (different
sample, different sample size, different result shape) isn't a real benchmark - it was a
directional-only first pass. Superseded by the same-data comparison below, which is the one to
cite.

### Apples-to-apples: both engines scored on the identical ONC-derived sample

To get a real comparison, `helix.personmatching`'s `Matcher.match_resources(source=, target=)`
was run pairwise over the **exact same vendored files** this repo's own ONC tests read
(`tests/fixtures/onc/sample_labeled_pairs.jsonl` and `population_{queries,candidates}.jsonl`) -
same 6,290 pairs, same 80,000 query-candidate evaluations, same ground truth, same confusion-matrix
definition (tp/fp/tn/fn from `expected_match`/`expected_match_ids`). Only the algorithm differs.
This was run as a one-off analysis script (not committed to either repo - see "Not committed"
below), from a `helix.personmatching` checkout with its own dependencies installed. Each FHIR
`Patient` dict was parsed via `fhir.resources.R4B.patient.Patient.model_validate()`, falling back to
validating a copy with empty-string fields stripped (FHIR's `string` type requires >=1
non-whitespace character; a handful of ONC-derived records have an empty city/state/given value) -
523/12,580 patients needed that fallback on the pairs tier; zero raised after that.

| Metric | This repo (Table 2, 30+8 rules) | `helix.personmatching` (legacy weighted score, threshold 0.955) |
|---|---|---|
| **Pairs tier** (6,290 pairs) | | |
| Recall | 0.9717 (tp=5,830, fn=170) | **1.0000** (tp=6,000, fn=0) |
| Precision | 0.9997 (not representative - see above) | 1.0000 (not representative, same reason) |
| FPR | 0.0069 (fp=2, tn=288) | **0.0000** (fp=0, tn=290) |
| **Population tier** (80,000 query-candidate evals) | | |
| Recall | 0.9717 | **1.0000** |
| Precision | 0.9990 | 0.9993 |
| FPR | 0.0001 (fp=6, tn=73,994) | 0.0001 (fp=4, tn=73,996) |
| F1 | 0.9851 | **0.9997** |
| Accuracy | 0.9978 | 1.0000 |

**Read plainly: on this exact same data, `helix.personmatching`'s legacy engine has meaningfully
higher recall than this repo's Table 2 engine, at comparably excellent precision/FPR (both engines'
FPR round to 0.0001 on the population tier; both are ~0 on the pairs tier).** This repo's 174
pairs-tier false negatives are concentrated in the `fuzzy_variant` category (152/174 - single-edit
typo/nickname/transposition mutations; recall 0.9240 within that category alone, vs. 0.9945 on
`normalization_edge_case`). The likely mechanism: a weighted sum across many independent fields is
naturally tolerant of one field degrading a little (SSN/DOB/phone/address all still contribute
full credit even when a name has a typo), while a Table 2 rule requires a *specific combination* of
fields to match within a narrow, capped fuzzy allowance (`max_fuzzy_fields`, Damerau-Levenshtein
<=1) - if a mutation happens to land outside every approved combination's exact tolerance, no rule
fires, full stop, regardless of how many *other* fields still agree.

**This is the expected shape of the tradeoff this whole repo exists to evaluate, not a defect to
fix reflexively** (`docs/PROJECT_MAP.md` §1: Table 2's entire premise is trading some recall for
combinations with a *computed, auditable* collision probability, ≤1-in-500-billion per approved
rule - a guarantee a weighted black-box score doesn't provide in the same form). Whether that
tradeoff is acceptable, and whether specific missed `fuzzy_variant` cases point at a rule/tolerance
worth revisiting, is exactly the kind of question session 8's planned disagreement-bucketed
legacy-comparison report is for - this comparison is a smaller, single-dataset instance of that
same question, not a replacement for it.

**Update (2026-09-04): committed as `evaluation/legacy_comparison.py`**, at explicit request, so
this comparison is re-runnable (e.g. after a rule change, or once the ONC fixtures get refreshed)
rather than rebuilt from scratch each time. It still isn't run by pytest or CI, and its extra
dependencies (`fhir.resources`, `fhir-core`, `nominally`, `python-crfsuite`) are deliberately not
added to this repo's `pyproject.toml` - documented as a separate manual `pip install` in the
script's own docstring instead, matching the sibling test-set repo's own `evaluation/rule_eval.py`
precedent ("intentionally not a dependency of the shippable patient_matching package"). It still
requires `helix.personmatching` cloned as a sibling repo to actually run - that's the same
eval-only cross-repo dependency `docs/PROJECT_MAP.md` §4 flags as a decision reserved for the
project lead (there, in the context of session 8); committing the *script* doesn't make that
dependency a default or a CI requirement, since nothing invokes it automatically. Usage:

```bash
PYTHONPATH=. python evaluation/legacy_comparison.py            # both tiers
PYTHONPATH=. python evaluation/legacy_comparison.py --tier pairs
PYTHONPATH=. python evaluation/legacy_comparison.py --helix-repo /path/to/helix.personmatching
```

## Limitations / Non-Goals

- **Data can silently drift from the sibling repo's canonical copy.** Vendoring trades "always
  current" for "standalone" — see "Vendoring decision" above and `tests/fixtures/onc/README.md`
  for the refresh procedure. Nothing automated detects drift; it's a manual, deliberate act.
- **No practitioner/provider coverage** — see Alternatives Considered. Out of scope for this repo.

Superseded by the vendoring decision above: this section previously noted that both tests skipped
in CI because `.github/workflows/build_and_test.yml` doesn't check out the sibling repo. That's no
longer true — the data is vendored locally, so both tests run as real gates in CI with no workflow
change needed. See Open Questions #1 for how that open question was resolved, then superseded.

## Open Questions

| # | Question | Needed From | Impact on Proposal |
|---|---|---|---|
| 1 | ~~Should CI check out the sibling repo so this test actually gates PRs?~~ **Resolved 2026-09-04: leave local-only for now** — then **superseded same day: vendor the data into this repo instead** (see "Vendoring decision"), making the original question moot. No CI checkout of a second repo is needed; both tests now run as real gates on every PR. | — | Both tests are real CI gates, not local-only/advisory. |
| 2 | ~~Should this also cover the population-query tier for precision/F1/accuracy?~~ **Resolved 2026-09-04: yes** — `tests/test_onc_population_regression.py` added, following `helix.personmatching`'s precedent of having a second, broader test tier alongside the pairs-style test. | — | Done — see "Population tier" above. |
| 3 | ~~Should thresholds track closer to measured values for tighter regression sensitivity?~~ **Resolved 2026-09-04: keep current headroom** — follow `helix.personmatching`'s own precedent, which is deliberately lenient on aggregate pass rate (`test_cms_dataset.py`/`test_cms_performance.py` assert things like `n_fail / total < 1.0`, essentially "not everything failed") and reserves zero-tolerance for one specific dangerous condition (`failed_records_with_higher_probabilities == 0` — a wrong match scoring higher than the correct one). This repo's thresholds are already well past that bar in rigor (real floor/ceiling numbers with headroom, not near-no-op checks, plus a zero-tolerance extraction-error gate of our own) without going all the way to exact-value pinning, which was already rejected above for a different reason (forces edits on every legitimate improvement). | — | Thresholds unchanged: pairs recall ≥ 0.95 / FPR ≤ 0.01; population precision ≥ 0.99 / recall ≥ 0.95 / FPR ≤ 0.001 / F1 ≥ 0.97. |
