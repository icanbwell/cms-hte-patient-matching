# Empirical u-probabilities vs. conservative model values

u = probability two randomly chosen, distinct people agree on a field. `u_unbiased` uses the finite-population pairs formula `Σ n_v(n_v-1) / (N(N-1))` and is the headline number; `u_simple` is the plug-in estimator `Σ (n_v/N)^2`.

## Headline results

| Field | Variant | u_unbiased | u_simple | Conservative u | Ratio (conservative/empirical) | Source |
|---|---|---|---|---|---|---|
| last_name | exact | 0.0006779 | 0.0006779 | 0.005 | 7.38x | Names2020_LastNames_RaceHispanic.xlsx |
| last_name_2010_comparison | exact | 0.0006946 | 0.0006946 | n/a | n/a | names_2010census.zip |
| last_name | fuzzy | 0.0008325 | 0.0008325 | 0.01 | 12.01x | Names2020_LastNames_RaceHispanic.xlsx |
| first_name | exact | 0.001793 | 0.001793 | 0.02 | 11.16x | Names2020_FirstNames_Sex.xlsx |
| first_name | fuzzy | 0.002257 | 0.002257 | 0.03 | 13.29x | Names2020_FirstNames_Sex.xlsx |
| middle_name | exact | 0.001793 | 0.001793 | 0.01 | 5.58x | Names2020_FirstNames_Sex.xlsx |
| year_of_birth | exact | 0.01178 | 0.01178 | 0.015 | 1.27x | nc-est2025-agesex-res.csv |
| dob_full | exact | 3.226e-05 | 3.226e-05 | 0.0001 | 3.10x | derived from year_of_birth |
| zip5 | exact | 9.698e-05 | 9.698e-05 | 0.0003 | 3.09x | acs5_zcta_population.json |
| state | exact | 0.04455 | 0.04455 | 0.06 | 1.35x | NST-EST2025-POP.xlsx |
| city | exact | 0.003121 | 0.003121 | 0.01 | 3.20x | sub-est2025.csv |
| street_line_given_zip | exact | 6.527e-05 | 0.0001444 | n/a | n/a | acs5_zcta_household_size.json + acs5_zcta_population.json |
| street_line_with_zip | exact | 6.33e-09 | 1.4e-08 | 3e-05 | 4739.45x | acs5_zcta_household_size.json + acs5_zcta_population.json |
| phone | exact | 1.31e-09 | 2.898e-09 | 1e-06 | 763.20x | NCHS Wireless Substitution survey (no data file) + street_line_with_zip |
| ssn_last4 | exact | 0.0001 | 0.0001 | 0.0001 | 1.00x | SSA SSN Randomization policy (no data file) |
| itin_last4 | exact | 0.0001 | 0.0001 | 0.0001 | 1.00x | assumed uniform by analogy to SSN (no data file) |
| mbi | exact | 1.471e-08 | 1.471e-08 | 1e-06 | 67.99x | MDCR ENROLL AB 1-8_CPS_02ENR_2024.xlsx |

## Per-field notes and caveats

### last_name (exact)

Headline = bound (a): listed names (156,619) renormalized to their own total, ignoring the unlisted remainder. Coverage = listed/total population = 0.8787 (262,612,981 / 298,870,618). Bound (b) lower bound, treating all unlisted individuals as unique singleton names: u_unbiased=5.234e-04, u_simple=5.234e-04. Names below the Census suppression threshold (<100 occurrences, or <11 for race/ethnicity cross-tabs) are not separately listed; this is the standard disclosure-avoidance suppression, not missing data.

Top 10 by frequency (value, share of listed population):

```
SMITH: 0.9023%
JOHNSON: 0.7076%
WILLIAMS: 0.5946%
BROWN: 0.5278%
JONES: 0.5267%
GARCIA: 0.4377%
MILLER: 0.4300%
RODRIGUEZ: 0.4135%
DAVIS: 0.4091%
MARTINEZ: 0.3960%
```

### last_name_2010_comparison (exact)

Headline = bound (a): listed names (162,252) renormalized to their own total, ignoring the unlisted remainder. Coverage = listed/total population = 0.9006 (265,660,058 / 294,972,059). Bound (b) lower bound, treating all unlisted individuals as unique singleton names: u_unbiased=5.634e-04, u_simple=5.634e-04. Names below the Census suppression threshold (<100 occurrences, or <11 for race/ethnicity cross-tabs) are not separately listed; this is the standard disclosure-avoidance suppression, not missing data.

Top 10 by frequency (value, share of listed population):

