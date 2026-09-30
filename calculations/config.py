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
# Note: the 2020 release only publishes last names broken out by race/Hispanic
# origin category (no single "all races combined" last-name-only file the way
# 2010 had). We sum across the race/ethnicity columns to reconstruct national
# counts; see LEARNINGS-style note in compute.py's surname loader.

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

# --- HUD USPS ZIP crosswalk (optional; requires HUD_TOKEN) ------------------
# https://www.huduser.gov/portal/datasets/usps_crosswalk.html — API documented at
# https://www.huduser.gov/portal/dataset/uspszip-api.html
HUD_CROSSWALK_API_URL = "https://www.huduser.gov/hudapi/public/usps"
# type=2 => ZIP-TRACT crosswalk (closest available to ZIP<->city allocation
# without a dedicated ZIP-to-city HUD product); see download.py for handling
# when HUD_TOKEN is unset (skip with an explicit message, no fabricated data).

# --- SSA baby names (fallback for first names if needed) --------------------
SSA_BABYNAMES_ZIP_URL = "https://www.ssa.gov/oact/babynames/names.zip"

# --- Conservative baseline u-values (from the patient-matching model) -------
CONSERVATIVE_U = {
    ("first_name", "exact"): 0.02,
    ("first_name", "fuzzy"): 0.03,
    ("last_name", "exact"): 0.005,
    ("last_name", "fuzzy"): 0.01,
    ("dob_full", "exact"): 0.0001,
    ("year_of_birth", "exact"): 0.015,
    ("zip5", "exact"): 0.0003,
    ("city", "exact"): 0.01,
    ("state", "exact"): 0.06,
    ("street_line_with_zip", "exact"): 0.00003,
    ("street_line_with_zip", "fuzzy"): 0.00006,
}

# --- Sanity-check ranges (compute.py prints warnings if outside these) ------
SANITY_RANGES = {
    "state": (0.03, 0.05),
    "year_of_birth": (0.012, 0.016),
    "last_name_exact": (0.0, 0.01),  # "well below 0.01"
}
