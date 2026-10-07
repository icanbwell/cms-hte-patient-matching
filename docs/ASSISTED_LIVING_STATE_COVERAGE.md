# Assisted living: state-by-state coverage

Assisted living has no national source, so the registry's `assisted_living` rows come from the
2021 Princeton dataset plus current state licensing lists. This doc records, for every state,
whether its list is downloaded automatically and, where it isn't, exactly why. Background and
overlap measurements are in `docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md`; how to run the
downloads is in `scripts/institutional_registry/MANUAL_DOWNLOADS.md`.

Research was done 2026-10-06 by fetching each endpoint, not from search summaries, with one
exception noted per row. The research covered the 43 states and DC that had 2021-only rows;
four states (ID, MA, NV, OK) were not researched, see the end of the "Not automated" section. "Stale rows" is the number of 2021-only Princeton rows in that state
before the new automation (20,080 across the 43 states not already covered by CA, MI, WI, FL).

## Not automated, and why

### Needs real work (a source exists, but it is awkward)

| State | Stale rows | What exists | Why it isn't automated | What a fix would take |
|---|---|---|---|---|
| OH | 650 | ODH Provider Search (ASP.NET form, `publicapps.odh.ohio.gov/eid/Provider_Search.aspx`), about 720-800 residential care facilities | The list view has street, city and county but **no ZIP**, is **paged 10 rows at a time**, and "all counties" doesn't work (88 county loops plus pager postbacks). ODH's ArcGIS layer has only 9 residential care rows (2018). | Fetch per-provider detail pages for ZIP (untested), or geocode. |
| WA | 456 | DSHS ALTSA lookup (`fortress.wa.gov/dshs/adsaapps/lookup/BHPubLookup.aspx`) | No bulk file. An ASP.NET postback per county (39 loops, `__VIEWSTATE`) returns an HTML table with street, city, ZIP in one cell; **no capacity**. Verified for Spokane and King. | Write the county loop and cell parser; doable, just fragile. |
| KS | 249 | KDADS Facilities Directory, an Oracle APEX interactive report (`webapps.kdads.ks.gov/prod/f?p=113:901`), 783 rows across all adult care home types | **No CSV/Excel export, and only the first 50 rows were fetchable**; paging needs APEX ajax calls (`wwv_flow.ajax`) that were not made to work. The marketing host `kdads.ks.gov` returns an Akamai 403 to curl. | Reverse-engineer the APEX pagination, or drive a browser. |
| AL | 207 | ADPH Facilities Directory (`dph1.adph.state.al.us/FacilitiesDirectory/`), an ASP.NET form with an Excel export | The only open copy, an ArcGIS layer, was **last edited 2017-11** (202 assisted living and 100 specialty-care rows) and misses newer facilities. The live form **was not tested**. | Test the `__VIEWSTATE` POST and Excel export. |
| CT | 168 | `data.ct.gov` dataset it4j-andf, updated daily (269 rows, 102 active) | It lists **Assisted Living Service Agency** licenses, i.e. the agency's address, usually inside a Managed Residential Community. **Connecticut doesn't license the buildings themselves**, so building addresses aren't available. | Nothing without another source. |
| SD | 141 | Official DOH list not published. Alternative: the DHS "Dakota at Home" directory (`dakotaathome.sd.gov`, 139 results) | The alternative is a **resource directory, not the licensee list**, so it may omit licensed facilities or include unlicensed ones. HTML only, address in one string. | Decide whether the directory is acceptable, then scrape it. |
| RI | 57 | RIDOH assisted living finder (`datahealth.ri.gov/find/assistedliving/`), 112 license rows | The list has **name, care type and city only**; street and ZIP need **one detail request per facility** (N+1). An Excel export exists per search snippets but no link was found. `health.ri.gov` returns a Cloudflare 403 (only `datahealth.ri.gov` works). | Loop over detail pages (verified on one). |
| DE | 28 | `dhss.delaware.gov/dhcq/dhcq/licensed-assisted-living-facilities/`, about 39 facilities in HTML accordions | Works, but small: the address is **one string** to split, and the page structure needs careful parsing. Not worth its own scraper yet. | Small scraper. |
| WY | 27 | Annual facility directory spreadsheet (`health.wyo.gov/wp-content/uploads/2026/10/2026-2027-Facility-Directory.xlsx`), 31 assisted living rows | The **URL changes every year**, a bare curl gets 403, and name, street and city/state/ZIP share **one multi-line cell**. Small. | Scrape the page link, split cells. |
| HI | 14 | State GIS layer (`geodata.hawaii.gov/arcgis/rest/services/HumanHealthSafety/MapServer/3`), 3,560 facilities of all types | Only **17 are "Assisted Living Facility"**; the care homes are Type I/II adult residential care homes (about 500) and **1,295 community care foster family homes**. Which of those count as institutional is a policy call. The status field is 0 on every row. | Decide the types, then it's a simple ArcGIS query. |