```
SMITH: 0.9196%
JOHNSON: 0.7276%
WILLIAMS: 0.6118%
BROWN: 0.5409%
JONES: 0.5366%
GARCIA: 0.4390%
MILLER: 0.4372%
DAVIS: 0.4202%
RODRIGUEZ: 0.4122%
MARTINEZ: 0.3991%
```

### last_name (fuzzy)

Ball = names within Damerau-OSA edit distance 1 (insert/delete/substitute/adjacent-transposition), found via a SymSpell-style deletion-neighborhood index over the 156,619 listed names (>= 5 chars eligible: 145,708); verified exactly with rapidfuzz. Fuzzy match is edit distance <= 1, i.e. exact match (p_v^2) plus the distance-1 near-miss ball mass. Names < 5 chars fall back to exact-match probability (p_v^2) only. Restricted to listed (>=100-occurrence) names -- same coverage caveat as the exact-match calculation.

Top 10 by frequency (value, share of listed population):

```
SMITH: 0.9023%
JOHNSON: 0.7076%
WILLIAMS: 0.5946%
BROWN: 0.5278%
JONES: 0.5267%
GARCIA: 0.4377%
MILLER: 0.4300%
RODRIGUEZ: 0.4135%
DAVIS: 0.4091%
MARTINEZ: 0.3960%
```

### first_name (exact)

Headline = bound (a): listed names (53,615) renormalized to their own total, ignoring the unlisted remainder. Coverage = listed/total population = 0.9378 (283,236,830 / 302,031,536). Bound (b) lower bound, treating all unlisted individuals as unique singleton names: u_unbiased=1.576e-03, u_simple=1.576e-03. Names below the Census suppression threshold (<100 occurrences, or <11 for race/ethnicity cross-tabs) are not separately listed; this is the standard disclosure-avoidance suppression, not missing data.

Top 10 by frequency (value, share of listed population):

```
MICHAEL: 1.2275%
JOHN: 1.1034%
JAMES: 1.0579%
DAVID: 0.9932%
ROBERT: 0.9742%
WILLIAM: 0.7909%
MARY: 0.6243%
MARIA: 0.5836%
DANIEL: 0.5674%
JOSEPH: 0.5651%
```

### first_name (fuzzy)

Ball = names within Damerau-OSA edit distance 1 (insert/delete/substitute/adjacent-transposition), found via a SymSpell-style deletion-neighborhood index over the 53,615 listed names (>= 5 chars eligible: 47,556); verified exactly with rapidfuzz. Fuzzy match is edit distance <= 1, i.e. exact match (p_v^2) plus the distance-1 near-miss ball mass. Names < 5 chars fall back to exact-match probability (p_v^2) only. Restricted to listed (>=100-occurrence) names -- same coverage caveat as the exact-match calculation.

Top 10 by frequency (value, share of listed population):

```
MICHAEL: 1.2275%
JOHN: 1.1034%
JAMES: 1.0579%
DAVID: 0.9932%
ROBERT: 0.9742%
WILLIAM: 0.7909%
MARY: 0.6243%
MARIA: 0.5836%
DANIEL: 0.5674%
JOSEPH: 0.5651%
```

### middle_name (exact)

PROXY, not a direct measurement: Census publishes no middle-name frequency table, so this reuses the first-name distribution (same source file) under the assumption that middle names are drawn from a similar cultural name pool as first names. True middle-name concentration could differ in either direction -- e.g. parents may deliberately pick a less-common middle name (lowering u), or lean on a smaller set of family/traditional names (raising u) -- and this tool cannot distinguish those effects. Headline = bound (a): listed names (53,615) renormalized to their own total, ignoring the unlisted remainder. Coverage = listed/total population = 0.9378 (283,236,830 / 302,031,536). Bound (b) lower bound, treating all unlisted individuals as unique singleton names: u_unbiased=1.576e-03, u_simple=1.576e-03. Names below the Census suppression threshold (<100 occurrences, or <11 for race/ethnicity cross-tabs) are not separately listed; this is the standard disclosure-avoidance suppression, not missing data.

Top 10 by frequency (value, share of listed population):

```
MICHAEL: 1.2275%
JOHN: 1.1034%
JAMES: 1.0579%
DAVID: 0.9932%
ROBERT: 0.9742%
WILLIAM: 0.7909%
MARY: 0.6243%
MARIA: 0.5836%
DANIEL: 0.5674%
JOSEPH: 0.5651%
```

### year_of_birth (exact)

