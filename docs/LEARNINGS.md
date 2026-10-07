# Learnings

Concrete technical findings from running this code against real data or real environments —
read this before re-investigating something already solved here.

## FHIR fields: `dict.get(key, default)` is not enough

Real FHIR payloads (e.g. `bronze.fhir_lake.patient_4_0_0`) can have an optional field present
in the dict but explicitly `null`, not merely absent. `dict.get("suffix", [])` only substitutes
the default when the *key is missing* — a present-but-`null` value passes straight through as
`None`, which then crashes on `len()`/iteration/subscript downstream. ONC's synthetic test data
never exercises this shape, which is why it wasn't caught until a live run.

**Fix pattern:** `dict.get(key) or default`, not `dict.get(key, default)`, for any field that
gets iterated or subscripted afterward. Applied in `patient_matching/normalization/` and
`patient_matching/matching/field_extractor.py` — see git blame on those files for the exact
before/after. Regression tests for each shape live alongside the existing tests in those
modules (search for `null` in test names).

**Where this could still bite:** any *new* field extraction/normalization code that reads a
FHIR dict without going through the existing normalizer/extractor helpers.

## scourgify's failure modes are already handled

`usaddress-scourgify`'s `normalize_address_record` raises `UnParseableAddressError` on a street
line it can't decompose (e.g. `"Main St"` with no house number, or `"PO BOX"`). This is a
subclass of `AddressNormalizationError`, which `address_normalizer.py` already catches and
falls back to basic text normalization for. Verified directly against the installed library,
not just by reading its source — see `test_unparseable_street_line_falls_back_instead_of_raising`.

## Library compliance: `usaddress-scourgify` and its transitive deps

