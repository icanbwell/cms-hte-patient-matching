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

## A placeholder given name makes the normalizer drop the real family name too

`NameNormalizer._normalize_name_entry` runs the placeholder patterns on `given + family`
concatenated (`"babygirl" + "aaron"`). The `^baby…` prefix pattern matches on the given name alone,
so the whole HumanName is discarded and the record ends up with no `last_name` at all — rule 30
(`Last* + DOB + Phone`) can't rescue it. On test-set 0.0.3 this hits the 61 `placeholder/given`
pairs. Repro: `{"name":[{"family":"AARON","given":["BABY GIRL","MARY"]}]}` normalizes to nothing.
Fixed: when the given name is a placeholder and the family name is not, the normalizer now drops
only the given names (`name_normalizer.py`; population recall +0.0036). See `docs/TEST_SET_0.0.3_ACCURACY_ANALYSIS.md` §3.1.

**Where this could still bite:** any check that tests a concatenation of fields against patterns
anchored with `^` — the first field decides the verdict for the whole.

## Test-set 0.0.5 drops pairs recall below the floor because trivial matches were removed

On the unchanged engine, pairs recall is 0.9516 on 0.0.3 and 0.9474 on 0.0.5 (floor 0.95); population
recall 0.9515 → 0.9504. The test-set stopped emitting fuzzy-variant pairs identical to their source
(128 of 180 `dob_swap` pairs in 0.0.3 were exact copies) and regenerated the data with a shifted seed,
so fuzzy-variant recall fell 0.957 → 0.938 and compound-variant recall 0.725 → 0.711. Categories the
generator changes did not touch are identical. See `docs/TEST_SET_0.0.5_ACCURACY_ANALYSIS.md`.

**Where this could still bite:** a recall floor calibrated on a benchmark that contains no-op pairs
overstates the engine; re-check floors whenever the generator's sampling changes, not only when the
engine does.

## ONC synthetic phones fail `phonenumbers.is_valid_number`

1,650 of 14,219 pairs-tier source records (356 of the 968 false negatives) carried a phone the
phone normalizer rejected as `invalid_number`. About 11% of ONC phones are well-formed 10-digit
numbers with an exchange code starting with 1 (or 0) — unassigned, so `is_valid_number` says no,
but still usable as an identifier. Fixed in the engine: `PhoneNormalizer._is_well_formed_nanp` accepts
a number that is invalid only because of its exchange (re-checked with a valid exchange first digit);
unassigned area codes and wrong lengths are still rejected. Population recall 0.9341 → 0.9515 on the
unmodified 0.0.3 data. (An earlier approach, remapping the phones in the test-set data, gave identical
numbers but needed a new release and pin bump and would not help real data.)

**Where this could still bite:** `is_valid_number` is a strict "real line" check; for identifier
matching a weaker "well-formed" check is usually the right bar — keep that distinction in mind for
any other field validated through a library that checks assignment, not shape.

## The §V.D placeholder table had gaps; one example is deliberately not implemented

Feeding every example from the spec's placeholder table through `NormalizationManager` and
`FieldExtractor` (positive controls included) found 29 of 88 cases surviving as matchable values.
Closed: SSN/ITIN last four `0000`/`9999`/`1234`/repeated digits (the old SSN patterns only looked at
a full SSN, so the last four the engine actually uses were never checked); phone numbers in the
`555` exchange; DOB `2000-01-01` and the other default-fill dates by name; `unknown@…` emails;
`123 Main St` (only when there is no unit) and `PO Box 0`; ZIP `00000`/`99999`; names `TBD`/`None`
and repeated characters (`ZZZ`); and a placeholder *family* name with a real given name (the
normalizer only handled the reverse). `TABLE_VERSION` is `1.1.0`.

**Not implemented: single-character given names.** Spec V.D lists `"X"`-style single characters as
placeholder names. Applied to given names it drops initial-only first names (`L.`), which cost 194
ONC pairs-tier true matches (recall 0.9516 → 0.9374, below the 0.95 floor) and which the ranked
accuracy levers (BAI-1061) want to *match*, not discard. `reason_for_name(..., allow_initial=True)` keeps
them for given names; a single-character family name is still a placeholder. **This is a
deliberate deviation from the CMS spec**, accepted by the project lead and the reviewer; a ticket to
revisit it is to be filed.

**Spec-literal on purpose:** a real SSN/ITIN last four of `1234`/`0000`/`9999` (or repeated digits)
and a real `2000-01-01` birthday are treated as absent, as the spec's table says. Dropping a field
only removes evidence, and shared defaults are a real false-positive source.