Single year of age (0-100, where AGE=100 is a '100 and over' open-ended top bucket) from NC-EST2025-AGESEX-RES, both sexes, converted to birth year = 2025 - age (as of July 1, 2025). Adults-only (18+) variant, for reference: u_unbiased=1.494e-02, u_simple=1.494e-02 -- higher than the all-ages headline because excluding ages 0-17 removes birth years with a flatter, less-concentrated distribution than the adult population's age pyramid. National population, not a specific payer's member population -- true u could differ for an age-skewed membership (e.g. Medicare Advantage).

Top 10 by frequency (value, share of listed population):

```
2000: 1.4357%
2001: 1.4247%
1990: 1.4090%
1991: 1.3992%
1999: 1.3940%
1992: 1.3745%
1989: 1.3675%
1998: 1.3551%
1993: 1.3525%
1988: 1.3440%
```

### dob_full (exact)

Assumes birthdates are uniformly distributed within a birth year: u_dob = u_yob / 365.25 (365.25 approximates the leap-day effect; real birth-date distributions have mild seasonal non-uniformity -- e.g. September birth clustering -- which would raise this slightly above the uniform-model estimate).

### zip5 (exact)

ZCTA (Census's generalized ZIP-code-like tabulation areas from ACS 2024 5-year estimates, table B01003) used as a proxy for USPS ZIP code. ZCTAs and ZIP codes are not identical: ZCTAs are built from whole census blocks and don't track USPS ZIP boundary changes, P.O.-box-only ZIPs, or unique-organization ZIPs, so this slightly misestimates true ZIP-code concentration. 33,174 ZCTAs with population > 0.

Top 10 by frequency (value, share of listed population):

```
77494: 0.0415%
08701: 0.0412%
77449: 0.0385%
78660: 0.0369%
77433: 0.0345%
77084: 0.0326%
60629: 0.0320%
11368: 0.0313%
92336: 0.0312%
11208: 0.0312%
```

### state (exact)

NST-EST2025-POP, July 1, 2025 estimate. Headline = 50 states + DC (51 areas). With Puerto Rico included (52 areas): u_unbiased=4.381e-02, u_simple=4.381e-02.

Top 10 by frequency (value, share of listed population):

```
California: 11.5146%
Texas: 9.2777%
Florida: 6.8647%
New York: 5.8523%
Pennsylvania: 3.8210%
Illinois: 3.7214%
Ohio: 3.4819%
Georgia: 3.3070%
North Carolina: 3.2763%
Michigan: 2.9632%
```

### city (exact)

Headline = bound (a): places/CDPs (19,483) renormalized to their own total, ignoring the population outside any place/CDP. Coverage = places/national = 0.6310 (215,662,427 / 341,784,857). Bound (b) lower bound, treating everyone outside any place/CDP as unique singleton residents: u_unbiased=1.243e-03, u_simple=1.243e-03. SUB-EST2025 incorporated places + Census Designated Places (SUMLEV 162), July 1, 2025 estimate. Separate caveat: this is Census place geography, not USPS mailing city -- many mailing addresses use a ZIP's default USPS city name that differs from (or spans multiple) Census places, which pulls in the opposite direction from the coverage gap above (understates concentration, rather than overstating it). No HUD_TOKEN was configured, so the alternate USPS-city-via-ZIP-crosswalk calculation was skipped (see download.py's printed manual-setup instructions).

Top 10 by frequency (value, share of listed population):

```
New York city, New York: 3.9806%
Los Angeles city, California: 1.7940%
Chicago city, Illinois: 1.2666%
Houston city, Texas: 1.1116%
Phoenix city, Arizona: 0.7723%
Philadelphia city, Pennsylvania: 0.7300%
San Antonio city, Texas: 0.7180%
San Diego city, California: 0.6520%
Dallas city, Texas: 0.6165%
Fort Worth city, Texas: 0.4767%
```

### street_line_given_zip (exact)

Same floor logic, but using the full household-size distribution (ACS B11016) instead of the ZCTA average: Σ_s households_of_size_s * s(s-1) / (P(P-1)), population-weighted implicitly via national summation. The '7-or-more-person' bucket is treated as exactly 7, which further understates the true value for that (small) subpopulation. u_unbiased column = household-size-distribution method; u_simple column = avg-household-size method. Co-resident FLOOR only: models P(two distinct people share a street address | same ZCTA) as (avg_household_size - 1) / (population - 1) via ACS B25010, population-weighted across ZCTAs, times P(same ZIP) from the ZCTA u-value. This ignores street-name collisions across different households within the same ZIP (e.g. two unrelated households both on '1st St'), so it UNDERSTATES true street-line agreement probability; treat as a lower bound, not a point estimate. u_street_given_zip (avg-size method) reported as u_simple; u_street_and_zip = u_street_given_zip * u_zip.

