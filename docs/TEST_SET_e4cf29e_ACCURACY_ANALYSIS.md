# Accuracy analysis against test-set `main` at `e4cf29e` (post BAI-1156 stack)

Date: 2026-10-15. Ticket: BAI-1167. Engine: `patient_matching` on `main` at `5c684e9` (Table 2
Category 1 rules 01–28, 30 + Category 2 household rules, including BAI-1152 multi-value blocking).
**No engine change in this document.** The engine is the same in every column below; only the data
changes.

Data: three snapshots of `cms-hte-patient-matching-test-set`, read straight from git (not via
`make fetch-onc-data`, which only knows tags):

| Label | Commit | What it is |
|---|---|---|
| **0.0.5** | `ea2d2e2` | Tag the engine's CI pins today (`ONC_TEST_SET_TAG`). Curated tiers only. |
| **#24** | `2b7e579` | v1 release candidate (BAI-1156): FHIR-conformant records, opaque ids, and the new **realistic** tiers. |
| **main** | `e4cf29e` | #24 plus the follow-up stack #25–#31 (BAI-1159/1160/1161/1162/1164). Not yet tagged. |

Scored with `z_scripts/score_test_set.py`, which uses the same normalize → extract →
`evaluate_pair()` path and confusion-matrix rules as `tests/test_onc_regression.py` and
`tests/test_onc_population_regression.py`. It reproduces the CI numbers on 0.0.5 (population
tp = 12,908, pairs fp = 3). There were 0 extraction or evaluation errors in every run.

## 1. Summary

**Curated tiers (what CI gates on):**

| Tier | Metric | 0.0.5 | #24 | main | CI floor / ceiling (temporary values) |
|---|---|---|---|---|---|
| Pairs (n 14,201 → 14,295) | Recall | 0.9469 (fn 723) | 0.9464 (fn 736) | 0.9464 (fn 736) | ≥ 0.94, passes |
| | FPR | 0.0052 (fp 3) | **0.0000** (fp 0) | 0.0000 (fp 0) | ≤ 0.01 |
| Population (80,000 evals) | Recall | 0.9500 (fn 680) | **0.9453** (fn 750) | **0.9455** (fn 592) | ≥ 0.949, **fails at #24 and main** |
| | Precision | 0.9998 | 1.0000 | 1.0000 | ≥ 0.99 |
| | FPR | 0.00005 (fp 3) | 0.0000 | 0.0000 | ≤ 0.001 |
| | F1 | 0.9742 | 0.9719 | 0.9720 | ≥ 0.97, passes by 0.002 |

**Realistic tiers (new in #24; not gated by the engine's CI):**

| Tier | Metric | #24 | main |
|---|---|---|---|
| Pairs (n 30,538 → 30,999) | Recall | 0.9500 (fn 678) | 0.9506 (fn 674) |
| | FPR | 0.0000 (fp 0 of 16,980) | **0.00023 (fp 4 of 17,362)** |
| | Precision | 1.0000 | 0.9997 |
| Population (80,000 evals) | Recall | 0.9509 (fn 665) | 0.9502 (fn 509) |
| | Precision | 1.0000 | **0.9996 (fp 4)** |
| | F1 | 0.9748 | 0.9743 |

Three takeaways:

1. **Bumping the CI pin to #24 or `main` fails the population recall floor.** Curated population
   recall falls from 0.9500 to about 0.9455 (0.949 is needed). The engine has not regressed. The
   data now has harder positives: new `surname_address_change` pairs, and more `marriage_variant`
   and `placeholder` misses (§3). F1 still passes, by 0.002.
2. **All 4 new false positives are `twin_like_negative`**, the same-day-sibling category added in
   test-set #28. The engine links 4 of 4 through rule 30 (`Last* + DOB + Phone`), the documented
   "legacy exception; no twin disambiguation" rule. These are the first wrong-patient links on the
   realistic tier.
3. **The old 3 false positives are gone.** 0.0.5's three `sibling_negative` ABRAHAM pairs (twins
   with different first names) were removed by #24's same-person guard. The FPR ceiling,
   0.0106-tight in 0.0.3/0.0.5, now has full headroom on the curated pairs tier.

## 2. Engine drift since the 0.0.5 analysis

`TEST_SET_0.0.5_ACCURACY_ANALYSIS.md` was measured on engine `a12f322`. On the same 0.0.5 data, the
current engine (`5c684e9`) gives pairs fn 723 (was 717) and population tp 12,908 (was 12,914). The
population figure matches what the population test's docstring records after the two spec-compliance
changes (the placeholder table and Street Line = line 1 + exact ZIP5). The pairs-tier +6 FN was not
attributed separately. The 0.0.5 column above
uses the current engine, so every column compares like with like.

## 3. Pairs tier: where recall moved (curated, 0.0.5 → #24)

Counts are true matches (tp / fn, recall) by `rationale` category. #25–#31 do not change the curated
pairs file, so `main` equals #24.

| Category | 0.0.5 | #24 = main | ΔFN |
|---|---|---|---|
| `compound_variant` | 1275 / 522 (0.710) | 1280 / 521 (0.711) | −1 |
| `fuzzy_variant` | 1715 / 114 (0.938) | 1700 / 104 (0.942) | −10 |
| `marriage_variant` | 1967 / 13 (0.993) | 1978 / 22 (0.989) | **+9** |
| `phone_churn` | 916 / 45 (0.953) | 912 / 49 (0.949) | +4 |
| `placeholder` | 280 / 5 (0.982) | 277 / 8 (0.972) | +3 |
| `surname_address_change` (new) | — | 156 / 10 (0.940) | **+10** |
| `normalization_edge_case` | 3988 / 4 | 3926 / 3 | −1 |
| `phone_variant` | 103 / 1 | 104 / 0 | −1 |
| `address_move`, `email_churn`, `ssn_dropped`, `surname_change` | unchanged | unchanged | 0 |

