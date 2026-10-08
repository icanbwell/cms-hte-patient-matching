"""Colorado: CDPHE licensed Assisted Living Residences, via the CDPHE ArcGIS FeatureServer.

Source: CDPHE_Health_Facilities layer 0, filtered to Facility_Type = 'Assisted Living
Residence' (all license subtypes: ALR ONLY, ALR/ACF, ALR/BISL). Other types in the layer
(nursing facilities, hospitals, home care/health agencies, clinics) are excluded. The
data.colorado.gov Socrata copy is a 2017 snapshot and is not used.

Freshness: Date_Data_Updated is 2026-06-15 on every row (live layer).
Status: Active (672) and Pending (11) rows are both kept; `status` carries the value.

Quirks: the address is a single field, Address_Full ("1330 N SIDNEY AVE, STERLING, CO
80751"), split with common.split_address. Capacity is Licensed_Beds_Total.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import (
    Session,
    arcgis_query,
    make_row,
    split_address,
)

STATE = "CO"
SOURCE = (
    "https://services3.arcgis.com/66aUo8zsujfVXRIT/arcgis/rest/services/"
    "CDPHE_Health_Facilities/FeatureServer/0"
)


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    rows = []
    for r in arcgis_query(session, SOURCE, "Facility_Type='Assisted Living Residence'"):
        addr = split_address(r.get("Address_Full") or "")
        rows.append(
            make_row(
                STATE,
                name=r.get("Facility_Name"),
                street=addr["street"],
                city=addr["city"],
                zip=addr["zip"],
                capacity=r.get("Licensed_Beds_Total"),
                license_id=r.get("Facility_ID"),
                license_type=r.get("Facility_Type_Detail"),
                status=r.get("Operating_Status"),
            )
        )
    return rows
