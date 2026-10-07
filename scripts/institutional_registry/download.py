"""Download every public source of institutional (group-quarters) addresses.

Sources (Proposal v3.3.6, Appendix A -- only the ones retrievable without an account):
- CMS Care Compare: nursing homes, hospitals, hospices (Provider Data Catalog API)
- CMS Provider of Services (POS) iQIES file (data.cms.gov catalog -> CSV)
- NCES IPEDS HD directory (campus addresses)
- Federal Bureau of Prisons facility API (per-facility JSON, found via bop.gov's list page)
- HIFLD Prison Boundaries via HIFLD Next (federal, state, county and local detention)
- Prison Policy Initiative state/federal/local facility lists (scraped; 2020 vintage; excluded by default)
- Princeton open dataset of state-licensed assisted living facilities (GitHub, 2021 data)
- Current state assisted living lists: California, Wisconsin, Florida (Michigan excluded by default)
- Overture Maps places: senior/assisted living, shelters, jails and prisons, halfway houses
Not downloadable automatically (state DOC rosters, BJS censuses, ...): download by hand into
`data/institutional_registry/manual/` -- see MANUAL_DOWNLOADS.md. CASS validation is a paid
service. Details in docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md.

Files land in `data/institutional_registry/` and are committed (the POS file gzipped to fit
GitHub's file-size limit). `manifest.json` records each file's source URL and download date.
All data is public; no PHI.

Usage:
    uv run python -m scripts.institutional_registry.download
"""

from __future__ import annotations

import argparse
import csv
import gzip
import http.cookiejar
import io
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.institutional_registry.states.common import ROW_FIELDS, Session

DEST = Path("data/institutional_registry")
CMS_CATALOG = "https://data.cms.gov/data.json"
PDC_DOWNLOAD = "https://data.cms.gov/provider-data/api/1/datastore/query/{id}/0/download?format=csv"
CARE_COMPARE = {
    "care_compare_nh": "4pq5-n9py",
    "care_compare_hospital": "xubh-q36u",
    "care_compare_hospice": "yc9t-dgbk",
}
CA_CCL_URL = (
    "https://gis.data.chhs.ca.gov/api/download/v1/items/"
    "db31b0884a074cff9260facb3f2ade45/csv?layers=0"
)
MI_AFC_URL = "https://documents.apps.lara.state.mi.us/bchs/afc_sw.txt"
WI_SERVICE = "https://dhsgis.wi.gov/server/rest/services/DHS_GIS/Facilities/MapServer"
WI_LAYERS = {
    7: "Community-Based Residential Facility",
    17: "Residential Care Apartment Complex",
    2: "Adult Family Home",
}
FL_SEARCH_URL = (
    "https://quality.healthfinder.fl.gov/Facility-Search/FacilityLocateSearch"
)
PPI_BASE = "https://www.prisonersofthecensus.org/data/"
HIFLD_COLLECTION = "https://hifld.publicenvirodata.org/api/collections/hifld"
BOP_LIST = "https://www.bop.gov/locations/list.jsp"
BOP_API = (
    "https://www.bop.gov/PublicInfo/execute/phyloc?todo=query&output=json&code={code}"
)
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"
ALF_URL = "https://raw.githubusercontent.com/antonstengel/assisted-living-data/main/assisted-living-facilities.csv"
OVERTURE_LIST = "https://overturemaps-us-west-2.s3.amazonaws.com/?list-type=2&prefix=release/&delimiter=/"
OVERTURE_CATEGORIES = [
    "retirement_home",
    "assisted_living_facility",
    "homeless_shelter",
    "jail_or_prison",
    "halfway_house",
]
# Sources that can't be fetched anonymously are downloaded by hand into this folder; see
# MANUAL_DOWNLOADS.md next to this file for what to put there and the required columns.
MANUAL_DIR = DEST / "manual"
MANIFEST = DEST / "manifest.json"
STATE_LISTS_DIR = DEST / "state_lists"
# Sources excluded from the committed data because their terms do not allow redistribution or
# could not be confirmed (see docs/DATA_SOURCE_LICENSES.md). --include-excluded fetches them
# for local use only; do not commit the results.
EXCLUDED_STATES = {"AK", "IN", "KY", "MI", "VA"}
USER_AGENT = "Mozilla/5.0 (cms-hte-patient-matching institutional registry)"


