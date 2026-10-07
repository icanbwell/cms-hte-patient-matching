# Institutional-address registry: data retrieval and feasibility

Spike for Proposal v3.3.6 ("Institutional / Multi-household Address Identification Methodology",
a modification to §IV.G). The proposal's Step 1 matches a Street Address against public facility
registries (Appendix A); Step 2 falls back to a postal multi-unit signal, routed to manual review.
This doc records **how each Appendix A source (and some it doesn't list) can actually be
retrieved**, and **how well exact matching against them works**. It does not evaluate
precision/recall against real patient data (PHI stays in governed environments) — see "What this
does not measure".

Reproduce (raw downloads and output go to `data/institutional_registry/` and are committed; each
file's source URL and download date is in `manifest.json`; measured
2026-10-06). Standard library only, no extra packages:

```bash
uv run python -m scripts.institutional_registry.download            # fetch every automatable source (~10 min; --skip-overture skips the slow Overture extract)
uv run python -m scripts.institutional_registry.build_registry      # -> institutional_addresses.csv
uv run python -m scripts.institutional_address_feasibility          # print the section 2 measurements
```

Sources that can't be fetched automatically are downloaded by hand into
`data/institutional_registry/manual/` and merged by the build; see
`scripts/institutional_registry/MANUAL_DOWNLOADS.md` for what to download and the CSV format.

## The registry CSV

`institutional_addresses.csv` has one row per distinct (institution type, normalized street, ZIP5):
`institution_type`, `match_policy`, `name`, `street`, `city`, `state`, `zip`, `beds`,
`data_collected`, the match key (`match_street`, `match_zip5`), and the `sources`/`source_ids` that
listed it. `data_collected` is the ISO date the data was gathered: taken from the source where it
states one (HIFLD per-facility source date, Princeton "Date Accessed", PPI survey date, Care
Compare/POS processing date, Overture release) and otherwise the date we downloaded the file. When
several sources list an address it is the newest of them, so an address confirmed by a current
source isn't labeled with a 2021 date. An address that
serves two types (e.g. a hospital campus that also houses a nursing home) appears once per type.
Current build: **154,525 rows**.

| `match_policy` | `institution_type` (rows) |
|---|---|
| `block_household_rules` (88,765) | assisted_living 60,641; nursing_home 14,792; correctional 7,907; homeless_shelter 3,828; halfway_house 767; psychiatric_hospital 624; federal_correctional 201; long_term_hospital 5 |
| `review` (65,760) | senior_living 48,941; hospice 6,051; higher_education_campus 5,994; hospital 4,774 |

`match_policy` is a default this spike chose, not something the proposal specifies (`MATCH_POLICY`
in `build_registry.py`). **`block_household_rules`** means the address must not be used as a
Household-tier field (Table 2-H rules H-03, H-06, H-09 and H-14, which pair Street Line with
SSN/ITIN last 4, Subscriber ID or Phone); the patient is still matched by every other rule. It is
set where residents live at the address. **`review`** is set where the address is mostly offices or
non-residential space, so blocking it automatically would over-block: `hospice` (mostly
administrative offices, often with a suite number), `higher_education_campus` (schools and offices,
no housing flag), `hospital` (acute care, critical access, children's, VA, DoD and rural emergency,
i.e. short-stay or outpatient), and `senior_living` (Overture's `retirement_home`, which mixes
nursing homes, assisted living and independent/senior apartments). Hospitals are split on Care
Compare's `Hospital Type`: `Psychiatric` and `Long-term` become their own types because patients
stay for extended periods.

## 1. Retrieval, source by source

| Source | Automated | How | Notes |
|---|---|---|---|
| CMS Care Compare — nursing homes | Yes, no key | Provider Data Catalog `4pq5-n9py`; CSV at `https://data.cms.gov/provider-data/api/1/datastore/query/<id>/0/download?format=csv` | 14,690 rows; street, city, state, ZIP, certified beds |
| CMS Care Compare — hospitals | Yes, no key | `xubh-q36u` | 5,419 rows; no bed count |
| CMS Care Compare — hospice | Yes, no key | `yc9t-dgbk` | 6,669 rows; `Address Line 1`/`2` |
| CMS Provider of Services (POS) | Yes, no key | Resolve the newest "Provider of Services File - Internet Quality Improvement and Evaluation System" entry in `https://data.cms.gov/data.json`, take its `text/csv` `downloadURL` (175 MB) | 77,564 rows. The URL changes every quarter, so never hardcode it. `prvdr_type_id` 20 = nursing home, 12 = hospice (decoded by joining to Care Compare on CCN). Hospitals are not in this file. Has certified bed counts. |
| NCES IPEDS | Yes, no key | `https://nces.ed.gov/ipeds/datacenter/data/HD<year>.zip` (HD2024 is latest; the current year 404s until published) | 6,072 campus addresses. IC2024 has no housing-capacity field, so a dorm cannot be told from the rest of the campus. |
| Federal Bureau of Prisons | Yes | No bulk export. List page `https://www.bop.gov/locations/list.jsp` exposes facility codes in `/locations/institutions/<code>/` links; `https://www.bop.gov/PublicInfo/execute/phyloc?todo=query&output=json&code=<CODE>` returns JSON per facility (address type 1 = physical) | Undocumented API (found in bop.gov's own JavaScript). 79 codes against ~118 institutions; listing by state/region returns nothing. |
| HIFLD Prison Boundaries | Yes, no key | DHS shut HIFLD Open on 2025-08-26; HIFLD Next republishes it. Walk `https://hifld.publicenvirodata.org/api/collections/hifld` -> "Prison Boundaries" child catalog -> latest-version collection -> GeoParquet asset on `storage.googleapis.com`; read with DuckDB | 6,468 facilities (5,845 open, 487 closed; county 3,694, state 2,079, local 346, federal 259), addresses on all but one. Capacity `-999` means unknown. The release ID in every URL changes, so the catalog is walked each run. License is "other"; check before redistributing. |
| Prison Policy Initiative facility lists (2020 vintage) | Yes (scraped) | One HTML table per state at `https://www.prisonersofthecensus.org/data/prisons2020/<ST>/`, linked from `.../data/state_federal_local_2020vintage.html` | 5,217 facilities, but only 42% have a street address and survey dates are 2012–2013. Adds 888 addresses HIFLD lacks. Terms of use not stated. |
| Overture Maps places | Yes, no key | DuckDB over the public S3 bucket `overturemaps-us-west-2` (~7 min scan); newest release resolved from the bucket listing | US `jail_or_prison`, `assisted_living_facility`, `retirement_home`, `homeless_shelter`, `halfway_house`. Overture's own `nursing` category is individual nurse practitioners, **not** nursing homes. License varies by contributing source. |
| Princeton assisted-living dataset | Yes, no key | `https://raw.githubusercontent.com/antonstengel/assisted-living-data/main/assisted-living-facilities.csv` (CC BY 4.0) | 44,649 state-licensed facilities with address, capacity, license number. **Collected in 2021**, so stale. ZIPs lose leading zeros (padded on load). |
| California assisted living (CDSS Community Care Licensing) | Yes, no key | CSV of all licensed facility types from `gis.data.chhs.ca.gov` (ArcGIS hub item; the older `data.chhs.ca.gov` CSV link returns a login page); filter `TYPE` 740/741 (Residential Care for the Elderly) | 37,923 rows, of which 8,603 elder care; all have street and ZIP. Status codes are undocumented in the file, so all are kept. |
| Michigan assisted living / adult foster care (LARA) | Yes, no key | `https://documents.apps.lara.state.mi.us/bchs/afc_sw.txt`, a comma-delimited file with **no header row**; layout is on LARA's "record description" page | 4,469 active rows. The street is in column 5, or column 4 when column 5 is empty (column 4 otherwise holds a suite). Includes small foster-care homes (types AF/AS/AM, 1-12 beds), group homes, and homes for the aged (AH/XH). |
| Wisconsin assisted living (DHS) | Yes, no key | Public ArcGIS service `dhsgis.wi.gov/server/rest/services/DHS_GIS/Facilities/MapServer`, layers 7 (CBRF), 17 (RCAC), 2 (adult family homes), 2,000 records per page. The open-data portal's own CSV download returns 403. | 4,125 rows (1,555 + 367 + 2,203). No capacity field. |
| Florida assisted living (AHCA FloridaHealthFinder) | Yes, no key | No bulk file. POST the facility search (type ALF, all counties) with a session cookie and anti-forgery token; the results page embeds the records as JSON | 3,024 facilities with address, ZIP, bed count, license status. Depends on the page structure, so the likeliest of the four to break. |
| Minnesota assisted living (MDH) | Yes, no key | The provider lookup's own CSV API (`provider-profile-api.web.health.state.mn.us/csv?...providerGroup=Assisted%20Living%20Facilities`) | 2,525 facilities. An earlier version of this doc said "no structured download"; that was wrong, only the search page had been checked. |
| 23 more state lists (AK, AZ, CO, GA, IA, IN, KY, LA, MD, MN, MO, NC, NE, NJ, NY, OR, PA, SC, TN, TX, UT, VA, WV) | Yes, no key | One module per state in `scripts/institutional_registry/states/` (spreadsheets, Socrata, ArcGIS, form posts, HTML) | See `docs/ASSISTED_LIVING_STATE_COVERAGE.md` for every source, count and caveat, and for the 20 states that could not be automated. |
| BJS Census of State and Federal Adult Correctional Facilities / Census of Jails | No | ICPSR (HTTP 403 anonymously) | Manual download; unconfirmed whether public files include street addresses. |
| State DOC rosters | No | Fragmented per state | Manual. |
| Vera Incarceration Trends | No | County-level only | No facility addresses. |
| CASS validation (Step 2) | No | USPS or paid vendors (Smarty, Melissa, Loqate, Experian) | Needs an account; not evaluated here. |

No usable open source was found for college dormitories (IPEDS is campus-level) or for
address-level homeless shelters beyond Overture (HUD's Housing Inventory Count is per program).

## 2. How well exact matching works

Each address goes through the engine's own `AddressNormalizer` (scourgify), and the match key is
**(normalized street line 1, ZIP5)** with any trailing unit/suite removed. The first two tables
cover the original CMS/IPEDS/BOP sources (`scripts/institutional_address_feasibility.py`).

| source | rows | usable key | distinct addresses | rural-route / PO-box style |
|---|---|---|---|---|
| bop_physical | 79 | 100.0% | 79 | 2.5% |
| care_compare_hospice | 6669 | 100.0% | 5910 | 1.8% |
| care_compare_hospital | 5419 | 100.0% | 5398 | 3.2% |
| care_compare_nh | 14690 | 100.0% | 14674 | 1.3% |
| ipeds_campus | 6072 | 99.8% | 5994 | 2.4% |
| pos_iqies | 21161 | 100.0% | 20434 | 1.3% |

**31,828 distinct addresses** across these sources.

**Same facility, two sources.** 14,689 nursing homes appear in both Care Compare and POS; their
normalized keys are identical for **99.3%**. The ~0.7% misses are a mix of real data disagreement
(different street entirely, e.g. a mailing vs. physical address) and normalization misses
(`Howel Mill Road NW` vs `HOWELL MILL ROAD N.W.`, `1st` vs `FIRST`, multi-address strings).

**Patient-side variation** (3,000 sampled registry addresses, perturbed, then looked up; the
typo row varies by a point or so between runs because the sample is random):

| variation | still matches |
|---|---|
| unit appended (`, APT 4B`) | 100.0% |
| room appended (` RM 114`) | 100.0% |
| lowercased | 100.0% |
| ZIP+4 | 100.0% |
| ZIP dropped | 0.0% |
| one-character street typo | about 8% |

Matching is exact by design, so it is robust to formatting, case, ZIP+4 and unit suffixes, and
**not** robust to a missing ZIP or a misspelled street. A fuzzy street match would trade that off
against false exclusions, which matter more here than missed exclusions (a blocked address silently
drops a Household-tier rule for every resident at it).

### Correctional sources overlap

Distinct (street, ZIP5) keys: HIFLD 5,744 (open facilities only), Overture `jail_or_prison` 3,290,
BOP 79; **7,213 across the three**. 79.7% of BOP addresses (63 of 79) appear in HIFLD, 55.8% of
Overture's appear in HIFLD, and 32.0% of HIFLD's appear in Overture, so the sources are
complementary rather than redundant. Of 1,858 distinct PPI addresses, 52.2% are already in HIFLD
and 888 are new.

### Senior living and assisted living

Overture's `retirement_home` covers **66.1%** of CMS nursing-home addresses (70.7% together with
`assisted_living_facility`), so it is the only national source that lists assisted living and
personal care homes alongside nursing homes, but it cannot separate them from senior apartments.
Of the Princeton 2021 assisted-living addresses, 8.9% match Overture's `assisted_living_facility`
and 38.1% match it or `retirement_home` — the two sources largely disagree on what exists, and
the Princeton data is five years old.

**State lists refresh most of the 2021 data.** Current state licensing lists are downloaded
automatically for 27 states: CA, MI, WI, FL, and 23 more (AK, AZ, CO, GA, IA, IN, KY, LA, MD, MN,
MO, NC, NE, NJ, NY, OR, PA, SC, TN, TX, UT, VA, WV). Per-state sources, row counts and caveats are
in `docs/ASSISTED_LIVING_STATE_COVERAGE.md`, which also lists the 20 states (and DC) that are not
automated and why. Compared with Princeton's 2021 addresses for the same states, 76% of the
36,978 addresses are still on the current lists (from 52% in IN to 98% in NY), and the lists add
11,218 addresses Princeton lacked. The two datasets agree on most addresses, which supports both;
the 24% missing from the current lists are likely closures or moves (not checked facility by
facility).

Rows dated 2021 only (`sources` = `princeton_alf`) fell from 38,040 to 12,614 of 60,641
`assisted_living` rows. Of those 12,614, 8,329 are in covered states (addresses absent from the
current list, probably closed) and 4,285 are in the 20 uncovered states and DC (largest: ME, OH, WA,
IL, KS, AL). The state lists include small group homes (e.g. Michigan foster care homes, Oregon
and Wisconsin adult foster/family homes) as Princeton's data does; `beds` carries capacity where
the state provides it so a consumer can filter them out.

## 3. Findings that change how this would be built

1. **Strip units on both sides of the key.** Registry streets embed suites (`7920 BELT LINE ROAD
   SUITE 760`, trailing ` -`), and scourgify leaves a unit inside line 1 when the line has
   stacked designators. Without stripping, appending a unit to a registry address matched only
   ~80% of the time. A `#` rule has to require something before it, or it eats `#16 WILSON FARM
   ROAD` house numbers.
2. **Unparseable lines fall back to unnormalized text**, so the same address can get
   `road` from one source and `rd` from another. Part of the 0.7% cross-source disagreement.
3. **Nursing homes, hospices and hospitals are well covered** (~26k CMS facilities with bed
   counts, free and current). **Correctional coverage is no longer the weak link**: HIFLD adds
   state prisons and local jails (7,213 distinct addresses across HIFLD, Overture and BOP), though
   HIFLD itself is an archive of a discontinued DHS product and will not be updated.
4. **Assisted living is still the weakest data, but much improved**: no authoritative national
   source exists, and Overture and the 2021 Princeton data disagree heavily. Current state
   licensing lists are automated for 27 states and agree with Princeton on 76% of addresses
   (a few are old: MD July 2025, AZ Feb 2025, LA Mar 2026). 12,614 rows still rest on 2021 data
   alone, 4,285 of them in states with no automated source. Separately, 1,390 Princeton rows
(3%) have no ZIP and are not in the registry at all; four states (ID, MA, NV, OK) lose all of
their Princeton rows this way and have not yet been researched for a state list.
5. **Campus ≠ dorm.** IPEDS gives one campus address; matching it excludes the administrative
   address but cannot tell which patients live in a residence hall.
6. **Bed counts exist for CMS facilities** (POS `crtfd_bed_cnt`, Care Compare certified beds) and
   for HIFLD and Princeton (capacity), so a facility size could be carried with the match and
   used to bound the u-value for a blocked address rather than just dropping it.
7. **Category names in open map data can't be trusted without checking.** Overture's `nursing`
   category looked like 15,480 nursing homes; sampling showed it is individual nurse
   practitioners. Check what a category contains before counting on it.
8. **Which facility types count as institutional is a policy decision for the proposal, not a
   data one.** Hospice, IPEDS and hospital samples are mostly non-residential, which is why they
   are `review`.

## 4. What this does not measure

- **Precision/recall against real patients.** Whether a registry hit corresponds to a resident of
  that facility (vs. staff, a medical office in the same building, or a mistaken entry) needs
  real member data in a governed environment (Tier 2/3 in `docs/sessions/conventions.md`).
- **False exclusion rate on ordinary residential addresses**, for the same reason.
- **Step 2** (CASS multi-unit density): not retrievable without a vendor account, and the
  proposal itself flags its thresholds as unvalidated.
- **Completeness**: no ground truth exists for the total number of group-quarters addresses, so
  coverage can't be stated as a percentage.
- **Overture and HIFLD accuracy** beyond overlap with other sources: the overlap figures show the
  sources agree partially, not which is right.

## 5. Suggested next steps

1. Decide which facility types count as institutional (nursing home, hospice, inpatient/psychiatric
   hospital, correctional, assisted living, shelter, dorm) so the registry can be filtered, not
   just unioned.
2. Confirm licenses for HIFLD (archive license is "other"), the PPI lists and Overture's
   contributing sources before the registry is distributed rather than used internally.
3. Decide how to treat Princeton-only assisted living rows in the 27 covered states: each has a
   current state list, so a 2021 address missing from it is probably closed (8,329 rows; 1,453 in
   CA alone). They are still in the registry, dated 2021. Decide whether to drop them, whether to
   add more states (ME, OH, WA, IL, KS, AL are the largest uncovered; see
   `docs/ASSISTED_LIVING_STATE_COVERAGE.md` for what each would take), and whether to filter
   small group homes by capacity.
4. If this proceeds, move `strip_unit`/`address_key` (currently in
   `scripts/institutional_registry/build_registry.py`) into `patient_matching/normalization/`
   with tests and add a registry loader; this spike deliberately stays in `scripts/`.
5. Validate hit rates on real member addresses in Databricks, with query definitions only
   committed, never output.
