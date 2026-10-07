"""Kentucky: assisted living communities and personal care homes (CHFS Office of Inspector General).

Two Excel directories linked from the OIG Division of Health Care index page:
  - Assisted Living Community Directory (types ALC, ALC-DC dementia care, ALC-BH behavioral
    health; capacity is the UNITS column)
  - Personal Care Home Directory (capacity is BEDS)
Both are residential settings, so both are included. Nursing facilities, ICF/IID, adult day
and home health are separate OIG directories and not read. Administrator, owner and
telephone columns are not carried.

Quirks: addresses are already split into ADDRESS / CITY / ZIP. One dementia-care row
(Forest Hills Common) has a blank license number in the source. No status column;
directories list current licenses. Updated by the state periodically (no as-of date in
the files).
"""

from __future__ import annotations

from typing import Dict, List

from scripts.institutional_registry.states.common import (
    Session,
    make_row,
    read_xlsx,
    sheet_dicts,
)

STATE = "KY"
_BASE = "https://www.chfs.ky.gov/agencies/os/oig/dhc/Documents/"
_AL_URL = _BASE + "Assisted%20Living%20Community%20Directory.xlsx"
_PC_URL = _BASE + "Personal%20Care%20Home%20Directory.xlsx"
SOURCE = f"{_AL_URL} ; {_PC_URL}"

_AL_TYPES = {
    "ALC": "Assisted Living Community",
    "ALC-DC": "Assisted Living Community (dementia care)",
    "ALC-BH": "Assisted Living Community (behavioral health)",
}


def _load(session: Session, url: str, required: str) -> List[Dict[str, str]]:
    records = sheet_dicts(read_xlsx(session.get(url)))
    if not records or required not in records[0]:
        raise RuntimeError(f"KY: unexpected layout in {url}")
    return records


def fetch(session: Session) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in _load(session, _AL_URL, "ADDRESS"):
        code = r.get("TYPE", "")
        out.append(
            make_row(
                STATE,
                name=r.get("NAME"),
                street=r.get("ADDRESS"),
                city=r.get("CITY"),
                zip=r.get("ZIP"),
                capacity=r.get("UNITS"),
                license_id=r.get("LICENSE #"),
                license_type=_AL_TYPES.get(code, code or "Assisted Living Community"),
            )
        )
    for r in _load(session, _PC_URL, "ADDRESS"):
        out.append(
            make_row(
                STATE,
                name=r.get("NAME"),
                street=r.get("ADDRESS"),
                city=r.get("CITY"),
                zip=r.get("ZIP"),
                capacity=r.get("BEDS"),
                license_id=r.get("LICENSE #"),
                license_type="Personal Care Home",
            )
        )
    return out