### street_line_with_zip (exact)

Co-resident FLOOR only: models P(two distinct people share a street address | same ZCTA) as (avg_household_size - 1) / (population - 1) via ACS B25010, population-weighted across ZCTAs, times P(same ZIP) from the ZCTA u-value. This ignores street-name collisions across different households within the same ZIP (e.g. two unrelated households both on '1st St'), so it UNDERSTATES true street-line agreement probability; treat as a lower bound, not a point estimate. u_street_given_zip (avg-size method) reported as u_simple; u_street_and_zip = u_street_given_zip * u_zip.

### phone (exact)

Co-resident landline-sharing FLOOR, not a point estimate: u_phone = P(co-resident) * P(shared household has a landline). P(co-resident) = street_line_with_zip's u (6.330e-09 unbiased / 1.400e-08 simple), since co-residents are trivially also same-ZIP. P(household has a landline) = 0.207 (19.8% dual-user + 0.9% landline-only households among adults, July-December 2024, NCHS National Health Interview Survey Table 1, https://doi.org/10.15620/cdc/174608) -- a household property (if one resident has a landline, so does every co-resident), not an independent per-person rate, which is why it multiplies P(co-resident) directly rather than being squared. The remaining ~79% of adults have a personal mobile number, effectively unique per person -- this floor has no data-backed way to model non-co-resident sharing (e.g. a family member's number listed for someone living elsewhere), which would push the true value higher than this floor. It also doesn't model mobile number reassignment: 35,000,000 US numbers/year are disconnected and reassigned to a new subscriber (FCC 18-31, CG Docket No. 17-59, para. 3 (2018-03-22)) -- a real, cited churn rate for the numbering pool, but turning it into a u-value would require knowing how long a record system typically goes without refreshing a patient's phone number after it changes, which is a record-keeping-practice question with no public data source, not a phone-network question; deliberately left unquantified rather than guessed (see docs/LEARNINGS.md).

### ssn_last4 (exact)

Closed-form, not Census-derived: SSA's SSN Randomization policy (effective 2011-06-25, https://www.ssa.gov/employer/randomization.html) made the last 4 digits fully random over 9999 possible values (0001-9999; 0000 never issued) for SSNs issued on or after that date. NOT valid for pre-2011 SSNs, which used sequential (non-random) serial assignment within area/group blocks and likely have a somewhat higher true u -- see docs/LEARNINGS.md for why this tool does not attempt to quantify that cohort without SSA's historical High Group List data.

### itin_last4 (exact)

Same closed-form math as SSN last-4 (0.0001 = 1/9999), applied by analogy. Unlike SSA's SSN Randomization, the IRS has not published an equivalent policy statement confirming ITIN serial numbers are drawn uniformly at random, so treat this as an unverified assumption, not a policy-backed closed form.

### mbi (exact)

Namespace-size floor, not a frequency distribution: u = 1 / N where N = 67,994,979, the CMS-reported total Medicare enrollment (person-year count) for 2024 (MDCR ENROLL AB 1, CMS Program Statistics). This assumes perfectly unique MBI issuance; it ignores real-world duplicate-issuance, reissuance (e.g. after an MBI is compromised), and transcription-error collisions, which is why the conservative floor (1e-6) is set far above this theoretical value rather than matching it -- the floor is pricing in those operational failure modes, not birthday-paradox-style random collision. 'Total enrollment' is a person-year count (each beneficiary counted once per year enrolled), which approximates but is not exactly the distinct-beneficiary count for the year.

## Sanity checks

- All sanity checks passed (state u in [0.03, 0.05], year-of-birth u in [0.01, 0.0149], exact last-name u below 0.01).
- Year-of-birth, adults 18+ variant, for reference: u_unbiased=0.01494, u_simple=0.01494.

## Methods

