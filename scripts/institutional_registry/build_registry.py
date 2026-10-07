"""Combine the downloaded sources into one CSV of institutional addresses and their type.

Reads the files written by `download.py` and writes
`data/institutional_registry/institutional_addresses.csv`, one row per distinct
(institution type, normalized street, ZIP5). Columns:

- institution_type: nursing_home | hospice | hospital | psychiatric_hospital |
  long_term_hospital | higher_education_campus | federal_correctional | assisted_living |
  senior_living | correctional | homeless_shelter | halfway_house (plus any type named in a
  hand-downloaded CSV under `manual/`; unknown types default to `review`)
- match_policy: `block_household_rules` (residents live there, so the address must not be used
  as a Household-tier field) or `review` (mostly offices/non-residential); see MATCH_POLICY
- name, street, city, state, zip, beds: from the first source that lists the address
  (`beds` is certified beds; blank when the source has none)
- data_collected: ISO date the data was gathered, taken from the source when it states one
  (HIFLD per-facility source date, Princeton "Date Accessed", PPI survey date, Care Compare
  processing date, Overture release) and otherwise the date the file was downloaded; the
  newest date among the sources that list the address
- match_street, match_zip5: the exact-match key (see `address_key`)
- sources, source_ids: every source/ID that listed the address, `|`-separated

Usage:
    uv run python -m scripts.institutional_registry.build_registry
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from patient_matching.normalization.address_normalizer import AddressNormalizer
from scripts.institutional_registry.download import (
    DEST,
    MANIFEST,
    MANUAL_DIR,
    STATE_LISTS_DIR,
)

OUTPUT = DEST / "institutional_addresses.csv"
# POS iQIES `prvdr_type_id` values, decoded by joining to Care Compare on CCN
# (every Care Compare nursing home is type 20, every hospice type 12).
POS_TYPES = {"20": "nursing_home", "12": "hospice"}
# Care Compare `Hospital Type` values that mean extended stays; every other type (acute
# care, critical access, children's, VA, DoD, rural emergency) stays plain "hospital".
HOSPITAL_TYPES = {
    "Psychiatric": "psychiatric_hospital",
    "Long-term": "long_term_hospital",
}
# Default policy, not a spec requirement. `block_household_rules` = residents live at the
# address, so Table 2-H rules that use Street Line must not fire on it (the patient is still
# matched by every other rule); `review` = the address is mostly offices or non-residential
# space (hospice admin offices, campus/school addresses), so blocking it automatically would
# over-block. All hospitals are blocked, as decided by the project owner, even though acute
# care patients stay briefly. Edit here to change it.
MATCH_POLICY = {
    "nursing_home": "block_household_rules",
    "federal_correctional": "block_household_rules",
    "psychiatric_hospital": "block_household_rules",
    "long_term_hospital": "block_household_rules",
    "assisted_living": "block_household_rules",
    "correctional": "block_household_rules",
    "homeless_shelter": "block_household_rules",
    "halfway_house": "block_household_rules",
    # Overture's `retirement_home` mixes nursing, assisted living, memory care and
    # independent/senior apartments with no way to tell them apart.
    "senior_living": "review",
    "hospital": "block_household_rules",
    "hospice": "review",
    "higher_education_campus": "review",
}
# Overture `taxonomy.primary` -> our institution_type. Overture's own `nursing` category is
# individual nurse practitioners, not nursing homes, so it is not used.
OVERTURE_TYPES = {
    "retirement_home": "senior_living",
    "assisted_living_facility": "assisted_living",
    "homeless_shelter": "homeless_shelter",
    "jail_or_prison": "correctional",
    "halfway_house": "halfway_house",
}
# California Community Care Licensing `TYPE` codes for Residential Care for the Elderly
# (740) and RCFE in a Continuing Care Retirement Community (741).
CA_ELDER_CARE_TYPES = {"740", "741"}
MANUAL_COLUMNS = ["institution_type", "name", "street", "city", "state", "zip"]
OUTPUT_COLUMNS = [
    "institution_type",
    "match_policy",
    "name",
    "street",
    "city",
    "state",
    "zip",
    "beds",
    "data_collected",
    "match_street",
    "match_zip5",
    "sources",
    "source_ids",
]


@dataclass(frozen=True)
class Record:
    """One facility address as listed by one source."""

    institution_type: str
    source: str
    source_id: str
    name: str
    street: str
    city: str
    state: str
    zip: str
    beds: str = ""
    collected: str = ""  # ISO date (or year) the source says its data was gathered
    match_street: str = ""
    match_zip5: str = ""

    @property
    def usable(self) -> bool:
        return self.match_street != "" and len(self.match_zip5) == 5


_NORMALIZER = AddressNormalizer()
_UNIT_RE = re.compile(
    r"(?:[,\s]+(?:SUITE|STE|UNIT|APT|APARTMENT|RM|ROOM|FLOOR|FL|BLDG|BUILDING|LOT)\b.*"
    r"|[,\s]+#\s*\w.*)$",
    re.IGNORECASE,
)


def strip_unit(street: str) -> str:
    """Drop a trailing secondary designator ('SUITE 760', '#130') and stray trailing dashes.

    scourgify leaves a unit inside line 1 when the line is stacked or unparseable, and
    CMS registries embed suites in the street field, so both sides are stripped.
    """
    return _UNIT_RE.sub("", street).strip(" -,")


def address_key(street: str, city: str, state: str, zip_code: str) -> Tuple[str, str]:
    """(normalized street line 1, ZIP5) -- the exact-match key a lookup would use.

    Goes through the engine's own AddressNormalizer so registry and patient addresses
    are canonicalized identically; the unit is not part of the key, since an
    institution's residents sit behind unit numbers.
    """
    out = _NORMALIZER.normalize_patient_addresses(
        {
            "address": [
                {
                    "line": [strip_unit(street)],
                    "city": city,
                    "state": state,
                    "postalCode": zip_code,
                }
            ]
        }
    )
    if not out or not out[0].get("line"):
        return ("", "")
    return (out[0]["line"][0], (out[0].get("postalCode") or "")[:5])


def _pad_zip(zip_code: str) -> str:
    """Some sources store ZIPs as integers and drop the leading zero ('03431' -> '3431')."""
    z = zip_code.strip()
    return z.zfill(5) if z.isdigit() and len(z) < 5 else z


def _rows(path: Path) -> Iterator[Dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")


def _iso_date(value: str) -> str:
    """'2024-08-19', '7/6/21', '6/30/2012' or an Overture release '2026-09-23.1' -> ISO date."""
    text = value.strip()
    for fmt in _DATE_FORMATS:
        for candidate in (text, text[:10]):
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
    return ""


def _file_date(path: Path) -> str:
    """Date a file was downloaded: the 'collected' date for sources that state none.

    Read from manifest.json, which download.py writes. Modification time is only a fallback
    (e.g. a hand-downloaded file in manual/), because after a git clone every committed
    file's modification time is the clone date.
    """
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        try:
            key = path.relative_to(DEST).as_posix()  # e.g. state_lists/MN.csv
        except ValueError:
            key = path.name
        entry = manifest.get(key)
        if entry:
            return str(entry["downloaded"])
    return date.fromtimestamp(path.stat().st_mtime).isoformat()


def _records(
    institution_type: str,
    source: str,
    rows: Iterable[Dict[str, str]],
    cols: Dict[str, Optional[str]],
    *,
    collected_col: Optional[str] = None,
    default_collected: str = "",
) -> Iterator[Record]:
    """Map source columns onto Record fields; `cols` values name the source column (None = blank).

    `collected` comes from `collected_col` when the row has a parseable date there, else
    `default_collected`.
    """
    for row in rows:
        get = {k: (row.get(v) or "").strip() if v else "" for k, v in cols.items()}
        collected = _iso_date(row.get(collected_col) or "") if collected_col else ""
        yield Record(
            institution_type=get.pop("institution_type", "") or institution_type,
            source=source,
            zip=_pad_zip(get.pop("zip")),
            collected=collected or default_collected,
            **get,
        )


def load_sources() -> List[Record]:
    """One Record per facility address per source (match key not yet computed)."""
    ccn = "CMS Certification Number (CCN)"
    care = {"city": "City/Town", "state": "State", "zip": "ZIP Code"}
    records: List[Record] = []

    # Care Compare (nursing homes) and POS carry a processing date per row; the rest state
    # none, so their date is when we downloaded the file (these are live "current" lists).
    records += _records(
        "nursing_home",
        "care_compare_nh",
        _rows(DEST / "care_compare_nh.csv"),
        {
            "source_id": ccn,
            "name": "Provider Name",
            "street": "Provider Address",
            "beds": "Number of Certified Beds",
            **care,
        },
        collected_col="Processing Date",
        default_collected=_file_date(DEST / "care_compare_nh.csv"),
    )
    for row in _rows(DEST / "care_compare_hospital.csv"):
        records += _records(
            HOSPITAL_TYPES.get(row["Hospital Type"], "hospital"),
            "care_compare_hospital",
            [row],
            {
                "source_id": "Facility ID",
                "name": "Facility Name",
                "street": "Address",
                "beds": None,
                **care,
            },
            default_collected=_file_date(DEST / "care_compare_hospital.csv"),
        )
    for row in _rows(DEST / "care_compare_hospice.csv"):
        row["street"] = f"{row['Address Line 1']} {row['Address Line 2']}".strip()
        records += _records(
            "hospice",
            "care_compare_hospice",
            [row],
            {
                "source_id": ccn,
                "name": "Facility Name",
                "street": "street",
                "beds": None,
                **care,
            },
            default_collected=_file_date(DEST / "care_compare_hospice.csv"),
        )
    pos_date = _file_date(DEST / "pos_iqies.csv.gz")
    for row in _rows(DEST / "pos_iqies.csv.gz"):
        if row["prvdr_type_id"] in POS_TYPES and row["pgm_trmntn_cd"] == "00":
            records += _records(
                POS_TYPES[row["prvdr_type_id"]],
                "pos_iqies",
                [row],
                {
                    "source_id": "prvdr_num",
                    "name": "fac_name",
                    "street": "st_adr",
                    "city": "city_name",
                    "state": "state_cd",
                    "zip": "zip_cd",
                    "beds": "crtfd_bed_cnt",
                },
                collected_col="processing_date",
                default_collected=pos_date,
            )
    records += _records(
        "higher_education_campus",
        "ipeds_campus",
        _rows(DEST / "ipeds_hd.csv"),
        {
            "source_id": "UNITID",
            "name": "INSTNM",
            "street": "ADDR",
            "city": "CITY",
            "state": "STABBR",
            "zip": "ZIP",
            "beds": None,
        },
        default_collected=_file_date(DEST / "ipeds_hd.csv"),
    )
    bop = json.loads((DEST / "bop.json").read_text())
    for address_type, source in (("1", "bop_physical"), ("3", "bop_mail")):
        records += _records(
            "federal_correctional",
            source,
            [a for a in bop if a.get("addressType") == address_type],
            {
                "source_id": "code",
                "name": "name",
                "street": "street",
                "city": "city",
                "state": "state",
                "zip": "zipCode",
                "beds": None,
            },
            default_collected=_file_date(DEST / "bop.json"),
        )
    return records + _load_optional_sources()


def _load_optional_sources() -> List[Record]:
    """Sources that may not have been downloaded yet; a missing file is a warning, not an error."""
    records: List[Record] = []

    alf_path = DEST / "assisted_living.csv"
    if alf_path.exists():
        records += _records(
            "assisted_living",
            "princeton_alf",
            _rows(alf_path),
            {
                "source_id": "License Number",
                "name": "Facility Name",
                "street": "Address",
                "city": "City",
                "state": "State",
                "zip": "Zip Code",
                "beds": "Capacity",
            },
            collected_col="Date Accessed",  # when each state's list was pulled (2021)
            default_collected="2021",  # ~150 rows have no date; the whole file is 2021 data
        )
    else:
        print(f"warning: {alf_path} missing; skipping assisted_living (run download)")

    hifld_path = DEST / "hifld_prisons.csv"
    if hifld_path.exists():
        for row in _rows(hifld_path):
            if row["STATUS"] == "CLOSED":
                continue
            if row["CAPACITY"].startswith("-"):  # HIFLD's -999 means "unknown"
                row["CAPACITY"] = ""
            records += _records(
                "federal_correctional" if row["TYPE"] == "FEDERAL" else "correctional",
                "hifld_prisons",
                [row],
                {
                    "source_id": "FACILITYID",
                    "name": "NAME",
                    "street": "ADDRESS",
                    "city": "CITY",
                    "state": "STATE",
                    "zip": "ZIP",
                    "beds": "CAPACITY",
                },
                collected_col="SOURCEDATE",  # per-facility date HIFLD last validated the record
            )
    else:
        print(f"warning: {hifld_path} missing; skipping HIFLD prisons (run download)")

    ppi_path = DEST / "ppi_facilities.csv"
    if ppi_path.exists():
        for row in _rows(ppi_path):
            records += _records(
                "federal_correctional" if row["type"] == "Federal" else "correctional",
                "ppi_facilities",
                [row],
                {
                    "source_id": None,
                    "name": "name",
                    "street": "address",
                    "city": "city",
                    "state": "state",
                    "zip": "zip",
                    "beds": None,  # `prisoners` is a current population, not capacity
                },
                collected_col="survey_date",
            )
    else:
        print(f"warning: {ppi_path} missing; skipping PPI facilities (run download)")

    overture_path = DEST / "overture_gq.csv"
    if overture_path.exists():
        for row in _rows(overture_path):
            if row["category"] in OVERTURE_TYPES:
                records += _records(
                    OVERTURE_TYPES[row["category"]],
                    "overture",
                    [row],
                    {
                        "source_id": "id",
                        "name": "name",
                        "street": "street",
                        "city": "city",
                        "state": "state",
                        "zip": "zip",
                        "beds": None,
                    },
                    collected_col="release",  # Overture release, e.g. 2026-09-23.1
                    default_collected=_file_date(overture_path),
                )
    else:
        print(f"warning: {overture_path} missing; skipping Overture (run download)")

    records += _load_state_assisted_living()

    manual_files = sorted(MANUAL_DIR.glob("*.csv")) if MANUAL_DIR.exists() else []
    if not manual_files:
        print(f"note: no files in {MANUAL_DIR} (see MANUAL_DOWNLOADS.md)")
    for path in manual_files:
        records += _load_manual(path)
    return records


def _strs(row: Dict[str, object]) -> Dict[str, str]:
    """JSON values can be ints or None (e.g. an integer ZIP); `_records` expects strings."""
    return {k: "" if v is None else str(v) for k, v in row.items()}


def _load_state_assisted_living() -> List[Record]:
    """Current state licensing lists (CA, MI, WI, FL), all typed `assisted_living`.

    Dated by when we downloaded them. They include small group homes (Michigan foster care
    homes with 1-12 beds, Wisconsin adult family homes), as the 2021 Princeton data does;
    `beds` carries the capacity so a consumer can filter them out.
    """
    records: List[Record] = []

    ca_path = DEST / "state_al_ca.csv"
    if ca_path.exists():
        records += _records(
            "assisted_living",
            "state_ca_ccl",
            (r for r in _rows(ca_path) if r["TYPE"] in CA_ELDER_CARE_TYPES),
            {
                "source_id": "FAC_NBR",
                "name": "NAME",
                "street": "RES_STREET_ADDR",
                "city": "RES_CITY",
                "state": "RES_STATE",
                "zip": "RES_ZIP_CODE",
                "beds": "CAPACITY",
            },
            default_collected=_file_date(ca_path),
        )

    mi_path = DEST / "state_al_mi.txt"
    if mi_path.exists():
        # No header row. Columns: county, type, license no., name, supplemental address,
        # street address, city, state, zip, phone, capacity, ... The street is in column 5,
        # or in column 4 when 5 is empty; column 4 otherwise holds a suite/unit.
        with mi_path.open(newline="", encoding="latin-1") as f:
            mi_rows = [
                {
                    "license": r[2],
                    "name": r[3],
                    "street": r[5] or r[4],
                    "city": r[6],
                    "state": r[7],
                    "zip": r[8],
                    "capacity": r[10],
                }
                for r in csv.reader(f)
                if len(r) > 10 and r[-1] == "ACTIVE"
            ]
        records += _records(
            "assisted_living",
            "state_mi_lara",
            mi_rows,
            {
                "source_id": "license",
                "name": "name",
                "street": "street",
                "city": "city",
                "state": "state",
                "zip": "zip",
                "beds": "capacity",
            },
            default_collected=_file_date(mi_path),
        )

    wi_path = DEST / "state_al_wi.json"
    if wi_path.exists():
        records += _records(
            "assisted_living",
            "state_wi_dhs",
            [_strs(r) for r in json.loads(wi_path.read_text())],
            {
                "source_id": "ASPEN_FACILITY_ID",
                "name": "FACILITY_NAME",
                "street": "ADDRESS",
                "city": "CITY",
                "state": "STATE",
                "zip": "ZIP",
                "beds": None,  # the service has no capacity field
            },
            default_collected=_file_date(wi_path),
        )

    fl_path = DEST / "state_al_fl.json"
    if fl_path.exists():
        records += _records(
            "assisted_living",
            "state_fl_ahca",
            [
                {**_strs(r), "state": "FL"}
                for r in json.loads(fl_path.read_text())
                if r.get("IsClosed") != "True"
            ],
            {
                "source_id": "FileNumber",
                "name": "Name",
                "street": "Address",
                "city": "City",
                "state": "state",
                "zip": "Zip",
                "beds": "BedCount",
            },
            default_collected=_file_date(fl_path),
        )

    # One normalized CSV per state, written by download.fetch_state_lists().
    state_lists = (
        sorted(STATE_LISTS_DIR.glob("*.csv")) if STATE_LISTS_DIR.exists() else []
    )
    for path in state_lists:
        records += _records(
            "assisted_living",
            f"state_{path.stem.lower()}",
            _rows(path),
            {
                "source_id": "license_id",
                "name": "name",
                "street": "street",
                "city": "city",
                "state": "state",
                "zip": "zip",
                "beds": "capacity",
            },
            default_collected=_file_date(path),
        )
    return records


def _load_manual(path: Path) -> List[Record]:
    """A hand-downloaded CSV in the MANUAL_DOWNLOADS.md format (one institution type per row)."""
    rows = list(_rows(path))
    missing = [c for c in MANUAL_COLUMNS if rows and c not in rows[0]]
    if missing:
        raise ValueError(
            f"{path}: missing required column(s) {missing}; expected {MANUAL_COLUMNS}"
        )
    return list(
        _records(
            "",
            f"manual:{path.name}",
            rows,
            {
                "institution_type": "institution_type",
                "source_id": None,
                "name": "name",
                "street": "street",
                "city": "city",
                "state": "state",
                "zip": "zip",
                "beds": "beds",
            },
            collected_col="data_collected",  # optional column in the manual CSV
            default_collected=_file_date(path),
        )
    )


def add_keys(records: Iterable[Record]) -> List[Record]:
    out = []
    for r in records:
        street, zip5 = address_key(r.street, r.city, r.state, r.zip)
        out.append(replace(r, match_street=street, match_zip5=zip5))
    return out


def build() -> List[Dict[str, str]]:
    """Dedupe to one row per (institution type, match key); drop rows with no usable key."""
    groups: Dict[Tuple[str, str, str], List[Record]] = {}
    dropped: Dict[str, int] = {}
    for r in add_keys(load_sources()):
        if r.usable:
            groups.setdefault(
                (r.institution_type, r.match_street, r.match_zip5), []
            ).append(r)
        else:
            dropped[r.source] = dropped.get(r.source, 0) + 1
    status_path = DEST / "state_lists_status.json"
    if status_path.exists():
        failed = sorted(
            code
            for code, s in json.loads(status_path.read_text()).items()
            if not s["ok"]
        )
        if failed:  # a failed state keeps its previous file, so its data may be stale
            print(
                f"warning: the last download did not update {', '.join(failed)}; "
                "using older files (reasons in state_lists_status.json)"
            )
    if dropped:  # rows with no street or no 5-digit ZIP can't be matched, so say so
        detail = ", ".join(f"{s} {n}" for s, n in sorted(dropped.items()))
        print(
            f"note: dropped {sum(dropped.values())} rows with no usable key: {detail}"
        )
    rows = []
    for (institution_type, match_street, match_zip5), group in sorted(groups.items()):
        first = group[0]
        rows.append(
            {
                "institution_type": institution_type,
                # A type missing from MATCH_POLICY (e.g. named in a manual CSV) defaults to review.
                "match_policy": MATCH_POLICY.get(institution_type, "review"),
                "name": first.name,
                "street": first.street,
                "city": first.city,
                "state": first.state,
                "zip": first.zip,
                "beds": first.beds,
                # Newest date among the sources listing it, so an address confirmed by a
                # current source isn't labeled with an older source's date.
                "data_collected": max((r.collected for r in group), default=""),
                "match_street": match_street,
                "match_zip5": match_zip5,
                "sources": "|".join(sorted({r.source for r in group})),
                "source_ids": "|".join(sorted({r.source_id for r in group})),
            }
        )
    return rows


def main() -> None:
    rows = build()
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUTPUT}")
    counts: Dict[Tuple[str, str], int] = {}
    for r in rows:
        key = (r["match_policy"], r["institution_type"])
        counts[key] = counts.get(key, 0) + 1
    for (policy, institution_type), n in sorted(counts.items()):
        print(f"{policy:22} {institution_type:26} {n}")


if __name__ == "__main__":
    main()
