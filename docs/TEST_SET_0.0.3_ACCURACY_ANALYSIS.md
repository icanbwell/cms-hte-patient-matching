# Accuracy analysis against test-set 0.0.3 — what improves recall

Date: 2026-10-06 (re-run after fixes 1 and 2, both engine changes). Engine: `patient_matching` on
`BAI-1061-test-set-0.0.3` (Table 2 Category 1 rules 01–28, 30 + Category 2 household rules).
Data: `cms-hte-patient-matching-test-set` tag `0.0.3` (commit `167f820`), fetched with
`make onc-tests`; the data is unmodified in every run below.

This supersedes the earlier three-change proposal's numbers, which were measured on the previous
test set (baseline recall 0.9717, ~80,000 evaluations).

## 1. Summary

| Run | Pairs recall (FN) | Pop. recall | Pop. precision | Pop. FPR | Pop. F1 | FP |
|---|---|---|---|---|---|---|
| 0.0.3 as shipped, original engine | 0.9290 (968) | 0.9305 | 0.9998 | 0.00004 | 0.9639 | 3 |
| + fix 1 (placeholder-name bug), 0.0.3 data | 0.9326 (919) | 0.9341 | 0.9998 | 0.00004 | 0.9658 | 3 |
| + fix 2 (phone normalizer keeps well-formed numbers with an unassigned exchange) | **0.9516 (660)** | **0.9515** | 0.9998 | 0.00004 | **0.9750** | 3 |

Both fixes are measured with the real code, not a simulation, on the unmodified 0.0.3 data. Pairs FPR is 0.0052 throughout; the
3 false positives are the sibling-twin pairs in `LEARNINGS.md` and never change.

With the fixes, population recall (0.9515) and F1 (0.9750) clear the original 0.95 / 0.97 floors that
were temporarily relaxed, and pairs recall (0.9516) clears 0.95. The floors have been restored in this PR (no data change or pin bump needed).

## 2. Where the 968 original false negatives came from

For each missed true match, the closest-to-matching rule and the field that blocked it (0.0.3 as
shipped, original engine):

| Group | FN | Closest rule blocked by |
|---|---|---|
| Initial-only first name + DOB error (`compound_variant`) | 331 | `first_name` 214, `mbi` 73, `namespace_id` 24, `dob` 19 |
| Family-name error + initial-only first name | 121 | `first_name` 107 |
| DOB error + family-name error | 102 | `dob` 70, `phone` 13 |
| `placeholder/given` (e.g. "BABY GIRL") | 61 | `first_name` 56 |
| `marriage_variant` | 47 | `street_line` 35 |
| Single DOB mutations (`dob_month/year/typo/day/swap`) | 116 | `dob` ~97 |
| `phone_churn` (replaced / dropped) | 47 | mixed |
| `ssn_dropped` | 22 | `street_line` 13 |
| `given_abbreviate` alone | 22 | `first_name` 22 |
| Other (surname change, hyphenated, diacritic, punctuation, address, email) | ~80 | `last_name`, `first_name`, `street_line` |

Two causes cut across these groups and were not about matching rules at all; both are now fixed (§3).

## 3. Fixes applied

### 3.1 Fix 1 — placeholder detection discarded valid family names (engine bug)

`NameNormalizer._normalize_name_entry` built `full_name = primary_given + family`
(`"babygirlaaron"`) and ran it through the prefix-anchored `^baby…`/`^infant…`/`^newborn…`
patterns. Because the *given* name starts with `baby`, the pattern matched and the whole HumanName
entry was dropped, **including a real family name**. The record then had no `last_name`, so every
rule needing one — including rule 30 (`Last* + DOB + Phone`) — could not fire.

Change (`patient_matching/normalization/name_normalizer.py`): when the given name is a placeholder
and the family name is not, drop the given names and keep the family name. When both are
placeholders (e.g. `Baby Boy Doe`) the entry is still dropped, as before.
Tests: `test_placeholder_given_keeps_real_family_name` (4 givens) and
`test_placeholder_given_and_family_still_filtered`; all 132 normalization tests pass.

Measured: population recall 0.9305 → 0.9341 (+0.0036), pairs FN 968 → 919. A pre-fix simulation
had predicted +0.0040.

### 3.2 Fix 2 — the phone normalizer dropped well-formed numbers with an unassigned exchange

1,650 of 14,219 pairs-tier source records had a phone the normalizer rejected as `invalid_number`
and silently dropped. About 11% of all ONC phones (36,573 of ~330,000 in the two shards sampled) are
well-formed 10-digit numbers whose exchange code starts with `1` (a few with `0`), which no real
line uses, so `phonenumbers.is_valid_number` rejects them. Two records holding the same such number
are still linked by it; discarding it threw away real match evidence.

Change (`patient_matching/normalization/phone_normalizer.py`): after `is_valid_number` fails, the
number is still accepted if it would be valid with its exchange's first digit swapped for a valid
one (`_is_well_formed_nanp`), and is then formatted to E.164 as usual. That keeps rejecting wrong
lengths, area codes that are not assigned (e.g. 555), and non-+1 numbers; placeholders (`0000000000`,
`5555555555`, ...) are still caught earlier by `PlaceholderDetector`.
Tests: `test_well_formed_number_with_unassigned_exchange_is_kept` (4 forms) and
`test_malformed_number_is_still_rejected` (6 forms); all 142 normalization tests pass.

