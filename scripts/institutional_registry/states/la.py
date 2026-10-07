"""Louisiana: licensed adult residential care providers (LDH Health Standards Section).

Source is the monthly "Licensed Providers Report" workbook, one sheet mixing all LDH license
programs. Only PROGRAM_DESCRIPTION == "Adult Residential Care" (ARCP levels 1-4, the state's
assisted living / residential care license) is kept. Excluded: nursing homes, ICF/IID,
adult day health, home and community based services, home health, hospice, behavioral health,
hospitals, etc. (not residential care, or not licensed as such). Administrator, email and
phone columns are not read.

Quirks: the filename carries YYYY_MM and the host answers only a browser UA (Session already
sends one). The fetcher tries the current month and the previous 14 months newest-first and
uses the first that resolves; it raises if none does. LDH publishes late, so the file is
typically several months old. Level is in the facility name ("... - Level 3"); the license
type is recorded as "Adult Residential Care". No capacity column. Geographic (site) address
columns are used, not the mailing address.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

from scripts.institutional_registry.states.common import (
    Session,
    make_row,
    read_xlsx,
    sheet_dicts,
)

STATE = "LA"
_BASE = "https://ldh.la.gov/assets/medicaid/hss/docs/DirectorySpreadsheets/"
SOURCE = _BASE + "Licensed_Providers_Report_YYYY_MM.xlsx (newest month that resolves)"
_PROGRAM = "Adult Residential Care"
_MONTHS_BACK = 15

# Set by fetch() to the URL actually used, for the run log.
resolved_url: Optional[str] = None


def _candidate_urls(today: datetime.date) -> List[str]:
    urls = []
    year, month = today.year, today.month
    for _ in range(_MONTHS_BACK):
        urls.append(f"{_BASE}Licensed_Providers_Report_{year}_{month:02d}.xlsx")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return urls


def fetch(session: Session) -> List[Dict[str, str]]:
    global resolved_url
    data = None
    errors = []
    for url in _candidate_urls(datetime.date.today()):
        try:
            data = session.get(url)
        except RuntimeError as err:  # 404 for months not published yet
            errors.append(str(err))
            continue
        if data[:2] == b"PK":  # an xlsx, not an HTML error page
            resolved_url = url
            break
        data = None
    if data is None:
        raise RuntimeError(
            f"LA: no Licensed_Providers_Report resolved; tried {len(errors)} months"
        )
    records = sheet_dicts(read_xlsx(data))
    if not records or "PROGRAM_DESCRIPTION" not in records[0]:
        raise RuntimeError(f"LA: unexpected layout in {resolved_url}")
    return [
        make_row(
            STATE,
            name=r.get("FACILITY_NAME"),
            street=r.get("GEOGRAPHICAL_STREET"),
            city=r.get("GEOGRAPHICAL_CITY"),
            zip=r.get("GEOGRAPHICAL_ZIP"),
            license_id=r.get("LICENSURE_NUM") or r.get("STATE_ID"),
            license_type=_PROGRAM,
        )
        for r in records
        if r.get("PROGRAM_DESCRIPTION", "").strip() == _PROGRAM
    ]
