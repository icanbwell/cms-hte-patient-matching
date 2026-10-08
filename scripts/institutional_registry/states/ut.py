"""Utah: licensed Assisted Living Facilities (Type I and Type II), via the Utah ArcGIS layer.

Source: LicensedHealthCareFacilities layer 0 (891 facilities across 13 license types),
filtered to LICENSE_TYPE LIKE '%Assisted%':
  - Assisted Living Facility - Type II (176)  (higher-care, includes secure/memory care)
  - Assisted Living Facility - Type I  (48)
Excluded: Nursing Care Facility, Hospital, Hospice, Home Health Agency, Personal Care
Agency (home care), ESRD, surgical, etc. "Small Health Care Facility" (5 rows) is excluded
because all 5 are Intermediate Care Facilities for Individuals with Intellectual
Disabilities (SPECIALTIES field), which the task excludes. The layer has no adult day or
board-and-care type.

Freshness: live layer; no snapshot date field (LICENSE_EXPIRATION_DATE runs into 2026-2027).
No status column; the layer lists currently licensed facilities.

Quirks: ZIP is numeric. UNIT ("Building A") is not part of the street line and is dropped.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, arcgis_query, make_row

STATE = "UT"
SOURCE = (
    "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/"
    "LicensedHealthCareFacilities/FeatureServer/0"
)


def _zip(value: object) -> str:
    return str(int(value)).zfill(5) if isinstance(value, (int, float)) and value else ""


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    return [
        make_row(
            STATE,
            name=r.get("FACILITY_NAME"),
            street=r.get("ADDRESS"),
            city=r.get("CITY"),
            zip=_zip(r.get("ZIP")),
            capacity=r.get("CAPACITY"),
            license_id=r.get("ID_NUMBER"),
            license_type=r.get("LICENSE_TYPE"),
        )
        for r in arcgis_query(session, SOURCE, "LICENSE_TYPE LIKE '%Assisted%'")
    ]
