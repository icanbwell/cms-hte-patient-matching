# Downloads: automatic and manual

## Downloaded automatically

`uv run python -m scripts.institutional_registry.download` writes these files to
`data/institutional_registry/`. You don't need to do anything for them. `--skip-overture` skips
the slow (~7 min) Overture extract.

The files are **committed to the repo** so the registry can be rebuilt without re-downloading.
`manifest.json` in the same folder records each file's exact source URL and download date (the
URLs below are the stable entry points; some, like the POS file and the HIFLD GeoParquet, are
resolved at download time and change between releases, so the manifest has the one actually
used). The POS file is stored gzipped (`pos_iqies.csv.gz`) because the raw 175 MB CSV exceeds
GitHub's 100 MB file limit. To refresh the data, re-run the download and commit the changes.

| File | Source (URL) | Becomes `institution_type` | Date used for `data_collected` |
|---|---|---|---|
| `care_compare_nh.csv` | CMS Care Compare nursing homes: `https://data.cms.gov/provider-data/dataset/4pq5-n9py` (CSV: `https://data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py/0/download?format=csv`) | `nursing_home` | Row's processing date |
| `care_compare_hospital.csv` | CMS Care Compare hospitals: `https://data.cms.gov/provider-data/dataset/xubh-q36u` | `hospital`, `psychiatric_hospital`, `long_term_hospital` (by Hospital Type) | Download date |
| `care_compare_hospice.csv` | CMS Care Compare hospices: `https://data.cms.gov/provider-data/dataset/yc9t-dgbk` | `hospice` | Download date |
| `pos_iqies.csv.gz` | CMS Provider of Services file, iQIES (nursing homes and hospices): catalog `https://data.cms.gov/data.json`, entry "Provider of Services File - Internet Quality Improvement and Evaluation System" (newest quarter); landing page `https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities` | `nursing_home`, `hospice` | Row's processing date, else download date |
| `ipeds_hd.csv` | NCES IPEDS institutional directory: `https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip` (newest year available) | `higher_education_campus` | Download date |
| `bop.json` | Federal Bureau of Prisons: facility codes from `https://www.bop.gov/locations/list.jsp`, then `https://www.bop.gov/PublicInfo/execute/phyloc?todo=query&output=json&code=<CODE>` | `federal_correctional` | Download date |
| `hifld_prisons.csv` | HIFLD Prison Boundaries via HIFLD Next: catalog `https://hifld.publicenvirodata.org/api/collections/hifld` -> "Prison Boundaries" -> GeoParquet on `storage.googleapis.com/hifld-next-portolan-published/...`; closed facilities are skipped | `correctional`, `federal_correctional` | Per-facility source date |
| `ppi_facilities.csv` | Prison Policy Initiative, state/federal/local facilities (2020 vintage, scraped): `https://www.prisonersofthecensus.org/data/state_federal_local_2020vintage.html` and `.../data/prisons2020/<ST>/` | `correctional`, `federal_correctional` | Row's survey date (2012-2013) |
| `assisted_living.csv` | Princeton open assisted-living dataset: `https://github.com/antonstengel/assisted-living-data` (file `assisted-living-facilities.csv`) | `assisted_living` | Row's "Date Accessed" (2021) |
| `state_al_ca.csv` | California CDSS Community Care Licensing facilities: `https://gis.data.chhs.ca.gov/api/download/v1/items/db31b0884a074cff9260facb3f2ade45/csv?layers=0`; only elder-care types 740/741 are used | `assisted_living` | Download date |
| `state_al_mi.txt` | Michigan LARA Adult Foster Care & Homes for the Aged: `https://documents.apps.lara.state.mi.us/bchs/afc_sw.txt` (no header row) | `assisted_living` | Download date |
| `state_al_wi.json` | Wisconsin DHS: `https://dhsgis.wi.gov/server/rest/services/DHS_GIS/Facilities/MapServer`, layers 7 (community-based residential facilities), 17 (residential care apartment complexes), 2 (adult family homes) | `assisted_living` | Download date |
| `state_al_fl.json` | Florida AHCA FloridaHealthFinder: `https://quality.healthfinder.fl.gov/Facility-Search/FacilityLocateSearch` (assisted living facilities, all counties; closed ones skipped) | `assisted_living` | Download date |
| `state_lists/<ST>.csv` (26 files: AK, AZ, CO, GA, IA, IN, KY, LA, MA, MD, MN, MO, NC, NE, NJ, NV, NY, OK, OR, PA, SC, TN, TX, UT, VA, WV) | Each state's licensing list, one module per state in `scripts/institutional_registry/states/` (spreadsheets, Socrata, ArcGIS, form posts, HTML). Exact source URL per state is in `manifest.json` and `docs/ASSISTED_LIVING_STATE_COVERAGE.md` | `assisted_living` | Download date |
| `overture_gq.csv` | Overture Maps places: `s3://overturemaps-us-west-2/release/<release>/theme=places/type=place/` (docs: `https://docs.overturemaps.org/guides/places/`) | `senior_living`, `assisted_living`, `homeless_shelter`, `correctional`, `halfway_house` | Overture release date |

