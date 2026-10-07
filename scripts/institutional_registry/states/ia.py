"""Iowa: Dept. of Inspections, Appeals & Licensing Health Facilities Database (dia-hfd.iowa.gov).

Flow per entity type: GET / (cookie + __RequestVerificationToken), POST token + TypeVals to
/Home/EntityPublicAdvancedSearch (stores the search in the session), POST the same to
/Home/GenerateEntitySearchCsv (JSON {success, fileName}), then GET
/Report/GetSessionCsv?fName=<fileName>.

Included entity types (TypeVals):
  22  Assisted Living Programs                        (~263)
  28  Assisted Living Programs for People with Dementia (~174) - separately licensed
      programs, distinct license numbers, so not duplicates of 22
  12  Residential Care Facilities                     (~61) - residents live there with
      supervision/personal care
Excluded: 52 Boarding Homes (~15; room and board only, no care services); 23 Elder Group
Homes (returns 0 rows). Only Status == Active rows are kept (the database lists active
facilities).

Freshness: live database, current as of the fetch.
Quirks: ZIPs are sometimes 9 digits without a hyphen (503122800); they are cut to 5 digits.
Administrator name, phone, fax and email columns exist in the source and are not carried.
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "IA"
SOURCE = "https://dia-hfd.iowa.gov/ (TypeVals 22, 28, 12; Home/GenerateEntitySearchCsv)"

_BASE = "https://dia-hfd.iowa.gov"
_TYPE_VALS = {"22": 100, "28": 50, "12": 20}  # TypeVals -> minimum plausible row count
_EXPECTED_COLUMNS = {
    "Entity Name",
    "Entity Type",
    "License #",
    "Max Occupancy",
    "Address",
    "City",
    "Zip",
    "Status",
}


def _fetch_type(session: Session, type_val: str, minimum: int) -> List[Dict[str, str]]:
    html = session.get_text(_BASE + "/")
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html)
    if not token:
        raise RuntimeError("IA: anti-forgery token not found on home page")
    form = {"__RequestVerificationToken": token.group(1), "TypeVals": type_val}
    session.post(_BASE + "/Home/EntityPublicAdvancedSearch", form)
    result = json.loads(session.post(_BASE + "/Home/GenerateEntitySearchCsv", form))
    if not result.get("success") or not result.get("fileName"):
        raise RuntimeError(
            f"IA: CSV generation failed for TypeVals={type_val}: {result}"
        )
    url = (
        _BASE + "/Report/GetSessionCsv?fName=" + urllib.parse.quote(result["fileName"])
    )
    reader = csv.DictReader(io.StringIO(session.get_text(url).lstrip("﻿")))
    missing = _EXPECTED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise RuntimeError(
            f"IA: CSV for TypeVals={type_val} missing columns {sorted(missing)}"
        )
    records = list(reader)
    if len(records) < minimum:
        raise RuntimeError(
            f"IA: TypeVals={type_val} returned {len(records)} rows; expected at least {minimum}"
        )
    return records


def fetch(session: Session) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for type_val, minimum in _TYPE_VALS.items():
        for r in _fetch_type(session, type_val, minimum):
            if r["Status"].strip() != "Active":
                continue
            rows.append(
                make_row(
                    STATE,
                    name=r["Entity Name"],
                    street=r["Address"],
                    city=r["City"],
                    zip=r["Zip"].strip()[:5],
                    capacity=r["Max Occupancy"],
                    license_id=r["License #"],
                    license_type=r["Entity Type"],
                    status=r["Status"],
                )
            )
    return rows
