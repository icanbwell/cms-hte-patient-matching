# Institutional-address registry: data retrieval and feasibility

Spike for Proposal v3.3.6 ("Institutional / Multi-household Address Identification Methodology",
a modification to §IV.G). The proposal's Step 1 matches a Street Address against public facility
registries (Appendix A); Step 2 falls back to a postal multi-unit signal, routed to manual review.
This doc records **how each Appendix A source can actually be retrieved**, and **how well exact
matching against the retrievable ones works**. It does not evaluate precision/recall against real
patient data (PHI stays in governed environments) — see "What this does not measure".

Reproduce (raw downloads and output go to `data/institutional_registry/`, gitignored; measured
2026-10-06):

```bash
uv run python -m scripts.institutional_registry.download            # fetch every retrievable source
uv run --with pandas python -m scripts.institutional_registry.build_registry   # -> institutional_addresses.csv
uv run --with pandas python -m scripts.institutional_address_feasibility       # print the section 2 measurements
```

`institutional_addresses.csv` has one row per distinct (institution type, normalized street, ZIP5):
`institution_type` (`nursing_home`, `hospice`, `hospital`, `higher_education_campus`,
`federal_correctional`), `name`, `street`, `city`, `state`, `zip`, `beds`, the match key
(`match_street`, `match_zip5`), and the `sources`/`source_ids` that listed it. Current build:
32,314 rows (nursing_home 14,792; hospice 6,051; higher_education_campus 5,994; hospital 5,398;
federal_correctional 79). An address that serves two types (e.g. a hospital campus that also
houses a nursing home) appears once per type.

## 1. Retrieval, source by source

