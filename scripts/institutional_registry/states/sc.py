"""South Carolina: SCDPH licensed Community Residential Care Facilities (CRCFs).

Source: the Health_Facilities ArcGIS FeatureServer (all SCDPH permit types), filtered to
PERMIT_TYPE = 'HLRESIDENTIALCARE' (428 rows), which is SC's assisted-living / personal-care
license. Excluded: nursing care, adult day care, home health, hospice, hospital,
residential treatment (substance abuse) and every other permit type in the layer.

Freshness: live layer; license expiration dates run through 2026-2027. All rows have
PERMIT_OPERATING_CODE 'ACT'.

Quirks: LF_STREET_ZIP is ZIP+4 ("29412-3506"); it is trimmed to the 5-digit ZIP. Capacity
is NBR_LICENSED (always populated); CRC_NBR_TOTAL_BEDS is null for ~64% of rows.
Street/city/zip use the LF_STREET_* (physical) fields, not the LF_BILL_* billing address.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, arcgis_query, make_row

STATE = "SC"
SOURCE = (
    "https://services5.arcgis.com/G4BLIH7rTQoIjCFv/arcgis/rest/services/"
    "Health_Facilities/FeatureServer/0"
)


def fetch(session: Session) -> List[Dict[str, str]]:
    rows = arcgis_query(
        session,
        SOURCE,
        "PERMIT_TYPE='HLRESIDENTIALCARE'",
        out_fields=(
            "LF_NAME,LF_STREET_ADDR1,LF_STREET_CITY,LF_STREET_ZIP,NBR_LICENSED,"
            "LICENSE_NBR,PERMIT_TYPE_DETAIL_DESC,PERMIT_OPERATING_CODE"
        ),
    )
    return [
        make_row(
            STATE,
            name=r.get("LF_NAME"),
            street=r.get("LF_STREET_ADDR1"),
            city=r.get("LF_STREET_CITY"),
            zip=(r.get("LF_STREET_ZIP") or "")[:5],
            capacity=r.get("NBR_LICENSED"),
            license_id=r.get("LICENSE_NBR"),
            license_type=r.get("PERMIT_TYPE_DETAIL_DESC"),
            status=r.get("PERMIT_OPERATING_CODE"),
        )
        for r in rows
    ]
