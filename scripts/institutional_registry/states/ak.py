"""Alaska: licensed assisted living homes (DOH Health Facilities Licensing & Certification).

The open-facilities workbook (e.g. 2026_08_031_alh_open_facilites_public.xlsx) is linked from
the assisted-living licensing page. The media id and filename change when the state
re-uploads (about monthly), so the fetcher scrapes the page for the .xlsx href each run and
raises if none is found. All rows are assisted living homes (licensed ALH), so all are kept.
Owner emails/phones in the file are not read.

Quirks: rows are license segments (a home can appear several times), so rows are
de-duplicated by License No (first occurrence kept). Physical address columns are used.
A banner (header is row 2) carries the "last updated" date. The file lists currently licensed
homes only; there is no status column. Provider phone/email, administrator and W-9 owner
columns exist and are not read.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Dict, List

from scripts.institutional_registry.states.common import (
    Session,
    make_row,
    read_xlsx,
    sheet_dicts,
)

STATE = "AK"
PAGE = "https://health.alaska.gov/en/services/assisted-living-licensing-and-renewals/"
SOURCE = PAGE + " (links to the open-facilities .xlsx)"


def _find_xlsx_url(session: Session) -> str:
    html = session.get_text(PAGE)
    hrefs = re.findall(r'href="([^"]+\.xlsx)[^"]*"', html, flags=re.IGNORECASE)
    open_lists = [h for h in hrefs if "alh" in h.lower() or "open" in h.lower()]
    if not open_lists:
        raise RuntimeError(f"AK: no assisted-living .xlsx link found on {PAGE}")
    return urllib.parse.urljoin(PAGE, open_lists[0])


def fetch(session: Session) -> List[Dict[str, str]]:
    url = _find_xlsx_url(session)
    records = sheet_dicts(
        read_xlsx(session.get(url)), header_row=2
    )  # banner + blank row first
    if not records or "Name Of Home" not in records[0]:
        raise RuntimeError(f"AK: unexpected layout in {url}")
    out: List[Dict[str, str]] = []
    seen = set()
    for r in records:
        license_id = r.get("License No", "").strip()
        if license_id in seen:
            continue
        seen.add(license_id)
        street = " ".join(
            p
            for p in (r.get("physical Street", ""), r.get("physical Street2", ""))
            if p.strip()
        )
        out.append(
            make_row(
                STATE,
                name=r.get("Name Of Home"),
                street=street,
                city=r.get("physical City"),
                zip=r.get("physical Zip"),
                capacity=r.get("No of Beds"),
                license_id=license_id,
                license_type="Assisted Living Home",
            )
        )
    return out
