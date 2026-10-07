"""New Jersey: assisted living residences and personal care homes (NJ DOH facility guide CSV).

Source is the all-facilities CSV behind the NJ DOH facility finder, filtered on `TypeDetail`.
Included (buildings where residents live):
  - Assisted Living Residence (licensed ALR)
  - Comprehensive Personal Care Home (assisted-living-level personal care homes)
  - Residential Health Care (residential health care facilities, a board-and-care type)
Excluded:
  - Assisted Living Program (ALP): a service delivered to residents of subsidized housing;
    the listed address is the provider agency, often shared with an ALR/CPCH row.
  - Alternative Family Care: caregivers' homes administered by a sponsor agency; the listed
    address is the sponsor's office.
  - Long Term Care Facility (nursing homes), Adult Day Health Care, Pediatric Day, hospice,
    home health, and all acute-care types.
The stale ArcGIS layer is not used. No capacity or status columns in this file (capacity is
blank); the file lists currently licensed facilities. Freshness: whatever the state last
published; the file carries no date.
Quirks: `Address2` holds suites, PO boxes and mailing notes, so it is ignored; `FACID` is the license id.
"""

from __future__ import annotations

import csv
import io
from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "NJ"
SOURCE = "https://www.nj.gov/health/guide/json/healthfacilities_map_datav2.csv"

INCLUDED_TYPE_DETAILS = {
    "Assisted Living Residence",
    "Comprehensive Personal Care Home",
    "Residential Health Care",
}


def fetch(session: Session) -> List[Dict[str, str]]:
    text = session.get_text(SOURCE).lstrip("﻿")
    if not text.startswith("FACID,"):
        raise RuntimeError("NJ facility CSV did not return the expected header")
    return [
        make_row(
            STATE,
            name=r.get("LEGALNAME"),
            street=r.get("Address"),
            city=r.get("City"),
            zip=r.get("FAC_ZIP"),
            license_id=r.get("FACID"),
            license_type=r.get("TypeDetail"),
        )
        for r in csv.DictReader(io.StringIO(text))
        if (r.get("TypeDetail") or "").strip() in INCLUDED_TYPE_DETAILS
    ]
