# Proposal: extend DOB and short-name fuzzy tolerance to recover recall

**Status:** draft, for discussion — not implemented in this engine. These are proposed
*amendments to the CMS Table 2 matching spec* (E.2/E.3, DOB tolerance), not code changes to
make unilaterally, since this engine's job is to faithfully implement the published spec.

## Why

`make onc-tests` currently measures (population tier, 80,000 query-candidate evaluations):

| Metric | Value | Floor/Ceiling |
|---|---|---|
| Precision | 0.9990 | ≥ 0.9900 |
| Recall | 0.9717 | ≥ 0.9500 |
| FPR | 0.000081 | ≤ 0.0010 |
| F1 | 0.9851 | ≥ 0.9700 |
| Accuracy | 0.9978 | - |

All floors are cleared comfortably, but recall has real headroom before the floor, and the
170 false negatives (out of ~6,000 true positives, pairs tier) break down as:

| Cause | Count | Share |
|---|---|---|
| DOB differs beyond the current ±1-day tolerance (month/day/year/typo/swap) | 105 | 62% |
| Name fuzzy variant exceeds E.2 (distance > 1) or E.3 (< 5 chars) | 43 | 25% |
| Record has no DOB and no other rule combination fires | 18 | 11% |
| Other / needs individual review | 4 | 2% |

The three proposals below target the first two rows. Each was validated empirically against
this repo's existing labeled test set — including the `hard_negative` and `special_population`
categories, which exist specifically to catch precision regressions — before being proposed.

## Proposed changes

### 1. Apply E.2's fuzzy method to the DOB string itself

**Mechanism:** DOB currently uses a bespoke ±1-calendar-day tolerance
(`field_comparator.py::dob_fuzzy_match`), separate from the Damerau-Levenshtein-distance-≤1
method (E.2) already approved for text fields. Looking at the actual failing pairs, almost all
"DOB mismatch" cases are single-digit transcription typos on the `YYYY-MM-DD` string — a decade
digit (`1943`→`1944`), a century digit (`1976`→`1376`), a month or day digit — structurally
identical to the name-typo errors E.2 already tolerates.

**Change:** treat two DOB values as matching if the ISO-8601 date strings have Damerau-Levenshtein
distance ≤ 1 (in addition to, or in place of, the ±1-day rule).

**Precision case:** this reuses a mechanism CMS has already vetted (E.2), rather than inventing a
new one. DOB fuzzy is never evaluated standalone — every Category 1 rule that includes DOB* also
requires First and/or Last Name — so a random unrelated person matching on name *and* having a
DOB one character off is a rarer coincidence than the single-field fuzzy-name case CMS already
accepts.

**Risk:**
- Edit-distance-1 on a fixed-format string doesn't distinguish *where* the edit lands. A
  same-digit-position edit near the year's leading digits (e.g. `1943`→`1843`, `1976`→`1376`) is
  a 100-year jump treated identically to a trivial day-digit edit. That's a much larger date
  divergence riding on the same "distance 1" guarantee, and the ONC synthetic typo fixture wasn't
  built to adversarially probe that specific position — it generates "nearby" corruptions, not
  worst-case ones — so the "0 new FP" result under-samples this failure mode.
- As specified, the comparator would treat two strings as matching purely on edit distance without
  confirming the result is a real calendar date. A malformed/impossible date (e.g. produced by a
  single-digit edit landing on the day field to give `31` in a 30-day month) shouldn't silently
  pass — the change needs an explicit "both sides parse as valid dates" guard, which the current
  ±1-day branch already has (`date.fromisoformat`) and this one would need to add.

### 2. Add a named month/day-transposition equivalence for DOB

**Mechanism:** a distinct, common error pattern — month and day literally swapped
(`2002-10-04` vs `2002-04-10`) — isn't a distance-1 edit on the date string (it's a block swap),
so proposal 1 doesn't catch it.

**Change:** treat two DOB values as matching if
`year` matches, `query.month == candidate.day`, `query.day == candidate.month`, and
`month != day` (guards against dates where day and month are numerically equal, which aren't a
real transposition).

**Precision case:** this is a single, closed, well-defined structural relationship, not a
distance radius — it doesn't broaden the DOB near-miss surface the way raising a threshold would.

**Risk:**
- For any two people (same or fuzzy-matched name) both born on a day ≤12 of a month ≤12 in the
  same year, this rule treats a *coincidental* month/day pair as equivalent even when it isn't a
  transposition typo at all — just two genuinely different birthdates that happen to satisfy the
  swap relationship. That's a real, non-zero collision rate at scale (roughly 1-in-dozens within
  that date subrange, for people who already cleared a name-match test) that a ~2,000-query
  fixture doesn't have the volume to surface — the same statistical-power caveat as the rejected
  distance-2 proposal, just easier to miss because the rule feels "closed-form."

