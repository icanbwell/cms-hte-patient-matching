"""Download every public source of institutional (group-quarters) addresses.

Sources (Proposal v3.3.6, Appendix A -- only the ones retrievable without an account):
- CMS Care Compare: nursing homes, hospitals, hospices (Provider Data Catalog API)
- CMS Provider of Services (POS) iQIES file (data.cms.gov catalog -> CSV)
- NCES IPEDS HD directory (campus addresses)
- Federal Bureau of Prisons facility API (per-facility JSON, found via bop.gov's list page)
Not retrievable here: HIFLD (portal shut down 2025-08-26), state DOC rosters, BJS jail
census, CASS validation -- see docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md.

Files land in `data/institutional_registry/` (gitignored). All data is public; no PHI.

Usage:
    uv run python -m scripts.institutional_registry.download
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

DEST = Path("data/institutional_registry")
CMS_CATALOG = "https://data.cms.gov/data.json"
PDC_DOWNLOAD = "https://data.cms.gov/provider-data/api/1/datastore/query/{id}/0/download?format=csv"
CARE_COMPARE = {
    "care_compare_nh": "4pq5-n9py",
    "care_compare_hospital": "xubh-q36u",
    "care_compare_hospice": "yc9t-dgbk",
}
BOP_LIST = "https://www.bop.gov/locations/list.jsp"
BOP_API = (
    "https://www.bop.gov/PublicInfo/execute/phyloc?todo=query&output=json&code={code}"
)
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"
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
        rows.extend(
            a for a in data.get("Addresses") or [] if a.get("addressType") == "1"
        )
        time.sleep(0.2)
    (DEST / "bop.json").write_text(json.dumps(rows))
    print(f"bop: {len(codes)} codes on list page -> {len(rows)} physical addresses")


def fetch_all() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, dataset_id in CARE_COMPARE.items():
        _curl(PDC_DOWNLOAD.format(id=dataset_id), DEST / f"{name}.csv", timeout=120)
        print(f"{name}: ok")
    _curl(latest_pos_csv_url(), DEST / "pos_iqies.csv")
    print("pos_iqies: ok")
    fetch_ipeds()
    fetch_bop()


if __name__ == "__main__":
    fetch_all()
