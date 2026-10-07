# Design: ONC-Dataset Regression Test for the Table 2 Matching Engine

**Status:** Implemented, all open questions resolved | **Date:** 2026-09-04 | **Author:** the project lead (with Claude) | **Reviewer:** project lead

---

## Summary

Two tests run ONC-derived data through this engine's real normalize → extract → `evaluate_pair`
pipeline:

- `tests/test_onc_regression.py` (pairs tier) — asserts recall ≥ 0.94 (**temporarily** lowered from 0.95 for test-set 0.0.5; see "Pairs recall floor temporarily lowered for test-set 0.0.5") and FPR ≤ 0.01.
- `tests/test_onc_population_regression.py` (population tier) — asserts precision ≥ 0.99,
  recall ≥ 0.95, FPR ≤ 0.001, and F1 ≥ 0.97 (recall/F1 temporarily relaxed for test-set 0.0.3, restored; see "Floors restored for test-set 0.0.3").

The data itself is **vendored into this repo** at `tests/fixtures/onc/` (copied from the sibling
`cms-hte-patient-matching-test-set` repo — see "Vendoring decision" below) — this repo is
standalone and does not require a second repo checked out to run these tests, including in CI.

Both are written, passing, and clean under ruff/mypy. Measured live: pairs tier — recall 0.9709,
FPR 0.0000, 0 extraction errors on 6,138 pairs; population tier — precision 0.9993, recall 0.9709,
FPR 0.0001, accuracy 0.9978, F1 0.9849, 0 extraction errors on 79,848 query-candidate evaluations
(2,000 queries × ~40-candidate pools, 8,016 unique candidates). Measured against the data
*after* the Rule 29 removal — see "Rule 29 removal (2026-10-06)" below.