### Only stale open data

| State | Stale rows | What exists | Why it isn't automated |
|---|---|---|---|
| IL | 402 | `data.illinois.gov` dataset 8z4a-ix8q (495 rows) | **Old snapshot**: license expiry dates run only 2018-12 to 2021-05 and it was last updated 2024-02. The current IDPH list is a Salesforce lookup in a browser (`llcs.dph.illinois.gov`), and `idph.illinois.gov/AssistedLiving` returned 503. |
| AR | 84 | ArcGIS layer `gis.arkansas.gov/.../Health/FeatureServer/5` (158 assisted living / residential care rows) | **Newest update is October 2018.** The official eLicensing provider search is a Salesforce site, and the DHS site is Cloudflare-blocked to curl. |
| ND | 104 | A PDF of about 70 facilities (`hhs.nd.gov/.../statewide-licensed-assisted-living-facilities-exception.pdf`) and an ArcGIS layer of 75 rows | The PDF is parseable with `pdftotext -layout` (not a Python dependency), and the ArcGIS layer was **last edited December 2021**. |

### No usable source found

| State | Stale rows | Why |
|---|---|---|
| ME | 953 | The linked "Assisted Living Facilities Search" (`gateway.maine.gov/dhhs-apps/rcare/`) **returns 404**. The Aspen licensed-provider search (POST form with a CSRF token) lists only Level IV residential care (7+ residents) and medical types, and was not tested. No ArcGIS or Socrata layer found. |
| MS | 191 | **PDF only** (`msdh.ms.gov/page/resources/7660.pdf`, dated 2026-09-18). The personal care homes section reads cleanly with `pdftotext -layout`, but no Excel, CSV or ArcGIS source exists, and the host needs a full Chrome user agent. |
| MT | 180 | **No roster is published**: the DPHHS licensure pages have only applications, forms and rules. The one DPHHS ArcGIS layer holds 64 nursing homes (2023). |
| NH | 109 | `dhhs.nh.gov` and `forms.nh.gov` return **HTTP 403 (Akamai) even with browser headers**; the list is a PDF or search UI that needs a real browser. The only GIS service has nursing homes only. |
| NM | 146 | `alf.hca.nm.gov` **timed out on connect from this network** (ports 80 and 443), so the 209-facility directory could not be inspected. It may be a network block; retry from another network. |
| VT | 108 | **PDF only** (`dlp.vermont.gov/.../rch_list_by_counties.pdf`, dated 2025-01-17). No `data.vermont.gov` dataset or VCGI layer exists. |
| DC | 11 | **PDF only** (`dchealth.dc.gov/.../Assisted Living Residences Directory.pdf`, 2026-09); the table wraps and `pdftotext` output is messy. The only open layer has 10 memory-care rows. |

### Not researched: ID, MA, NV, OK

These four states were missed by the research above, which covered only the states that had
2021-only rows in the registry. They have none because **their Princeton rows have no ZIP code at
all** (NV 387 rows, ID 272, MA 268, OK 189), and the registry requires street plus ZIP to build a
match key, so those rows were dropped. Their `assisted_living` rows today come only from Overture
(ID 104, MA 177, NV 67, OK 115). Princeton also has blank ZIPs on 178 Kansas rows, 74 New Mexico
rows, 11 Maine rows and 4 DC rows (1,390 of 44,638 overall). No state source for these four has
been looked for yet.

## Automated

27 states are downloaded automatically: CA, MI, WI and FL (raw files `state_al_*`, see
`MANUAL_DOWNLOADS.md`) and the 23 below, one module each in
`scripts/institutional_registry/states/`, written to `data/institutional_registry/state_lists/<ST>.csv`.
All 23 returned rows on the 2026-10-06 run and none failed (`state_lists_status.json` records the
result of every run, including failures). Every row has street, city and ZIP except 2 in AK and 1
in GA, which have no ZIP in the source.

