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

All 15 suggestions with their uplift are in the ranked table in §5.A. Checked against the 2e-12 collision threshold (§5.7), the best spec-compliant package is DOB ±1 digit in rules 02, 03 and the household rules plus initial-only first name in the household rules: pairs recall 0.9780 (+0.0306). Each half alone also clears the 0.95 floor.

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
sibling-twin FPs from `LEARNINGS.md` are unchanged. The false-positive count is unchanged (3) with the
new `::household::constructed` decoys in the pools; the identities of the 3 were not compared across
versions because the seed shift makes the rows non-comparable.

## 5. What would raise accuracy the most (measured on 0.0.5)

### 5.A All suggestions ranked by spec-compliant pairs-recall uplift

Every change measured, one row each. Baseline: pairs recall 0.9474 (fn 717), population recall 0.9504,
population F1 0.9745. Target: pairs recall ≥ 0.95 (needs +0.0026), population recall ≥ 0.95, population F1
≥ 0.97. Uplift is the absolute change against the baseline. The false-positive count is 3 in every run (no
new false positives).

Three recall columns, because the first overstates what is approvable:

- **Unrestricted:** the change applied in every rule it could touch, ignoring the 2e-12 collision threshold.
- **Spec-compliant (bold):** the change applied only in the rules where P(collision) stays at or under
  2e-12 using Table 3 values scaled by the measured multiplier of the widened field (§5.7). This is the
  number that can be proposed without asking CMS for an exception, and the table is ranked by it.
- **Empirical basis:** same, but the Census-measured fields (names, DOB, ZIP, SSN/ITIN last 4) use their
  measured u. Evidence for a waiver, not a pass of the spec's test.

| Rank | Suggestion | Pairs recall, unrestricted (fn) | Uplift | Pop. recall | Pop. F1 | **Pairs recall, spec-compliant** | **Uplift** | Pairs recall, empirical basis | Uplift | Clears 0.95 spec-compliant? |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **5 + 1**: DOB ±1 digit in every DOB-using rule + initial-only first name in every rule | 0.9876 (169) | +0.0402 | 0.9879 | 0.9938 | **0.9780** | **+0.0306** | 0.9822 | +0.0348 | Yes |
| 2 | **5 + 6**: DOB ±1 digit in every DOB-using rule + initial-only first name inside household rules | 0.9822 (243) | +0.0348 | 0.9838 | 0.9917 | **0.9780** | **+0.0306** | 0.9822 | +0.0348 | Yes |
| 3 | **1 + 2 + 3**: initial-only + DOB ±1 digit (fuzzy-eligible rules) + 4-character fuzzy | 0.9854 (199) | +0.0380 | 0.9855 | 0.9926 | **0.9561** | **+0.0087** | 0.9787 | +0.0314 | Yes |
| 4 | **1 + 2**: initial-only first name + DOB ±1 digit (rules where DOB is already fuzzy-eligible) | 0.9838 (221) | +0.0364 | 0.9843 | 0.9920 | **0.9557** | **+0.0083** | 0.9772 | +0.0299 | Yes |
| 5 | **1**: Initial-only first name, every rule | 0.9730 (368) | +0.0256 | 0.9752 | 0.9873 | **0.9557** | **+0.0083** | 0.9562 | +0.0088 | Yes |
| 6 | **5 + 7**: DOB ±1 digit in every DOB-using rule + initial-only in rules with ≥ 4 fields | 0.9775 (306) | +0.0302 | 0.9795 | 0.9896 | **0.9533** | **+0.0059** | 0.9764 | +0.0291 | Yes |
| 7 | **5**: DOB ±1 digit in **every** DOB-using rule (incl. exact-DOB rules like 11, 12) | 0.9761 (326) | +0.0287 | 0.9778 | 0.9887 | **0.9533** | **+0.0059** | 0.9761 | +0.0287 | Yes |
| 8 | **6**: Initial-only first name, only inside household (Category 2) rules | 0.9533 (636) | +0.0059 | 0.9562 | 0.9775 | **0.9533** | **+0.0059** | 0.9533 | +0.0059 | Yes |
| 9 | **2**: DOB ±1 digit, only where DOB is already fuzzy-eligible (01, 02, 03, 10, 24) | 0.9534 (635) | +0.0060 | 0.9554 | 0.9771 | **0.9517** | **+0.0043** | 0.9534 | +0.0060 | Yes (thin) |
| 10 | **9**: DOB ±1 digit, only inside household (Category 2) rules | 0.9515 (660) | +0.0042 | 0.9547 | 0.9767 | **0.9515** | **+0.0042** | 0.9515 | +0.0042 | Yes (thin) |
| 11 | **3**: Fuzzy first/last name at 4 characters (minimum 5 → 4) | 0.9512 (664) | +0.0039 | 0.9534 | 0.9760 | **0.9512** | **+0.0038** | 0.9512 | +0.0039 | Yes (thin) |
| 12 | **7**: Initial-only first name, only rules whose step has ≥ 4 fields | 0.9504 (675) | +0.0031 | 0.9538 | 0.9762 | **0.9499** | **+0.0026** | 0.9504 | +0.0031 | **No** |
| 13 | **4**: Month/day swap only | 0.9481 (707) | +0.0007 | 0.9511 | 0.9748 | **0.9478** | **+0.0004** | 0.9481 | +0.0007 | **No** |
| 14 | **5 + 6 + 8**: lever 5 + household-only initial + edit distance 2 for ≥ 7 characters | 0.9825 (239) | +0.0351 | 0.9843 | 0.9920 | not computed | – | not computed | – | not computed (edit-distance-2 u not measured) |
| 15 | **8**: Edit distance 2 for strings ≥ 7 characters | 0.9490 (695) | +0.0016 | 0.9523 | 0.9755 | not computed | – | not computed | – | not computed (edit-distance-2 u not measured) |

