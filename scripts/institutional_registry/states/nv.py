"""Nevada: DPBH Health Care Quality and Compliance licensee search ("CLICs"), public search.

There is no bulk file. The public search is a stateful ASP.NET WebForms page: pick business
unit "Health Facilities" (HHF), then license type AGC ("Residential Facility for Groups"),
search, then page through a 10-row grid with __doPostBack-style requests, each reusing the
previous response's ViewState. About 45 pages.

Included: AGC, Residential Facility for Groups, which is the license Nevada uses for assisted
living and group residential homes, with Status Active only (all 441 rows returned on
2026-10-06 were Active, but the filter is kept in case the search starts returning inactive
licenses). Other license types the search offers (HIC, SNF, ...) are not used.

Why curl: Python's certificate store can't verify this host's chain ("unable to get local
issuer certificate") although curl, using the system trust store, can. TLS verification is
kept on, so requests go through curl with a cookie jar instead of urllib.

Quirks: the address is ONE string ("5217 W. GOWAN RD. LAS VEGAS, NV 89130") with no comma
before the city, so it is split with scourgify (a project dependency). The contact person's
name and phone are deliberately not read. The fetch raises if the number of rows collected
doesn't match the "N records" total the page reports.
"""

from __future__ import annotations

import html
import math
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from scourgify import normalize_address_record

from scripts.institutional_registry.states.common import CHROME_UA, Session, make_row

STATE = "NV"
SOURCE = "https://nvdpbh.aithent.com/Protected/LIC/LicenseeSearch.aspx?Program=HF&PubliSearch=Y"

_PREFIX = "ctl00$ContentPlaceHolder1$ucLicenseeSearchPublic$"
_GRID = "ctl00$ContentPlaceHolder1$ucLicenseeSearchResult$ResultsGrid"
_SEARCH_BUTTON = "ctl00$ContentPlaceHolder1$CommonLinkButton1"
_TYPE_NAME = "RESIDENTIAL FACILITY FOR GROUPS"
_PAGE_SIZE = 10


def _curl(jar: Path, url: str, data: Optional[str] = None) -> str:
    """GET, or POST `data` (urlencoded, piped on stdin: the ViewState is large), with cookies."""
    cmd = [
        "curl",
        "-sSL",
        "--fail",
        "-m",
        "90",
        "-A",
        CHROME_UA,
        "-b",
        str(jar),
        "-c",
        str(jar),
    ]
    if data is not None:
        cmd += [
            "-H",
            "Content-Type: application/x-www-form-urlencoded",
            "--data-binary",
            "@-",
        ]
    cmd.append(url)
    result = subprocess.run(
        cmd,
        input=data.encode() if data is not None else None,
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", "replace")


def _hidden_fields(page: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for tag in re.finditer(r'<input[^>]*type="hidden"[^>]*>', page):
        name = re.search(r'name="([^"]*)"', tag.group(0))
        value = re.search(r'value="([^"]*)"', tag.group(0))
        if name:
            fields[name.group(1)] = html.unescape(value.group(1)) if value else ""
    return fields


def _post(jar: Path, page: str, extra: Dict[str, str]) -> str:
    form = {**_hidden_fields(page), **extra}
    return _curl(jar, SOURCE, urllib.parse.urlencode(form))


def _cells(row_html: str) -> List[str]:
    return [
        re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
        for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
    ]


def _data_rows(page: str) -> List[List[str]]:
    """Grid rows for this license type: 14 cells with the type name in cell 1."""
    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = _cells(row_html)
        if len(cells) == 14 and cells[1] == _TYPE_NAME:
            rows.append(cells)
    return rows


def _split_address(full: str) -> Dict[str, str]:
    """'5217 W. GOWAN RD. LAS VEGAS, NV 89130' -> street, city, zip (via scourgify)."""
    try:
        parsed = normalize_address_record(full)
    except Exception as err:  # noqa: BLE001 - scourgify raises several error types
        raise ValueError(f"NV: could not split address {full!r}: {err}") from err
    street = " ".join(
        p for p in (parsed.get("address_line_1"), parsed.get("address_line_2")) if p
    )
    return {
        "street": street.title(),
        "city": (parsed.get("city") or "").title(),
        "zip": (parsed.get("postal_code") or "")[:5],
    }


def fetch(session: Session) -> List[Dict[str, str]]:
    """Return this state's facility rows in the shape defined by common.make_row."""
    del session  # requests go through curl (see module docstring)
    with tempfile.TemporaryDirectory() as tmp:
        jar = Path(tmp) / "cookies.txt"
        page = _curl(jar, SOURCE)
        page = _post(
            jar,
            page,
            {
                "__EVENTTARGET": _PREFIX + "ddlBusinessUnit",
                _PREFIX + "ddlBusinessUnit": "HHF",
            },
        )
        selected = {
            _PREFIX + "ddlBusinessUnit": "HHF",
            _PREFIX + "cmbLicenseType": "AGC",
        }
        page = _post(
            jar, page, {"__EVENTTARGET": _PREFIX + "cmbLicenseType", **selected}
        )
        page = _post(jar, page, {"__EVENTTARGET": _SEARCH_BUTTON, **selected})

        total_match = re.search(r"\d+-\d+ of (\d+) records", page)
        if not total_match:
            raise RuntimeError(
                "NV: results page has no 'N records' total; page changed?"
            )
        total = int(total_match.group(1))
        pages = math.ceil(total / _PAGE_SIZE)

        rows = _data_rows(page)
        for number in range(2, pages + 1):
            page = _post(
                jar,
                page,
                {
                    "__EVENTTARGET": _GRID,
                    "__EVENTARGUMENT": f"Page${number}",
                    **selected,
                },
            )
            rows += _data_rows(page)

    if len(rows) != total:
        raise RuntimeError(
            f"NV: collected {len(rows)} rows but the page reports {total}"
        )
    out = []
    for cells in rows:
        name, _type, credential, status, _expires, _discipline, address = cells[:7]
        if status != "Active":
            continue
        parts = _split_address(address)
        out.append(
            make_row(
                STATE,
                name=name,
                street=parts["street"],
                city=parts["city"],
                zip=parts["zip"],
                capacity=cells[11],
                license_id=credential,
                license_type="Residential Facility for Groups",
                status=status,
            )
        )
    return out