| State | Rows | Source and method | Types kept | Freshness and notes |
|---|---|---|---|---|
| AK | 814 | DHSS licensed assisted living homes spreadsheet; the link is scraped from the licensing page each run because the filename changes monthly | Assisted Living Home | Updated 2026-08-31. Rows are license segments, de-duplicated by license number. |
| AZ | 2,072 | ADHS ArcGIS layer 18 (`All_State_Licensed_Facilities_in_Arizona`) | Assisted Living Home 1,719; Assisted Living Center 328; Adult Foster Care 25 | **February 2025 snapshot**; the other ADHS layers carry the same run date, so no newer ADHS data was found. Behavioral health and respite settings excluded. |
| CO | 683 | CDPHE ArcGIS layer | Assisted Living Residence (ALR only 358; ALR/ACF 284; ALR/BISL 41) | Updated 2026-06-15. 11 `Pending` rows are kept, with that status. |
| GA | 1,888 | DCH facility search, which serves a 5 MB XML dump of every facility | Personal Care Home 1,562; Assisted Living Community 326 | No capacity or status. Community living arrangements (developmental disability homes) excluded. |
| IA | 498 | DIAL Health Facilities Database: token, search, then a session CSV export per type | Assisted Living Programs 263; dementia ALPs 174; Residential Care Facilities 61 | All active. Boarding homes (room and board only) excluded. 44 addresses have more than one row (an assisted living building plus its memory care wing under separate licenses). |
| IN | 230 | ISDH residential care directory (one HTML page) | Residential care facilities | **Indiana has no assisted living license**, so this is the closest list. Page posted 2026-09-24. |
| KY | 294 | CHFS spreadsheets for assisted living communities and personal care homes | Assisted living communities 247 (plain, dementia care, behavioral health); personal care homes 47 | No as-of date in the files. |
| LA | 164 | LDH licensed providers spreadsheet, filtered to Adult Residential Care | Adult Residential Care (levels 1-4) | **File is `2026_03`, about 7 months old**: LDH has not published later months. No capacity. |
| MD | 1,568 | OHCQ Socrata dataset on `opendata.maryland.gov` | All rows are assisted living programs (no type column) | **Last updated July 2025.** License ID present on 1,236 rows. |
| MN | 2,525 | MDH provider lookup API, returned as CSV | Assisted Living Facility 1,582; with dementia care 601; provisional 342 | Licenses expire 2026-27, so current. 4 duplicate licenses share two buildings. |
| MO | 600 | DHSS Section for Long-Term Care Regulation, Socrata | ALF 60; ALF** 271; RCF 166; RCF* 103 (nursing and ICF dropped) | `status` holds the license expiration date, not a status. |
| NC | 1,083 | DHSR adult care home and family care home spreadsheets | Adult care homes (7+ beds) 568; family care homes (2-6 beds) 515 | As of 07/2026. |
| NE | 277 | NE DHHS layer on ArcGIS Online (see below) | Assisted Living Facility | Roster dated 2025-10-15. **The canonical `gis.ne.gov` service is down**; see "Implemented but needs attention". |
| NJ | 241 | DOH health facilities CSV, filtered by type | Assisted Living Residence 193; Comprehensive Personal Care Home 35; Residential Health Care 13 | No capacity. "Assisted Living Program" (14, service agencies) and "Alternative Family Care" (4, sponsor offices) excluded. |
| NY | 555 | DOH adult care facility directory, Socrata | Adult Home 406; Enriched Housing Program 149 | No date in the data. |
| OR | 2,155 | ODHS licensed settings export: token, then a POST that returns CSV | Adult foster home 1,583; residential care 332; assisted living 240 (nursing facilities dropped) | **Adult foster home names are not carried**: they are mostly the licensee's personal name, and this repo is public. Address and license ID are kept. |
| PA | 992 | DHS licensed personal care homes, Socrata | Personal care homes only | **PA's separately licensed "assisted living residences" are not in this dataset.** |
| SC | 428 | DPH health facilities ArcGIS layer, filtered to community residential care | Community Residential Care Facility | Live layer. |
| TN | 370 | TDH facility listings: token, then a form POST returning an HTML table (a Chrome user agent is required) | Assisted care living 329; homes for the aged 38; adult care homes 3 | 362 licensed, 5 on probation, 3 lapsed; all kept, status carried in the row. |
| TX | 2,007 | HHSC assisted living directory spreadsheet | Assisted Living Type A 336; Type B 1,663; Type C 8 | File dated 2026-10-05. |
| UT | 224 | UGRC ArcGIS layer of licensed health care facilities, filtered to assisted living | Assisted Living Type I 48; Type II 176 | Live layer. "Small Health Care Facility" (all ICF/IID) and personal care agencies excluded. |
| VA | 575 | VDSS search page, whose HTML embeds the API JSON in a comment | Assisted Living Facility | Live. Falls back to the visible result cards if the comment goes away (checked identical). |
| WV | 83 | OHFLAC facility lookup: JSON POST with the full DataTables body | Large AL 54; Small AL 28; Residential Care Community 1 (active only) | 162 closed rows dropped. |