Not in the table: household-identifier-only rules (`phone + street + zip` and similar). They show large
uplift on this benchmark (e.g. 506 of 717 misses) but are rejected in §5.6 because they identify a
household, not a person. The numbered levers are defined in §5.1–§5.5.

Each row applies one change to the current engine and re-runs both tiers on the unmodified 0.0.5 files.
These are monkeypatched approximations of proposed rules, not implementations (throwaway script, not
committed). Baseline: pairs recall 0.9474 (fn 717), population recall 0.9504 (fn 674), F1 0.9745.

| # | Change | Pairs recall (fn) | Pairs uplift | Pop. recall (fn) | Pop. uplift | Pop. F1 | F1 uplift | New FP |
|---|---|---|---|---|---|---|---|---|
| | Baseline (no change) | 0.9474 (717) | – | 0.9504 (674) | – | 0.9745 | – | – |
| 1 | **Initial-only first name** matches a full first name with that letter (`S` ≙ `STANLEY`) | 0.9730 (368) | **+0.0256** | 0.9752 (337) | **+0.0248** | 0.9873 | +0.0128 | 0 |
| 2 | **DOB edit distance ≤ 1** (Damerau-Levenshtein on `YYYYMMDD`, includes month/day swap) | 0.9534 (635) | +0.0060 | 0.9554 (606) | +0.0050 | 0.9771 | +0.0026 | 0 |
| 3 | **Fuzzy first/last name allowed at 4 characters** (min length 5 → 4) | 0.9512 (664) | +0.0038 | 0.9534 (633) | +0.0030 | 0.9760 | +0.0015 | 0 |
| 4 | Month/day swap only | 0.9481 (707) | +0.0007 | 0.9511 (665) | +0.0007 | 0.9748 | +0.0003 | 0 |
| | 1 + 2 | 0.9838 (221) | +0.0364 | 0.9843 (213) | +0.0339 | 0.9920 | +0.0175 | 0 |
| | 1 + 2 + 3 | **0.9854 (199)** | **+0.0380** | **0.9855 (197)** | **+0.0351** | **0.9926** | +0.0181 | 0 |

Uplift is the absolute change against the baseline row. Lever 3 adds +0.0016 pairs recall (+0.0012
population) on top of 1 + 2, so its marginal value shrinks once the others land.

### 5.0 Target metrics and which levers reach them

Targets are the checked-in gates (`tests/test_onc_regression.py`, `tests/test_onc_population_regression.py`).
Gap = uplift still needed from the baseline.

