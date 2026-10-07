# Accuracy analysis against test-set 0.0.5 — why pairs recall falls below the floor

Date: 2026-10-07. Engine: `patient_matching` on `main` at `a12f322` (Table 2 Category 1 rules 01–28, 30
+ Category 2 household rules), i.e. including the placeholder-given-name and phone-validity fixes from
`TEST_SET_0.0.3_ACCURACY_ANALYSIS.md`. **No engine change in this document.**
Data: `cms-hte-patient-matching-test-set` tag `0.0.5`, fetched with
`ONC_TEST_SET_TAG=0.0.5 make onc-tests`. The 0.0.3 comparison numbers are the same engine re-run on
tag `0.0.3` in the same session (they reproduce the 0.9516 / 0.9515 recorded in the 0.0.3 analysis).

## 1. Summary

| Tier | Metric | 0.0.3 | 0.0.5 | Floor / ceiling |
|---|---|---|---|---|
| Pairs (n = 14,219 → 14,201) | Recall | 0.9516 (fn 660) | **0.9474 (fn 717)** | ≥ 0.95 — **fails** |
| | FPR | 0.0052 (fp 3) | 0.0052 (fp 3) | ≤ 0.01 |
| Population (n_evals 87,747 → 80,000) | Recall | 0.9515 (fn 662) | 0.9504 (fn 674) | ≥ 0.95 — passes by 0.0004 (5 true matches) |
| | Precision | 0.9998 | 0.9998 | ≥ 0.99 |
| | FPR | 0.00004 (fp 3) | 0.00004 (fp 3) | ≤ 0.001 |
| | F1 | 0.9750 | 0.9745 | ≥ 0.97 |

The engine did not change between the two columns; the data did. Recall fell because the 0.0.5
snapshot removed pairs the engine matched trivially and re-sampled the rest, not because a rule
regressed. Every category the test-set changes did not touch (`phone_churn`, `ssn_dropped`,
`marriage_variant`, `surname_change`, `email_churn`, `normalization_edge_case`) has identical
tp/fn in both runs.

To clear the pairs floor on 0.0.5 the engine would need 37 fewer false negatives (fn ≤ 680 of 13,619
true matches).

## 2. What changed in the test set (0.0.3 → 0.0.5)

Four PRs merged after 0.0.3, all under BAI-1061/BAI-1074 in `cms-hte-patient-matching-test-set`:

| PR | Change | Effect on this engine's numbers |
|---|---|---|
| #20 | `generate_fuzzy_variant` never emits a pair identical to its source (`dob_swap`, `given_nickname`, `dob_typo`, `family_transpose`). In 0.0.3, 310 of 2,000 standalone fuzzy pairs were exact copies, which always match. | Lowers recall: removes guaranteed true positives (the PR measured −0.0035 population recall on regenerated data). |
| #21 | Adds `case_exclusions.py`; reproduces the hand filter that dropped rule-29-only true matches (336 pairs, 368 population candidates). | Neutral to slightly negative: the predicate reproduces 316 of the 317 hand-removed pairs; the first version over-dropped ~50 pairs the engine cannot link, which would have hidden false negatives (review caught it). |
| #22 | Regenerates `evaluation/cases/*.jsonl` from the generators at the default seed. | The seed stream shifted, so rows are **not comparable** to 0.0.3 pair-for-pair. Population pools now include `::household::constructed` decoys. |
| #18 | Adds `make generate-full-dataset` (9-shard export). | None — no committed data file. |

Dataset size: pairs 14,219 → 14,201 (13,637 → 13,619 true matches, 582 non-matches both); population
candidates 15,812 → 15,747, evaluations 87,747 → 80,000.

## 3. Where the pairs-tier recall went

Counts are true matches only, same engine, same code path as `tests/test_onc_regression.py`; grouped
by `rationale`.

| Group | 0.0.3 tp / fn (recall) | 0.0.5 tp / fn (recall) | ΔFN |
|---|---|---|---|
| `compound_variant`, abbreviated first name + DOB error | 124 / 325 (0.276) | 130 / 345 (0.274) | +20 |
| `fuzzy_variant/dob_*` (day, month, year, typo, swap) | 787 / 64 (0.925) | 758 / 92 (0.892) | +28 |
| `fuzzy_variant/dob_swap` alone | 174 / 6 (0.967) | 60 / 9 (0.870) | +3 |
| `fuzzy_variant/family_drop_letters` | 194 / 7 (0.965) | 191 / 11 (0.946) | +4 |
| `compound_variant`, DOB error + other | 576 / 75 (0.885) | 577 / 79 (0.880) | +4 |
| `compound_variant`, abbreviated first name + other | 482 / 92 (0.840) | 440 / 95 (0.822) | +3 |
| `fuzzy_variant` (all) | 1,769 / 80 (0.957) | 1,716 / 113 (0.938) | +33 |
| `compound_variant` (all) | 1,300 / 493 (0.725) | 1,278 / 519 (0.711) | +26 |
| All other categories | identical | identical | −2 |
| **Total** | **12,977 / 660 (0.9516)** | **12,902 / 717 (0.9474)** | **+57** |

