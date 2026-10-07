"""Arizona: ADHS licensed residential facilities, via the ADHS ArcGIS FeatureServer.

Source: layer 18 of ADHS's "All State Licensed Facilities in Arizona" service (all ADHS
license types; we filter on TYPE).

Included (counts as of the Feb 2025 snapshot):
  - ASSISTED LIVING HOME   (1,719) residential, up to 10 residents
  - ASSISTED LIVING CENTER (328)   larger assisted-living facilities
  - ADULT FOSTER CARE      (25)    adult care homes, up to 4 residents who live there
Excluded: nursing homes and nursing-supported group homes (nursing/ICF-IID), adult day
health care, behavioral health residential / therapeutic / respite homes (treatment
settings, not assisted living), DD group homes, hospitals.

Freshness: every row has RUN_DATE 2025-02-03 and the service description says "Last
updated on February 2025". The sibling AZLicensedFacilities service (layers 9 and 12) carries
the same RUN_DATE, so no newer ADHS snapshot was found. All rows are ACTIVE.

Quirks: ZIP is an integer. N_ADDRESS / N_CITY / N_ZIP are ADHS's geocoder-cleaned address
(e.g. "216 JOY NEVIN AVE"); the raw ADDRESS is used when the cleaned one is empty.
Capacity is a string like "16.0"; CAPACITY_INT is used.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, arcgis_query, make_row

STATE = "AZ"
SOURCE = (
    "https://services1.arcgis.com/mpVYz37anSdrK4d8/ArcGIS/rest/services/"
    "All_State_Licensed_Facilities_in_Arizona/FeatureServer/18"
)
_TYPES = ("ASSISTED LIVING HOME", "ASSISTED LIVING CENTER", "ADULT FOSTER CARE")


def _zip(value: object) -> str:
    return str(int(value)).zfill(5) if isinstance(value, (int, float)) and value else ""


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    where = "TYPE IN (" + ",".join(f"'{t}'" for t in _TYPES) + ")"
    return [
        make_row(
            STATE,
            name=r.get("FACILITY_NAME"),
            street=r.get("N_ADDRESS") or r.get("ADDRESS"),
            city=r.get("N_CITY") or r.get("CITY"),
            zip=_zip(r.get("N_ZIP") or r.get("ZIP")),
            capacity=r.get("CAPACITY_INT")
            if r.get("CAPACITY_INT") is not None
            else r.get("Capacity"),
            license_id=r.get("LICENSE_NUMBER"),
            license_type=r.get("TYPE"),
            status=r.get("OPERATION_STATUS"),
        )
        for r in arcgis_query(session, SOURCE, where)
    ]
