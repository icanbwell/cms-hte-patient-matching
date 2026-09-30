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
