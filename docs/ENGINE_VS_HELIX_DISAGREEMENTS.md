# Engine vs `helix.personmatching`: per-record disagreements on both test-set tiers

Date: 2026-10-21. Ticket: BAI-1167. Engine: `patient_matching` on `main` at `5c684e9` (Table 2 rules
engine, verification only). **No engine or helix change in this document**; both matchers run exactly
as released and only the comparison is new (`z_scripts/compare_engines.py`).

## 1. Verdict

**The two matchers have the same recall (0.945–0.953 on every tier, within 0.3 points of each other) but
miss different records, and on the realistic tier helix links more wrong patients: 53 false links against
the engine's 4 on the 80,000-evaluation population test (21 at the match service's 0.9555 cut-off).**
Helix 2.1.0, 2.20 and 3.0.1 give identical verdicts and scores on this data, so the version question does
not change any number below.

## 2. Results

`tp`/`fp`/`tn`/`fn` are record-level counts. A positive is "these two records are the same person".
Helix "matches" when its total score is at least **0.955**, the library's own cut-off. Helix columns are
the same for 2.1.0, 2.20 and 3.0.1 (§6).

| Tier | Matcher | tp | fp | tn | fn | Recall | False-positive rate |
|---|---|---|---|---|---|---|---|
| Curated pairs (n 14,201) | Engine | 12,896 | 3 | 579 | 723 | 0.9469 | 0.0052 |
| | Helix | 12,876 | 2 | 580 | 743 | 0.9454 | 0.0034 |
| Curated population (n 80,000) | Engine | 12,908 | 3 | 66,409 | 680 | 0.9500 | 0.00005 |
| | Helix | 12,872 | 2 | 66,410 | 716 | 0.9473 | 0.00003 |
| Realistic pairs (n 30,999) | Engine | 12,963 | 4 | 17,358 | 674 | 0.9506 | 0.0002 |
| | Helix | 12,975 | 21 | 17,341 | 662 | 0.9515 | 0.0012 |
| Realistic population (n 80,000) | Engine | 9,717 | 4 | 69,770 | 509 | 0.9502 | 0.00006 |
| | Helix | 9,740 | 53 | 69,721 | 486 | 0.9525 | 0.00076 |

Precision on the realistic population: engine 0.9996, helix 0.9946. The **pairs tier over-samples rare
categories** (every category is present in bulk), so read precision from the population rows.

The curated rows reproduce the engine's published numbers on test-set 0.0.5 (population tp 12,908, pairs
fp 3); the realistic engine rows reproduce `TEST_SET_e4cf29e_ACCURACY_ANALYSIS.md`.

### Helix at the match service's cut-off (0.9555)

The real-time match service keeps a candidate only at `MATCH_SCORE_THRESHOLD=0.9555`, not 0.955. Re-deciding
helix's matches at 0.9555 (`--helix-threshold 0.9555`, same scores, no re-run of the matcher):

| Tier | Helix fp at 0.955 | Helix fp at 0.9555 | Helix tp / fn |
|---|---|---|---|
| Curated pairs and population | 2 | 2 | unchanged |
| Realistic pairs | 21 | **12** | unchanged (12,975 / 662) |
| Realistic population | 53 | **21** | unchanged (9,740 / 486) |

Moving 0.0005 removed 9 false links (pairs) and 32 (population) and **no true link** on this data. That is a property of this test set
(no true match scored inside that band), not a guarantee for real data. Precision on the realistic
population becomes 0.9979 for helix (engine 0.9996).

## 3. Where they differ (pairs tier)

Every record falls in one of four buckets: **both right**, **both wrong**, **engine only right**,
**helix only right**. Counts below are records in each non-"both right" bucket; categories not listed had
no disagreement.

