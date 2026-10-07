"""Shared helpers for the per-state assisted-living fetchers. Standard library only.

Each state module in this package exposes:

    STATE: str                 two-letter code
    SOURCE: str                URL(s) the data comes from, recorded in manifest.json
    fetch(session) -> list[dict]   rows built with `make_row`

`make_row` is the one normalized shape every state returns, so build_registry.py needs no
state-specific code. Fetchers do all parsing (XLSX, HTML, JSON, ArcGIS paging, form posts).
"""

from __future__ import annotations

import http.cookiejar
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Union

# Several state hosts (LA, TN, MS, WY, ...) return 403 to a bare curl or "Mozilla/5.0" UA
# and answer a full browser string.
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ROW_FIELDS = (
    "name",
    "street",
    "city",
    "state",
    "zip",
    "capacity",
    "license_id",
    "license_type",
    "status",
)


class Session:
    """HTTP client with cookies (for form/anti-forgery flows), retries and a browser UA."""

    def __init__(
        self, *, user_agent: str = CHROME_UA, timeout: int = 90, retries: int = 3
    ) -> None:
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self._headers = {
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._timeout = timeout
        self._retries = retries

    def request(
        self,
        url: str,
        *,
        data: Union[None, bytes, Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        method: Optional[str] = None,
    ) -> bytes:
        body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
        merged = {**self._headers, **(headers or {})}
        last: Optional[Exception] = None
        for attempt in range(self._retries):
            try:
                req = urllib.request.Request(
                    url, data=body, headers=merged, method=method
                )
                with self._opener.open(req, timeout=self._timeout) as resp:
                    return bytes(resp.read())
            except urllib.error.HTTPError as err:
                if err.code in (400, 401, 403, 404):  # retrying won't help
                    raise RuntimeError(f"{err.code} for {url}") from err
                last = err
            except (urllib.error.URLError, TimeoutError) as err:
                last = err
            time.sleep(2**attempt)
        raise RuntimeError(f"request failed after {self._retries} tries: {url}: {last}")

    def get(self, url: str, **kwargs: Any) -> bytes:
        return self.request(url, **kwargs)

    def post(
        self, url: str, data: Union[bytes, Dict[str, str]], **kwargs: Any
    ) -> bytes:
        return self.request(url, data=data, method="POST", **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return json.loads(self.get(url, **kwargs))

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.get(url, **kwargs).decode("utf-8", "replace")


def _clean(value: Any) -> str:
    """None -> '', 12.0 -> '12', and whitespace collapsed (sources pad fields with spaces)."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = re.sub(r"\s+", " ", str(value)).strip()
    whole = re.fullmatch(r"(-?\d+)\.0+", text)  # '13.00000' -> '13'
    return whole.group(1) if whole else text


def make_row(
    state: str,
    *,
    name: Any,
    street: Any,
    city: Any,
    zip: Any,  # noqa: A002 - matches the output column name
    capacity: Any = "",
    license_id: Any = "",
    license_type: Any = "",
    status: Any = "",
) -> Dict[str, str]:
    """One normalized facility row. `street` is the street line only (no city/state/ZIP)."""
    return {
        "name": _clean(name),
        "street": _clean(street),
        "city": _clean(city),
        "state": state,
        "zip": _clean(zip),
        "capacity": _clean(capacity),
        "license_id": _clean(license_id),
        "license_type": _clean(license_type),
        "status": _clean(status),
    }


def split_address(full: str) -> Dict[str, str]:
    """Split '1330 N SIDNEY AVE, STERLING, CO 80751' into street / city / state / zip.

    Falls back to leaving everything in `street` when the pattern doesn't match.
    """
    match = re.match(
        r"^(?P<street>.+?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Za-z]{2})\.?\s+(?P<zip>\d{5}(?:-\d{4})?)\s*$",
        full.strip(),
    )
    if not match:
        return {"street": full.strip(), "city": "", "state": "", "zip": ""}
    return match.groupdict()


# --------------------------------------------------------------------------- ArcGIS / Socrata


def arcgis_query(
    session: Session,
    layer_url: str,
    where: str = "1=1",
    *,
    out_fields: str = "*",
    page_size: int = 1000,
) -> List[Dict[str, Any]]:
    """All attribute rows of an ArcGIS REST layer matching `where`, paged by resultOffset."""
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "false",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
            "f": "json",
        }
        data = session.get_json(
            layer_url.rstrip("/") + "/query?" + urllib.parse.urlencode(params)
        )
        if "error" in data:
            raise RuntimeError(f"ArcGIS error from {layer_url}: {data['error']}")
        features = [f["attributes"] for f in data.get("features", [])]
        rows += features
        if not features or (
            len(features) < page_size and not data.get("exceededTransferLimit")
        ):
            return rows
        offset += len(features)


def socrata_rows(
    session: Session,
    resource_url: str,
    *,
    where: Optional[str] = None,
    page_size: int = 1000,
) -> List[Dict[str, Any]]:
    """All rows of a Socrata resource (e.g. https://data.pa.gov/resource/pqf4-d4xn.json)."""
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        params = {"$limit": str(page_size), "$offset": str(offset), "$order": ":id"}
        if where:
            params["$where"] = where
        page = session.get_json(resource_url + "?" + urllib.parse.urlencode(params))
        rows += page
        if len(page) < page_size:
            return rows
        offset += page_size


# --------------------------------------------------------------------------- XLSX (stdlib)

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref)
    assert letters is not None
    index = 0
    for ch in letters.group():
        index = index * 26 + ord(ch) - 64
    return index - 1


def _unescape_ooxml(text: str) -> str:
    """OOXML stores control characters as _xHHHH_ (e.g. a carriage return is _x000D_)."""
    return re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), text)


def read_xlsx(data: bytes, sheet: int = 0) -> List[List[str]]:
    """Cell text of one worksheet as a list of rows (blank cells are '').

    Reads the OOXML directly because openpyxl isn't a project dependency. Dates come back as
    Excel serial numbers; formulas as their cached value.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = [
                _unescape_ooxml("".join(t.text or "" for t in si.iter(f"{_NS}t")))
                for si in root.findall(f"{_NS}si")
            ]
        sheets = sorted(
            (
                n
                for n in zf.namelist()
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)
            ),
            key=lambda n: int(re.findall(r"\d+", n)[-1]),
        )
        tree = ET.fromstring(zf.read(sheets[sheet]))
    rows: List[List[str]] = []
    for row in tree.iter(f"{_NS}row"):
        cells: Dict[int, str] = {}
        for cell in row.findall(f"{_NS}c"):
            kind = cell.get("t")
            value = cell.find(f"{_NS}v")
            if kind == "s" and value is not None:
                text = shared[int(value.text or 0)]
            elif kind == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(f"{_NS}t"))
            else:
                text = (value.text or "") if value is not None else ""
            cells[_column_index(cell.get("r") or "A1")] = _unescape_ooxml(text)
        line = [""] * (max(cells) + 1) if cells else []
        for index, text in cells.items():
            line[index] = text
        rows.append(line)
    return rows


def sheet_dicts(
    rows: Sequence[Sequence[str]], header_row: int = 0
) -> List[Dict[str, str]]:
    """Turn `read_xlsx` rows into dicts keyed by the header row (blank headers skipped)."""
    header = [h.strip() for h in rows[header_row]]
    out = []
    for line in rows[header_row + 1 :]:
        padded = list(line) + [""] * (len(header) - len(line))
        record = {h: v for h, v in zip(header, padded) if h}
        if any(v.strip() for v in record.values()):
            out.append(record)
    return out
