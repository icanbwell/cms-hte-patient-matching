"""West Virginia: OHFLAC Facility Lookup (ohflac.wvdhhr.org), DataTables server-side JSON.

The page's JavaScript (/Apps/Scripts/Lookup/facsearch-2.0.js) POSTs a full DataTables
server-side body, with FedCode = <TypeFilter><SubTypeFilter>, to /Apps/Lookup/FacilitySearch/
FacilitySearch. A minimal body fails with a server-side null reference, so this module sends the
page's exact shape (draw, columns[], order, start, length=-1 for all rows, search and the page's
filter fields). StatusFilter="active" limits the server response to active licenses; Status is
checked again client-side.

Included facility types (FedCode):
  W7*  Assisted Living Residence: Large Assisted Living (~54 active) and Small Assisted Living
       (~28 active); the 10 Personal Care Homes under W7 are all closed
  W3*  Residential Care Community (1 active)
  W2*  Residential Board and Care Home (0 active today; kept so new licenses are picked up)
Excluded: Alzheimer's Unit (W8, a unit inside another licensed facility), nursing homes (02),
ICF/IID (11), adult day care (W5), hospice (16), home health (05), behavioral health,
recovery residences and every other type in the dropdown. Closed/pending licenses are excluded.

Freshness: live licensing database, current as of the fetch.
Quirks: Street2 (suite/unit) is appended to the street line when present. Capacity is
LicensedBedCount. Administrator, legal-name, phone and fax fields are not carried.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "WV"
SOURCE = (
    "https://ohflac.wvdhhr.org/Apps/Lookup/FacilitySearch "
    "(POST .../FacilitySearch/FacilitySearch, FedCode W7*, W3*, W2*)"
)

_PAGE = "https://ohflac.wvdhhr.org/Apps/Lookup/FacilitySearch"
_FED_CODES = {"W7*": 40, "W3*": 0, "W2*": 0}  # FedCode -> minimum expected active rows
_COLUMNS = (
    "DT_RowId Name LegalName Admin StateKey Status OpenedDate ClosedDate ContactInformation "
    "Street Street2 City State ZIP County PhoneNumberExport FAXNumberExport FacType SubType "
    "Abbreviation LicenseType Number EffectiveDate ExpiresDate LicensedBedCount "
    "CertifiedBedCount CurrentSSIBedCount Medicare Medicaid SSI Licensure Longitude Latitude "
    "Funding TotalBeds Code"
).split()


def _body(fed_code: str) -> Dict[str, Any]:
    return {
        "draw": 1,
        "columns": [
            {
                "data": col,
                "name": "",
                "searchable": col
                in ("Name", "ContactInformation", "Funding", "Abbreviation"),
                "orderable": True,
                "search": {"value": "", "regex": False},
            }
            for col in _COLUMNS
        ],
        "order": [{"column": 1, "dir": "asc"}],
        "start": 0,
        "length": -1,
        "search": {"value": "", "regex": False},
        "FedCode": fed_code,
        "NameFilter": "",
        "CountyFilter": "All Counties",
        "AdvCountyFilter": None,
        "LegalNameFilter": "",
        "StatusFilter": "active",
        "ContactFilter": "",
        "WithinDistance": "",
        "ZIPFilter": "",
        "PaymentFilter": "medicare,medicaid,ssi,private",
        "BedsFilter": ",",
        "LicenseFilter": "",
        "ApprovedAMAPs": 0,
    }


def fetch(session: Session) -> List[Dict[str, str]]:
    session.get_text(_PAGE)  # cookie
    rows: List[Dict[str, str]] = []
    for fed_code, minimum in _FED_CODES.items():
        raw = session.post(
            _PAGE + "/FacilitySearch",
            json.dumps(_body(fed_code)).encode(),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )
        result = json.loads(raw)
        data = result.get("data")
        if not isinstance(data, list) or "error" in result:
            raise RuntimeError(
                f"WV: unexpected response for FedCode {fed_code}: {str(raw)[:200]}"
            )
        if len(data) != result.get("recordsFiltered"):
            raise RuntimeError(
                f"WV: FedCode {fed_code} returned {len(data)} of {result.get('recordsFiltered')}"
            )
        if len(data) < minimum:
            raise RuntimeError(
                f"WV: FedCode {fed_code} returned {len(data)} rows; expected >= {minimum}"
            )
        for r in data:
            if (r.get("Status") or "").strip() != "Active":
                continue
            street = ", ".join(
                p.strip()
                for p in (r.get("Street"), r.get("Street2"))
                if p and p.strip()
            )
            rows.append(
                make_row(
                    STATE,
                    name=r.get("Name"),
                    street=street,
                    city=r.get("City"),
                    zip=r.get("ZIP"),
                    capacity=r.get("LicensedBedCount"),
                    license_id=r.get("Number"),
                    license_type=r.get("SubType") or r.get("FacType"),
                    status=r.get("Status"),
                )
            )
    return rows
