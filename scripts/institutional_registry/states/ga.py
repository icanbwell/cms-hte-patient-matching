"""Georgia: personal care homes and assisted living communities (GA DCH, Healthcare Facility Regulation).

Source: the facility-search page https://forms.dch.georgia.gov/hfrd/FACSEARCH.aspx returns, to a
plain GET, a ~5 MB XML document (<Root><FAC_SEARCH .../>...) listing every DCH-regulated
facility. Attributes: FACID, FACNAME, FACTYPE, Address, City, State, Zip, County, Phone,
LICENSE_DATE (all optional per element).

Included FACTYPE values:
  PERSONAL CARE HOME            licensed residential setting (the bulk of Georgia's board-and-care)
  ASSISTED LIVING COMMUNITY     licensed residential setting, larger/higher-acuity
Excluded: COMMUNITY LIVING ARRANGEMENT (developmental-disability homes), nursing homes, hospices,
home care, adult day care, drug-abuse treatment and every other DCH facility type.

Freshness: live search backing data (LICENSE_DATE is the most recent license issue date; it is
absent on some rows). No capacity or status in this feed (the separate GetFacilitiesData.svc JSON
has licensed beds but requires one request per city, so it is not used). The phone attribute is
a business phone and is not carried.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List

from scripts.institutional_registry.states.common import (
    Session,
    make_row,
    safe_fromstring,
)

STATE = "GA"
SOURCE = "https://forms.dch.georgia.gov/hfrd/FACSEARCH.aspx"

KEEP_TYPES = {"PERSONAL CARE HOME", "ASSISTED LIVING COMMUNITY"}


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    raw = session.get(SOURCE)
    try:
        root = safe_fromstring(raw)
    except (ET.ParseError, UnicodeDecodeError, ValueError) as err:
        raise RuntimeError(f"GA: {SOURCE} no longer returns plain XML: {err}") from err
    elements = root.findall("FAC_SEARCH")
    if len(elements) < 5000:
        raise RuntimeError(
            f"GA: expected >5000 FAC_SEARCH elements, found {len(elements)}"
        )
    rows = []
    for el in elements:
        factype = (el.get("FACTYPE") or "").strip().upper()
        if factype not in KEEP_TYPES:
            continue
        rows.append(
            make_row(
                STATE,
                name=el.get("FACNAME"),
                street=el.get("Address"),
                city=el.get("City"),
                zip=el.get("Zip"),
                license_id=el.get("FACID"),
                license_type=factype.title(),
            )
        )
    if len(rows) < 1000:
        raise RuntimeError(
            f"GA: only {len(rows)} PCH/ALC rows; FACTYPE values may have changed"
        )
    return rows
