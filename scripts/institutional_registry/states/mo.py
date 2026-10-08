"""Missouri: assisted living and residential care facilities (MO DHSS Section for Long-Term Care
Regulation), via the data.mo.gov Socrata dataset fenu-sipv ("Long-term care facilities").

level_of_care codes included:
  ALF, ALF**   assisted living facilities
  RCF, RCF*    residential care facilities (room and board plus personal care)
Excluded: SNF (skilled nursing) and ICF (intermediate care) - nursing homes.

Freshness: current licenses; `status` carries the license expiration date (YYYY-MM-DD).
Quirks: zip_code is ZIP+4 in the source and is kept as given; the facility's administrator
name, phone and mailing address are not carried. The `*`/`**` suffixes are Missouri's own
sub-classifications (kept in license_type verbatim).
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row, socrata_rows

STATE = "MO"
SOURCE = "https://data.mo.gov/resource/fenu-sipv.json"

KEEP_LEVELS = {"ALF", "ALF**", "RCF", "RCF*"}


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    data = socrata_rows(session, SOURCE)
    if data and "level_of_care" not in data[0]:
        raise RuntimeError("MO: level_of_care column missing; dataset schema changed")
    rows = []
    for r in data:
        level = (r.get("level_of_care") or "").strip()
        if level not in KEEP_LEVELS:
            continue
        rows.append(
            make_row(
                STATE,
                name=r.get("facility_name"),
                street=r.get("address"),
                city=r.get("city"),
                zip=r.get("zip_code"),
                capacity=r.get("capacity"),
                license_id=r.get("fcilicensenumber"),
                license_type=level,
                status=(r.get("license_expiration") or "")[:10],
            )
        )
    if len(rows) < 300:
        raise RuntimeError(
            f"MO: only {len(rows)} ALF/RCF rows; dataset may have changed"
        )
    return rows
