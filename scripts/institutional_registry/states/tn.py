"""Tennessee: Dept. of Health licensed health care facility listings (internet.health.tn.gov).

Flow per facility type: GET /facilitylistings (cookie + __RequestVerificationToken), POST the
search form (CurrentSearchModel.FacilityType=<code>, County=ALL, Name="", AffiliateOnly=No,
RadioGroup=Curr = current licensed facilities). The response is one HTML table; column 2 holds
"Name / street / City, TN ZIP / phone", column 4 holds license number, status and beds.

Included facility types (code):
  0537 Assisted Care Living Facility (~329)
  0593 Adult Care Home          - small residential homes for adults needing supervision/
                                  personal care; residents live there
  0536 Home for the Aged        - residential homes for older adults providing room and care
Excluded: 0594 TBI Residential Home and 0550 HIV Supportive Living Facility (condition-specific
programs, not general assisted living); every non-residential type in the dropdown.

Freshness: live listing of currently licensed facilities.
Quirks: column 3 (administrator, owner name and mailing address, phones) is deliberately
ignored; only the facility column is parsed. Bed counts are zero-padded ("0064"). The server
rejects non-browser user agents (Session already sends one). The page prints "Results = N",
which is cross-checked against the number of parsed rows.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "TN"
SOURCE = "https://internet.health.tn.gov/facilitylistings (types 0537, 0593, 0536)"

_URL = "https://internet.health.tn.gov/facilitylistings"
_TYPES = {
    "0537": "Assisted Care Living Facility",
    "0593": "Adult Care Home",
    "0536": "Home for the Aged",
}


class _Table(HTMLParser):
    """Collects, per <tr class="row">, the text lines of each <td> (<br>/<div> split lines)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: List[List[List[str]]] = []
        self._row: List[List[str]] = []
        self._cell: List[str] = []
        self._in_row = False
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: List) -> None:
        if tag == "tr" and "row" in (dict(attrs).get("class") or "").split():
            self._in_row, self._row = True, []
        elif tag == "td" and self._in_row:
            self._in_cell, self._cell = True, [""]
        elif tag in ("br", "div") and self._in_cell:
            self._cell.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_cell:
            self._in_cell = False
            self._row.append([ln.strip() for ln in self._cell if ln.strip()])
        elif tag == "tr" and self._in_row:
            self._in_row = False
            self.rows.append(self._row)
        elif tag == "div" and self._in_cell:
            self._cell.append("")

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell[-1] += data


_CITY_LINE = re.compile(r"^(?P<city>.+?),\s*TN\.?\s+(?P<zip>\d{5})(?:-\d{4})?$")
_PHONE = re.compile(r"^\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}$")


def _parse_facility_cell(lines: List[str]) -> Dict[str, str]:
    """['Name', '115 Woodmont Blvd', 'Nashville, TN 37205', '615-997-3033'] -> fields."""
    if lines and _PHONE.match(lines[-1]):
        lines = lines[:-1]
    city_at = next((i for i, ln in enumerate(lines) if _CITY_LINE.match(ln)), None)
    if city_at is None or city_at < 1:
        raise RuntimeError(
            f"TN: cannot find 'City, TN ZIP' line in facility cell {lines!r}"
        )
    match = _CITY_LINE.match(lines[city_at])
    assert match is not None
    street_lines = lines[1:city_at]  # may be empty if the source has no street
    return {
        "name": lines[0],
        "street": ", ".join(street_lines),
        "city": match.group("city"),
        "zip": match.group("zip"),
    }


def _fetch_type(session: Session, code: str) -> List[Dict[str, str]]:
    html = session.get_text(_URL)
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
    if not token:
        raise RuntimeError("TN: anti-forgery token not found on /facilitylistings")
    page = session.post(
        _URL,
        {
            "CurrentSearchModel.FacilityType": code,
            "CurrentSearchModel.County": "ALL",
            "CurrentSearchModel.Name": "",
            "CurrentSearchModel.AffiliateOnly": "No",
            "CurrentSearchModel.RadioGroup": "Curr",
            "__RequestVerificationToken": token.group(1),
        },
    ).decode("utf-8", "replace")
    expected = re.search(r"Results\s*=\s*(\d+)", page)
    if not expected:
        raise RuntimeError(f"TN: no 'Results = N' line in response for type {code}")
    parser = _Table()
    parser.feed(page)
    rows: List[Dict[str, str]] = []
    for cells in parser.rows:
        if len(cells) < 4:
            raise RuntimeError(
                f"TN: expected 4 cells per row, got {len(cells)}: {cells!r}"
            )
        fields = _parse_facility_cell(cells[1])
        detail = "\n".join(cells[3])
        lic = re.search(r"Facility License Number:\s*(\S+)", detail)
        status = re.search(r"Status:\s*(.+)", detail)
        beds = re.search(r"Number of Beds:\s*(\d+)", detail)
        rows.append(
            make_row(
                STATE,
                name=fields["name"],
                street=fields["street"],
                city=fields["city"],
                zip=fields["zip"],
                capacity=str(int(beds.group(1))) if beds else "",
                license_id=lic.group(1) if lic else "",
                license_type=_TYPES[code],
                status=status.group(1) if status else "",
            )
        )
    if len(rows) != int(expected.group(1)):
        raise RuntimeError(
            f"TN: type {code} parsed {len(rows)} rows but page says Results = {expected.group(1)}"
        )
    return rows


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    rows: List[Dict[str, str]] = []
    for code in _TYPES:
        rows += _fetch_type(session, code)
    if sum(1 for r in rows if r["license_type"] == _TYPES["0537"]) < 200:
        raise RuntimeError(
            "TN: far fewer assisted care living facilities than expected (~329)"
        )
    return rows
