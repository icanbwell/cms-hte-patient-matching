"""North Carolina: licensed adult care homes and family care homes (NC DHSR).

Two Excel lists from the Division of Health Service Regulation:
  - Ahlist.xlsx: adult care homes / homes for the aged (7+ beds, license prefix HAL)
  - Fchlist.xlsx: family care homes (2-6 beds, license prefix FCL)
Both are residential care where residents live, so both are included. Nursing homes, mental
health group homes and adult day programs are separate DHSR lists and not read.

Quirks: banner rows precede the header (header is row 2). The site address columns
(Site Address/City/Zip) are used, not the separate "Facility Address" columns, which are the
mailing address and differ for some family care homes. Facility name is the DBA name, falling
back to the licensee legal name. Correspondence/contact names are not read. Lists are
refreshed monthly; the as-of month ("As of 07/2026") is in the banner. No status column.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from scripts.institutional_registry.states.common import (
    Session,
    make_row,
    read_xlsx,
    sheet_dicts,
)

STATE = "NC"
_LISTS: Tuple[Tuple[str, str], ...] = (
    ("https://info.ncdhhs.gov/dhsr/data/Ahlist.xlsx", "Adult Care Home"),
    ("https://info.ncdhhs.gov/dhsr/data/Fchlist.xlsx", "Family Care Home"),
)
SOURCE = " ; ".join(url for url, _ in _LISTS)
_HEADER_ROW = 2


def fetch(session: Session) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for url, license_type in _LISTS:
        records = sheet_dicts(read_xlsx(session.get(url)), header_row=_HEADER_ROW)
        if not records or "Site Address" not in records[0]:
            raise RuntimeError(
                f"NC: unexpected layout (header row {_HEADER_ROW}) in {url}"
            )
        for r in records:
            if not r.get("License #"):
                continue  # trailing notes/footer rows
            out.append(
                make_row(
                    STATE,
                    name=r.get("DBA Name") or r.get("Name of Licensee Legal Name"),
                    street=r.get("Site Address"),
                    city=r.get("Site City"),
                    zip=r.get("Site Zip"),
                    capacity=r.get("Bed Count"),
                    license_id=r.get("License #"),
                    license_type=license_type,
                )
            )
    return out
