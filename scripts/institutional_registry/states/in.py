"""Indiana: licensed residential care facilities (Indiana Department of Health, QAMIS directory).

Indiana has no "assisted living" license; assisted-living-style housing is licensed as a
residential care facility (and "comprehensive care" is the nursing-home license, excluded). So
this static directory of residential care facilities is the source. Every listing is marked
"(Residential)" and is included; nursing/comprehensive care directories are separate pages.

Freshness: the page states "Posted to the Web on: <date>" (a monthly-ish posting); status
carries each facility's license expiration date. No capacity in this directory.
Parsing: each facility is a <div class="provider"> of <p> lines: bold name, one or more street
lines, "CITY,  ZIP" (no state), then administrator/tel/fax/license lines. Administrator, phone
and fax are not carried. The page (~230 facilities) is fragile: fetch() raises if the provider
count is implausible or any block lacks a name, city/ZIP line or license number.

The module is named in_.py because `in` is a Python keyword; STATE is "IN".
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from scripts.institutional_registry.states.common import Session, make_row

STATE = "IN"
SOURCE = "https://www.in.gov/health/reports/QAMIS/resdir/wdirRes.htm"

_CITY_ZIP = re.compile(r"^(?P<city>.+?),\s*(?P<zip>\d{5}(?:-\d{4})?)?\s*$")
_NAME_TYPE = re.compile(r"^(?P<name>.*?)\s*\((?P<type>[^()]*)\)\s*$")


class _Providers(HTMLParser):
    """Collects the text of every <p> inside each <div class="provider">."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: List[List[str]] = []
        self._depth = 0  # div nesting depth inside a provider block (0 = outside)
        self._p: List[str] = []
        self._in_p = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "div":
            if self._depth:
                self._depth += 1
            elif ("class", "provider") in attrs:
                self._depth = 1
                self.blocks.append([])
        elif tag == "p" and self._depth:
            self._in_p = True
            self._p = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_p:
            self._in_p = False
            text = re.sub(r"\s+", " ", "".join(self._p)).strip()
            if text:
                self.blocks[-1].append(text)
        elif tag == "div" and self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_p:
            self._p.append(data)


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    page = session.get_text(SOURCE)
    parser = _Providers()
    parser.feed(page)
    if not 150 <= len(parser.blocks) <= 600:
        raise RuntimeError(
            f"IN: {len(parser.blocks)} provider blocks; page structure changed?"
        )
    rows = []
    for lines in parser.blocks:
        license_line = next((x for x in lines if x.startswith("License #:")), "")
        expire_line = next((x for x in lines if x.startswith("Lic Expire Date:")), "")
        city_idx = next(
            (i for i, x in enumerate(lines) if _CITY_ZIP.match(x) and i >= 2), None
        )
        name_match = _NAME_TYPE.match(lines[0]) if lines else None
        if city_idx is None or not license_line:
            raise RuntimeError(f"IN: unparseable provider block: {lines[:4]}")
        city_zip = _CITY_ZIP.match(lines[city_idx])
        assert city_zip is not None
        rows.append(
            make_row(
                STATE,
                name=name_match.group("name") if name_match else lines[0],
                street=", ".join(lines[1:city_idx]),
                city=city_zip.group("city"),
                zip=city_zip.group("zip"),
                license_id=license_line.split(":", 1)[1],
                license_type=(
                    name_match.group("type") if name_match else "Residential"
                ),
                status=expire_line.split(":", 1)[1] if expire_line else "",
            )
        )
    return rows
