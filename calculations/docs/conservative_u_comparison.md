# Conservative u-values vs. empirical Census estimates

Comparison of the hand-picked "conservative u" values used by the patient-matching model
against the empirical u-probabilities produced by this tool (`make calculate`), run against
2020 Census / ACS / CMS data downloaded and re-verified on 2026-09-30.

u is the probability that two randomly chosen, distinct people agree on a given field. A larger
conservative value relative to the empirical estimate means more margin (the model is being
deliberately pessimistic); a ratio close to 1x means little to no margin.

## Where each column comes from

Every table in this doc has exactly two kinds of numbers — don't mix them up:

- **"Conservative u" (INPUT, not calculated here)**: the hand-picked assumptions from the
  patient-matching model's own spec (the CMS HTE Patient Matching u-probability table). This
  tool does not produce these numbers; they are the values being checked *against*.
- **"Empirical u" (CALCULATED by this tool)**: the output of `make calculate` in this
  `calculations/` directory, derived from public Census/ACS/CMS data or (for SSN/ITIN) a
  closed-form calculation backed by public SSA policy — see `outputs/u_probabilities.md` for
  full per-field methodology and `compute.py` for the source code. Anywhere you see a citation
  like "1/9999, closed-form" or "N = 2024 Medicare enrollment," that's this tool's math, not the
  spec's.

The "Margin" column is just Conservative ÷ Empirical — it is not itself sourced from either side.

## Fields the tool computes

| Field | Variant | Conservative u (spec, input) | Empirical u (this tool, calculated) | Margin (spec ÷ tool) |
|---|---|---|---|---|
| Last Name | exact | 0.005 | 0.0006779 | 7.38x |
| Last Name | fuzzy | 0.01 | 0.0008325 | 12.01x |
| First Name | exact | 0.02 | 0.001793 | 11.16x |
| First Name | fuzzy | 0.03 | 0.002257 | 13.29x |
| Middle Name | exact | 0.01 | 0.001793 (proxy) | 5.58x |
| Year of Birth | exact | 0.015 | 0.01178 | **1.27x** |
| Date of Birth (full) | exact | 0.0001 | 3.226e-05 | 3.10x |
| ZIP Code (5-digit) | exact | 0.0003 | 9.698e-05 | 3.09x |
| State | exact | 0.06 | 0.04455 | 1.35x |
| City | exact | 0.01 | 0.003121 (bound a; see note below) | 3.20x |
| Street line | exact / fuzzy | 0.00003 / 0.00006 | see note below | see note below |
| Phone Number | exact | 0.000001 | 1.31e-09 (co-resident-landline floor; see note below) | see note below |
| SSN Last 4 | exact | 0.0001 | 0.0001 (1/9999, closed-form) | **1.00x** |
| ITIN Last 4 | exact | 0.0001 | 0.0001 (1/9999, assumed by analogy) | **1.00x** |
| MBI | exact | 0.000001 | 1.471e-08 (1/N, N = 2024 Medicare enrollment) | 67.99x |

Every number in the "Conservative u" column above came from the spec and is reproduced verbatim
(not recomputed). Every number in the "Empirical u" column was produced by running
`make calculate` in `calculations/` against the sources cited per-field below.

### Fuzzy name-match values were revised after two bug fixes

An earlier run of this tool understated fuzzy-match u for last/first name (0.0002143 and
0.0008324 respectively) because `name_fuzzy_u` omitted the exact-match term (p_v²) for eligible
names — since fuzzy match (edit distance ≤ 1) is a superset of exact match (edit distance 0),
that omission made "fuzzy u" come out *lower* than "exact u," which is definitionally impossible.
That fix added the exact-match term back in, producing 0.0008427 / 0.002307 (11.87x / 13.00x).

