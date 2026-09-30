"""Configuration: paths, resolved source URLs, and API keys.

All URLs below were resolved by hand on 2026-09-29 by starting from the landing
pages listed in the project spec and following the actual download links found
there (verified with `curl -I`/`curl -o` — not guessed). See the comment above
each URL for how it was found. If census.gov reorganizes these pages, re-derive
the URLs the same way (visit the landing page, find the link to the current
vintage file, verify it downloads with a non-HTML content-type).

Note: www2.census.gov is fronted by Cloudflare, and a prior "Request Rejected"
WAF response for a URL can get cached at the edge (`cache-control: public,
max-age=14400` from the origin is honored by Cloudflare even for the reject
page). `download.py` appends a cache-busting query parameter to every request
to avoid being served a stale cached rejection.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Load calculations/.env if present (CENSUS_API_KEY, HUD_TOKEN) ---------
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    # Minimal manual fallback if python-dotenv isn't installed.
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

# --- Paths -------------------------------------------------------------
ROOT = Path(__file__).parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

for _d in (DATA_RAW, DATA_PROCESSED, OUTPUTS):
    _d.mkdir(parents=True, exist_ok=True)

# --- Credentials (optional) ---------------------------------------------
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "").strip()
HUD_TOKEN = os.environ.get("HUD_TOKEN", "").strip()

# --- HTTP settings --------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT = 60
MAX_RETRIES = 5
BACKOFF_FACTOR = 1.5

# --- Surnames --------------------------------------------------------------
# Landing page: https://www.census.gov/topics/population/genealogy/data/2010_surnames.html
# The page's "File B - Complete Surnames (Zip with Excel/CSV)" link resolves to:
SURNAMES_2010_ZIP_URL = "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
# Contains Names_2010Census.csv: name,rank,count,prop100k,cum_prop100k,pct<race>...

# Landing page: https://www.census.gov/topics/population/genealogy/data.html links to
# https://www.census.gov/topics/population/genealogy/data/2020_names.html, which lists
# the 2020 Census names files. We use the complete (non-top-1000) files:
FIRSTNAMES_2020_SEX_XLSX_URL = (
    "https://www2.census.gov/topics/genealogy/2020surnames/Names2020_FirstNames_Sex.xlsx"
)
LASTNAMES_2020_RACEHISPANIC_XLSX_URL = (
    "https://www2.census.gov/topics/genealogy/2020surnames/Names2020_LastNames_RaceHispanic.xlsx"
)
# Note: this file also breaks last names out by race/Hispanic origin category,
# but it publishes a "FREQUENCY (COUNT)" column that is already the national
# total across all categories (verified: it equals the sum of the per-category
# columns) -- compute.py's load_lastnames_2020() uses that column directly, no
# re-summation needed.

# --- National single-year-of-age by sex ------------------------------------
# Landing page: https://www.census.gov/data/datasets/time-series/demo/popest/2020s-national-detail.html
# links directly to the dataset file:
NC_EST2025_AGESEX_RES_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/national/"
    "asrh/nc-est2025-agesex-res.csv"
)

# --- State totals ------------------------------------------------------
# Landing page: https://www.census.gov/data/tables/time-series/demo/popest/2020s-state-total.html
NST_EST2025_POP_XLSX_URL = (
    "https://www2.census.gov/programs-surveys/popest/tables/2020-2025/state/totals/"
    "NST-EST2025-POP.xlsx"
)

# --- Places (incorporated places + CDPs) -----------------------------------
# Landing page: https://www.census.gov/programs-surveys/popest/technical-documentation/file-layouts.html
# points at the FTP2 datasets tree; the national combined file lives at:
SUB_EST2025_CSV_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/cities/"
    "totals/sub-est2025.csv"
)

# --- Census API (ACS 5-year, ZCTA level) ------------------------------------
# Latest vintage confirmed to respond (as of 2026-09-29): 2024 5-year ACS
# (2020-2024 period estimates). 2025 5-year ACS is not yet published.
ACS5_YEAR = 2024
CENSUS_API_BASE = f"https://api.census.gov/data/{ACS5_YEAR}/acs/acs5"

# get=NAME,B01003_001E&for=zip%20code%20tabulation%20area:*
ACS5_ZCTA_POPULATION_VARS = ["NAME", "B01003_001E"]
# Household size distribution (family + nonfamily households by size)
ACS5_ZCTA_HOUSEHOLD_SIZE_VARS = [
    "NAME",
    "B11016_002E",  # family households, total
    "B11016_003E",  # family, 2-person
    "B11016_004E",  # family, 3-person
    "B11016_005E",  # family, 4-person
    "B11016_006E",  # family, 5-person
    "B11016_007E",  # family, 6-person
    "B11016_008E",  # family, 7-or-more-person
    "B11016_009E",  # nonfamily households, total
    "B11016_010E",  # nonfamily, 1-person
    "B11016_011E",  # nonfamily, 2-person
    "B11016_012E",  # nonfamily, 3-person
    "B11016_013E",  # nonfamily, 4-person
    "B11016_014E",  # nonfamily, 5-person
    "B11016_015E",  # nonfamily, 6-person
    "B11016_016E",  # nonfamily, 7-or-more-person
    "B25010_001E",  # average household size (occupied housing units)
]
ACS5_ZCTA_HOUSING_UNITS_VARS = ["NAME", "B25001_001E"]

# --- SSN/ITIN randomization policy (closed-form, no data file needed) -------
# SSA switched to full randomization of all 9 SSN digits on 2011-06-25 ("SSN
# Randomization"): https://www.ssa.gov/employer/randomization.html. Before
# that date, the last 4 digits ("serial number") were assigned sequentially
# (0001, 0002, ...) within each area/group block, not drawn at random -- see
# docs/LEARNINGS.md for why this means SSN_ITIN_LAST4_VALID_VALUES is only a
# valid uniform-distribution model for SSNs issued *after* that date.
SSN_RANDOMIZATION_START_DATE = "2011-06-25"
SSN_ITIN_LAST4_VALID_VALUES = 9999  # 0001-9999; 0000 is never issued.

# --- HUD USPS ZIP crosswalk (optional; requires HUD_TOKEN) ------------------
# https://www.huduser.gov/portal/datasets/usps_crosswalk.html — API documented at
# https://www.huduser.gov/portal/dataset/uspszip-api.html
HUD_CROSSWALK_API_URL = "https://www.huduser.gov/hudapi/public/usps"
# type=2 => ZIP-TRACT crosswalk (closest available to ZIP<->city allocation
# without a dedicated ZIP-to-city HUD product); see download.py for handling
# when HUD_TOKEN is unset (skip with an explicit message, no fabricated data).

# --- CMS Medicare total enrollment (namespace-size proxy for MBI) -----------
# Found via https://data.cms.gov/data.json (the CMS open-data catalog): the
# "CMS Program Statistics - Medicare Total Enrollment : 2024-01-01" dataset
# entry's distribution[0].downloadURL. This dataset has no data-api/v1 access
# (confirmed by calling .../data and getting "does not contain any
# interactive versions"); the catalog-listed ZIP is the only way to get it.
# Table "MDCR ENROLL AB 1" inside gives total enrollment (person-year count)
# by calendar year; we use the 2024 row, the latest available at the time of
# writing (see compute.py's mbi_u for exactly which cell).
MDCR_ENROLLMENT_ZIP_URL = (
    "https://data.cms.gov/sites/default/files/2026-09/"
    "0a06b80d-bccb-4634-b062-7e53acdae289/"
    "MDCR%20ENROLL%20AB%201-8_CPS_02ENR_2024.zip"
)
MDCR_ENROLLMENT_XLSX_NAME = "MDCR ENROLL AB 1-8_CPS_02ENR_2024.xlsx"
MDCR_ENROLLMENT_YEAR = 2024

# --- Conservative baseline u-values (from the patient-matching model) -------
CONSERVATIVE_U = {
    ("first_name", "exact"): 0.02,
    ("first_name", "fuzzy"): 0.03,
    ("middle_name", "exact"): 0.01,
    ("last_name", "exact"): 0.005,
    ("last_name", "fuzzy"): 0.01,
    ("dob_full", "exact"): 0.0001,
    ("year_of_birth", "exact"): 0.015,
    ("zip5", "exact"): 0.0003,
    ("city", "exact"): 0.01,
    ("state", "exact"): 0.06,
    ("street_line_with_zip", "exact"): 0.00003,
    ("street_line_with_zip", "fuzzy"): 0.00006,
    ("ssn_last4", "exact"): 0.0001,
    ("itin_last4", "exact"): 0.0001,
    ("mbi", "exact"): 0.000001,
}

# --- Sanity-check ranges (compute.py prints warnings if outside these) ------
# year_of_birth is calibrated against the all-ages (0-100) headline, not the
# adults-18+ reference figure (see compute.year_of_birth_u). An earlier,
# un-derived guess here (0.012-0.016) was apparently calibrated against an
# adults-only population instead and false-flagged the correct all-ages
# number (~0.0118) as out of range -- see docs/LEARNINGS.md. This range is
# bounded below by the fully-uniform-distribution floor for the 101
# single-year-of-age buckets AGE 0-100 (1/101 = 0.0099, i.e. "no concentration
# at all" -- a real population pyramid should always clear this) and above by
# the adults-only figure (~0.0149, i.e. "as concentrated as if no one under 18
# existed" -- the true all-ages number should stay below that).
SANITY_RANGES = {
    "state": (0.03, 0.05),
    "year_of_birth": (0.0100, 0.0149),
    "last_name_exact": (0.0, 0.01),  # "well below 0.01"
}