def _curl(url: str, out: Optional[Path] = None, *, timeout: int = 300) -> bytes:
    """GET `url` with curl (as scripts/fetch_onc_test_data.py does); write to `out` if given."""
    cmd = [
        "curl",
        "-sSL",
        "--fail",
        "--retry",
        "3",
        "-m",
        str(timeout),
        "-A",
        USER_AGENT,
        url,
    ]
    body = subprocess.run(cmd, check=True, capture_output=True).stdout
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
    return body


def _record(name: str, source: str) -> None:
    """Note where `name` came from and when, in `manifest.json` next to the files.

    The date matters because these files are committed: after a `git clone` every file's
    modification time is the clone date, so build_registry.py reads the download date from
    here instead.
    """
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    manifest[name] = {"source": source, "downloaded": date.today().isoformat()}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _save(url: str, name: str, *, timeout: int = 300) -> None:
    """Download `url` to DEST/name and record it in the manifest."""
    _curl(url, DEST / name, timeout=timeout)
    _record(name, url)


def latest_pos_csv_url() -> str:
    """Resolve the newest POS iQIES CSV from the catalog (never hardcode: URLs change quarterly)."""
    catalog = json.loads(_curl(CMS_CATALOG, timeout=120))
    entries = [
        d
        for d in catalog["dataset"]
        if d["title"].startswith("Provider of Services File - Internet Quality")
    ]
    newest = max(entries, key=lambda d: d["title"].rsplit(" : ", 1)[-1])
    for dist in newest["distribution"]:
        if dist.get("mediaType") == "text/csv":
            return str(dist["downloadURL"])
    raise RuntimeError(f"no CSV distribution on {newest['title']}")


def fetch_pos() -> None:
    """CMS Provider of Services (iQIES), stored gzipped.

    The raw CSV is 175 MB, over GitHub's 100 MB per-file limit, and these files are
    committed; gzip is lossless and brings it to a committable size.
    """
    url = latest_pos_csv_url()
    (DEST / "pos_iqies.csv.gz").write_bytes(
        gzip.compress(_curl(url, timeout=600), compresslevel=9)
    )
    _record("pos_iqies.csv.gz", url)
    print("pos_iqies: ok")


def fetch_ipeds() -> None:
    """Newest IPEDS HD file; the current year 404s until NCES publishes it."""
    for year in range(time.localtime().tm_year, time.localtime().tm_year - 4, -1):
        try:
            body = _curl(IPEDS_URL.format(year=year), timeout=120)
        except subprocess.CalledProcessError:
            continue
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            (DEST / "ipeds_hd.csv").write_bytes(zf.read(name))
        _record("ipeds_hd.csv", IPEDS_URL.format(year=year))
        print(f"ipeds: HD{year}")
        return
    raise RuntimeError("no IPEDS HD file found for the last 4 years")


def fetch_bop() -> None:
    """BOP has no bulk export; scrape facility codes from the list page, then hit its JSON API."""
    page = _curl(BOP_LIST, timeout=60).decode("utf-8", "replace")
    codes = sorted(set(re.findall(r"/locations/institutions/([a-z0-9]+)/", page)))
    rows: List[Dict[str, Any]] = []
    for code in codes:
        data = json.loads(_curl(BOP_API.format(code=code.upper()), timeout=30))
        # Type 1 is the physical address; type 3 is the inmate mail/parcels address, usually
        # a PO box, which is what a resident's own records are likely to carry.
        rows.extend(
            a for a in data.get("Addresses") or [] if a.get("addressType") in ("1", "3")
        )
        time.sleep(0.2)
    (DEST / "bop.json").write_text(json.dumps(rows))
    _record("bop.json", f"{BOP_LIST} (facility codes) -> {BOP_API}")
    print(
        f"bop: {len(codes)} codes on list page -> {len(rows)} addresses "
        "(physical and inmate mail)"
    )


def fetch_assisted_living() -> None:
    """Princeton open dataset of state-licensed assisted living facilities (CC BY 4.0, 2021)."""
    _save(ALF_URL, "assisted_living.csv", timeout=120)
    print("assisted_living: ok (state licensing data accessed 2021 -- stale)")