Measured (on top of fix 1, unmodified 0.0.3 data): population recall 0.9341 → 0.9515 (+0.0174),
pairs FN 919 → 660, false positives unchanged at 3.

This replaces an earlier approach of rewriting the phones in the test-set data
(icanbwell/cms-hte-patient-matching-test-set#19), which gave identical metrics but would have needed a
new test-set release and pin bump and would not help real data with the same shape.

Trade-off: the engine now accepts a phone that cannot belong to a real line. Population-tier false
positives did not change, and phone only counts as evidence inside the Table 2 rules that also require
other fields (or the Category 2 household step), but this loosens a production validity gate.

## 4. Remaining levers (measured on the fixed baseline)

Each row is one change applied alone to the fixed baseline (population recall 0.9515). These are
monkeypatched approximations of proposed rules, not implementations.

| Change | Pairs recall | Pop. recall | Gain | Pop. F1 | New FP |
|---|---|---|---|---|---|
| Initial-only first name (`STANLEY` ≙ `S.`) | 0.9752 | 0.9752 | +0.0237 | 0.9873 | 0 |
| DOB edit distance ≤ 1 (includes month/day swap) | 0.9572 | 0.9579 | +0.0064 | 0.9784 | 0 |
| 4-character name fuzzy carve-out | 0.9552 | 0.9548 | +0.0033 | 0.9768 | 0 |
| Month/day swap only | 0.9521 | 0.9520 | +0.0005 | 0.9753 | 0 |
| DOB edit distance + 4-char carve-out (prior proposals 1–3) | 0.9608 | 0.9612 | +0.0097 | 0.9801 | 0 |
| All of initial + DOB + 4-char | 0.9864 | 0.9869 | +0.0354 | 0.9933 | 0 |

### 4.1 Initial-only first names (needs a CMS decision)

`given_abbreviate` is the largest remaining blocker. Table 2 cannot match it: first-name fuzzy
matching is disallowed for strings under 5 characters (§V.E.3), and an initial is not an
edit-distance-1 variant. The experiment treats a single-letter first name as matching a full first
name starting with that letter, in every rule — including 3-field rules such as rule 11
(`First Name + DOB + Phone`). If adopted, restrict it to rules where at least three *other* fields
match exactly and re-derive that rule's P(collision); an initial is far less selective than the full
first-name u-value Table 3 assumes (not quantified here).

### 4.2 DOB edit distance and month/day swap (prior proposals 1 and 2)

Both still reproduce. The "edit distance" variant is Damerau-Levenshtein ≤ 1 on the `YYYYMMDD`
digits plus month/day transposition, applied wherever a rule already marks DOB fuzzy-eligible
(rules 01, 02, 03, 10, 24). Month/day swap alone adds almost nothing on this data; the gain is
the single-digit typo. Table 3 has no DOB-fuzzy u-value, so adopting this needs a derived one. Rough
size of the widening (not computed here): a date has ~70–80 digit-level neighbours at DL ≤ 1,
against 3 dates for ±1 day.

### 4.3 4-character name carve-out (prior proposal 3)

DL ≤ 1 on 4-character names, accepted only if exactly one non-DOB field went fuzzy and the rest of
the rule matched exactly. Smallest of the three, same u-value caveat.

### 4.4 Hyphenated surnames (inconclusive)

`surname_change/hyphenated` (12 FNs, `AARON` vs `AARON-ABUSHAAR`): an experiment adding hyphen
components to each side's last names had zero effect — the normalizer likely strips the hyphen
before the hook sees it. Not tested properly; no conclusion drawn.

## 5. Residual false negatives (fixed baseline, 660 pairs-tier)

By category: `compound_variant` 493 (mostly an initial-only first name plus a DOB or family-name
error), `fuzzy_variant` 80, `phone_churn` 45, `marriage_variant` 13, `ssn_dropped` 9, `placeholder` 6,
`surname_change` 6, `normalization_edge_case` 4, `address_move` 2, `email_churn` 2.

Most of `compound_variant` is where no Table 2 rule can apply: an abbreviated first name together
with a DOB error and no MBI or namespace ID. Those are by-design misses under the current spec, not
rule gaps — only the changes in §4 (a spec change) would reach them.

## 6. Recommended order

1. Land fixes 1 and 2 (engine) — this PR.
2. ~~Restore the 0.95 / 0.97 floors~~ — done in this PR (pairs recall margin is thin, ~0.0016).
3. Take initial-only first names to the CMS spec owners (§4.1): the biggest remaining lever
   (+0.024), needs a guard and a P(collision) derivation.
4. DOB edit distance and the 4-character carve-out (§4.2, §4.3) are smaller (+0.006, +0.003) and
   also spec changes needing u-values. Month/day swap alone is not worth a separate rule.

## 7. Method and caveats

- Baseline and fix numbers come from `make onc-tests`'s pytest + `scripts/summarize_onc_metrics.py`
  against the original fetched 0.0.3 files.
- §4 counterfactuals re-run both tiers over the same fixtures through
  `normalize → extract → evaluate_pair` with the engine monkeypatched in a throwaway script (not
  committed). DOB variants did not re-derive P(collision); the engine's collision figures are unchanged.
- The pairs tier over-samples rare categories (its recall is not a real-world rate); the population
  tier is the representative one.
- FP is 3 in every run, but the 0.0.3 negatives are mostly sibling/twin and name-collision pairs;
  they say little about FPR for initial-only or DOB-typo matching against real populations. Tier
  2/3 validation (`docs/sessions/conventions.md`) is still required before any §4 change ships.