- **Exact-match names**: Census only lists names occurring >=100 times nationally (2020) or >=100 times (2010); listed names are renormalized to their own total for the headline bound (a). A lower bound (b), treating the unlisted remainder as all-singleton names, is reported in each field's notes.
- **Fuzzy-match names**: for listed names of >=5 normalized characters, a SymSpell-style deletion-neighborhood index finds all other listed names within Damerau-OSA edit distance 1 (insert/delete/substitute/adjacent transposition); candidates are verified exactly with rapidfuzz (not approximated). Names <5 characters fall back to their exact-match probability.
- **Year of birth**: NC-EST2025-AGESEX-RES single-year-of-age population, converted to birth year assuming the July 1, 2025 reference date.
- **Full DOB**: u_yob / 365.25, assuming uniform distribution of birthdates within a birth year (see caveat below).
- **ZIP**: ACS 5-year (2024) table B01003 at the ZCTA level, used as a proxy for USPS ZIP code.
- **State**: NST-EST2025-POP, July 1, 2025 estimate, 50 states + DC headline (Puerto Rico variant also computed).
- **City**: SUB-EST2025 incorporated places + CDPs.
- **Street line + ZIP**: co-resident floor, P(share an address | same ZCTA) estimated two ways -- (avg household size - 1)/(population - 1) from B25010, and the full household-size distribution from B11016 -- combined with P(same ZIP) from the ZCTA population distribution. This is a FLOOR: it ignores street-name collisions between unrelated households in the same ZIP, so true street-line agreement is >= this estimate.
- **Phone**: co-resident landline-sharing FLOOR -- P(co-resident) (from street_line_with_zip) times P(shared household has a landline) (NCHS Wireless Substitution survey, household-level). Excludes non-co-resident sharing and mobile number reassignment/recycling; see caveat below.
- **Middle name**: PROXY -- reuses the 2020 first-name distribution (Census publishes no middle-name table); see caveat below.
- **SSN/ITIN last 4**: closed-form 1/9999, not Census-derived; valid only for the post-2011-randomization cohort (see caveat below).
- **MBI**: namespace-size floor u = 1/N using CMS's total Medicare enrollment (N), not a frequency distribution.

## Sources and download dates

All data downloaded/re-verified on 2026-09-30.

- 2010 Census surnames: https://www2.census.gov/topics/genealogy/2010surnames/names.zip
- 2020 Census first names: https://www2.census.gov/topics/genealogy/2020surnames/Names2020_FirstNames_Sex.xlsx
- 2020 Census last names: https://www2.census.gov/topics/genealogy/2020surnames/Names2020_LastNames_RaceHispanic.xlsx
- National single-year-of-age/sex estimates: https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/national/asrh/nc-est2025-agesex-res.csv
- State population totals: https://www2.census.gov/programs-surveys/popest/tables/2020-2025/state/totals/NST-EST2025-POP.xlsx
- Places (SUB-EST2025): https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/cities/totals/sub-est2025.csv
- ACS 2024 5-year, ZCTA level (population B01003, household size B11016/B25010, housing units B25001): https://api.census.gov/data/2024/acs/acs5
- HUD USPS ZIP crosswalk: skipped (no HUD_TOKEN configured); see download.py for manual setup instructions.

- CMS Medicare total enrollment (2024), used for the MBI namespace-size floor: https://data.cms.gov/sites/default/files/2026-09/0a06b80d-bccb-4634-b062-7e53acdae289/MDCR%20ENROLL%20AB%201-8_CPS_02ENR_2024.zip

- SSA SSN Randomization policy (used for the SSN/ITIN last-4 closed form, no data file downloaded): https://www.ssa.gov/employer/randomization.html

- NCHS Wireless Substitution survey (July-December 2024, used for the phone co-resident-landline floor, no data file downloaded): https://doi.org/10.15620/cdc/174608

## Caveats

- **Suppression**: Census name files only list names above an occurrence threshold; unlisted names are a long tail of rare names. Two bounds are given per name field (see per-field notes).
- **ZCTA vs ZIP**: ZCTAs approximate but do not equal USPS ZIP code areas.
- **Uniform-DOB assumption**: real birth dates are not perfectly uniform within a year (seasonal effects), so u_dob is a slight underestimate.
- **National vs. member population**: all inputs are U.S. national population estimates, not a specific payer/provider's member population, which may have different age/geographic distributions.
- **Street line + ZIP is a floor**: see street-line notes above.
- **Phone is a floor**: see phone notes above -- only quantifies co-resident landline sharing, not the full universe of real-world phone-sharing scenarios.
- **Middle name is a proxy**, not a direct measurement (see per-field notes); true middle-name concentration could be higher or lower than the first-name distribution used here.
- **SSN/ITIN last-4 closed form covers only the post-2011-randomization cohort**: most currently-insured adults have a pre-2011 SSN, for which the last 4 digits were assigned sequentially (not randomly) within area/group blocks, and the true population-wide u is likely somewhat higher than 1/9999 (see per-field notes and docs/LEARNINGS.md).
- **MBI is a namespace-size floor**, not an empirical frequency distribution, and ignores duplicate-issuance/reissuance/transcription-error collisions (see per-field notes).