def hifld_parquet_url(title: str) -> str:
    """Resolve a HIFLD Next collection's GeoParquet URL by title.

    HIFLD Open (DHS) shut down 2025-08-26; HIFLD Next republishes the archived layers as a
    STAC-style catalog. The release ID in every URL changes, so walk the catalog from its
    stable entry point: collections -> child catalog -> latest-version collection -> asset.
    """
    root = json.loads(_curl(HIFLD_COLLECTION, timeout=60))
    child = next(
        link["href"]
        for link in root["links"]
        if link["rel"] == "child" and link.get("title") == title
    )
    nested = json.loads(_curl(child, timeout=60))
    versions = [link["href"] for link in nested["links"] if link["rel"] == "child"]
    catalog = json.loads(_curl(versions[0], timeout=60))
    latest = next(
        link["href"] for link in catalog["links"] if link["rel"] == "latest-version"
    )
    collection = json.loads(_curl(latest, timeout=60))
    for asset in collection["assets"].values():
        if asset["type"] == "application/vnd.apache.parquet":
            return str(asset["href"])
    raise RuntimeError(f"no GeoParquet asset for HIFLD collection {title!r}")


def fetch_hifld_prisons() -> None:
    """HIFLD Prison Boundaries: federal, state, county and local detention facilities."""
    import duckdb  # project dependency; imported lazily so the other downloads don't need it

    url = hifld_parquet_url("Prison Boundaries")
    con = duckdb.connect()
    con.execute("install httpfs; load httpfs")
    # `url` comes from a remote catalog, so it is bound as a parameter, not interpolated. The
    # COPY target can't be a parameter in DuckDB; it is a program constant.
    con.execute(
        f"copy (select FACILITYID, NAME, ADDRESS, CITY, STATE, ZIP, TYPE, STATUS, CAPACITY, "  # nosec B608
        "SOURCEDATE from read_parquet(?)) "
        f"to '{DEST / 'hifld_prisons.csv'}' (format csv, header)",
        [url],
    )
    _record("hifld_prisons.csv", url)
    print("hifld_prisons: ok")


