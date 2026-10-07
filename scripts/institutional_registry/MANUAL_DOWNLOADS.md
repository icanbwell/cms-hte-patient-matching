# Manual downloads

`download.py` fetches everything that can be fetched automatically: CMS Care Compare and
Provider of Services, IPEDS, BOP, HIFLD Prison Boundaries (via HIFLD Next), the Prison Policy
Initiative facility lists, the Princeton assisted-living dataset, and Overture Maps. The sources
below can't be, because they sit behind a login or are published per state as separate web pages.
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

Optional: `beds` (capacity). Extra columns are ignored. If the source file has different column
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
| State assisted-living licensing lists newer than 2021 | The Princeton file (auto-downloaded) is from 2021 | Each state health or aging department publishes its own list; the Princeton paper (`https://arxiv.org/abs/2212.14092`) lists the 2021 source per state. | `assisted_living` |
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
