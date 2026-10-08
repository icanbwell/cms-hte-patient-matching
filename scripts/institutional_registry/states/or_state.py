"""Oregon: ODHS Licensed Long-Term Care Settings (ltclicensing.oregon.gov), CSV export.

Flow: GET /Providers (cookie + hidden __RequestVerificationToken + total result count in the
export form's hidden PageSize field), then POST /Providers/Export with type=csv, that
PageSize and Filters=Status=Open.

Included (all are residential settings where people live):
  ALF  assisted living facility
  RCF  residential care facility
  AFH  adult foster home (small 1-5 bed homes; many rows, low capacity each)
Excluded: NF (nursing facility) - nursing homes are out of scope.
Closed facilities are excluded by the Status=Open filter.

Freshness: live licensing database, current as of the fetch.
Quirks: the file has no state column (always OR). AFH "Name" is frequently the licensee's
personal name (e.g. "Lastname Firstname"), since the home is run from the provider's house.
This repo is public and its policy is to keep personal names out, so the name is NOT carried
for AFH rows (blank); the address and license ID are, which is what address matching needs.
ALF and RCF names are business names and are kept. Phone and Email columns are also not
carried. The export returns only a page of rows, so PageSize must be at
least the total (read from the page, not hard-coded).
"""

from __future__ import annotations

import csv
import io
import re
from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "OR"
SOURCE = (
    "https://ltclicensing.oregon.gov/Providers "
    "(POST https://ltclicensing.oregon.gov/Providers/Export, type=csv, Filters=Status=Open)"
)

_PAGE = "https://ltclicensing.oregon.gov/Providers"
_EXPORT = "https://ltclicensing.oregon.gov/Providers/Export"
_KEEP_TYPES = {"ALF", "RCF", "AFH"}
_EXPECTED_COLUMNS = {
    "ID",
    "Name",
    "Type",
    "Address",
    "City",
    "Zip",
    "Licensed beds",
    "Status",
}


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    html = session.get_text(_PAGE)
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
    size = re.search(r'name="PageSize"[^>]*value="(\d+)"', html) or re.search(
        r'id="PageSize"[^>]*value="(\d+)"', html
    )
    if not token or not size:
        raise RuntimeError(
            "OR: anti-forgery token or PageSize field not found on /Providers"
        )
    page_size = max(int(size.group(1)), 1) + 500  # headroom if the page count is stale
    raw = session.post(
        _EXPORT,
        {
            "PageSize": str(page_size),
            "type": "csv",
            "Filters": "Status=Open",
            "__RequestVerificationToken": token.group(1),
        },
    ).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    missing = _EXPECTED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise RuntimeError(f"OR: export is missing columns {sorted(missing)}")
    records = list(reader)
    if len(records) < 1000:
        raise RuntimeError(
            f"OR: export returned only {len(records)} rows; expected ~2,300"
        )
    types = {r["Type"] for r in records}
    if not _KEEP_TYPES <= types:
        raise RuntimeError(
            f"OR: expected types {sorted(_KEEP_TYPES)} not all present: {types}"
        )
    return [
        make_row(
            STATE,
            name=""
            if r["Type"] == "AFH"
            else r["Name"],  # AFH names are personal names
            street=r["Address"],
            city=r["City"],
            zip=r["Zip"],
            capacity=r["Licensed beds"],
            license_id=r["ID"],
            license_type=r["Type"],
            status=r["Status"],
        )
        for r in records
        if r["Type"] in _KEEP_TYPES
    ]
