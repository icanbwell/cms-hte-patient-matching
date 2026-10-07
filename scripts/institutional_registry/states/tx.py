"""Texas: licensed assisted living facilities (HHSC directory, AL.xlsx).

Source is the HHSC "Directory of Assisted Living Facility Providers with an Active License".
Row 0 of the sheet is a title banner (it carries the as-of date), so the header is row 1.
Every row is an assisted living facility (Type A, B or C licenses), so all are included.
Texas licenses nursing facilities, ICF/IID and day-activity programs in separate directories;
none are in this file. The sheet also carries owner, administrator and provider email columns;
they are deliberately not read.

Quirks: ZIP is often ZIP+4 (kept as-is); the state column is "TX" or "TEXAS" (ignored, the row
state is fixed). No status column: the file lists only active licenses ("Facility Licensed" is
YES on every row). Refreshed roughly daily; the as-of date is in the banner.
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import (
    Session,
    make_row,
    read_xlsx,
    sheet_dicts,
)

STATE = "TX"
SOURCE = "https://apps.hhs.texas.gov/providers/directories/AL.xlsx"


def fetch(session: Session) -> List[Dict[str, str]]:
    records = sheet_dicts(read_xlsx(session.get(SOURCE)), header_row=1)
    if not records or "Physical Address" not in records[0]:
        raise RuntimeError(f"TX: unexpected layout (header row 1) in {SOURCE}")
    return [
        make_row(
            STATE,
            name=r.get("Facility Name"),
            street=r.get("Physical Address"),
            city=r.get("Physical Address CITY"),
            zip=r.get("Physical Address Zipcode"),
            capacity=r.get("Total Licensed Capacity"),
            license_id=r.get("License No"),
            license_type=f"Assisted Living {r.get('Service  Type', '')}".strip(),
            status="Licensed"
            if r.get("Facility  Licensed", "").upper() == "YES"
            else "",
        )
        for r in records
    ]
