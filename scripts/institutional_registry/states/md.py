"""Maryland: licensed assisted living programs (MD Dept. of Health OHCQ), via opendata.maryland.gov.

Dataset i48m-922u ("Assisted Living") mirrors the state's MD_LongTermCareAssistedLiving ArcGIS
layer (both 1,568 rows). It has no type or status column: every row is an assisted living
program licensed by OHCQ, and all are included (residents live there). Not Montgomery
County's d7m6-524h, which is county-only. Nursing homes are a different dataset.

Freshness: Socrata metadata says last updated 2025-07-21, so newer licenses are missing.
Quirks: `ohcq_index_no` (license id) is blank for some rows; capacity is the licensed bed count.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row, socrata_rows

STATE = "MD"
SOURCE = "https://opendata.maryland.gov/resource/i48m-922u.json"


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    return [
        make_row(
            STATE,
            name=r.get("facility_name"),
            street=r.get("facility_address"),
            city=r.get("facility_city"),
            zip=r.get("facility_zip"),
            capacity=r.get("license_capacity"),
            license_id=r.get("ohcq_index_no"),
            license_type="Assisted Living Program",
        )
        for r in socrata_rows(session, SOURCE)
    ]
