"""Oklahoma: OSDH Long Term Care Service facility layer (ArcGIS Online, OSDH's own org).

Layer 1 (layer 0 does not exist) of `LongTermCareFacilities_2024`, built from OSDH's 2024
Medical Facilities Service Directory. Anonymous; no token or special user agent.

Included: Assisted Living (187) and Residential Care (27). Excluded: Nursing Home, ICF/IID,
Adult Day Care. ADMINISTRATOR, FACILITY_EMAIL and TELEPHONE are deliberately not carried.

Freshness: item last modified 2025-11-20; the description says it is updated as OSDH gets new
information, but the source directory is from 2024.
Quirks: ZIP is stored as a number (padded to 5 digits here). No license status field, only a
validation flag; capacity is licensed beds (BEDLICTOT).
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, arcgis_query, make_row

STATE = "OK"
SOURCE = (
    "https://services9.arcgis.com/QeqGrHRDFO8mPwTf/arcgis/rest/services/"
    "LongTermCareFacilities_2024/FeatureServer/1"
)


def fetch(session: Session) -> List[Dict[str, str]]:
    rows = arcgis_query(
        session,
        SOURCE,
        "FACILITY_TYPE IN ('Assisted Living','Residential Care')",
        page_size=2000,
    )
    return [
        make_row(
            STATE,
            name=r.get("NAME"),
            street=r.get("ADDRESS"),
            city=r.get("CITY"),
            zip=str(int(r["ZIP"])).zfill(5) if r.get("ZIP") else "",
            capacity=r.get("BEDLICTOT"),
            license_id=r.get("FACID"),
            license_type=r.get("FACILITY_TYPE"),
        )
        for r in rows
    ]
