"""New York: adult homes and enriched housing programs (NY DOH), via health.data.ny.gov Socrata.

Dataset wssx-idhx ("Adult Care Facility Directory"). Included: Adult Home and Enriched
Housing Program (both are congregate residential care where residents live). Some adult homes
and enriched housing programs also hold an Assisted Living Residence (ALR) designation; that
is a flag on these same rows (`assisted_living_program_beds`), not a separate building, so
no double count. Any other type value is excluded as not a residence of this kind; at
the time of writing the dataset contains only these two types.
No status column; the directory lists operating certified facilities.
Quirks: `address` may carry a PO box or suite suffix after a comma; capacity is `number_of_beds`
(certified beds). `certificate_number` is used as license_id.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row, socrata_rows

STATE = "NY"
SOURCE = "https://health.data.ny.gov/resource/wssx-idhx.json"

INCLUDED_TYPES = {"adult home", "enriched housing program"}


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    return [
        make_row(
            STATE,
            name=r.get("facility_name"),
            street=r.get("address"),
            city=r.get("city"),
            zip=r.get("zip"),
            capacity=r.get("number_of_beds"),
            license_id=r.get("certificate_number"),
            license_type=r.get("type"),
        )
        for r in socrata_rows(session, SOURCE)
        if (r.get("type") or "").strip().lower() in INCLUDED_TYPES
    ]