| Category | Curated: engine only | Curated: helix only | Curated: both wrong | Realistic: engine only | Realistic: helix only | Realistic: both wrong |
|---|---|---|---|---|---|---|
| compound_variant | **387** | 168 | 354 | **377** | 190 | 271 |
| fuzzy_variant | 1 | **114** | 0 | 2 | **120** | 1 |
| phone_churn | 0 | **45** | 0 | 0 | **40** | 0 |
| marriage_variant | 0 | 13 | 0 | 0 | 13 | 9 |
| ssn_dropped | 0 | 10 | 0 | 0 | 0 | 1 |
| surname_change | 0 | 6 | 0 | 0 | 7 | 0 |
| surname_address_change | n/a | n/a | n/a | 0 | 6 | 1 |
| placeholder | 0 | 5 | 0 | 0 | 10 | 0 |
| normalization_edge_case | 1 | 4 | 0 | 0 | 3 | 0 |
| email_churn / address_move / phone_variant | 0 | 4 | 0 | 0 | 2 | 0 |
| sibling_negative | 0 | 1 | 2 | 0 | 0 | 0 |
| near_miss_negative | 0 | 0 | 0 | 9 | 0 | 0 |
| hard_negative | 0 | 0 | 0 | 5 | 0 | 0 |
| name_collision_negative | 0 | 0 | 0 | 3 | 0 | 0 |
| twin_like_negative | 0 | 0 | 0 | 0 | 2 | 2 |
| household_member_negative / special_population | 0 | 0 | 0 | 2 | 0 | 0 |

(`n/a`: the category does not exist in the curated tier.)

What the counts say:

- **They are complementary on true matches.** The engine wins on `compound_variant` (several fields change at
  once). Helix wins on `fuzzy_variant` (typos), `phone_churn`, `marriage_variant`, `ssn_dropped`,
  `surname_change` and `placeholder`.
- **They share one blind spot.** 271 of the 285 realistic "both wrong" pairs are `compound_variant`, and
  354 of 356 on the curated tier. Neither matcher recovers a record that changed several identifying
  fields together.
- **On the realistic tier helix's extra links are mostly negatives the engine rejects**: 19 of helix's 21
  false links are records the engine gets right (§4).

Population tier (80,000 query×candidate evaluations), disagreement rows only:

| Tier | Engine only right | Helix only right | Both wrong |
|---|---|---|---|
| Curated | 383 | 348 | 335 |
| Realistic | 320 | 294 | 219 |

**Population rows carry one composite label, not a per-candidate category.** Each query's rationale is the
`+`-joined list of every variant in its candidate set, and candidate ids are opaque hashes, so a
disagreement cannot be attributed to a category on this tier. Use the pairs tier for the by-category view.

## 4. False links (wrong-patient links)