**Cost of the rest:** the `555` exchange rule drops 4 ONC pairs (recall 0.9516 → 0.9513; population
0.9515 → 0.9513). Not implemented (no data): a DOB equal to the record's registration date, and
`123 Main St` "accompanied by a real city match".

**Over-reach found in review and fixed:** the name placeholder patterns are prefix-anchored
(`^infant`, `^baby`, `^zz+`) and were written for a *given* name, so applying them to a family name
alone drops real surnames (Infante, Babyak, Zzaman); only the unidentified / unknown / single-or-repeated-character reasons
(`FAMILY_NAME_EXACT_REASONS`) may drop a family name, and `doe`/`na` are kept as real surnames.
The test and newborn word lists are *not* used for a family name on its own: `Sample`, `Demo` and
`Baby` are real surnames (review finding), so they drop only as a given name or when the given name
is a placeholder too. The
unknown-value word list is not used for names wholesale (`nil`, `null` are real names). The `555`
rule applies to North American numbers only (`+46 8 555 1234` is valid) and sees through a phone
extension. "123 Main St" is rescued only by a *real* unit in line 2 (`looks_like_unit`), not any
non-blank line.

**Present-but-null again:** `ident.get("value", "")` returns `None` for a null value and the new ITIN
last-four check crashed on it; `lines[1]` can be `None` too (a FHIR null entry paired with `_line`).
Use `or ""`. Both are covered in `test_placeholder_edge_cases.py`.

**Where this could still bite:** test fixtures that use `555` phones, `123 Main St` or a 2000-01-01
birth date as "real" sample values now normalize to nothing; use values outside the spec table.
An attribution run (enable one group at a time against the ONC pairs tier) is the fast way to find
which new placeholder rule costs recall.

## Street Line is address line 1 plus an exact ZIP5, not every address line

CMS v3.4.0 Table 3 defines Street Line as "street line and ZIP standardized; ZIP must remain
exact." The engine put every address line (line 1 and the unit in line 2) into one set and
intersected the text, so it linked two records on a shared unit (`apt 2`) in different buildings,
and on identical street text in different ZIPs. Verified through `NormalizationManager` and
`MatchingEngine`, with a positive control. Fixed in `field_extractor.py`: each address emits one
`"<line 1>|<ZIP5>"` value (nothing without a 5-digit ZIP, nothing for a line that is only a unit),
`zip_codes` is ZIP5 so ZIP+4 matches ZIP5, and `FieldComparator.street_line_fuzzy_*` fuzzes the
line only (Damerau-Levenshtein <= 1, >= 5 characters) with the ZIP held exact.

**Effect on the ONC population tier:** 2 of 87,747 pairs flip, recall 0.9515 → 0.9513. Both are
labeled matches whose records have a street line and a blank ZIP, so they linked on street text
alone before. By the spec's own wording a blank ZIP cannot be "exact", so they no longer link; it
was decided (2026-10-07) to keep the strict reading, with no "both ZIPs blank" carve-out.

**Why it is usually invisible:** Phone + Street Line (C2-37) is largely subsumed by rule 11
(First Name + DOB + Phone), which needs no address, so a test that gives two records a shared phone
passes through rule 11 and never exercises Street Line. Test Street Line through rule 01
(First* + Last* + DOB* + Street Line*) with no phone, email or ID on either record.

**Where this could still bite:** (1) a persisted DuckDB or Mongo cache holds the old bare
street text and must be rebuilt (old values never match the new ones). (2) Any address stored
without a ZIP now has no Street Line at all, so rules 01 and H-14 / C2-37 / C2-39 cannot use it.
(3) Normalizers that leave a unit in line 1 (stacked designators) still put it in the value.
(4) "Line 1" is not always the first FHIR `line`: when scourgify can't parse an address it keeps the
original order, so `["c/o jane doe", "123 main st"]` would have made every record at a care-of or
facility-name line share one Street Line. `_street_line_one` takes the first line that starts with a
house number, else the first line. (5) Normalization strips `#`, so unit-only lines arrive as `4b`,
`unit 5 b`, `ph 3`; `_is_unit_only` covers those forms and the rarer USPS designators, and requires
the identifier to contain a digit or be one letter so `floor rd`, `unit dr` and `lot ln` stay streets.
(6) Placeholder ZIPs (`00000`, `99999`) are dropped by the V.D placeholder table (see the section
above), so they no longer form a Street Line value.
(7) Test with a case the in-memory blocker cannot reject for you: a ZIP one digit off on an identical
line passes blocking (composite edit distance 1), so only the Street Line comparator rejects it.

## Widened-match levers: most rules have no P(collision) headroom, and a test harness can hide a lever's effect

