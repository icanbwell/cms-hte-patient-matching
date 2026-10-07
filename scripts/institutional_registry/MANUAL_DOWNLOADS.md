# Downloads: automatic and manual

## Downloaded automatically

`uv run python -m scripts.institutional_registry.download` writes these files to
`data/institutional_registry/` (gitignored). You don't need to do anything for them.
`--skip-overture` skips the slow (~7 min) Overture extract.

| File | Source | Becomes `institution_type` | Date used for `data_collected` |
|---|---|---|---|
| `care_compare_nh.csv` | CMS Care Compare nursing homes | `nursing_home` | Row's processing date |
| `care_compare_hospital.csv` | CMS Care Compare hospitals | `hospital`, `psychiatric_hospital`, `long_term_hospital` (by Hospital Type) | Download date |
| `care_compare_hospice.csv` | CMS Care Compare hospices | `hospice` | Download date |
| `pos_iqies.csv` | CMS Provider of Services file (iQIES; nursing homes and hospices) | `nursing_home`, `hospice` | Row's processing date, else download date |
| `ipeds_hd.csv` | NCES IPEDS campus directory | `higher_education_campus` | Download date |
| `bop.json` | Federal Bureau of Prisons facility API | `federal_correctional` | Download date |
| `hifld_prisons.csv` | HIFLD Prison Boundaries (via HIFLD Next); closed facilities are skipped | `correctional`, `federal_correctional` | Per-facility source date |
| `ppi_facilities.csv` | Prison Policy Initiative facility lists (scraped; many rows have no address) | `correctional`, `federal_correctional` | Row's survey date (2012-2013) |
| `assisted_living.csv` | Princeton open assisted-living dataset (GitHub) | `assisted_living` | Row's "Date Accessed" (2021) |
| `state_al_ca.csv` | California CDSS Community Care Licensing facilities; only elder-care types 740/741 are used | `assisted_living` | Download date |
| `state_al_mi.txt` | Michigan LARA Adult Foster Care & Homes for the Aged list (no header row) | `assisted_living` | Download date |
| `state_al_wi.json` | Wisconsin DHS: community-based residential facilities, residential care apartment complexes, adult family homes | `assisted_living` | Download date |
| `state_al_fl.json` | Florida AHCA assisted living facilities (closed ones skipped) | `assisted_living` | Download date |
| `overture_gq.csv` | Overture Maps places | `senior_living`, `assisted_living`, `homeless_shelter`, `correctional`, `halfway_house` | Overture release date |

`build_registry.py` reads these (plus anything in `manual/`) and writes
`institutional_addresses.csv`. A missing automatic file is a warning, not an error, so the build
still runs if a download was skipped.

## Manual downloads

`download.py` fetches everything it can. The sources below can't be fetched automatically,
because they sit behind a login or are published per state as separate web pages.
Download them by hand and drop the files into:

```
data/institutional_registry/manual/
```

(gitignored; `download.py` creates the folder). `build_registry.py` merges every `*.csv` in that
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
| State assisted-living licensing lists for states other than CA, MI, WI and FL (optional) | Refreshes the 2021 Princeton data, which is still the only source for those states (24,374 rows). CA, MI, WI and FL are **already automated**, as is the Princeton dataset itself. Minnesota (2,350 stale rows) has a search-only database and PDF directories with no structured download. Next largest stale states: AZ, TX, MD, GA. | No national file: each state health or aging department publishes its own list in its own format. The Princeton paper (`https://arxiv.org/abs/2212.14092`) describes the 2021 sources. Add a `data_collected` column (see above) so the build dates them correctly. | `assisted_living` |
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
