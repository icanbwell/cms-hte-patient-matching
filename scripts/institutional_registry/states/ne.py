"""Nebraska: DHHS licensed assisted living facilities (ALF), via ArcGIS Online.

Every row is an assisted living facility (ABBREV = 'ALF', 277 rows); nothing is filtered.

Source: layer 27 ("Assisted Living Facility") of the NE DHHS-owned ArcGIS Online service
"Assisted_Living_Facility_Upload" (Rural Health Transformation Program map). It has the
same schema as the state-hosted layer https://gis.ne.gov/agencyext/rest/services/
DHHS_Assisted_Living_Facilities/FeatureServer/0, which was returning
{"error":{"code":500,"message":"9017$SITE_NOT_INITIALIZED"}} for the whole agencyext site
(service directory, metadata and queries) on 2026-10-06, so the ArcGIS Online copy is the
primary and the gis.ne.gov layer is the fallback.

Freshness: the roster date on every row is 2025-10-15 ("on current roster"); the layer was
last edited 2026-08-26. No status column; rows are the current roster.

Quirks: use the FAC_* / MDSDBA_FACILITY_ADDRESS fields (physical location); CITY/ZIP/ADDRESS2
are the mailing address. FAC_ADDR_2 is mostly a PO Box and is ignored. FAC_ZIP is an integer.
Capacity is BEDLICTOT; license_id is STATEID (e.g. ALF027).
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, arcgis_query, make_row

STATE = "NE"
_PRIMARY = (
    "https://services8.arcgis.com/sfauBl8MaKYMG7K4/arcgis/rest/services/"
    "Assisted_Living_Facility_Upload/FeatureServer/27"
)
_FALLBACK = "https://gis.ne.gov/agencyext/rest/services/DHHS_Assisted_Living_Facilities/FeatureServer/0"
SOURCE = f"{_PRIMARY} ; fallback {_FALLBACK}"


def _zip(value: object) -> str:
    return str(int(value)).zfill(5) if isinstance(value, (int, float)) and value else ""


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    try:
        rows = arcgis_query(session, _PRIMARY)
    except RuntimeError:
        rows = arcgis_query(session, _FALLBACK)
    return [
        make_row(
            STATE,
            name=r.get("Legal_Name"),
            street=r.get("MDSDBA_FACILITY_ADDRESS"),
            city=r.get("FAC_CITY"),
            zip=_zip(r.get("FAC_ZIP")),
            capacity=r.get("BEDLICTOT"),
            license_id=r.get("STATEID"),
            license_type="Assisted Living Facility",
        )
        for r in rows
    ]