### Comparison with the 2021 Princeton data

For each covered state, how many of Princeton's 2021 addresses appear in the current list, and how
many current addresses Princeton lacked (exact match on normalized street + ZIP5):

| State | Princeton 2021 | Still listed | In current list, not in Princeton |
|---|---|---|---|
| AK | 681 | 63% | 366 |
| AZ | 2,086 | 77% | 450 |
| CA | 7,740 | 80% | 2,324 |
| CO | 691 | 79% | 111 |
| FL | 3,153 | 79% | 526 |
| GA | 1,629 | 83% | 454 |
| IA | 265 | 87% | 203 |
| IN | 364 | 52% | 39 |
| KY | 111 | 86% | 127 |
| LA | 158 | 85% | 24 |
| MD | 1,659 | 75% | 306 |
| MI | 4,419 | 75% | 981 |
| MN | 2,536 | 60% | 984 |
| MO | 631 | 85% | 51 |
| NC | 670 | 78% | 521 |
| NE | 287 | 75% | 62 |
| NJ | 257 | 84% | 20 |
| NY | 539 | 98% | 13 |
| OR | 485 | 88% | 1,639 |
| PA | 1,125 | 73% | 155 |
| SC | 468 | 78% | 51 |
| TN | 367 | 71% | 108 |
| TX | 1,895 | 77% | 410 |
| UT | 227 | 85% | 20 |
| VA | 564 | 81% | 117 |
| WI | 3,877 | 70% | 1,145 |
| WV | 94 | 76% | 11 |
| **All 27** | **36,978** | **76%** | **11,218** |

The two sources agree on most addresses, which supports both. Oregon's large "new" count is
adult foster homes, which Princeton largely did not include. Indiana (52%) and Minnesota (60%)
agree least: Indiana's list is residential care rather than assisted living, and Minnesota's
assisted living licensing was introduced around 2021 (not verified here), so its 2021 data may
predate the current licenses.

**What is left from 2021.** `assisted_living` has 60,641 rows; 48,027 are dated 2026 and 12,614
rest on the 2021 data alone (down from 38,040). Of those 12,614, **8,329 are in the 27 covered
states**: they are not on the state's current list, so they are probably closed or moved (the
largest are CA 1,453, WI 1,133, MI 1,089, MN 967, FL 619). They are still in the registry,
dated 2021, so a consumer can drop them. The other **4,285 are in the 20 jurisdictions (19 states and DC) with no automated
source** (largest: ME 953, OH 650, WA 456, IL 402, KS 249, AL 207).

## Implemented but needs attention

| State | Issue |
|---|---|
| NE | `gis.ne.gov/agencyext` returned `SITE_NOT_INITIALIZED` (HTTP 500) for every request on 2026-10-06, including the service directory. The module reads a same-schema copy owned by NE DHHS on ArcGIS Online (`services8.arcgis.com/sfauBl8MaKYMG7K4/.../Assisted_Living_Facility_Upload/FeatureServer/27`), falling back to the canonical service. The copy is a Rural Health Transformation Program map layer, not the canonical DHHS service, though its 277 rows match the earlier count. One license ID appears twice. |
| MD, AZ, LA, NE | Data is old: MD July 2025, AZ February 2025, LA March 2026, NE October 2025. Facilities licensed since are missing. |
| PA, IN | Not assisted living in the strict sense: PA is personal care homes, IN is residential care (the state has no assisted living license). |
| VA, GA, FL, OR, IA, TN, WV | Depend on page or form structure (embedded JSON comment, XML dump, anti-forgery tokens, a DataTables body). Each module raises a clear error if the structure changes, and the downloader keeps the previous file and records the reason in `state_lists_status.json` rather than failing the run. |
| MN, IA | The same building can appear under more than one license; dedupe by address downstream for one row per building. |
| All | Small group homes are included where a state licenses them with assisted living (Michigan foster care homes, Oregon and Wisconsin adult foster/family homes, North Carolina family care homes, Arizona adult foster care), as the 2021 Princeton data does. `beds` carries capacity (blank for GA, LA, NJ, VA, IN, WI) so a consumer can filter them. |