| Metric | Target | Baseline (0.0.5) | Gap to target |
|---|---|---|---|
| Pairs recall | ≥ 0.9500 | 0.9474 | **+0.0026** (37 fewer fn) |
| Pairs FPR | ≤ 0.0100 | 0.0052 | met |
| Population recall | ≥ 0.9500 | 0.9504 | met (margin 0.0004) |
| Population precision | ≥ 0.9900 | 0.9998 | met |
| Population FPR | ≤ 0.0010 | 0.00004 | met |
| Population F1 | ≥ 0.9700 | 0.9745 | met (margin 0.0045) |

Only pairs recall fails, so the uplift that matters is pairs recall. Margin over target after each change
(a negative or thin margin means the change does not safely restore the gate):

| Change | Pairs recall | Margin vs 0.95 | Pop. recall | Margin vs 0.95 | Pop. F1 | Margin vs 0.97 | All targets met? |
|---|---|---|---|---|---|---|---|
| Baseline | 0.9474 | **−0.0026** | 0.9504 | +0.0004 | 0.9745 | +0.0045 | **No** |
| 1. Initial-only first name | 0.9730 | +0.0230 | 0.9752 | +0.0252 | 0.9873 | +0.0173 | Yes |
| 2. DOB edit distance ≤ 1 | 0.9534 | +0.0034 | 0.9554 | +0.0054 | 0.9771 | +0.0071 | Yes |
| 3. 4-character fuzzy | 0.9512 | +0.0012 | 0.9534 | +0.0034 | 0.9760 | +0.0060 | Yes (thin) |
| 4. Month/day swap only | 0.9481 | −0.0019 | 0.9511 | +0.0011 | 0.9748 | +0.0048 | **No** |
| 1 + 2 | 0.9838 | +0.0338 | 0.9843 | +0.0343 | 0.9920 | +0.0220 | Yes |
| 1 + 2 + 3 | 0.9854 | +0.0354 | 0.9855 | +0.0355 | 0.9926 | +0.0226 | Yes |

Precision and FPR targets stay met in every run (precision 0.9998, no new false positives).

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

### 5.5 Additional levers found by searching the misses

To look beyond the four levers above, each of the 717 pairs-tier misses was reduced to which fields agree
between source and target (exact, one edit apart, initial-only, or missing on a side). Two patterns
dominate:

- **One or two fields wrong on an otherwise identical record.** The largest signatures are "first name
  is an initial + DOB one digit off" (about 300 pairs) with last name, phone, street, ZIP and SSN last 4
  all exact; then "last name one edit off on a ≤4-character name + initial"; then DOB one digit off alone.
- **Sparse records** (phone dropped or replaced, no DOB, placeholder address). Nothing recoverable.

That pointed to variants of the existing levers plus one new one, each measured on the 0.0.5 data
(monkeypatched, as in §5). Uplift is against the baseline (pairs 0.9474 / pop. 0.9504 / F1 0.9745).

| # | Change | Pairs recall (fn) | Pairs uplift | Pop. recall | Pop. uplift | Pop. F1 | New FP | Meets 0.95 target? |
|---|---|---|---|---|---|---|---|---|
| 5 | **DOB edit distance ≤ 1 in every rule that uses DOB**, including rules where DOB is exact today (e.g. rule 11 First Name + DOB + Phone) | **0.9761 (326)** | **+0.0287** | 0.9778 | +0.0274 | 0.9887 | 0 | Yes, margin +0.0261 |
| 6 | Initial-only first name **restricted to Category 2 (household) rules**, where phone/email/SSN last 4 already matched exactly in step 1 | 0.9533 (636) | +0.0059 | 0.9562 | +0.0058 | 0.9775 | 0 | Yes, margin +0.0033 |
| 7 | Initial-only first name restricted to rules with ≥ 4 fields | 0.9504 (675) | +0.0030 | 0.9538 | +0.0034 | 0.9762 | 0 | Barely, margin +0.0004 |
| 8 | Fuzzy match at edit distance 2 for strings ≥ 7 characters (`family_drop_letters` of 2 letters) | 0.9490 (695) | +0.0016 | 0.9523 | +0.0019 | 0.9755 | 0 | No |
| 9 | DOB edit distance ≤ 1 applied only inside Category 2 rules | 0.9515 (660) | +0.0042 | 0.9547 | +0.0043 | 0.9767 | 0 | Yes, margin +0.0015 (corrected: see note below) |
| | **5 + 6** | **0.9822 (243)** | **+0.0348** | 0.9838 | +0.0334 | 0.9917 | 0 | Yes |
| | 5 + 1 (initial-only in all rules) | 0.9876 (169) | +0.0402 | 0.9879 | +0.0375 | 0.9938 | 0 | Yes |
| | 5 + 6 + 8 | 0.9825 (239) | +0.0351 | 0.9843 | +0.0339 | 0.9920 | 0 | Yes |