Three files in the same folder are generated rather than downloaded: `manifest.json` and
`state_lists_status.json` (written by `download.py`; the latter records, per state, whether the
last run worked and why not if it didn't) and `institutional_addresses.csv` (written by `build_registry.py`, which reads the
files above plus anything in `manual/`). A missing automatic file is a warning, not an error, so
the build still runs if a download was skipped.

### Terms of use

Committing these files republishes them in a public repo. Status of each source's terms, as far
as I checked:

| Source | Terms |
|---|---|
| CMS (Care Compare, POS), NCES IPEDS, Federal Bureau of Prisons | US government public data |
| Princeton assisted-living dataset | CC BY 4.0: credit "Assisted Living in the United States: an Open Dataset" (A. Stengel, Princeton) |
| HIFLD Prison Boundaries (HIFLD Next archive) | The catalog lists the license as "other"; **not confirmed** |
| Prison Policy Initiative facility lists | No terms stated on the site; **not confirmed** |
| Overture Maps places | Varies by contributing source; **not checked** (see the Overture docs) |
| State licensing lists (CA, MI, WI, FL) | State government publications; terms **not checked** |

## Manual downloads

`download.py` fetches everything it can. The sources below can't be fetched automatically,
because they sit behind a login or are published per state as separate web pages.
Download them by hand and drop the files into:

```
data/institutional_registry/manual/
```

(`download.py` creates the folder; files you add there can be committed like the others). `build_registry.py` merges every `*.csv` in that
folder into `institutional_addresses.csv`, with `source` set to `manual:<filename>`.

## Required CSV format

One header row, then one row per facility. Required columns (exact names):

| column | example |
|---|---|
| `institution_type` | `correctional` |
| `name` | `Texas Department of Criminal Justice - Ellis Unit` |
| `street` | `1697 FM 980` |
| `city` | `Huntsville` |
| `state` | `TX` |
| `zip` | `77343` |

Optional: `beds` (capacity) and `data_collected` (the date the source says its data was gathered,
e.g. `2026-09-15`; if omitted, the file's download date is used). Extra columns are ignored. If the source file has different column
names (e.g. `ADDRESS`, `ZIPCODE`), rename them in a spreadsheet; the build script does not guess.

`institution_type` is free text. Use one of the existing types if one fits so the
`match_policy` column is set correctly: `correctional`, `federal_correctional`,
`assisted_living`, `homeless_shelter`, `halfway_house` (all `block_household_rules`), or
`senior_living` (`review`). Any other value is accepted and gets `review`.

## What to download

Status: these were found by searching, but **not** downloaded or checked for an address column.
Confirm the file has street addresses before relying on it.

| Source | Gap it fills | Where | Use `institution_type` |
|---|---|---|---|
| BJS **Census of State and Federal Adult Correctional Facilities** (2019) | State/federal prisons; useful to cross-check HIFLD | ICPSR study 38325 (`https://www.icpsr.umich.edu/web/NACJD/studies/38325`); anonymous download returned HTTP 403 so it needs an ICPSR login. Unconfirmed whether the public file includes street addresses. | `correctional` |
| BJS **Census of Jails** (2019) | Local jails | ICPSR study 38323 (`https://www.icpsr.umich.edu/web/NACJD/studies/38323`); same login requirement and same address question. | `correctional` |
| ICE detention facilities (Deportation Data Project, CC0) | Immigration detention | `https://deportationdata.org/news/2026-04-22-facilities-release.html`. Unconfirmed whether street addresses are included. | `correctional` |
| State assisted-living licensing lists for the states not automated (optional) | Refreshes the 2021 Princeton data, which is still the only source for those states (4,285 rows). 30 states are **already automated**, as is the Princeton dataset itself. `docs/ASSISTED_LIVING_STATE_COVERAGE.md` lists the 20 jurisdictions that aren't, with the specific reason for each (PDF-only, no ZIP in the list view, a stale snapshot, a blocked host, ...) and what a fix would take. Largest: ME, OH, WA, IL, KS, AL. Idaho's list is behind a reCAPTCHA (an export would have to be requested from the state). | No national file: each state health or aging department publishes its own list in its own format. The Princeton paper (`https://arxiv.org/abs/2212.14092`) describes the 2021 sources. Add a `data_collected` column (see above) so the build dates them correctly. | `assisted_living` |
| State Department of Corrections facility rosters | Cross-check and fill HIFLD gaps | Each state DOC website (fragmented; no national file). | `correctional` |

No usable open source was found for **college dormitories** (IPEDS gives campus addresses only,
and the IPEDS IC file has no housing capacity) or for **address-level homeless shelters** beyond
what Overture lists (HUD's Housing Inventory Count is reported per program, not per address).

## After adding files

```bash
uv run python -m scripts.institutional_registry.build_registry
```

The build prints a `note:` line if the folder is empty and fails with the missing column names
if a file doesn't match the format above.