Rules 11, 12, 13-16, 08, 09 and 23 sit at exactly 2e-12, the approval threshold, so widening any of their
fields (DOB within one edit: measured 32.4x the exact-DOB u; initial-only first name: 37.5x) cannot pass
Table 3 as written. Rules 02, 03 and the eight household rules have the headroom. Restricted to the rules
that fit, the best package (DOB within one edit in 02/03/household + initial-only in household) keeps
0.9780 of the unrestricted 0.9822 pairs recall. Measured with `calculations/`,
`scripts/collision_feasibility.py` and `scripts/lever_recall.py`; see
`docs/TEST_SET_0.0.5_ACCURACY_ANALYSIS.md` section 5.7.

Separately, the first lever harness reported "DOB within one edit in household rules only" as having no
effect because it widened only `dob_fuzzy_match`; household rules compare DOB with exact matching, so
that path was never touched. The corrected harness shows +0.0042 pairs recall.

**Where this could still bite:** a monkeypatched counterfactual that reports "no effect" may just be
patching a code path the rule does not use; check that the baseline-vs-lever comparison actually exercises
the field in that rule before concluding a lever is inert.

## Only a generational suffix may veto a match; `md`/`phd` used to

Spec (Name Handling): "If a *generational* suffix can be identified on both the query and the response
and they do not match, the responder SHALL NOT return the match." The engine collected every suffix,
and `_suffix_conflict` vetoed any two non-overlapping sets, so `MD` vs `PhD`, `Jr` vs `MD`, `Esq` vs
`MD` and an unrecognized `MBA` vs `Jr` were all negated, and a shared `MD` hid a real `Jr` vs `Sr`
conflict (`Jr, MD` vs `Sr, MD` linked because the sets overlapped). Fixed: `GENERATIONAL_SUFFIXES`
(`jr sr i ii iii iv v vi vii viii ix x`, in `name_normalizer.py`) is the only thing `FieldExtractor`
collects into `suffixes`, and `NameNormalizer.suffixes_conflict` applies the same rule. Zero ONC cost
(the test set's only suffixes are `II`, `JR.`, `SR.`). Probe: two records identical except the suffix,
through the real pipeline, with `Jr`/`Sr` and `Jr`/`Jr.` controls.

**Narrowing the veto must not narrow what counts as generational.** Before, *any* unrecognized suffix
still vetoed; after restricting to a table, a generational suffix the table lacked (`VII`, `7th`,
`sixth`, `the second`, `2d`) silently stopped vetoing, so `VII` vs `VIII` went from blocked to linked.
The table now covers `vii`-`x`, the spelled ordinals and `2d`/`3d`; a raw suffix string is split into its
separate suffixes (`"Jr., MD"` -> `jr`, `md`; `"the"` is dropped); a bare string suffix is one suffix,
not a set of characters; and `FieldExtractor` canonicalizes (`generational_suffixes`) instead of
trusting that the input was normalized, so a raw `"Jr."` still vetoes.

**Where this could still bite:** a generational suffix the table does not list (`XI`+, other languages)
no longer vetoes; a suffix typed into the family or given name (`"Alvarez Jr"`) is never collected, on
`main` or here.

## First Name accepts the middle name (spec says it must not) - not changed, 194 ONC matches depend on it

Spec: name fields are "separated into discrete components", and Middle Name is "a last-resort
tiebreaker only" inside the two-candidate escalation (C.7.3). `FieldExtractor` adds *every* given name
to `first_names`, so a record's middle name satisfies First Name: a first name matches the other
record's middle name, and middle matches middle. Restricting `first_names` to the first given name
(plus its nicknames, and the first given name of each other name entry) is a three-line change and
passes the 37 spec tests, but costs **194 ONC pairs-tier true matches** (recall 0.9474 -> 0.9331,
population 0.9504 -> 0.9358; both below their floors) and gains none. All 194 are `given_abbreviate`
pairs such as `MICHAEL J` vs `M. J`: the initial replaces the first name, and the pair links today only
because the middle name (`J`, `RALPH`) matches. The benchmark labels them as matches.

This is the same trade as initial-only first names: the ranked levers in
`docs/TEST_SET_0.0.5_ACCURACY_ANALYSIS.md` want to *add* an initial-only first-name match (with a
priced collision), and the middle-name leak currently provides part of that recall unpriced. Decide
them together; do not tighten the leak alone. Probe: legacy vs new `first_names` over
`sample_labeled_pairs.jsonl`, pairs lost grouped by `rationale`.

**Where this could still bite:** an initial-only first-name rule added later will overlap with this
leak; remove the leak in the same change so the added rule's collision price is the whole story.
