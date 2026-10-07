"""Massachusetts: MassGIS "Long-Term Care Residences" ArcGIS layer.

The layer is built from Executive Office of Elder Affairs (assisted living residences) and
DPH (rest homes, nursing homes) records and is anonymous (no token or special user agent).

Included: ALR (assisted living residence) and RH (rest home, a licensed residential care
setting). Excluded: NH (nursing home).

Freshness: layer data last edited 2026-05-01.
Quirks: no capacity or status fields. The city field, MAIL_CITY, is the mailing city and may
differ from the physical town. ADDRESS is the street line only.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, arcgis_query, make_row

STATE = "MA"
SOURCE = (
    "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/"
    "Long_Term_Care_Residences/FeatureServer/0"
)

_TYPES = {"ALR": "Assisted Living Residence", "RH": "Rest Home"}


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    rows = arcgis_query(session, SOURCE, "FAC_TYPE IN ('ALR','RH')", page_size=2000)
    return [
        make_row(
            STATE,
            name=r.get("FAC_NAME"),
            street=r.get("ADDRESS"),
            city=r.get("MAIL_CITY"),
            zip=r.get("ZIPCODE"),
            license_id=r.get("MAD_ID"),
            license_type=_TYPES.get(r.get("FAC_TYPE") or "", r.get("FAC_TYPE")),
        )
        for r in rows
    ]