Findings:

- **Lever 5 is the largest single uplift measured** (+0.0287, 391 fewer false negatives), larger than
  initial-only first name (+0.0256) and more than four times lever 2. The reason: most DOB-error misses
  are in rules where DOB is exact today (rules 11, 12 and others), which lever 2 never touches. It is
  also the riskiest to price. `calculations/` now measures it (§5.7): a DOB within one edit is 32.4 times more
  likely to collide than an exact DOB, so rule 11 goes from 2e-12 to about 6.5e-11, about 32 times over the
  2e-12 approval threshold. Restricted to the rules that stay under it, lever 5 drops to 0.9533 (+0.0059).
- **Lever 6 is the safest way to use initial-only first names.** It gets +0.0059 by itself, enough to clear
  the target, while keeping the weak match (measured: an initial matches 37.5 times as often as an exact first name) behind
  a household-level exact match. 5 + 6 reaches 0.9822 pairs recall; adding initial-only in every rule
  adds only +0.0054 more.
- Lever 8 is small and brings the same u-value problem as lever 3 for little gain. Not recommended.
- **Correction to lever 9.** An earlier version of this document reported lever 9 as having no effect, on the
  reasoning that household rules have no fuzzy-eligible DOB. That was an artifact of the first test harness,
  which only widened the fuzzy-eligible DOB path and missed household rules whose DOB must match exactly.
  With the harness in `scripts/lever_recall.py` (which widens both paths) lever 9 gives pairs recall 0.9515
  (+0.0042) and passes the collision check in all 8 household rules (§5.7).

### 5.6 Candidate new rules, measured and mostly rejected

The same field-agreement view was used to test brand-new field combinations (2 to 4 fields from first name,
last name, DOB, phone, email, SSN last 4, street, ZIP, with fuzzy variants) as additional exact-match
rules. Many have zero false positives on this benchmark and large uplift, for example `phone + street + zip`
(covers 506 of the 717 pairs-tier misses, 1 false positive) and `SSN last 4 + street + ZIP` (395, 0 false
positives). **These should not be adopted.** Phone, email, SSN last 4 and address are household
identifiers; the spec moved rules 13-16 into the household/individual architecture precisely because
those fields identify a household, not a person (see `table2_rules.py`). A rule built only from household
identifiers would merge family members, and this benchmark cannot see that: its negatives are random pairs
plus a small sibling set (36 pairs), so zero false positives is weak evidence.

Combinations that include a person-level field plus a household identifier (for example `DOB (±1 digit) +
phone + street`, 372 misses, 0 false positives, P(collision) about 2e-13 using the DOB value assumed when this section was first written) are
effectively lever 5 restated as separate rules, and add nothing beyond it.

### 5.7 Does each lever stay under the 2e-12 collision threshold? (measured in `calculations/`)

A widened match raises the u-probability of the field it widens, and a rule is only approvable if the
product of its fields' u-values stays at or under 2e-12. The `calculations/` tool (`make calculate`) now
measures the widened values from Census data, and `scripts/collision_feasibility.py` prices every rule.

**Measured multipliers** (empirical widened u divided by the empirical baseline it widens):