A second, smaller bug was found and fixed after that: `build_fuzzy_ball_mass`'s min_len
exclusion (names shorter than 5 characters are supposed to be entirely excluded from fuzzy
matching, falling back to exact-match probability only) wasn't symmetric. An eligible name's
deletion-neighborhood candidate search could match a real, listed *short* (ineligible) name and
pull in that short name's full probability mass — even though the short name itself never got a
ball computed and so never contributed this back. On the real 2020 Census last-name file this
fired for ~14% of eligible names (e.g. `CHENG` absorbing all of `CHEN`'s mass) and inflated
last-name fuzzy u by about 1.2% (0.0008427 → the corrected 0.0008325 in the table above). The fix
restricts that candidate path to eligible names only. Both fixes are one-directional corrections
(each bug always inflated or deflated the number the same way), so the values in the table above
are now lower (last name) / lower (first name) than the immediately-preceding run, but still
higher than the original, doubly-buggy pre-exact-match-term run.

### Year of birth: thin margin, and a sanity-check range fixed to match

Year of birth has the tightest margin of any computed field (1.27x). An earlier run of this tool
also flagged its own sanity check on this number:

```
WARNING: Year-of-birth u_unbiased=0.0118 is outside the expected [0.012, 0.016] range -- investigate before reporting.
```

That wasn't a computation bug, and 0.01178 is the correct number for this tool's intended
population: this tool covers everyone who could be matched (newborns and minors included, not
just adults), and the `[0.012, 0.016]` range had no documented derivation — it turns out to have
been calibrated against an adults-only cut of the population (the adults-18+ reference figure,
0.01494, *does* fall inside that old range), not the all-ages headline this tool actually reports.
`SANITY_RANGES["year_of_birth"]` in `config.py` has been corrected to `(0.0100, 0.0149)`, bounded
below by the fully-uniform-distribution floor for 101 single-year-of-age buckets (1/101 = 0.0099 —
a real population pyramid should always clear this) and above by the adults-only figure (a true
all-ages number should always be more diluted, i.e. lower, than that). The conservative value
(0.015) and the empirical value (0.01178) remain close enough that this row has little headroom —
worth revisiting whether 0.015 is still the right conservative assumption, independent of the
sanity-check fix.

### City: headline is bound (a), same coverage caveat as the name fields — now disclosed

`city_u()` renormalizes places + Census Designated Places (SUMLEV 162) to their own total for
the headline number (bound (a), 0.003121 above) — the same pattern `name_exact_u` uses for
listed names. That pattern needs a coverage disclosure to be safe, because places/CDPs cover
only **63.1%** of the national population (215.7M of 341.8M people; many people live in
unincorporated areas that belong to no place or CDP). An earlier version of this tool computed
bound (a) for city without ever computing or disclosing a bound (b) the way every name field
does, and its only caveat pointed the reader in the *opposite* direction (Census-place-vs-USPS-
mailing-city geography mismatch, which understates concentration) — giving no hint that the
uncomputed coverage gap overstates it, and by more.

Now fixed: `city_u()` also computes bound (b) — places/CDPs plus everyone outside any place/CDP
treated as unique singleton residents — and reports it in the field's notes:
`u_unbiased=1.243e-03`, vs. bound (a)'s `0.003121`, a **2.51x** difference. The headline number in
the table above is unchanged (bound (a), for consistency with how every other listed/unlisted
field in this tool reports its headline), but the true margin against the conservative value
(0.01) is closer to **8x** (0.01 / 0.001243) than the 3.20x the bound-(a)-only number implies.
See `outputs/u_probabilities.md`'s `city` notes for the full coverage figure.

### Street line: table and tool aren't asking the same question

The conservative-u table assumes ZIP has already matched exactly, and gives a u for the street
line alone, conditional on that. The tool produces two different quantities instead of one:

- `street_line_given_zip` (u ≈ 6.527e-05): probability of street-line agreement *conditional on*
  already being in the same ZCTA. This is the conceptually closer match to the table's "street
  line" row, but the tool doesn't independently produce a conservative floor to diff it against.
- `street_line_with_zip` (u ≈ 6.33e-09): the *joint* probability of matching street line AND ZIP
  together (unconditional). This is why it comes out 4739x smaller than the table's 0.00003 —
  it's answering a different question (joint vs. conditional), not indicating the conservative
  value is wildly under-conservative.

Comparing the table's 0.00003 against `street_line_given_zip` (6.5e-05) is the apples-to-apples
read, and on that basis the conservative value is actually *smaller* than the empirical estimate
for this field — worth a closer look.

### Phone: a partial floor, not a full point estimate — don't read the 763x margin as "way over-conservative"

Phone is structurally different from every other computed field: it's not a namespace-collision
question (public data can't model two strangers being randomly assigned the same number), it's a
*sharing* question. The only sharing mechanism this tool can quantify from public data is a
landline shared by co-resident household members — the same mechanism as the street-line floor,
scaled down by the fraction of households that still have a landline at all.

`phone_u()` computes `u = P(co-resident) * P(shared household has a landline)`:
- `P(co-resident)` reuses `street_line_with_zip`'s u (6.33e-09) — co-residents are trivially also
  same-ZIP, so that FieldResult already *is* an estimate of P(co-resident).
- `P(shared household has a landline)` = 20.7% of adults, from CDC NCHS's National Health
  Interview Survey (Wireless Substitution: Early Release of Estimates, July-December 2024,
  released June 2025, https://doi.org/10.15620/cdc/174608, Table 1: 19.8% dual-user + 0.9%
  landline-only households). The other ~79% of adults have a personal mobile number, effectively
  unique per person.

This gives `u_unbiased = 1.31e-09`, a **763x** margin against the conservative value (0.000001).
**That margin is not evidence the conservative assumption is overly cautious** — this floor
deliberately excludes every other real-world phone-sharing mechanism, two of which are named but
not quantified:
- A family member's mobile number listed for someone who doesn't live with them (common for
  elderly patients or children with divorced parents), or a shared "family contact" number — no
  public data found for either.
- Mobile number **reassignment**: FCC 18-31 (CG Docket No. 17-59, para. 3, 2018) cites ~35 million
  US phone numbers disconnected and reassigned to a new subscriber every year (sourced from
  NANPA's own utilization reports), and 47 CFR 52.15(f)(2) caps the mandatory hold period before
  reassignment at 90 days for residential numbers. That's a real, citable churn rate for the
  numbering pool — but turning it into a u-value would require knowing how long a record system
  typically goes without refreshing a patient's phone number after it changes, which is a
  record-keeping-practice question with no public data source, not a phone-network question.
  Deliberately left unquantified rather than guessed (see `docs/LEARNINGS.md`).

The conservative value is very likely pricing in these mechanisms; this tool's floor structurally
cannot. Treat 1.31e-09 as "here's the one mechanism we can prove from public survey data," not as
"phone has 763x more headroom than it needs."

### Middle name: proxy via the first-name distribution, not a direct measurement

Census publishes no middle-name frequency table, so `middle_name_proxy_u()` reuses the 2020
first-name distribution on the assumption that middle names are drawn from a similar cultural
name pool. True middle-name concentration could be higher or lower than this proxy — parents may
deliberately pick a less-common middle name (lowering u), or lean on a smaller set of
family/traditional names (raising u) — and this tool can't distinguish those effects. Treat the
5.58x margin as indicative, not authoritative.

### SSN / ITIN last 4: closed-form, but only for the post-2011-randomization cohort

`1/9999 ≈ 0.0001` is a closed-form value backed by SSA's SSN Randomization policy (effective
2011-06-25), not a Census measurement — which is why the "margin" here is exactly 1.00x: the
conservative table's assumption and this tool's closed form are the *same calculation*, not an
independent check.

That closed form only holds for SSNs issued on or after 2011-06-25. Before that date, the last 4
digits ("serial number") were assigned *sequentially* within area/group blocks, not randomly.
Since most currently-insured adults have a pre-2011 SSN, the population-wide true u is likely
*higher* than 1/9999 (low serial numbers appear in every block ever opened; high serial numbers
only in blocks issued to exhaustion — see `docs/LEARNINGS.md` for the full mechanism). This tool
deliberately does not fabricate a pre/post-2011 blended estimate — doing so would require SSA's
historical "High Group List" cross-referenced with population-by-state/year data, which is out of
scope for a Census/ACS/CMS-only tool. **Treat 0.0001 as unverified for the pre-2011 majority of
the population, not confirmed by this margin.**

ITIN last-4 uses the same math by analogy, but the IRS has not published an equivalent
randomization-policy statement, so even the post-2011-cohort closed form is an unverified
assumption there, not policy-backed.

### MBI: namespace-size floor using real CMS enrollment data, not a frequency distribution

`mbi_u()` computes `u = 1/N` where N = 67,994,978.58, CMS's reported total Medicare enrollment
(person-year count) for 2024, from CMS's public "Program Statistics - Medicare Total Enrollment"
dataset. This gives a real, citable denominator in place of a guess, but it's still a
namespace-size floor, not an empirical frequency distribution: it assumes every MBI is issued to
exactly one person with no duplicates. The 67.99x margin between this floor (1.471e-08) and the
conservative value (1e-6) is by design — the conservative value is pricing in real-world
duplicate-issuance, reissuance (e.g. after a compromised MBI), and transcription-error
collisions, not birthday-paradox-style random collision, so it should stay well above the
theoretical floor.

## Fields not computed by this tool

For these, only the spec's "Conservative u" number exists — this tool has no "Empirical u" to
put next to it, because no public Census/ACS/CMS dataset (or citable policy document) can
estimate them the way it does for the fields above. These are not discrepancies; there is simply
nothing in the right-hand column.

| Field | Conservative u (spec, input) | Why this tool can't calculate an empirical u |
|---|---|---|
| Suffix | 0.2 | Dismissed in the spec (data quality/selectivity); no public suffix frequency table. |
| Year of Birth (dismissed variant) | 0.015 | Dismissed in the spec separately from the exact variant already computed above. |
| Email Address | 0.000001 | Same shape as Phone — no public sharing-rate survey wired in yet (see note below for a candidate approach). |
| Legal ID | 0.000001 | Namespace-specific per issuing authority (each state DMV, State Dept); no single public count spans all issuers. |
| Namespace-bound unique IDs (EMPI, FHIR Patient Identifier, CSP UUID) | ≈0 | Namespace size = your own organization's patient count — internal data, not public. |
| Insurance Member ID | 0.000001 | Payer-specific enrollment count; no single public per-payer figure. |
| Insurance Subscriber ID | 0.0001 | Same as Member ID, plus the ~40% dependent-sharing assumption isn't validated against public data (KFF/Census CPS could, but isn't wired in). |
| Relationship Linkage — clinical source | 0.01 | An error-rate question, not a frequency-distribution question; needs an internal accuracy study against ground truth. |
| Relationship Linkage — self-reported/intake | 0.05 | Same as above. |

## Summary

Most computed fields carry a comfortable margin (3x–68x) between the conservative value and the
empirical estimate. Six items warrant follow-up:

1. Year of birth's margin is thin (1.27x). The tool's sanity-check range has been fixed to
   correctly reflect the all-ages headline it actually reports (see note above), so the warning
   is gone, but the underlying margin itself is unchanged — still worth deciding whether 0.015
   is the right conservative value.
2. City's table margin (3.20x) is against bound (a), which excludes the ~37% of the population
   outside any Census place/CDP; the coverage-adjusted margin is closer to 8x. Use bound (b)
   (1.243e-03, in the field's notes) if the question is "how conservative is 0.01, really?"
3. Street line's conservative value should be compared against `street_line_given_zip`
   (conditional on ZIP match), not `street_line_with_zip` (joint) — on that basis the
   conservative value is close to, or below, the empirical estimate.
4. Phone's 763x margin is the widest of any field, and specifically should **not** be read as
   "over-conservative" — it's a partial co-resident-landline floor, not a full point estimate;
   see the Phone section above for why the gap is expected, not a finding.
5. SSN/ITIN last-4's 1.00x "margin" is not independent verification — it's the same closed-form
   calculation as the conservative value, and it's unverified for the pre-2011 majority of the
   population (see the SSN/ITIN section above and `docs/LEARNINGS.md`).
6. Middle name's margin (5.58x) rests on a proxy distribution (first names), not a direct
   measurement — treat it as indicative only.