Net +13 FN. `compound_variant` is still the floor-binding category (521 of 736 misses, 71%), exactly
as in 0.0.5. The levers ranked in the 0.0.5 analysis §5 (initial-only first name, DOB within one
edit) remain the way to restore the 0.95 floors.

Non-matches: `sibling_negative` goes from fp 3 / 36 to 0 / 33, `name_collision_negative` from 75 to 70
pairs, and the other negative categories have 0 false positives in every snapshot.

## 4. Realistic tier (#24 → main)

| Category | #24 | main | Note |
|---|---|---|---|
| `compound_variant` | 1271 / 467 (0.731) | 1288 / 461 (0.736) | |
| `fuzzy_variant` | 1670 / 109 (0.939) | 1668 / 121 (0.932) | +12 FN |
| `phone_churn` | 967 / 47 (0.954) | 977 / 40 (0.961) | |
| `placeholder` | 298 / 15 (0.952) | 312 / 10 (0.969) | |
| `surname_address_change` | 192 / 3 (0.985) | 198 / 7 (0.966) | |
| `twin_like_negative` (new) | — | **fp 4 / 4** | §5 |
| `near_miss_negative` | fp 0 / 11,449 | fp 0 / 11,583 | |
| `household_member_negative` | fp 0 / 2,388 | fp 0 / 2,387 | |
| `special_population` | fp 0 / 200 | fp 0 / 459 | |

Every other negative category has 0 false positives. The realistic tier sits near the 0.95 recall
line on both tiers (0.9506 / 0.9502). This is the same picture as curated, driven by the same
`compound_variant` misses.

**Population tier, by expected-match count (main).** #27 added queries with 0 and 1 true matches:

| Expected matches | Curated queries (fn / fp) | Realistic queries (fn / fp) |
|---|---|---|
| 0 | 176 (0 / 0) | 204 (0 / 0) |
| 1 | 283 (14 / 0) | 340 (18 / 0) |
| 2+ | 1,541 (578 / 0) | 1,456 (491 / 4) |

The engine never links anything for the zero-match queries. Single-match queries recall at 0.95,
the same as the rest.

## 5. The four `twin_like_negative` false positives

Each pair has the same surname and birth date, clearly different first names, and a shared phone
(two also share an address). One side has no SSN. All are linked by **rule 30**. One pair is also
linked by rules 02 and 11:

| Case | First names | Rules fired |
|---|---|---|
| `15482590::15667250::near_miss::twin` | ROOSEVELT / ANTHONY | 30 |
| `15769754::15485601::near_miss::twin` | JOELLEN L / AMBER L | **02, 11**, 30 |
| `15853563::15473756::near_miss::twin` | KENYA / TALITHA IDA | 30 |
| `16007727::15410951::near_miss::twin` | CHERITY / TIARA | 30 |

- **Rule 30** has no first-name field, so it cannot tell same-day siblings with one household phone
  apart. `table2_rules.py` already labels it "legacy exception; no twin disambiguation"
  (spec §IV.G). This is the twin ambiguity recorded in `LEARNINGS.md` for 0.0.2/0.0.3, now with a
  test-set category that measures it directly.
- **Rules 02 and 11** fire on JOELLEN L / AMBER L only because both carry the middle initial `L`, and
  `FieldExtractor` puts every given name, single letters included, into `first_names`. Without the
  initials, rule 11 does not fire (verified). This is the middle-name leak `LEARNINGS.md` already
  records ("First Name accepts the middle name"), now seen producing a link between two different
  people. It does not change the count here (rule 30 links the pair anyway).

Sample size is tiny: 4 rows in the pairs tier, 4 population evaluations. The FPR they produce
(0.00023 pairs, 0.00005 population) is well under both ceilings.

## 6. Recommendation

1. **Don't bump `ONC_TEST_SET_TAG` to #24/`main` alone.** Curated population recall (0.9455)
   fails the 0.949 floor. Either bump together with the accuracy levers from the 0.0.5 analysis §7,
   or lower the floor to 0.945 with a note pointing here, as was done for 0.0.5.
2. **Have the test-set owner tag `e4cf29e`** (for example `0.0.6`), so the engine can pin it
   reproducibly and CI can score the realistic tier too.
3. **Decide what twins should expect.** Rule 30 links same-day siblings who share a phone, by
   design. The test set now labels them non-matches. Either accept them as known false positives,
   with a ceiling that allows them, or add twin disambiguation (for example a first-name veto when
   both first names are present and clearly different) and price it.
4. **Ask the test-set owner for an evaluation-only category sidecar for the population tier.**
   Since the label-leak fix, candidate ids are opaque hashes, so population misses can no longer
   be attributed to a category (as the 0.0.5 analysis §4 did). A separate file mapping opaque id →
   category, not part of the model input, would restore that without reintroducing the leak.

## 7. Method and caveats

- Reproduce: extract the six `evaluation/cases/*.jsonl` files at each commit
  (`git show <sha>:evaluation/cases/<file>`), then
  `PYTHONPATH=. python z_scripts/score_test_set.py --cases-dir <dir> --tier curated|realistic --out m.json`.
  `z_scripts/test_score_test_set.py` covers the scorer on synthetic rows.
- The pairs tier over-samples rare categories, so its precision has no real-world meaning; use the
  population tier for precision/F1 (same caveat as the CI tests).
- `case_id`s are only stable for pairs a release keeps, so §3 and §4 compare category counts, not
  pair-for-pair.
- The realistic tier shifts every birth date forward 9 years (test-set BAI-1161). The engine
  compares DOBs between records, so the shift applies equally to both sides and doesn't affect
  matching.
