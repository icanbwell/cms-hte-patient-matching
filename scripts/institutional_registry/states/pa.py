"""Pennsylvania: licensed personal care homes (PA DHS), via the data.pa.gov Socrata API.

Every row is a personal care home. Pennsylvania's separately licensed "assisted living
residences" are not in this dataset, so PA coverage is personal care homes only.
No status column; the dataset lists licensed homes.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row, socrata_rows

STATE = "PA"
SOURCE = "https://data.pa.gov/resource/pqf4-d4xn.json"


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    return [
        make_row(
            STATE,
            name=r.get("facname"),
            street=r.get("street"),
            city=r.get("city"),
            zip=r.get("zip"),
            capacity=r.get("totcapcty"),
            license_type=r.get("typservtxt"),
        )
        for r in socrata_rows(session, SOURCE)
    ]