class _TableParser(HTMLParser):
    """Collect every <tr> of a page as a list of cell strings."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: List[List[str]] = []
        self._row: Optional[List[str]] = None
        self._cell = ""
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell, self._cell = True, ""

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None:
            self._row.append(" ".join(self._cell.split()))
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell += data


def fetch_ppi_facilities() -> None:
    """Prison Policy Initiative state/federal/local facility lists (2020 vintage).

    One HTML table per state. Many local jails have no street address and the survey
    dates are 2012-2013, so this is a supplement to HIFLD, not a replacement. Terms of
    use are not stated on the site; check before redistributing.
    """
    index = _curl(PPI_BASE + "state_federal_local_2020vintage.html", timeout=60).decode(
        "utf-8", "replace"
    )
    states = sorted(set(re.findall(r'href="prisons2020/([A-Z]{2})/"', index)))
    rows: List[List[str]] = []
    for state in states:
        parser = _TableParser()
        parser.feed(
            _curl(f"{PPI_BASE}prisons2020/{state}/", timeout=60).decode(
                "utf-8", "replace"
            )
        )
        header, *body = parser.rows
        rows += [[state, *r] for r in body if len(r) == len(header)]
        time.sleep(0.3)
    with (DEST / "ppi_facilities.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "state",
                "name",
                "prisoners",
                "type",
                "address",
                "city",
                "zip",
                "county",
                "survey_date",
            ]
        )
        writer.writerows(rows)
    _record(
        "ppi_facilities.csv",
        f"{PPI_BASE}state_federal_local_2020vintage.html (one page per state: {PPI_BASE}prisons2020/<ST>/)",
    )
    print(f"ppi_facilities: {len(states)} states, {len(rows)} facilities")


def fetch_ca_assisted_living() -> None:
    """California CDSS Community Care Licensing facilities (all license types, ~10 MB).

    The elder-care rows (TYPE 740/741, Residential Care for the Elderly) are picked out in
    build_registry.py. The CSV comes from the CHHS ArcGIS hub item named in CA_CCL_URL.
    """
    _save(CA_CCL_URL, "state_al_ca.csv", timeout=180)
    print("state_al_ca: ok")


def fetch_mi_assisted_living() -> None:
    """Michigan LARA statewide Adult Foster Care & Homes for the Aged list.

    Comma-delimited with no header row; the record layout is documented at
    michigan.gov/lara/.../adult-foster-care-record-description and parsed in build_registry.py.
    """
    _save(MI_AFC_URL, "state_al_mi.txt", timeout=120)
    print("state_al_mi: ok")


def fetch_wi_assisted_living() -> None:
    """Wisconsin DHS public ArcGIS service: CBRF, RCAC and Adult Family Home layers.

    The DHS open-data portal's own CSV download returns 403, but the underlying map service
    answers queries anonymously (2,000 records per page).
    """
    rows: List[Dict[str, Any]] = []
    for layer, label in WI_LAYERS.items():
        offset = 0
        while True:
            query = (
                f"{WI_SERVICE}/{layer}/query?where=1%3D1&outFields=*&returnGeometry=false"
                f"&resultOffset={offset}&resultRecordCount=2000&f=json"
            )
            page = json.loads(_curl(query, timeout=60))
            features = [f["attributes"] for f in page.get("features", [])]
            rows += [{**f, "layer": label} for f in features]
            if len(features) < 2000:
                break
            offset += 2000
    (DEST / "state_al_wi.json").write_text(json.dumps(rows))
    layers = ",".join(str(layer) for layer in WI_LAYERS)
    _record("state_al_wi.json", f"{WI_SERVICE}/<layer {layers}>/query")
    print(f"state_al_wi: {len(rows)} facilities")


def fetch_fl_assisted_living() -> None:
    """Florida AHCA FloridaHealthFinder: all licensed assisted living facilities.

    The site has no bulk file; its facility search embeds the matching records as JSON in
    the results page. Searching "all counties" returns the whole state in one POST, but the
    form needs a session cookie and an anti-forgery token from a prior GET.
    """
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    opener.addheaders = [("User-Agent", USER_AGENT)]
    page = opener.open(FL_SEARCH_URL, timeout=60).read().decode("utf-8", "replace")
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page)
    if token is None:
        raise RuntimeError("Florida search page changed: no anti-forgery token found")
    form = {
        "__RequestVerificationToken": token.group(1),
        "FacilityTypeSelection": "ALF",
        "countySelection": "",  # all counties
        "LicenseStatus": "",
        "OpenClosed_LicenseStatus": "",
        "facilityName": "",
        "city": "",
        "address": "",
    }
    request = urllib.request.Request(
        FL_SEARCH_URL + "?handler=AdvancedSearch",
        urllib.parse.urlencode(form).encode(),
        method="POST",
    )
    body = opener.open(request, timeout=120).read().decode("utf-8", "replace")
    marker = body.find('"FileNumber"')
    if marker < 0:
        raise RuntimeError("Florida results page changed: no embedded facility records")
    records, _ = json.JSONDecoder().raw_decode(body[body.rfind("[{", 0, marker) :])
    (DEST / "state_al_fl.json").write_text(json.dumps(records))
    _record(
        "state_al_fl.json", f"{FL_SEARCH_URL} (POST, facility type ALF, all counties)"
    )
    print(f"state_al_fl: {len(records)} facilities")


def fetch_state_assisted_living(*, include_excluded: bool = False) -> None:
    """Current state licensing lists for the states that publish them (CA, WI, FL; MI is excluded)."""
    fetch_ca_assisted_living()
    if include_excluded:
        fetch_mi_assisted_living()
    else:
        print("state_al_mi: excluded, skipped")
    fetch_wi_assisted_living()
    fetch_fl_assisted_living()


def fetch_state_lists(*, include_excluded: bool = False) -> None:
    """Run every module in `states/` and save its rows to state_lists/<ST>.csv.

    One state failing must not stop the others, so each is isolated. A state that is marked
    BROKEN, raises, or returns nothing keeps whatever file an earlier run left (stale rather
    than missing) and is recorded in state_lists_status.json with the reason; that file is
    the source for docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md's broken-states table.
    """
    from scripts.institutional_registry.states import state_modules

    STATE_LISTS_DIR.mkdir(parents=True, exist_ok=True)
    session = Session()
    status: Dict[str, Dict[str, Any]] = {}
    for module in state_modules():
        code = module.STATE
        if code in EXCLUDED_STATES and not include_excluded:
            print(f"state_lists {code}: excluded, skipped")
            continue
        broken = getattr(module, "BROKEN", None)
        if broken:
            status[code] = {"ok": False, "reason": f"marked broken: {broken}"}
        else:
            try:
                rows = module.fetch(session)
            except Exception as err:  # noqa: BLE001 - isolate per-state failures
                status[code] = {"ok": False, "reason": f"{type(err).__name__}: {err}"}
            else:
                if not rows:
                    status[code] = {"ok": False, "reason": "returned no rows"}
                else:
                    with (STATE_LISTS_DIR / f"{code}.csv").open(
                        "w", newline="", encoding="utf-8"
                    ) as f:
                        writer = csv.DictWriter(
                            f, fieldnames=ROW_FIELDS, lineterminator="\n"
                        )
                        writer.writeheader()
                        writer.writerows(rows)
                    _record(f"state_lists/{code}.csv", module.SOURCE)
                    status[code] = {"ok": True, "rows": len(rows)}
        status[code]["checked"] = date.today().isoformat()
        print(f"state_lists {code}: {status[code]}")
    (DEST / "state_lists_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n"
    )
    failed = sorted(c for c, s in status.items() if not s["ok"])
    if failed:
        print(f"state_lists: {len(failed)} state(s) not updated: {', '.join(failed)}")


def latest_overture_release() -> str:
    """Newest Overture release folder name, from the public bucket listing."""
    listing = _curl(OVERTURE_LIST, timeout=60).decode("utf-8", "replace")
    return str(max(re.findall(r"release/([0-9][0-9.-]*)/", listing)))


def fetch_overture() -> None:
    """Extract US group-quarters places from Overture Maps (scans ~GBs on S3; ~7 minutes).

    Overture files nursing homes and assisted living under `retirement_home` /
    `assisted_living_facility`; its `nursing` category is individual nurse
    practitioners, so it is deliberately not pulled.
    """
    import duckdb  # project dependency; imported lazily so the other downloads don't need it

    release = latest_overture_release()
    con = duckdb.connect()
    con.execute("install httpfs; load httpfs; set s3_region='us-west-2'")
    path = f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
    placeholders = ", ".join("?" for _ in OVERTURE_CATEGORIES)
    # The release name comes from a remote bucket listing, so it and the category names are
    # bound as parameters. The COPY target can't be a parameter; it is a program constant.
    con.execute(
        f"copy (select id, struct_extract(names, 'primary') as name, "  # nosec B608
        "struct_extract(taxonomy, 'primary') as category, confidence, "
        "addresses[1].freeform as street, addresses[1].locality as city, "
        "addresses[1].region as state, addresses[1].postcode as zip, "
        "cast(? as varchar) as release "
        "from read_parquet(?) "
        "where addresses[1].country = 'US' "
        f"and struct_extract(taxonomy, 'primary') in ({placeholders})) "
        f"to '{DEST / 'overture_gq.csv'}' (format csv, header)",
        [release, path, *OVERTURE_CATEGORIES],
    )
    _record("overture_gq.csv", path)
    print(f"overture: release {release} ok")


def fetch_all(*, skip_overture: bool = False, include_excluded: bool = False) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    for name, dataset_id in CARE_COMPARE.items():
        _save(PDC_DOWNLOAD.format(id=dataset_id), f"{name}.csv", timeout=120)
        print(f"{name}: ok")
    fetch_pos()
    fetch_ipeds()
    fetch_bop()
    fetch_assisted_living()
    fetch_hifld_prisons()
    if include_excluded:
        fetch_ppi_facilities()
    else:
        print("ppi_facilities: excluded, skipped")
    fetch_state_assisted_living(include_excluded=include_excluded)
    fetch_state_lists(include_excluded=include_excluded)
    if skip_overture:
        print("overture: skipped")
    else:
        fetch_overture()
    print(
        f"\nSources that can't be downloaded automatically go in {MANUAL_DIR}/ -- "
        "see scripts/institutional_registry/MANUAL_DOWNLOADS.md"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-overture",
        action="store_true",
        help="skip the slow (~7 min) Overture Maps extract",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        help="also fetch sources excluded from the committed data (PPI, AK, IN, KY, MI, VA); "
        "do not commit them (see docs/DATA_SOURCE_LICENSES.md)",
    )
    args = parser.parse_args()
    fetch_all(skip_overture=args.skip_overture, include_excluded=args.include_excluded)
