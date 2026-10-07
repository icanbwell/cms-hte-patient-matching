"""Minnesota: licensed assisted living facilities (MN Dept. of Health provider locator CSV API).

Included: every row of the "Assisted Living Facilities" provider group, which is Minnesota's
assisted living licensure (ALF, ALF with dementia care, and the provisional versions of both).
Residents live in all of these. Nothing is excluded: the group contains no day programs or
agencies. Nursing homes, home care, etc. are other provider groups and are not requested.

Data: the provider-profile CSV carries the licensed physical (not mailing) address, a license
number, and `alf`, the licensed ALF capacity (units/beds) for the license. The `status`
column is empty for every row; the effective/expiration dates on each row are in the future
(licenses are current), so the list is a current-licensee list.
Quirks: a facility id can carry two license numbers at one address (4 rows share 2 ids), so
the same building can appear twice; both are kept (distinct license_id). `license_type` is the
provider type (ALF / ALF dementia care / provisional), not the corporate form in the `license_type` column.
"""

from __future__ import annotations

import csv
import io
from typing import Dict, List

from scripts.institutional_registry.states.common import Session, make_row

STATE = "MN"
SOURCE = (
    "https://provider-profile-api.web.health.state.mn.us/csv?county=&city=&name=&id=&zipCode="
    "&providerGroup=Assisted%20Living%20Facilities&providerType=&miles=&limit=100000"
)


def fetch(session: Session) -> List[Dict[str, str]]:
    text = session.get_text(SOURCE).lstrip("﻿")
    if not text.startswith('"hfid"'):
        raise RuntimeError("MN provider CSV did not return the expected header")
    return [
        make_row(
            STATE,
            name=r.get("license_name") or r.get("provider_name"),
            street=r.get("physical_address"),
            city=r.get("physical_city"),
            zip=r.get("physical_zip"),
            capacity=r.get("alf"),
            license_id=r.get("license_number"),
            license_type=(r.get("provider_type") or "").title(),
            status=r.get("status"),
        )
        for r in csv.DictReader(io.StringIO(text))
    ]