`usaddress-scourgify` (0.7.1), `usaddress` (0.5.16), and `probableparsing` (0.0.1) all resolve
from the organization's JFrog Artifactory PyPI virtual repository — confirmed both in
`uv.lock` and via a live `%pip install` in the prod Databricks workspace. No compliance gap;
`pyproject.toml`'s `usaddress-scourgify>=0.6.0` already resolves to an approved version through
the lockfile. (A local `.venv` may lag behind `uv.lock` — e.g. it had 0.6.0 installed instead of
the locked 0.7.1 — that's a stale local sync, not a registry/compliance issue; run `uv sync`.)

## Pre-2011 SSNs are not uniformly random in the last 4 digits

SSA's SSN Randomization policy (effective 2011-06-25,
https://www.ssa.gov/employer/randomization.html) made all 9 digits of a newly-issued SSN
random, including the last-4 "serial number." Before that date, SSNs used the area-group-serial
scheme (AAA-GG-SSSS), and the serial number was assigned *sequentially* (0001, 0002, ...) within
each area/group block — not drawn at random. Since most currently-insured adults were issued
their SSN before 2011, `calculations/compute.py`'s `ssn_itin_last4_u()` closed-form value
(`1/9999`) is only directly valid for the post-2011-randomization cohort, not the population as
a whole.

**Why this matters for u-probability estimation:** pooled across the many area/group blocks
issued over ~75 years, low serial numbers (0001, 0002...) occur in every block ever opened, while
high serial numbers (9998, 9999) occur only in blocks issued to exhaustion. This structurally
skews the population-wide last-4-digit distribution toward low values, meaning the true u for
pre-2011 SSNs is likely *higher* than 1/9999, not lower — `1/9999` is not a conservative
(over-)estimate here, it's probably an underestimate for the majority pre-2011 cohort.

**Why this tool doesn't quantify the pre-2011 cohort:** doing so would require SSA's historical
"High Group List" (tracking highest group number issued per area over time) cross-referenced
with population-by-state/birth-year data — the method used in Acquisti & Gross, "Predicting
Social Security Numbers from Public Data" (PNAS, 2009). That's a genealogy/demographic
reconstruction exercise, not something derivable from the Census/ACS/CMS sources this tool
already downloads, so `ssn_itin_last4_u()` deliberately only returns the post-2011 closed form
and documents the gap in its docstring/notes rather than fabricating a blended estimate.

**Where this could still bite:** if someone later tries to compute a population-wide (not
cohort-specific) SSN-last-4 u-value and cites `1/9999` as the finished number instead of a
post-2011-only floor.

## Renormalizing to a listed/covered-only total needs an explicit coverage check, every time

`name_exact_u()` (last/first/middle name) already handles the "Census only lists names above an
occurrence threshold" problem correctly: it renormalizes the listed names to their own total for
the headline (bound a), but *also* computes and discloses a bound (b) that treats the unlisted
remainder as singletons, so a reader can see how much the renormalization could be hiding.
`city_u()` did the renormalization step (places + CDPs, SUMLEV 162, to their own total) without
the matching bound (b)/coverage disclosure — an oversight, not a deliberate scope decision, since
places/CDPs cover only ~63% of the national population (many people live in unincorporated areas
belonging to no place or CDP). That silently inflated the headline `city` u by ~2.5x relative to
the coverage-adjusted lower bound. Fixed by giving `city_u()` the same bound (a)/(b) treatment,
parameterized on the national population total (from `load_state_pop()`).

**Where this could still bite:** any *new* field added to `compute.py` that renormalizes a
listed/covered subset to its own total (rather than the true population) needs this same
bound (a)/(b) pair, not just a prose caveat about definitional mismatches (ZCTA-vs-ZIP,
Census-place-vs-USPS-city, etc.) — those are a *different* kind of bias and can point in the
opposite direction, as they do for `city`.

## Symmetric exclusions need to be enforced on both sides of the relation

`build_fuzzy_ball_mass()`'s `min_len` cutoff is supposed to fully exclude short names from fuzzy
matching (they fall back to exact-match probability only — see its docstring and
`test_fuzzy_ball_mass_respects_min_len`). The exclusion was only enforced one-directionally: a
short (ineligible) name never got its own ball computed, but its probability mass could still be
pulled into an *eligible* name's ball if the eligible name's single-character deletion happened
to equal that short, listed name (e.g. `CHENG` deleting the `G` produces `CHEN`, a real, common,
listed 4-character surname). On the real 2020 Census last-name file this fired for ~14% of
eligible names and inflated last-name fuzzy u by ~1.2% — always in the inflating direction, since
ball mass is only ever added. Fixed by restricting that candidate-matching path to eligible names
only (`compute.py`'s `build_fuzzy_ball_mass`).

**Where this could still bite:** any future "X is excluded/capped/floored" rule in this codebase
that's implemented as "X doesn't compute its own contribution" rather than "X can't appear on
either side of the relationship" — the former is easy to get right for X's own row and silently
wrong for everyone else's.

## A sanity-check range must be calibrated against the same population it checks

`SANITY_RANGES["year_of_birth"]` (`config.py`) was `(0.012, 0.016)` with no documented
derivation, and `make calculate` flagged the correct, real all-ages (AGE 0-100) headline
(~0.0118, from `year_of_birth_u()`) as out of range on every run. It turns out `(0.012, 0.016)`
brackets the tool's *adults-18+* reference figure (~0.0149) instead — this tool intentionally
covers the whole population (newborns and minors are real patients, not excluded), and an
all-ages number is always lower than an adults-only number computed from the same data (adding
ages 0-17 adds birth years with a flatter, less-concentrated distribution than the adult age
pyramid, pulling u down). The range was checking the wrong population's expected shape against
the right population's real number.

Fixed by recalibrating the range to `(0.0100, 0.0149)`: the lower bound is the
fully-uniform-distribution floor for 101 single-year-of-age buckets (1/101 = 0.0099 — a real
population pyramid should always be at least this concentrated), and the upper bound is the
adults-only reference figure itself (an all-ages number should always be more diluted than
adults-only, computed from the same source data).

**Where this could still bite:** any sanity range added to `SANITY_RANGES` without writing down
*how* it was derived and *which* population/variant it assumes — the check silently drifts out of
sync the moment someone changes which variant is headlined, exactly as happened here.

## Fetching CDC/NCHS PDFs directly can hit an Akamai WAF block, even with a browser User-Agent

`https://www.cdc.gov/nchs/data/nhis/earlyrelease/wireless202506.pdf` (used for `phone_u()`'s
landline-household-share input) returns an Akamai "Access Denied" HTML page instead of the PDF,
even with a full browser `User-Agent` and `Accept`/`Accept-Language` headers set (same family of
issue as the Cloudflare WAF-caching problem already documented for `www2.census.gov` in
`config.py`, different vendor). The same document is mirrored at
`https://stacks.cdc.gov/view/cdc/<id>/cdc_<id>_DS1.pdf` (CDC's document-stacks archive), which is
not behind the same WAF and served the real PDF on the first request.

**Where this could still bite:** any future source added from `www.cdc.gov/nchs/...` directly —
check `stacks.cdc.gov` for a mirrored copy first, or expect to need the same
cache-busting-query-param workaround `download.py` already uses for `www2.census.gov`.

## Phone/email agreement is a sharing-rate question, not a namespace-collision question

Every other field `compute.py` estimates (names, DOB, ZIP, state, city, street line) models the
probability two *unrelated* people coincidentally share a value, from a population frequency
table. Phone (and, if ever added, email) is structurally different: personal mobile numbers are
effectively unique per person, so the only way two distinct patients legitimately share one is
through deliberate or household *sharing* (a landline, a family-plan "contact" number, a joint
account) — a behavioral-survey question, not a Census-frequency-table question.

`phone_u()` handles this by reusing an existing floor (`street_line_and_zip_u`'s co-resident
probability) and scaling it by a survey-sourced household-landline share (CDC NCHS's Wireless
Substitution survey, see `config.NCHS_ADULT_DUAL_USER_HOUSEHOLD_PCT`/
`NCHS_ADULT_LANDLINE_ONLY_HOUSEHOLD_PCT`), rather than trying to build a new namespace/frequency
model from scratch. The household-vs-per-person distinction in that survey matters: landline
status is a property of the *household* (if one resident has one, every co-resident does too),
not an independent per-person rate, so it multiplies the co-resident probability directly rather
than being squared.

**Where this could still bite:** this floor only captures co-resident landline sharing. It has no
data-backed way to model non-co-resident sharing (e.g. a family member's number listed for
someone who lives elsewhere) or mobile number reassignment (see the next entry for why that one
is a named, cited, but deliberately unquantified gap), so the resulting ~763x margin against the
conservative value should not be read as "the conservative
assumption is overly cautious" — see `docs/conservative_u_comparison.md`'s Phone section. The same
caution will apply to email if a similar sharing-rate estimate is ever wired in.

## A real, cited statistic can still be the wrong shape to turn into a u-value

Looked for public data to quantify mobile-number-reassignment collisions (a named gap in
`phone_u()`, above) and found a solid, citable number: FCC 18-31 (CG Docket No. 17-59, para. 3,
2018-03-22), sourced from NANPA's own utilization reports, states ~35 million US phone numbers are
disconnected and reassigned to a new subscriber every year (`config.FCC_ANNUAL_NUMBER_REASSIGNMENT_COUNT`),
and 47 CFR 52.15(f)(2) caps the mandatory pre-reassignment hold at 90 days for residential numbers.

That number measures the wrong thing for this tool's purposes: it's the numbering pool's annual
*churn rate*, not the probability that two people's *records* currently show the same
(recently-reassigned) number. Converting one into the other requires a second number this tool
has no source for — how long a record system typically goes without refreshing a patient's phone
number after it changes, which is a record-keeping-practice question, not a phone-network
question. Deliberately left unquantified in `phone_u()`'s notes rather than guessed at.

**Where this could still bite:** finding *a* number related to a question isn't the same as
finding *the* number the formula needs. Before wiring a newly-found statistic into a u-value,
check that its unit/denominator actually matches what the formula multiplies it by — here, an
annual rate over the whole numbering pool isn't a per-person or per-record probability without an
unavailable extra assumption.

## Email agreement has the same shape as phone, but no comparably current data source

Looked for a phone-style sharing-rate survey to compute `email_u()` the way `phone_u()` already
works for phone (co-resident-style floor scaled by a survey percentage). The only public data
point found: Pew Research's 2013 "Couples, the Internet, and Social Media" survey (n=2,252,
MOE ±2.3pp) — 27% of internet users in a marriage/committed relationship share an email account
with their partner (12% for ages 18-29 up to 47% for 65+). No newer replication of this specific
question was found; current password-manager-vendor surveys (LastPass, NordPass) measure a
different thing (knowing someone else's password, not two people's records listing the *same*
email address as their own contact info).

Unlike NCHS's 2024 phone data, this would rest entirely on one pre-smartphone/pre-2FA-era survey
question with no modern replication — a materially weaker foundation than every other source
this tool cites (NCHS, Census, ACS, CMS, SSA policy are all current and methodologically rigorous
by comparison). Not implemented as of this writing; `email` remains in
`docs/conservative_u_comparison.md`'s "fields not computed" table pending a decision on whether a
12-year-old, narrow-population survey question meets this tool's bar, or a fresher source turns up.

**Where this could still bite:** if a newer email-sharing survey is found later, check whether it
asks the same question (shared *account/identity*, not shared *password knowledge* or shared
*access*) before treating it as a drop-in replacement for the 2013 Pew number.

## Removing a rule can orphan test cases labeled "true match" under the old rule set

CMS removed Table 2 rule 29 (`First Name* + Last Name* + Phone + ZIP`, no DOB). Deleting it from
`table2_rules.py` dropped ONC-regression recall (both tiers) from 0.9717 to 0.9463, below the 0.95
floor. 152 true-match cases — mostly DOB mutations outside the ±1-day tolerance — matched *only*
via rule 29; no other Category 1 or Category 2 rule matches them, because every one requires an
exact (or ±1-day) DOB. Those cases encode the old rule's behavior, not a bug in the engine, so the
fix was to drop them from the test data (in the sibling test-set repo), not to lower the floor.

**How it was diagnosed:** evaluate every true-match pair with the rule set before/after (rebuild
the removed `MatchingRule` by hand for the "before" engine) and diff the per-pair outcomes. The
household (Category 2) rules were already in both engines, so they can't be what rescues these.

**Where this could still bite:** any future rule removal/addition shifts the ONC recall/FPR
baseline the same way; check which labeled cases flipped before touching a floor/ceiling. Also,
the fixture data is fetched from a pinned commit of the test-set repo — the pin has to be bumped
for a data fix there to reach this repo.

## Test-set 0.0.2's pairs-tier metric drop is the new categories, not an engine regression

Pinning test-set `0.0.2` took the pairs tier from recall 0.9709 / FPR 0.0000 to 0.9265 / 0.0964
(11,668 pairs). Re-running only the pre-existing categories on the 0.0.2 file gives recall 0.973 /
FPR 0.000 — unchanged. The whole drop is the two new session 14 categories:

- `compound_variant`: 570 false negatives of 1,793 true matches.
- `sibling_negative`: 43 false positives of 81 non-matches (all twins, age gap 0).

**Why `compound_variant` misses.** Tabulating which fields agree in each false negative:

- **383 have DOB off by more than 1 day** with every other field agreeing. Every approved Table 2
  rule that uses a name also requires DOB (±1 day), and the one DOB-free rule (29) was removed, so
  no rule can match these. Same situation as the 152 rule-29 cases above — a labeling/spec
  mismatch, not an engine bug. Recall over spec-matchable true matches is ~0.969.
- **452 of the 570 involve `given_abbreviate`** (e.g. `L.` vs `LUREANE`). An initial is neither
  exact nor fuzzy (fuzzy needs both strings >= 5 chars and Damerau-Levenshtein <= 1). A lone
  abbreviation still passes via rule 30 (`Last* + DOB + Phone`); it fails once combined with a DOB
  or last-name error, or with no phone on file.

**Why `sibling_negative` false-positives.** Twins share first name, last name, DOB and address, so
rules 01, 02, 11, 30 and household rules C2-34/C2-37 all fire legitimately. Most pairs have no
middle name, SSN last-4 or email on one side, so there is no conflicting evidence to veto on; only
~7 of 43 have a middle-name or SSN conflict. The engine's only negative-evidence check is suffix.

**How it was diagnosed:** tabulate per-field agreement (`=`, fuzzy, `±1d`, differs, missing) for
every false negative/positive, grouped by `rationale` category, instead of reading individual
failing cases. The 255 other false negatives (108 DOB-off, 47 `marriage_variant`, 22
`ssn_dropped`, 20 normalization) pre-date 0.0.2.

**Where this could still bite:** restoring the 0.95 / 0.01 pairs floors (relaxed in #70) needs the
test set's labels to be rule-set-aware (re-label or tier out the DOB-off cases, decide what twins
with no distinguishing data should expect) — engine changes alone can't get there. Matching an
initial to a full first name would help `given_abbreviate`, but the CMS fuzzy constraints (E.2/E.4)
don't allow it, so it would be a deliberate, documented deviation.

## 40 of the 43 `sibling_negative` false positives are labels the next test-set fixes

On test-set `0.0.2` the engine links 43 of 81 `sibling_negative` pairs (FPR 0.0964 overall).
Test-set PR #15 (label validity) adds a same-person guard (shared real SSN, or normalized
first + family + DOB) and drops every sibling pair it flags. Running the engine over both files with
`scripts/sibling_fp_overlap.py`:

| | count |
|---|---|
| Pairs the guard flags as possibly the same person | 44 (all removed by #15) |
| ...of which the engine links (false positives) | 40 |
| Extra pair #15 removes (new "different first names" sibling rule) | 1 |
| False positives #15 keeps as non-matches | **3** |

Pairs-tier FPR on #15's file: **0.0106** (3 / 282 non-matches), down from 0.0964. Recall is
unchanged at 0.9265 (#15 does not touch positives), so the recall floor is still bound by
`compound_variant` (see above).

**The 3 that survive are twins with different first names, linked under approved rules:**

- `15631358::15845294`, `15651130::15817119` — rule 30 (`Last* + DOB + Phone`, no first name).
  Same household phone, so the rule fires by design.
- `15660144::15986843` — rules 01/02/11/30/C2-34. First name is `exact` because one twin's first
  given name is the other's middle name, and first name is compared against all given names.

None is an engine bug against the spec. All three are the twin ambiguity the spec leaves
unresolved (§IV.G). Note that `docs/TESTING_AGAINST_TEST_SET.md` §4 ("literal twins are absent
from every tier by design") predates session 14: the `sibling_negative` pairs with
`age_gap_years=0` are twins.

**Where this could still bite:** restoring the 0.01 FPR ceiling after #15 still fails by these 3
pairs (0.0106 > 0.01). Either decide what twins with no distinguishing data should expect, or
set the ceiling just above 0.0106 with a note. Re-run the script before each pin bump; it keys
pairs by `case_id`, which is only stable for pairs a release keeps.

## Institutional-address registry: most sources are automatable, but check before concluding "can't"

Spike for Proposal v3.3.6 (see `docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md`). CMS Care Compare, the POS file, IPEDS, HIFLD Prison Boundaries (via HIFLD Next's catalog, since HIFLD Open was shut down 2025-08-26), Prison Policy Initiative's per-state tables (HTML scrape), the Princeton assisted-living CSV and Overture Maps all download without an account; BOP has only an undocumented per-facility JSON API; BJS censuses (ICPSR login), state DOC rosters and CASS validation need a manual step or an account. Two earlier "not retrievable" conclusions (HIFLD, PPI) were wrong: they came from a page-summary tool rather than fetching the URL, and the PPI state pages sit under `/data/prisons2020/`, not `/prisons2020/`. Overture's `nursing` category is individual nurse practitioners, not nursing homes (15,480 places, ~1% address overlap with CMS); nursing homes sit under `retirement_home`. A match key of (normalized street line 1, ZIP5) needs the unit stripped from **both** sides: registry streets embed suites, and scourgify leaves a unit inside line 1 when designators are stacked or the line is unparseable (unit-suffix match rate 80% -> 100% once stripped). A `#` unit rule must require a preceding character or it eats `#16 WILSON FARM ROAD`.

State assisted-living lists (CA, MI, WI, FL) are each a different shape: California's older `data.chhs.ca.gov` CSV link now returns an HTML login page (use the `gis.data.chhs.ca.gov` ArcGIS item); Michigan's file has no header row and puts the street in column 5, or column 4 when 5 is empty (column 4 otherwise holds a suite); Wisconsin's portal CSV download is 403 but the DHS ArcGIS REST service is open (page at 2,000 records); Florida has no bulk file but its search results embed all records as JSON, behind a session cookie and anti-forgery token. A check that a "download" returns the right content type, not just HTTP 200, would have caught the California case (the 200 response was a login page).

Twenty-three more state lists are fetched by one module each under `scripts/institutional_registry/states/` (see `docs/ASSISTED_LIVING_STATE_COVERAGE.md`; sources differ: XLSX, Socrata, ArcGIS, token-protected form posts, embedded JSON). Things that bit: several hosts (LA, TN, MS, WY) return 403 to a bare curl or "Mozilla/5.0" and need a full Chrome user agent; Excel stores carriage returns as `_x000D_` inside strings, so a stdlib XLSX reader must decode `_xHHHH_`; Nebraska's canonical ArcGIS service returned `SITE_NOT_INITIALIZED` while an identical copy on ArcGIS Online worked; the state's own "download" can be absent while the site's search backend serves a clean file (Minnesota's lookup has a CSV API, found only by looking beyond the search page); and Oregon's adult foster home names are licensees' personal names, so they are dropped because this repo is public. A source that silently drops rows is worse than one that fails: Princeton's rows for ID, MA, NV and OK have no ZIP, so a street-plus-ZIP key discarded all 1,116 without any warning.

Engine comparison, found while checking what an address list can block (details in `docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md` finding 9): `FieldExtractor` puts every address line, including the unit, into one `street_line` set, and `FieldComparator.exact_match` counts any shared element, with no ZIP, city or state. So `100 Main St` in two different states match, different buildings with the same `Apt 2` match, and `PO Box 12` in AK matches `PO Box 12` in TX. The household rules (H-03/06/09/14) use Street Line alone, while the 0.00003 collision value is `street_line_with_zip` (street and ZIP both matching). Not changed (engine code is out of scope for that PR). BOP publishes two addresses per prison (physical and inmate-mail, 66 of 79 mail addresses are PO boxes), and a resident's record is likely to carry the mail one, so the registry now keeps both.

**Where this could still bite:** the POS CSV URL changes every quarter (resolve it from `data.cms.gov/data.json`), and unparseable street lines fall back to unnormalized text, so the same address can key differently across sources.
