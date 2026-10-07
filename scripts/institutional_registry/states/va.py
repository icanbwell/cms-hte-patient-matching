"""Virginia: licensed assisted living facilities (VA DSS Division of Licensing Programs).

Source: the public ALF search page, requested with perPage=1000 so one page holds every
facility (~575). The server-rendered page embeds the search API response as HTML-escaped JSON
inside an HTML comment ("DEBUG: Raw Search API Response", a <pre> block), and also renders one
visible "staff-card" per facility. Strategy:
  1. Primary: the embedded JSON (has licenseId, licensed flag, facilityType, structured address).
  2. Fallback, if the debug block is removed: the visible cards (name, "street, CITY, ZIP",
     licenseId from the card link). Cards have no licensed flag or type, so license_type is set
     to the endpoint's type ("Assisted Living Facility") and unlicensed rows can't be filtered.
If neither structure parses, or the result count disagrees with the page, fetch() raises.

Included: everything the ALF endpoint returns with licensed == true (Virginia's ALF license
covers both assisted living and residential living care; both are residential). Facilities
flagged licensed == false are dropped. Phone numbers are not carried.

Quirks: address.streetNumber is missing on a few rows (the street is then addressLine1 alone);
addressLine1 may already include the number on some rows, so the number is only prefixed when
addressLine1 doesn't already start with it. City is upper case as supplied (e.g. "MC LEAN").
Page is live, so data is current as of the fetch.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any, Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "VA"
SOURCE = (
    "https://www.dss.virginia.gov/licensed-care/search-licensing-programs/"
    "assisted-living-facility-search/?facilityName=&location=&zipCode=&page=1&perPage=1000"
    "&sort=asc&endpoint=alf"
)

_PRE = re.compile(
    r"DEBUG: Raw Search API Response\s*-->\s*<!--.*?<pre[^>]*>(.*?)</pre>", re.DOTALL
)
_CARD = re.compile(
    r'<a class="card-heading" href="\?licenseId=(\d+)[^"]*">(.*?)</a>'
    r'.*?<div class="card-department">\s*<svg.*?</svg>\s*([^<]*?)\s*</div>',
    re.DOTALL,
)


def _from_json(page: str) -> List[Dict[str, str]]:
    match = _PRE.search(page)
    if not match:
        raise LookupError("no embedded JSON block")
    data: Any = json.loads(html.unescape(match.group(1)))
    facilities = data["licensedFacilities"]
    total = data.get("total")
    if total is not None and int(total) != len(facilities):
        raise RuntimeError(
            f"VA: API total {total} != {len(facilities)} facilities returned"
        )
    rows = []
    for fac in facilities:
        if fac.get("licensed") is not True:
            continue
        addr = fac.get("address") or {}
        line1 = (addr.get("addressLine1") or "").strip()
        number = (addr.get("streetNumber") or "").strip()
        street = (
            line1 if (not number or line1.startswith(number)) else f"{number} {line1}"
        )
        rows.append(
            make_row(
                STATE,
                name=fac.get("facilityName"),
                street=street,
                city=addr.get("city"),
                zip=addr.get("zipCode"),
                license_id=fac.get("licenseId"),
                license_type=fac.get("facilityType"),
                status="Licensed",
            )
        )
    return rows


def _from_cards(page: str) -> List[Dict[str, str]]:
    rows = []
    for lic, name, address in _CARD.findall(page):
        parts = [p.strip() for p in html.unescape(address).rsplit(",", 2)]
        if len(parts) != 3:
            raise RuntimeError(f"VA: unexpected card address {address!r}")
        rows.append(
            make_row(
                STATE,
                name=html.unescape(name),
                street=parts[0],
                city=parts[1],
                zip=parts[2],
                license_id=lic,
                license_type="Assisted Living Facility",
            )
        )
    return rows


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    page = session.get_text(SOURCE)
    try:
        rows = _from_json(page)
    except (LookupError, KeyError, ValueError):
        rows = _from_cards(page)
    if len(rows) < 400:
        raise RuntimeError(
            f"VA: only {len(rows)} facilities parsed; page structure changed?"
        )
    return rows