| Widening | Widened u | Baseline u | Multiplier |
|---|---|---|---|
| Initial-only first name (first letter agrees) | 0.06717 | 0.001793 (exact first name) | **37.5×** |
| DOB within one edit (digit replaced or swapped, month/day swap, ±1 day) | 0.001044 | 3.226e-05 (exact DOB, date level) | **32.4×** |
| DOB month/day swap (plus ±1 day) | 1.084e-04 | 3.226e-05 | 3.36× |
| DOB ±1 day (the spec's existing DOB* tolerance, for reference) | 9.678e-05 | 3.226e-05 | 3.00× |
| First name fuzzy, 4-character minimum | 0.002583 | 0.002257 (5-character minimum) | 1.14× |
| Last name fuzzy, 4-character minimum | 0.000911 | 0.000833 | 1.09× |

These replace the values assumed earlier in this document (75× for DOB, 5× for an initial). The initial
widens the match far more than assumed (37.5×, so a much weaker identifier) and the DOB widening somewhat
less (32.4×).

**Two bases for the threshold test:**

- **Scaled-conservative (spec-compliant):** the rule's published P(collision) is multiplied by the measured
  multiplier for each widened field, which keeps Table 3's built-in margin of pessimism. Capped at u = 1.
- **Empirical:** names, DOB, ZIP and SSN/ITIN last 4 use measured u; street, phone, email, MBI and the
  legal/insurance/namespace IDs stay at their Table 3 value because the tool has only a floor, or no
  estimate, for them.

**Rules where each lever fits under 2e-12** (of the rules it applies to):

| Lever | Spec-compliant (scaled-conservative) | Empirical basis |
|---|---|---|
| Initial-only first name, every rule | 10 of 26: 02, 03 and all 8 household rules | 17 of 26: adds 01, 04, 05, 06, 07, 27, 28 |
| Initial-only, household rules only | 8 of 8 | 8 of 8 |
| DOB ±1 digit, every DOB rule | 10 of 25: 02, 03 and all 8 household rules | 25 of 25 |
| DOB ±1 digit, fuzzy-eligible rules | 2 of 5: 02, 03 | 5 of 5 |
| DOB ±1 digit, household rules only | 8 of 8 | 8 of 8 |
| 4-character fuzzy | 17 of 20 | 20 of 20 |
| DOB month/day swap | 2 of 5: 02, 03 | 5 of 5 |

Rules 11, 12, 13–16 (Category 1), 08, 09 and 23 sit at exactly 2e-12, so no widening of any of their fields
fits under the spec's own numbers. Rules 01, 04–07, 10, 24, 27, 28 and 30 have 2× to 7× of headroom and fit
only the narrowest changes. Rules 02 and 03 (First + Last + DOB + Phone/Email, P = 1e-14) have 200× and the
eight household rules have the most room, so that is where the spec-compliant uplift is.

**Recall when each lever is applied only where it fits** (the "spec-compliant" columns in §5.A):

| Lever | Unrestricted | Spec-compliant | Empirical basis |
|---|---|---|---|
| Initial-only, every rule | 0.9730 | 0.9557 | 0.9562 |
| Initial-only, household rules only | 0.9533 | **0.9533** | 0.9533 |
| DOB ±1 digit, every DOB rule | 0.9761 | 0.9533 | 0.9761 |
| DOB ±1 digit, household rules only | 0.9515 | **0.9515** | 0.9515 |
| DOB ±1 digit, fuzzy-eligible rules | 0.9534 | 0.9517 | 0.9534 |
| 4-character fuzzy | 0.9512 | 0.9512 | 0.9512 |
| **DOB ±1 digit (every DOB rule) + initial-only (household)** | 0.9822 | **0.9780** | 0.9822 |
| DOB ±1 digit (every DOB rule) + initial-only (every rule) | 0.9876 | 0.9780 | 0.9822 |

Reading it:

- **Two levers are fully spec-compliant on their own and clear the 0.95 floor:** initial-only first name
  inside the household rules (0.9533, +0.0059) and DOB ±1 digit inside the household rules (0.9515, +0.0042).
  Every rule they touch stays under 2e-12 on both bases.
- **Together with DOB ±1 digit in rules 02 and 03, they reach 0.9780 (+0.0306) while staying spec-compliant.**
  That is 0.0042 below the unrestricted 0.9822, so almost nothing is lost by respecting the threshold.
- **The larger unrestricted numbers need an exception.** DOB ±1 digit in every DOB rule (0.9761) and
  initial-only in every rule (0.9730) depend on widening rules 11, 12 and others that have no headroom.
  The empirical basis shows the Census data would support the DOB widening in all 25 rules, which is the
  case to make to CMS for a waiver; it does not satisfy Table 3 as written.
- **Combining levers narrows where each fits.** In rules 02 and 03 either widening fits alone, not both
  (1e-14 × 37.5 × 32.4 = 1.2e-11). The assignment script picks the largest subset that fits per rule.

**Not covered:** edit distance 2 for strings of 7 or more characters (lever 8): no u was measured for it, it
adds only +0.0016, and it is not recommended. The 4-character fuzzy multipliers are for first and last
names only; the lever as patched also lowers the minimum for street lines, which is not quantified. Rules
11, 12 and 13–16 would need a compensating stricter field (not measured here) to take any widening.

**How to rerun:**

```bash
cd calculations && make calculate        # writes the widened rows to outputs/u_probabilities.csv
cd .. && ONC_TEST_SET_TAG=0.0.5 make fetch-onc-data
uv run python scripts/collision_feasibility.py      # per-rule P(collision) feasibility
uv run python scripts/lever_recall.py --json out.json   # recall with each lever restricted
```

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

Target: pairs recall back to ≥ 0.95 (gap +0.0026), all other gates held, and every widened rule at or under
the 2e-12 collision threshold (§5.7).

1. **Propose this spec-compliant package: initial-only first name inside the household (Category 2) rules,
   plus DOB within one edit in rules 02, 03 and the household rules.** Pairs recall 0.9780 (+0.0306),
   population recall 0.9802, F1 0.9899, no new false positives, every touched rule under 2e-12 on both
   bases. Each half also clears the floor alone (initial-only household +0.0059, DOB household +0.0042),
   so it can be staged.
2. **Do not widen rules 11, 12, 13–16, 08, 09 and 23** without an exception: they are at exactly 2e-12.
   If the larger gain is wanted (DOB within one edit in every DOB rule, 0.9761 alone, 0.9822 with the
   household initial), take the empirical evidence to CMS (§5.7): the measured multiplier is 32.4× and the
   Census-measured fields leave the rules far under the threshold empirically, but Table 3 as written does
   not allow it.
3. **Do not use initial-only first name in every rule.** It adds only +0.0054 over the household-only
   version on top of the DOB lever, and fits under 2e-12 in just 10 of 26 rules spec-compliantly.
4. Do not add new household-identifier-only rules (§5.6) however good they look on this benchmark. Levers 3,
   4, 7 and 8 do not by themselves clear the target safely.
5. Until a spec change ships, pin 0.0.5 (`Makefile`: `ONC_TEST_SET_TAG ?= 0.0.5`) with a temporary pairs
   recall floor of 0.94 (margin 0.0074) pointing at this document, and restore 0.95 when the change lands.
   This is a gate change and needs the project lead's sign-off; it is the second relaxation for a data
   change (the first was 0.0.2/0.0.3).
6. Every lever still needs CMS sign-off and Tier 2/3 validation. The collision check here prices fields
   using the published P(collision) times a measured multiplier; it is not a re-derivation of Table 3. Do
   not change engine behaviour on this evidence alone: these are counterfactuals on a synthetic benchmark
   that over-samples these exact variants.

## 8. Method and caveats

- Metrics from `make onc-tests` (pytest + `scripts/summarize_onc_metrics.py`) on unmodified fetched
  files; the per-rationale table comes from a throwaway script that runs `normalize → extract →
  evaluate_pair` over the same files (not committed). Its totals match the gated test (12,977/660 and
  12,902/717).
- Lever numbers (§5) and the restricted numbers (§5.7) come from `scripts/lever_recall.py`, which patches `FieldComparator` (initial-only: widens
  `exact_match`, so it also applies to any single-character value in any field; DOB edit distance:
  replaces `dob_fuzzy_match`; 4-character: sets `MIN_FUZZY_LENGTH` to 4 globally, looser than the
  proposed carve-out). The no-lever run reproduces the gated test's 717 / 674 false negatives.
- §5.5 restrictions: lever 6 limits the patched comparison to rules whose id starts `C2-`; lever 7 to rules
  with ≥ 4 fields; lever 5 patches `exact_match` so any date-shaped value pair gets edit distance ≤ 1.
  §5.6 counts exact-field-agreement combinations over the misses and all baseline-unmatched negatives
  (pairs and population); its P(collision) line used assumed DOB and initial values and predates §5.7,
  which uses measured ones.
- Pairs tier over-samples rare categories; its recall is not a real-world rate. The population tier is
  the representative one.
- 0.0.3 and 0.0.5 are different samples (seed stream shifted), so category-level deltas of a few
  units are sampling noise, not signal.
- FP = 3 in both; the negatives are mostly sibling/twin and name-collision pairs and say little about
  FPR for initial-only or DOB-typo matching. Tier 2/3 validation (`docs/sessions/conventions.md`) is
  still required before any engine change ships.
