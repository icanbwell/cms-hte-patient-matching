"""Idempotent downloaders for all raw data sources used by compute.py.

Design:
- Every file download goes through `_download_file`, which streams to disk,
  shows a tqdm progress bar, retries with backoff, sends a browser-like
  User-Agent (census.gov's WAF 403s the default `python-requests` UA), and
  appends a cache-busting query parameter (`_dl=<epoch>`) — a prior WAF
  rejection response for a URL can get cached at the Cloudflare edge in front
  of www2.census.gov and re-served as a 200 with `text/html` content, which
  looks like success unless you check Content-Type / magic bytes.
- Every function is idempotent: if the destination file already exists and is
  non-empty, it is skipped (logged as such).
- Census API (ACS5 ZCTA-level) calls are paginated implicitly by the API
  itself (it returns all rows in one JSON response for these tables), and use
  CENSUS_API_KEY when set to avoid the unauthenticated rate limit.
- Nothing here fabricates a URL. Where a source cannot be resolved
  automatically (HUD crosswalk with no token), we print exact manual
  instructions and skip -- we do not fail the whole pipeline.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("download")


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": config.USER_AGENT})
    return s


class DownloadError(RuntimeError):
    """Raised when a source file could not be downloaded."""


def _require_within_data_raw(path: Path) -> Path:
    """Resolve `path` and reject anything that would escape `config.DATA_RAW`.

    All destinations here come from hardcoded filenames in this module and
    config.py, never from remote/user input, but this keeps that invariant
    enforced rather than assumed.
    """
    resolved = path.resolve()
    if config.DATA_RAW.resolve() not in resolved.parents and resolved != config.DATA_RAW.resolve():
        raise DownloadError(f"Refusing to write outside DATA_RAW: {resolved}")
    return resolved


def _download_file(url: str, dest: Path, session: requests.Session | None = None) -> None:
    """Stream `url` to `dest`. Skip if dest already exists and is non-empty.

    Raises DownloadError if the file cannot be downloaded.
    """
    if dest.exists() and dest.stat().st_size > 0:
        log.info("SKIP (exists, %d bytes): %s", dest.stat().st_size, dest.name)
        return

    dest = _require_within_data_raw(dest)
    sess = session or _session()
    cache_bust = f"{'&' if '?' in url else '?'}_dl={int(time.time())}"
    full_url = url + cache_bust
    try:
        with sess.get(full_url, stream=True, timeout=config.REQUEST_TIMEOUT) as resp:
            status = resp.status_code
            ctype = resp.headers.get("Content-Type", "")
            total = int(resp.headers.get("Content-Length", 0))
            log.info("GET %s -> %d, content-type=%s, length=%s", url, status, ctype, total)
            if status != 200:
                raise DownloadError(f"FAILED ({status}): {url}")
            if "text/html" in ctype:
                raise DownloadError(
                    f"FAILED: server returned HTML (likely a WAF block page) instead of "
                    f"the file, for {url}. Manual download may be required."
                )
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f, tqdm(
                total=total or None, unit="B", unit_scale=True, desc=dest.name
            ) as bar:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
            size = tmp.stat().st_size
            if size == 0:
                tmp.unlink(missing_ok=True)
                raise DownloadError(f"FAILED: zero-byte download for {url}")
            tmp.rename(dest)
            log.info("OK: %s (%d bytes)", dest.name, size)
    except requests.RequestException as exc:
        raise DownloadError(f"FAILED ({exc}): {url}") from exc


def download_surnames_2010() -> Path:
    """Download the 2010 Census surnames file; return the path it was written to."""
    dest = config.DATA_RAW / "names_2010census.zip"
    _download_file(config.SURNAMES_2010_ZIP_URL, dest)
    return dest


def download_firstnames_2020() -> Path:
    """Download the 2020 Census first-names-by-sex file; return its path."""
    dest = config.DATA_RAW / "Names2020_FirstNames_Sex.xlsx"
    _download_file(config.FIRSTNAMES_2020_SEX_XLSX_URL, dest)
    return dest


def download_lastnames_2020() -> Path:
    """Download the 2020 Census last-names-by-race/Hispanic-origin file; return its path."""
    dest = config.DATA_RAW / "Names2020_LastNames_RaceHispanic.xlsx"
    _download_file(config.LASTNAMES_2020_RACEHISPANIC_XLSX_URL, dest)
    return dest


def download_agesex() -> Path:
    """Download the national age/sex population estimates file; return its path."""
    dest = config.DATA_RAW / "nc-est2025-agesex-res.csv"
    _download_file(config.NC_EST2025_AGESEX_RES_URL, dest)
    return dest


def download_state_pop() -> Path:
    """Download the state population estimates file; return its path."""
    dest = config.DATA_RAW / "NST-EST2025-POP.xlsx"
    _download_file(config.NST_EST2025_POP_XLSX_URL, dest)
    return dest


def download_places() -> Path:
    """Download the sub-county/incorporated-places population estimates file; return its path."""
    dest = config.DATA_RAW / "sub-est2025.csv"
    _download_file(config.SUB_EST2025_CSV_URL, dest)
    return dest


def _census_api_get(variables: list[str], for_clause: str, dest: Path) -> Path:
    """Call the Census API for `variables`/`for_clause` and write the JSON response to `dest`.

    Raises DownloadError if every retry attempt fails.
    """
    if dest.exists() and dest.stat().st_size > 0:
        log.info("SKIP (exists, %d bytes): %s", dest.stat().st_size, dest.name)
        return dest
    dest = _require_within_data_raw(dest)
    params = {"get": ",".join(variables), "for": for_clause}
    if config.CENSUS_API_KEY:
        params["key"] = config.CENSUS_API_KEY
    else:
        log.warning(
            "CENSUS_API_KEY not set; calling api.census.gov unauthenticated. "
            "This is subject to a low rate limit and may be throttled for the "
            "large ZCTA-level queries (~33k+ rows)."
        )
    sess = _session()
    last_exc: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = sess.get(
                config.CENSUS_API_BASE, params=params, timeout=config.REQUEST_TIMEOUT * 2
            )
            log.info(
                "GET %s -> %d (attempt %d)", resp.url.split("&key=")[0], resp.status_code, attempt
            )
            resp.raise_for_status()
            data = resp.json()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(data))
            log.info("OK: %s (%d rows)", dest.name, len(data) - 1)
            return dest
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_exc = exc
            log.warning("Attempt %d failed (%s) fetching %s; retrying...", attempt, exc, dest.name)
            time.sleep(config.BACKOFF_FACTOR * attempt)
    raise DownloadError(
        f"FAILED ({last_exc}) fetching {dest.name} after {config.MAX_RETRIES} attempts"
    )


def download_zcta_population() -> Path:
    """Fetch ZCTA-level population counts (ACS5) via the Census API; return the JSON path."""
    return _census_api_get(
        config.ACS5_ZCTA_POPULATION_VARS,
        "zip code tabulation area:*",
        config.DATA_RAW / "acs5_zcta_population.json",
    )


def download_zcta_household_size() -> Path:
    """Fetch ZCTA-level household size counts (ACS5) via the Census API; return the JSON path."""
    return _census_api_get(
        config.ACS5_ZCTA_HOUSEHOLD_SIZE_VARS,
        "zip code tabulation area:*",
        config.DATA_RAW / "acs5_zcta_household_size.json",
    )


def download_zcta_housing_units() -> Path:
    """Fetch ZCTA-level housing unit counts (ACS5) via the Census API; return the JSON path."""
    return _census_api_get(
        config.ACS5_ZCTA_HOUSING_UNITS_VARS,
        "zip code tabulation area:*",
        config.DATA_RAW / "acs5_zcta_housing_units.json",
    )


def download_hud_crosswalk() -> Path | None:
    """Fetch the HUD USPS ZIP-tract crosswalk; return its path, or None if skipped/failed.

    Unlike the other download_* functions, failure here is non-fatal by design: it's an
    optional data source (requires HUD_TOKEN) used only as an alternate ZIP-to-city
    allocation, with a documented Census-only fallback in compute.py.
    """
    dest = config.DATA_RAW / "hud_usps_zip_crosswalk.json"
    if dest.exists() and dest.stat().st_size > 0:
        log.info("SKIP (exists, %d bytes): %s", dest.stat().st_size, dest.name)
        return dest
    if not config.HUD_TOKEN:
        print(
            "\n[MANUAL STEP REQUIRED] HUD_TOKEN is not set, so the HUD USPS "
            "ZIP crosswalk (used for an alternate ZIP-to-city allocation in "
            "the city u-probability calculation) is being skipped.\n"
            "To enable it:\n"
            "  1. Register for a free HUD USER account and generate an API "
            "token at https://www.huduser.gov/hudapi/public/register\n"
            "  2. Set HUD_TOKEN=<your token> in calculations/.env\n"
            "  3. Re-run `python run_all.py`\n"
            "Without this, compute.py computes city u-probabilities from "
            "Census incorporated-places/CDP data only (SUB-EST2025), and "
            "notes the mailing-city-vs-Census-place caveat in the output.\n"
        )
        return None
    dest = _require_within_data_raw(dest)
    sess = _session()
    headers = {"Authorization": f"Bearer {config.HUD_TOKEN}"}
    params = {"type": 2, "query": "All"}
    try:
        resp = sess.get(
            config.HUD_CROSSWALK_API_URL,
            headers=headers,
            params=params,
            timeout=config.REQUEST_TIMEOUT,
        )
        log.info("GET %s -> %d", resp.url, resp.status_code)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(resp.text)
        log.info("OK: %s", dest.name)
        return dest
    except requests.RequestException as exc:
        log.error(
            "FAILED (%s) fetching HUD crosswalk. Falling back to Census "
            "places-only city calculation.",
            exc,
        )
        return None


def download_all() -> None:
    """Download every required raw source into config.DATA_RAW, in sequence."""
    log.info("=== Downloading all sources into %s ===", config.DATA_RAW)
    download_surnames_2010()
    download_firstnames_2020()
    download_lastnames_2020()
    download_agesex()
    download_state_pop()
    download_places()
    download_zcta_population()
    download_zcta_household_size()
    download_zcta_housing_units()
    download_hud_crosswalk()
    log.info("=== Download pass complete ===")


if __name__ == "__main__":
    download_all()