| Appendix A source | Retrievable | How | Notes |
|---|---|---|---|
| CMS Care Compare — nursing homes | Yes, no key | Provider Data Catalog `4pq5-n9py`; CSV at `https://data.cms.gov/provider-data/api/1/datastore/query/<id>/0/download?format=csv` | 14,690 rows; street, city, state, ZIP, certified beds |
| CMS Care Compare — hospitals | Yes, no key | `xubh-q36u` | 5,419 rows; no bed count |
| CMS Care Compare — hospice | Yes, no key | `yc9t-dgbk` | 6,669 rows; `Address Line 1`/`2` |
| CMS Provider of Services (POS) | Yes, no key | Resolve the newest "Provider of Services File - Internet Quality Improvement and Evaluation System" entry in `https://data.cms.gov/data.json`, take its `text/csv` `downloadURL` (175 MB) | 77,564 rows. The URL changes every quarter, so never hardcode it. `prvdr_type_id` 20 = nursing home, 12 = hospice (decoded by joining to Care Compare on CCN). Hospitals are not in this file. Has certified bed counts. |
| NCES IPEDS | Yes, no key | `https://nces.ed.gov/ipeds/datacenter/data/HD<year>.zip` (HD2024 is latest; the current year 404s until published) | 6,072 campus addresses. IC2024 has no housing-capacity field, so a dorm cannot be told from the rest of the campus. |
| Federal Bureau of Prisons | Partly | No bulk export. List page `https://www.bop.gov/locations/list.jsp` exposes facility codes in `/locations/institutions/<code>/` links; `https://www.bop.gov/PublicInfo/execute/phyloc?todo=query&output=json&code=<CODE>` returns JSON per facility (address type 1 = physical, 3 = inmate mail) | The API is undocumented (found in bop.gov's own JavaScript). The list page yields 79 codes against ~118 institutions; listing by state/region returns nothing. |
| HIFLD group-quarters layers | Not confirmed | DHS shut HIFLD Open on 2025-08-26. Community archives: Data Rescue Project (DataLumos), HIFLD Next (PEDP), HSDL | No stable direct-download URL confirmed. The NASA NCCS ArcGIS mirror refused connections from the sandbox. Needs a manual pull or confirming an archive's license/URL before this can be automated. |
| State DOC rosters, BJS Census of Jails, Vera | No | BJS Census of Jails is on ICPSR (HTTP 403 anonymously); state DOC data is fragmented per state; Vera Incarceration Trends is county-level only | No bulk facility-address source for state prisons or local jails was found. |
| CASS validation (Step 2) | Not a download | USPS or paid vendors (Smarty, Melissa, Loqate, Experian) | Needs an account; not evaluated here. |

## 2. How well exact matching works

Registry = Care Compare (nursing home, hospital, hospice) + POS (types 20 and 12, active only) +
IPEDS campuses + BOP physical addresses. Each address goes through the engine's own
`AddressNormalizer` (scourgify), and the match key is **(normalized street line 1, ZIP5)** with any
trailing unit/suite removed.

| source | rows | usable key | distinct addresses | rural-route / PO-box style |
|---|---|---|---|---|
| bop_physical | 79 | 100.0% | 79 | 2.5% |
| care_compare_hospice | 6669 | 100.0% | 5910 | 1.8% |
| care_compare_hospital | 5419 | 100.0% | 5398 | 3.2% |
| care_compare_nh | 14690 | 100.0% | 14674 | 1.3% |
| ipeds_campus | 6072 | 99.8% | 5994 | 2.4% |
| pos_iqies | 21161 | 100.0% | 20434 | 1.3% |

**31,828 distinct addresses** across all sources.

**Same facility, two sources.** 14,689 nursing homes appear in both Care Compare and POS; their
normalized keys are identical for **99.3%**. The ~0.7% misses are a mix of real data disagreement
(different street entirely, e.g. a mailing vs. physical address) and normalization misses
(`Howel Mill Road NW` vs `HOWELL MILL ROAD N.W.`, `1st` vs `FIRST`, multi-address strings).

**Patient-side variation** (3,000 sampled registry addresses, perturbed, then looked up):

| variation | still matches |
|---|---|
| unit appended (`, APT 4B`) | 100.0% |
| room appended (` RM 114`) | 100.0% |
| lowercased | 100.0% |
| ZIP+4 | 100.0% |
| ZIP dropped | 0.0% |
| one-character street typo | 8.5% |

Reading the table: matching is exact by design, so it is robust to formatting, case, ZIP+4 and
unit suffixes, and **not** robust to a missing ZIP or a misspelled street. A fuzzy street match would
trade that off against false exclusions, which matter more here than missed exclusions (an excluded
address silently drops a Household-tier rule for every resident at it).

## 3. Findings that change how this would be built

1. **Strip units on both sides of the key.** Registry streets embed suites (`7920 BELT LINE ROAD
   SUITE 760`, trailing ` -`), and scourgify leaves a unit inside line 1 when the line has
   stacked designators. Without stripping, appending a unit to a registry address matched only
   ~80% of the time. A `#` rule has to require something before it, or it eats `#16 WILSON FARM
   ROAD` house numbers.
2. **Unparseable lines fall back to unnormalized text**, so the same address can get
   `road` from one source and `rd` from another. Part of the 0.7% cross-source disagreement.
3. **Facility coverage is strongest where populations are largest**: nursing homes, hospices and
   hospitals are complete, free and current (~26k CMS facilities with bed counts). Correctional
   coverage is the weak link: 79 federal facilities, nothing for state prisons or local jails.
4. **Campus ≠ dorm.** IPEDS gives one campus address; matching it excludes the administrative
   address but cannot tell which patients live in a residence hall.
5. **Bed counts exist for CMS facilities** (POS `crtfd_bed_cnt`, Care Compare certified beds),
   so Step 1 could carry a facility size, and the u-value for an excluded address could be
   bounded rather than just dropped.
6. **Hospital and medical-office addresses are not residential group quarters.** Registry hits on
   hospitals and POS types beyond nursing homes/hospice would exclude addresses where patients
   do not live. Which facility types count as "institutional" is a policy decision for the
   proposal, not a data one.

## 4. What this does not measure

- **Precision/recall against real patients.** Whether a registry hit corresponds to a resident of
  that facility (vs. staff, a medical office in the same building, or a mistaken entry) needs
  real member data in a governed environment (Tier 2/3 in `docs/sessions/conventions.md`).
- **False exclusion rate on ordinary residential addresses**, for the same reason.
- **Step 2** (CASS multi-unit density): not retrievable without a vendor account, and the
  proposal itself flags its thresholds as unvalidated.
- **Completeness**: no ground truth exists for the total number of group-quarters addresses, so
  coverage can't be stated as a percentage.

## 5. Suggested next steps

1. Decide which facility types count as institutional (nursing home, hospice, inpatient/psychiatric
   hospital, correctional, dorm) so the registry can be filtered, not just unioned.
2. Resolve the correctional gap: confirm an archive of HIFLD Prison Boundaries (license, stable
   URL), or accept federal-only coverage and say so in the spec.
3. If this proceeds, move `strip_unit`/`address_key` (currently in
   `scripts/institutional_registry/build_registry.py`) into `patient_matching/normalization/`
   with tests and add a registry loader; this spike deliberately stays in `scripts/`.
4. Validate hit rates on real member addresses in Databricks, with query definitions only
   committed, never output.