**Helix, realistic pairs, 21 false links at 0.955** (rule = the helix rule that produced the top score;
descriptions from helix's `rule_library.py`):

| Category | Count | Helix rules that fired |
|---|---|---|
| near_miss_negative | 9 | Rule-015 ×8, Rule-002 ×1 |
| hard_negative | 5 | Rule-001 ×2, Rule-002 ×2, Rule-015 ×1 |
| name_collision_negative | 3 | Rule-017 ×3 |
| twin_like_negative | 2 | Rule-014 ×2 |
| household_member_negative | 1 | Rule-006 |
| special_population | 1 | Rule-006 |

| Helix rule | Attributes it requires |
|---|---|
| Rule-015 | family name, DOB, adult-today flag, gender, address line 1, zip, **email** (no given name) |
| Rule-014 | same as Rule-015 with **phone** in place of email (no given name) |
| Rule-017 | given name, family name, DOB, gender, SSN last 4 |
| Rule-001 | given name, family name, gender, DOB, zip |
| Rule-006 | given name, family name, DOB month and day, gender, address line 1, zip |
| Rule-002 | given name, DOB, address line 1, zip |

**Rule-015 is the main source on the population.** It produced 34 of the 53 helix false links, and 31 of
those 34 score between 0.955 and 0.9555, which is why the service's cut-off removes them. The 21 that remain
at 0.9555 come from Rule-017 ×5, Rule-001 ×5, Rule-006 ×4, Rule-015 ×3, Rule-014 ×2 and Rule-002 ×2; their
scores run 0.9556 to 1.0000, so a threshold change does not fix them. Rules 014 and 015 do not look at the
given name, so two household members who share a family name, DOB, address and an email or phone can link
(consistent with the twin-like and near-miss categories; this is an inference from the rule definitions,
not something the scorer reports).

**Engine, realistic: 4 false links, all `twin_like_negative`** (same-day siblings). The BAI-1167 analysis
attributes all four to rule 30 (`Last* + DOB + Phone`, the documented legacy exception with no twin
disambiguation). Helix links 2 of those 4, so both matchers have the twin problem; helix's is about half
the size and the engine's is the only false-link class it has.

**Curated tier:** engine 3 false links, helix 2, all `sibling_negative` (the same-family twin pairs from
test-set 0.0.5); 2 of them are linked by both.

## 5. What this does and does not say

- It is a comparison on **synthetic test-set data**, one run per cell, deterministic. It says nothing yet
  about real b.well records (replaying real data is the next phase of the v1 proposal).
- The engine is scored with `evaluate_pair()` (verification only, no candidate retrieval), the same path as
  `tests/test_onc_regression.py`. `evaluate_pair` returns a bool, so **there is no rule attribution for the
  engine's own verdicts** in this report; only helix rows carry a rule. Attribution would need a small
  public method on `MatchingEngine` and its own PR.
- Helix is scored in one direction only: `source` is the pair's source (or the population query) and `target`
  is the pair's target (or the candidate).
- Whether the engine's recall gains on `compound_variant` are worth its misses on typos and phone changes
  is a policy question (a combined or tiered decision is possible); this report does not answer it.

## 6. Which helix versions production uses

Read from lockfiles and Helm values on the default branches, 2026-10-21. **Lockfiles are not deployments**;
no deployed image tag or running pipeline build was checked here.

| Consumer | Locked helix version | Match decision |
|---|---|---|
| Real-time match service (`main`) | 3.0.1 (`>=3.0.1`) | score ≥ 0.9555 (`MATCH_SCORE_THRESHOLD`, Helm values and code default) |
| Batch ingestion pipeline (default branch) | 2.20 (`>=2.1.0`) | library's `matched` flag (0.955); no separate threshold found in its matcher module |

- **2.20 vs 2.1.0:** `git diff 2.1.0 2.20 -- helix_personmatching` is empty. 2.20 changes 15 files, all
  packaging, CI and Docker (`setup.py` and `Pipfile` to `pyproject.toml`/`uv.lock`), so the 2.1.0 columns are
  the 2.20 columns.
- **3.0.1 vs 2.1.0:** 3.0.1 migrates to `fhir.resources` 8.3 (Pydantic v2) and touches 65 files. On all four
  tiers the per-record CSVs are **byte-identical** to 2.1.0, scores included.

So the pipeline path is judged at 0.955 and the service path at 0.9555. Both rows of §2 apply, and the
0.9555 table shows what the service sees.

## 7. Open items

1. **Which cut-off the comparison should use.** 0.9555 removes helix's Rule-015 band on this data at no
   measured recall cost; 0.955 is what the pipeline applies. The project and DS leads own that choice.
2. **Engine rule attribution** (§5) if a rule-by-rule comparison is wanted.
3. **Real-record replay** to confirm the synthetic gaps (recall ~0.95 for both, helix's extra links) hold.
4. **Deployed versions**: confirm the prod service image tag and pipeline build against §6.

## 8. Method and reproduction

Data is read from git, not from a checkout (curated tier at test-set `ea2d2e2` = tag 0.0.5, realistic tier
at `e4cf29e`), and helix from `git archive` of its tags, all into a scratch directory:

```bash
git -C <test-set> show ea2d2e2:evaluation/cases/<file>.jsonl > <dir>/<file>.jsonl   # curated
git -C <test-set> show e4cf29e:evaluation/cases/<file>.jsonl > <dir>/<file>.jsonl   # realistic
git -C <helix> archive 2.1.0 | tar -x -C <scratch>/helix_2.1.0                      # and 3.0.1

PYTHONPATH=. python z_scripts/compare_engines.py --cases-dir <dir> --tier {curated,realistic} \
    --helix-repo <scratch>/helix_2.1.0 --out-dir <out> [--helix-threshold 0.9555]
```

- Helix 2.1.0 needs `fhir.resources<8`; 3.0.1 needs `>=8.3`. They ran in two virtualenvs; the 3.0.1 one
  pins `fhirschemapy==0.0.12` so the engine is identical (engine counts match in both).
- Each run writes `pairs_<tier>.csv` and `population_<tier>.csv` holding only the records where the two
  matchers do not both agree with the label: ids, category, label, each verdict, bucket, and helix's score
  and rule. No patient fields. The anchors in §2 were reproduced exactly with helix 2.1.0 before any other
  run was trusted.
- Test: `z_scripts/test_compare_engines.py` (injected `Side(prepare, match)` stubs, no data).