### 3. Narrow E.3's 5-character floor to 4, only as a same-rule corroborating signal

**Mechanism:** E.3 blocks fuzzy matching on any string under 5 characters, which excludes short
surnames from fuzzy tolerance entirely (e.g. `AAHIL`/`AHIL`, a single-letter deletion, never gets
evaluated because the result is 4 characters).

**Change:** allow fuzzy matching down to 4 characters, but only when every *other* required field
in that rule's combination is an **exact** (non-fuzzy) match. In that context the short fuzzy
field is corroboration, not the decisive identity signal — the collision risk E.3 exists to guard
against (a short ambiguous string carrying the match on its own) doesn't apply.

**Risk:**
- The number of distance-1 neighbors of a 4-character string is a much larger fraction of all
  possible 4-character strings than it is for a 5+ character string, so the floor drop raises
  collision surface disproportionately for short surnames even with the all-other-fields-exact
  guard — the guard reduces but doesn't eliminate risk, since "all other fields exact" is weak
  protection when those other fields (e.g. a common first name, a shared household address)
  aren't very distinguishing either.
- This is a bigger spec/architecture change than it looks: E.2/E.3 as written are per-field rules
  (a field either is or isn't fuzzy-eligible); making a field's fuzzy eligibility *conditional on
  every other field in the rule combination matching exactly* introduces a new kind of
  conditional-fuzzy concept Table 2 doesn't currently express. That likely needs its own
  spec-drafting and review track, not just a threshold-number change.
- Weakest statistical backing of the three: this fixture contains exactly one case in this
  category at this length, so "0 new FPs" is a single data point, not a validated bound.

### Explicitly not proposed: raising E.2's distance bound to 2 generally

Tested for reference: recovers only 4 additional FN with no new FPs on this sample, but the
`hard_negative` adversarial category has only 4 cases in the whole fixture — nowhere near enough
statistical power to bound collision risk for a change that affects every fuzzy-eligible field
(name, street line, etc.), not just DOB. Doubling the edit-distance radius roughly squares the
space of "nearby" strings that could collide by chance. Holding this back rather than proposing it.

### Not included here: missing-DOB coverage gap

18 of the 170 FN (11%) have no DOB on one or both sides, and no existing Category 1 rule
combination covers First+Last+Address without DOB. This is a rule-coverage gap, not a tolerance
change, and carries a different risk profile (family members sharing an address and surname) that
deserves its own analysis rather than being bundled into this proposal.

## Measured impact (population tier, 80,000 evaluations, all floors from `test_onc_population_regression.py`)

fp/tn are identical across every variant below (6 fp / 73,994 tn) — none of the three proposals
changed a single false-positive outcome on this dataset. Precision and FPR are therefore unchanged
to the precision shown; recall, F1, and accuracy move.

| Metric | Baseline | + Change 1 (DOB DL≤1) | + Change 2 (DOB month/day swap) | + Change 3 (name len 5→4) | All 3 combined |
|---|---|---|---|---|---|
| Precision | 0.9990 | 0.9990 | 0.9990 | 0.9990 | 0.9990 |
| Recall | 0.9717 | 0.9833 | 0.9847 | 0.9732 | **0.9862** |
| FPR | 0.000081 | 0.000081 | 0.000081 | 0.000081 | 0.000081 |
| Accuracy | 0.9978 | 0.9987 | 0.9988 | 0.9979 | 0.9989 |
| F1 | 0.9851 | 0.9911 | 0.9918 | 0.9859 | **0.9925** |
| fn (of ~6,000 positives) | 170 | 100 | 92 | 161 | 83 |

Notes:
- Change 2's column is cumulative on top of Change 1 (it's a refinement to the same DOB
  comparator) — not meaningful in isolation.
- Change 3 is independent of 1/2 (it touches name fields, not DOB) and is shown both alone and
  in the combined total.
- Change 1 alone delivers most of the gain (+1.16pt recall); Change 2 adds +0.14pt further;
  Change 3 alone is the weakest lever (+0.15pt) but is additive and cost-free on this dataset.
- All four gated floors (`precision_floor=0.99`, `recall_floor=0.95`, `fpr_ceiling=0.001`,
  `f1_floor=0.97`) clear with more headroom under every proposed change than under baseline.

## Recommendation

Propose changes 1 and 2 together as a DOB-tolerance amendment (biggest, best-evidenced gain,
single coherent change to one comparator). Propose change 3 separately as a narrower E.3
carve-out, since it touches a different field class and a different section of the spec.