- **Fuzzy variants (+33 FN, −53 TP):** the expected #20 effect. `dob_swap` went from 180 pairs to 69,
  because 128 of the 0.0.3 swaps were no-ops (per #20). The remaining real swaps match 87% of the time.
  The same applies to `given_nickname`, `dob_typo` and `family_transpose` (fewer, harder pairs).
- **Compound variants (+26 FN):** #20 does not touch `generate_compound_variant`, so this is not the
  no-op removal. The likely causes are the rule-29 exclusion (the final predicate keeps pairs the
  engine can't link that the first version dropped) and the re-sampled seed stream. **Not verified**
  — the 0.0.3 and 0.0.5 pairs are different rows, so a per-pair diff is not possible.
- Per-rationale counts move a few units either way (e.g. `abbrev+dob_swap` FN 35 → 19, `abbrev+dob_day`
  FN 66 → 85) because the compound mutation mix is re-sampled; none of these is a rule behaviour change.

The structure of the residual is the same as 0.0.3: `abbrev + DOB error` is 345 of 717 false negatives
(48%), recall 0.27, and no Table 2 rule can match it without an MBI or namespace ID (see
`TEST_SET_0.0.3_ACCURACY_ANALYSIS.md` §4.1, §5).

## 4. Population tier

Recall 0.9504 (fn 674 of 13,588 true matches). Margin to the 0.95 floor is 5 true matches; F1 0.9745
has 0.0045 of headroom. The tier moved less than the pairs tier (−0.0011 vs −0.0042); the likely reason is that fuzzy and
compound variants are a smaller share of its true matches (not measured). Zero new false positives; the 3
sibling-twin FPs from `LEARNINGS.md` are unchanged. The `::household::constructed` decoys in the new
pools did not produce an extra false positive.

## 5. What would raise accuracy the most (measured on 0.0.5)

Each row applies one change to the current engine and re-runs both tiers on the unmodified 0.0.5 files.
These are monkeypatched approximations of proposed rules, not implementations (throwaway script, not
committed). Baseline: pairs recall 0.9474 (fn 717), population recall 0.9504 (fn 674), F1 0.9745.

| # | Change | Pairs recall (fn) | Pop. recall (fn) | Pop. F1 | New FP |
|---|---|---|---|---|---|
| 1 | **Initial-only first name** matches a full first name with that letter (`S` ≙ `STANLEY`) | 0.9730 (368) | 0.9752 (337) | 0.9873 | 0 |
| 2 | **DOB edit distance ≤ 1** (Damerau-Levenshtein on `YYYYMMDD`, includes month/day swap) | 0.9534 (635) | 0.9554 (606) | 0.9771 | 0 |
| 3 | **Fuzzy first/last name allowed at 4 characters** (min length 5 → 4) | 0.9512 (664) | 0.9534 (633) | 0.9760 | 0 |
| 4 | Month/day swap only | 0.9481 (707) | 0.9511 (665) | 0.9748 | 0 |
| | 1 + 2 | 0.9838 (221) | 0.9843 (213) | 0.9920 | 0 |
| | 1 + 2 + 3 | **0.9854 (199)** | **0.9855 (197)** | **0.9926** | 0 |

Ranking by false negatives removed (pairs tier): initial-only first name −349, DOB edit distance −82,
4-character fuzzy −53, month/day swap −10. The first alone clears the 0.95 floor by 0.023 on both tiers;
the second alone clears it by 0.003–0.005; the third alone by 0.001–0.003.

### 5.1 Initial-only first name (largest lever)

Removes 349 of 717 false negatives (49%): nearly all of `compound_variant` with `given_abbreviate`
plus a DOB error, which no Table 2 rule can match today (first-name fuzzy is disallowed under 5
characters, and an initial is not an edit-distance-1 variant). Needs a CMS spec decision. The
experiment applies it in every rule, including 3-field rules such as rule 11 (First Name + DOB +
Phone). If adopted, restrict it to rules where at least three other fields match exactly and derive
that rule's P(collision), since an initial is far less selective than the full-name u-value Table 3
assumes. Zero new false positives here, but the 0.0.5 negatives are mostly siblings and name collisions
and say little about initials against a real population.

### 5.2 DOB edit distance ≤ 1

Removes 82 (the single-field `dob_*` variants and compounds with a name error that a ±1-day tolerance misses). Applied wherever a rule already marks DOB fuzzy-eligible (rules 01, 02, 03, 10, 24). Table 3
has no DOB-fuzzy u-value, so adopting this needs a derived one; a date has roughly 70–80 digit-level
neighbours at distance 1 against 3 dates for ±1 day, so P(collision) rises materially.
Combined with lever 1 it removes most of the `abbrev + DOB error` group (+0.0108 pairs recall over
lever 1 alone); a few such pairs remain (see §6).

### 5.3 4-character fuzzy

Removes 53 (name-fuzzy cases on names of exactly 4 characters; the per-rationale split was not
broken out). The experiment lowers the length floor globally; the proposed carve-out
restricts it to rules where exactly one non-DOB field is fuzzy and everything else matches exactly,
which would recover somewhat less. Contradicts §V.E.3 as written (no fuzzy under 5 characters).

### 5.4 Month/day swap alone — not worth a rule

Only 10 false negatives (+0.0007). Lever 2 already includes it.

## 6. What remains after all three levers (199 pairs-tier false negatives)

| Group | FN |
|---|---|
| `compound_variant` (two simultaneous errors, e.g. family typo + DOB error; DOB error + abbreviation not fixed by lever 2) | 69 |
| `phone_churn` (replaced 22, dropped 23) | 45 |
| `marriage_variant` | 13 |
| `fuzzy_variant/dob_typo/month/day/year` (still missed with lever 2) | ~36 |
| `ssn_dropped` | 9 |
| `fuzzy_variant/family_drop_letters` | 5 |
| `surname_change/no_history` | 4 |
| other (`placeholder/given`, diacritic, punctuation, `dob_swap`) | ~18 |

The `phone_churn` misses inspected (6 of 45) are sparse records: name and DOB agree, but one side has
no phone or an unrelated one, and no SSN, address or email overlaps. Under Table 2 that is too little
evidence, so these are by-design misses rather than a rule gap (the other 39 were not inspected).

## 7. Recommendation

1. Pin 0.0.5 (`Makefile`: `ONC_TEST_SET_TAG ?= 0.0.5`) and lower the pairs recall floor to 0.94
   (margin 0.0074) with a pointer to this document, so main stays green. This is a gate change and needs
   the project lead's sign-off; it is the second relaxation for a data change (the first was 0.0.2/0.0.3).
2. Take lever 1 (initial-only first name) to the CMS spec owners first. It is the only change that moves
   accuracy materially, and alone it restores the 0.95 floor on both tiers with room to spare. Restore
   the 0.95 floor when it ships.
3. Treat lever 2 (DOB edit distance) as the second request, and lever 3 (4-character fuzzy) as optional.
   All three need derived P(collision) values and Tier 2/3 validation before shipping.
4. Do not change engine behaviour on this evidence alone: these are counterfactuals measured on a
   synthetic benchmark that over-samples these exact variants.

## 8. Method and caveats

- Metrics from `make onc-tests` (pytest + `scripts/summarize_onc_metrics.py`) on unmodified fetched
  files; the per-rationale table comes from a throwaway script that runs `normalize → extract →
  evaluate_pair` over the same files (not committed). Its totals match the gated test (12,977/660 and
  12,902/717).
- Lever numbers (§5) come from a throwaway script that patches `FieldComparator` (initial-only: widens
  `exact_match`, so it also applies to any single-character value in any field; DOB edit distance:
  replaces `dob_fuzzy_match`; 4-character: sets `MIN_FUZZY_LENGTH` to 4 globally, looser than the
  proposed carve-out). The no-lever run reproduces the gated test's 717 / 674 false negatives.
- Pairs tier over-samples rare categories; its recall is not a real-world rate. The population tier is
  the representative one.
- 0.0.3 and 0.0.5 are different samples (seed stream shifted), so category-level deltas of a few
  units are sampling noise, not signal.
- FP = 3 in both; the negatives are mostly sibling/twin and name-collision pairs and say little about
  FPR for initial-only or DOB-typo matching. Tier 2/3 validation (`docs/sessions/conventions.md`) is
  still required before any engine change ships.