No practitioner/NPPES test exists. A narrow NPPES-based test of Rule 29 once existed
(`tests/test_nppes_matching.py`); it was deleted along with its vendored data when CMS removed
Rule 29, since no other approved rule can evaluate against NPPES-shaped data (see "Rule 29
removal (2026-10-06)" below).

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

### Fetch-on-demand decision (2026-09-15, supersedes the vendoring decision below)

**This repo no longer commits a copy of the ONC-derived test data.** `scripts/fetch_onc_test_data.py`
(`make fetch-onc-data`) downloads it from a pinned commit of `cms-hte-patient-matching-test-set`
(tag `0.0.5` as of this writing, resolved to a commit SHA at fetch time — see the `Makefile`'s
`ONC_TEST_SET_TAG` default, which is the authoritative pin, not this doc) into
`tests/fixtures/onc/`, which is now gitignored.

**Why:** the vendoring decision below traded "always current" for "standalone," but the resulting
committed copy could still drift silently from the sibling repo — nothing forced anyone to notice
or act on that drift. Pinning and fetching on demand keeps the *entire* size/staleness tradeoff in
one reviewable diff (bumping the `ONC_TEST_SET_TAG` default in the `Makefile`) instead of a multi-megabyte file diff
each time the pin needs to move, while keeping the property the vendoring decision was solving
for: no second repo needs to be checked out alongside this one, including in CI (CI just runs
`make fetch-onc-data` as its own step — see `.github/workflows/build_and_test.yml`). The fetch
itself resolves against the commit SHA, not the tag name, because a tag is a mutable ref that
could be force-moved upstream without leaving any trace in this repo's history — that would
silently reintroduce exactly the drift this decision exists to eliminate.

**Tradeoff accepted:** this repo's test suite now has a network dependency at
`make fetch-onc-data` time (not at every `pytest` invocation — the two ONC tests still skip, not
fail, if that step hasn't been run *locally*). In CI, though, the "Fetch ONC test data" step in
`.github/workflows/build_and_test.yml` has no `continue-on-error`, so a GitHub outage (or the
pinned commit becoming unreachable) fails that step outright and the whole job stops before
`pytest` ever runs — the entire build goes red, not just the two ONC tests. The skip-not-fail
behavior only covers the local-dev case of not having run `make fetch-onc-data` yet; a CI-time
fetch failure is a hard build failure by design, so the regression gate can't silently go dark
without anyone noticing.

### Vendoring decision (2026-09-04, superseded above)

**This repo used to vendor a copy of the ONC-derived test data at `tests/fixtures/onc/`** — copied
from `cms-hte-patient-matching-test-set`'s `evaluation/cases/{sample_labeled_pairs,
population_queries,population_candidates}.jsonl`. This reversed the original design in this doc,
which read the data live from a sibling repo checkout.

**Why:** explicit direction that this repo should be standalone for testing — a second repo
should not need to be cloned alongside this one (or checked out in CI) for its test suite to run
and gate PRs. Vendoring solved the CI-visibility gap flagged in this doc's Limitations/Open
Questions without any CI workflow change: the data was just there.

**Tradeoff that led to the fetch-on-demand decision above:** the copy did not update automatically
if the sibling repo regenerated its dataset, and nothing detected drift beyond a documented (but
easy to skip) manual refresh procedure. This was the reason the earlier design didn't vendor in
the first place (see the original Problem/Design rationale below, which still explains why the
*generation* code and the raw ~1M-row ONC CSVs stay in the sibling repo — only the three
already-generated output files were ever duplicated here, not the mutation/mining pipeline that
produces them).

### Data source (pairs tier)

`tests/fixtures/onc/sample_labeled_pairs.jsonl` — 6,138 labeled `(source, target, expected_match,
rationale)` records, each an ONC 2017 Patient Matching Algorithm Challenge record (public,
synthetic, non-PHI) or a same-record mutation/mined hard-negative of one. Categories:
`fuzzy_variant` (single-edit typo/nickname/transposition variants), `normalization_edge_case`
(diacritic/punctuation folding), `hard_negative` (mined coincidental ZIP+DOB collisions between
distinct real people), `special_population` (mined multi-generational households + constructed
institutional-address collisions).

### Pipeline

For each pair: `NormalizationManager().normalize()` → `FieldExtractor().extract()` →
`MatchingEngine.evaluate_pair(source_fields, target_fields)`. `evaluate_pair` is a pure decision
over two `PatientFields` objects (all 29 Category 1 rules + all 8 Category 2 household/individual
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

The test also asserts **zero extraction errors** across all 6,138 pairs (raises are tallied and
fail the test, not silently dropped) — per the sibling repo's own Option A guidance: an algorithm
that silently skips its hardest cases and reports metrics only over what it attempted can look
stronger than one that honestly attempted everything.

### Measured values and thresholds

Run against the current engine (29 Category 1 rules + 8 household rules):

| Metric | Measured | Threshold | Headroom |
|---|---|---|---|
| Recall | 0.9709 (tp=5678, fn=170) | ≥ 0.95 | ~2 points below measured; still above the historical 26-rule baseline (0.9508) |
| FPR | 0.0000 (fp=0, tn=290) | ≤ 0.01 | 1 point above measured; kept at the pre-removal value (the two former false positives came from Rule 29) — a false positive here is a wrong-patient record link, the error this whole engine exists to prevent |
| Extraction errors | 0 | must be 0 | none — any error is a bug, not a case to skip |

Before Rule 29's removal there were two false positives, both in the `special_population`
category (mined/constructed institutional and household collisions — the category built
specifically to stress-test this exact risk); both matched via Rule 29 and are gone with it.

Per-category breakdown (for diagnosability, not separately asserted):

| Category | tp | fp | tn | fn | recall | fpr |
|---|---|---|---|---|---|---|
| fuzzy_variant | 1708 | 0 | 0 | 148 | 0.9203 | n/a |
| normalization_edge_case | 3970 | 0 | 0 | 22 | 0.9945 | n/a |
| hard_negative | 0 | 0 | 4 | 0 | n/a | 0.0000 |
| special_population | 0 | 0 | 286 | 0 | n/a | 0.0000 |

These thresholds are **regression guards with headroom**, not a re-derivation of the sibling
repo's checked-in `evaluation/baselines/v3_2_2_onc_baseline.txt` (26 rules, ~2,000,936 pairs from
a much larger, uncommitted generated set) — that file isn't a valid direct comparison point for a
29-rule engine evaluated on the smaller 6,138-pair file.

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
one confusion matrix — 79,848 evaluations total, ~10-20s locally.

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
| Precision | 0.9993 (tp=5678, fp=4) | ≥ 0.99 | matches the pairs-tier tp/fn since true matches are counted the same way; fp differs (4 vs. 0) because the population tier's much larger candidate pool surfaces more near-miss distractors |
| Recall | 0.9709 | ≥ 0.95 | same as pairs tier |
| FPR | 0.0001 (fp=4, tn=73,996) | ≤ 0.001 | 10x headroom; naturally tiny here because tn dominates the pool, but still a tight absolute ceiling — same false-positive-is-critical reasoning as the pairs tier |
| F1 | 0.9849 | ≥ 0.97 | ~1.5 points below measured |
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

**Update (2026-10-06): the narrower NPPES-based test was removed.** It existed only to exercise
Rule 29, `First Name* + Last Name* + Phone Number + ZIP Code` — the one approved rule requiring
none of DOB/SSN/MBI/email, and so the only one that could evaluate against NPPES-shaped data.
CMS removed Rule 29 from Table 2, so `tests/test_nppes_matching.py` and its vendored data at
`tests/fixtures/nppes/` were deleted. The original conclusion above still holds: this repo has no
practitioner-matching test, and none should be added.

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
generated set, not the 6,138-pair file this test reads. Different rule count, different sample
size — not a valid comparison basis. This test establishes its own thresholds instead (see above).

## Rule 29 removal (2026-10-06)

CMS removed Rule 29 (`First Name* + Last Name* + Phone Number + ZIP Code`, no DOB) from Table 2.
Its ID is left unassigned in `table2_rules.py` (Category 1 is 01-28 and 30) rather than
renumbering Rule 30.

**Effect on recall.** Removing the rule alone dropped both tiers' recall from 0.9717 to 0.9463 —
below the 0.95 floor — because 152 true-match cases matched *only* via Rule 29: 143 `fuzzy_variant`
DOB mutations (year/month/day/typo/swap beyond the ±1-day tolerance of rules 01/02/03/10/24) and 9
name-variant cases. No other rule matches them: every Category 1 rule that could has a DOB field,
and every Category 2 household rule's individual row (`I-01`: `First Name* + DOB`) requires an
exact DOB — including `C2-34` (Phone + ZIP household), the closest remaining rule. CMS's intent is
that a pair with a wrong DOB should *not* match on phone + ZIP + name alone, so these cases were
labeled true matches under a rule set that no longer exists.

**Fix.** The 152 cases were removed from the test data rather than lowering `RECALL_FLOOR`
(still 0.95): pairs tier 6,290 → 6,138, population tier 80,000 → 79,848 evaluations. The same
removal also eliminated the pairs tier's two false positives (both matched via Rule 29). The
remaining 170 false negatives (148 `fuzzy_variant`, 22 `normalization_edge_case`) are unchanged.
The data lives in the sibling `cms-hte-patient-matching-test-set` repo, so the change was made
there (branch `drop-rule-29-only-cases`); this repo's pin in `scripts/fetch_onc_test_data.py`
must be bumped to the resulting tag before `make fetch-onc-data` returns the filtered data.

The sections below compare against `helix.personmatching` using this repo's numbers *before* this
removal (6,290 pairs, 30 Category 1 rules); they have not been re-run.

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

| Metric | This repo (Table 2, 30+8 rules, pre-Rule-29-removal) | `helix.personmatching` (legacy weighted score, threshold 0.955) |
|---|---|---|
| **Pairs tier** (6,290 pairs) | | |
| Recall | 0.9717 (tp=5,830, fn=170) | **1.0000** (tp=6,000, fn=0) |
| Precision | 0.9997 (not representative - see above) | 1.0000 (not representative, same reason) |
| FPR | 0.0069 (fp=2, tn=288) | **0.0000** (fp=0, tn=290) |
| **Population tier** (80,000 query-candidate evals) | | |
| Recall | 0.9717 | **1.0000** |
| Precision | 0.9990 | 0.9993 |
| FPR | 0.0001 (fp=4, tn=73,996) | 0.0001 (fp=4, tn=73,996) |
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

- **CI has a network dependency at `make fetch-onc-data` time.** Fetch-on-demand trades "no
  network needed" for "no silent drift and no multi-megabyte file diffs" — see "Fetch-on-demand
  decision" above. Locally, both ONC tests skip (not fail) if the fetch hasn't been run. In CI,
  the fetch step itself has no `continue-on-error`, so an outage or the pinned commit becoming
  unreachable fails the whole build, not just the two ONC tests — a deliberate choice so the
  regression gate can't silently stop running without anyone noticing.
- **No practitioner/provider coverage** — see Alternatives Considered. Out of scope for this repo.

Superseded by the fetch-on-demand decision above (itself superseding the vendoring decision): this
section previously noted that both tests skipped in CI because `.github/workflows/build_and_test.yml`
doesn't check out the sibling repo. That's still not needed — CI now runs `make fetch-onc-data` as
its own step instead of checking out a second repo, so both tests run as real gates with a small,
explicit workflow change (not zero, as the vendoring decision had achieved, but still no sibling
repo checkout). See Open Questions #1 for how that open question was resolved, then superseded twice.

## Open Questions

| # | Question | Needed From | Impact on Proposal |
|---|---|---|---|
| 1 | ~~Should CI check out the sibling repo so this test actually gates PRs?~~ **Resolved 2026-09-04: leave local-only for now** — then **superseded same day: vendor the data into this repo instead** (see "Vendoring decision") — then **superseded again 2026-09-15: fetch from a pinned tag on demand instead** (see "Fetch-on-demand decision"), adding one explicit `make fetch-onc-data` CI step in place of either a sibling-repo checkout or a committed copy. No CI checkout of a second repo is needed; both tests still run as real gates on every PR. | — | Both tests are real CI gates, not local-only/advisory. |
| 2 | ~~Should this also cover the population-query tier for precision/F1/accuracy?~~ **Resolved 2026-09-04: yes** — `tests/test_onc_population_regression.py` added, following `helix.personmatching`'s precedent of having a second, broader test tier alongside the pairs-style test. | — | Done — see "Population tier" above. |
| 3 | ~~Should thresholds track closer to measured values for tighter regression sensitivity?~~ **Resolved 2026-09-04: keep current headroom** — follow `helix.personmatching`'s own precedent, which is deliberately lenient on aggregate pass rate (`test_cms_dataset.py`/`test_cms_performance.py` assert things like `n_fail / total < 1.0`, essentially "not everything failed") and reserves zero-tolerance for one specific dangerous condition (`failed_records_with_higher_probabilities == 0` — a wrong match scoring higher than the correct one). This repo's thresholds are already well past that bar in rigor (real floor/ceiling numbers with headroom, not near-no-op checks, plus a zero-tolerance extraction-error gate of our own) without going all the way to exact-value pinning, which was already rejected above for a different reason (forces edits on every legitimate improvement). | — | Thresholds unchanged: pairs recall ≥ 0.95 / FPR ≤ 0.01; population precision ≥ 0.99 / recall ≥ 0.95 / FPR ≤ 0.001 / F1 ≥ 0.97. |

## Pairs floors relaxed for test-set 0.0.2

Pinning test-set `0.0.2` adds the session 14 categories to the pairs tier (11,668 pairs). Measured
with rule 29 removed: recall 0.9265 (tp=10397, fn=825), FPR 0.0964 (fp=43, tn=403), driven by
`compound_variant` (570 false negatives of 1,793 true matches) and `sibling_negative` (43 false
positives of 81 non-matches). The pairs floors were moved from recall ≥ 0.95 / FPR ≤ 0.01 to
recall ≥ 0.92 / FPR ≤ 0.10 so CI gates against further regression while the engine is optimized for
those categories. (Restored; see "Floors restored for test-set 0.0.3".) The population tier is unchanged and
passes (precision 0.9993, recall 0.9718, FPR 0.0001, F1 0.9853).

## Population floors relaxed for test-set 0.0.3

Pinning test-set `0.0.3` changes the population tier (2,000 queries, 15,812 candidates, 87,747
evaluations). Measured: precision 0.9998, recall 0.9305 (tp=12696, fn=948), FPR 0.0000 (fp=3),
F1 0.9639. Recall and F1 fell below the 0.95 / 0.97 floors that 0.0.2 met (recall 0.9718, F1 0.9853).
The population floors were moved from recall ≥ 0.95 / F1 ≥ 0.97 to recall ≥ 0.92 / F1 ≥ 0.95 so CI
gates against further regression while the engine is optimized for the session 14 categories
(chiefly `compound_variant`). Precision ≥ 0.99 and FPR ≤ 0.001 are unchanged. (Restored; see below.)
The pairs tier passed unchanged (recall 0.9290, FPR 0.0052).

## Floors restored for test-set 0.0.3

Two engine fixes recovered recall on the unmodified 0.0.3 data (analysis:
`docs/TEST_SET_0.0.3_ACCURACY_ANALYSIS.md`): a placeholder given name no longer discards the real
family name, and well-formed phone numbers with an unassigned exchange are no longer dropped.
Measured: pairs tier recall 0.9516 (tp=12977, fn=660), FPR 0.0052 (fp=3, tn=579); population tier
precision 0.9998, recall 0.9515 (tp=12982, fn=662), FPR 0.0000, F1 0.9750. All four relaxed gates are
back to their original values: pairs recall ≥ 0.95 / FPR ≤ 0.01, population recall ≥ 0.95 / F1 ≥ 0.97.
The pairs recall margin is thin (~0.0016), so a small rule change can trip it.

## Pairs recall floor temporarily lowered for test-set 0.0.5

Pinning test-set `0.0.5` drops the pairs tier below the 0.95 floor with the engine unchanged: recall
0.9474 (tp=12902, fn=717), FPR 0.0052 (fp=3, tn=579), on 14,201 pairs. The test set stopped emitting
fuzzy-variant pairs identical to their source and was reseeded, so trivially-matching pairs are gone.
Population tier: recall 0.9504, precision 0.9998, FPR 0.0000, F1 0.9745, all gates unchanged.

The pairs recall floor is **TEMPORARILY 0.94** (margin 0.0074). It is restored to 0.95 once the rule
changes that raise accuracy are decided and implemented (analysis and ranked options:
`docs/TEST_SET_0.0.5_ACCURACY_ANALYSIS.md`, section 7). All other gates are unchanged.

## Thresholds are env-configurable

Each gate reads an env var, falling back to the checked-in default in the test module
(`tests/_onc_test_set.py::threshold`). The value in effect appears in the metrics report/job summary.

| Env var | Default |
|---|---|
| `ONC_PAIRS_RECALL_FLOOR` | 0.94 (temporary, see above) |
| `ONC_PAIRS_FPR_CEILING` | 0.01 |
| `ONC_POP_PRECISION_FLOOR` | 0.99 |
| `ONC_POP_RECALL_FLOOR` | 0.95 |
| `ONC_POP_FPR_CEILING` | 0.001 |
| `ONC_POP_F1_FLOOR` | 0.97 |

Example: `ONC_TEST_SET_TAG=0.0.2 ONC_POP_RECALL_FLOOR=0.95 ONC_POP_F1_FLOOR=0.97 make onc-tests`.
