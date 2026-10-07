"""Combine the downloaded sources into one CSV of institutional addresses and their type.

Reads the files written by `download.py` and writes
`data/institutional_registry/institutional_addresses.csv`, one row per distinct
(institution type, normalized street, ZIP5). Columns:

- institution_type: nursing_home | hospice | hospital | higher_education_campus |
  federal_correctional
- name, street, city, state, zip, beds: from the first source that lists the address
  (`beds` is certified beds; blank when the source has none)
- match_street, match_zip5: the exact-match key (see `address_key`)
- sources, source_ids: every source/ID that listed the address, `|`-separated

Usage:
    uv run --with pandas python -m scripts.institutional_registry.build_registry
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from patient_matching.normalization.address_normalizer import AddressNormalizer
from scripts.institutional_registry.download import DEST

OUTPUT = DEST / "institutional_addresses.csv"
# POS iQIES `prvdr_type_id` values, decoded by joining to Care Compare on CCN
# (every Care Compare nursing home is type 20, every hospice type 12).
POS_TYPES = {"20": "nursing_home", "12": "hospice"}
SOURCE_COLUMNS = [
    "institution_type",
    "source",
    "source_id",
    "name",
    "street",
    "city",
    "state",
    "zip",
    "beds",
]

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


def _frame(
    institution_type: str, source: str, df: pd.DataFrame, cols: Dict[str, Optional[str]]
) -> pd.DataFrame:
    out = pd.DataFrame({k: df[v] if v else "" for k, v in cols.items()})
    out.insert(0, "source", source)
    out.insert(0, "institution_type", institution_type)
    return out.reindex(columns=SOURCE_COLUMNS).fillna("")


def load_sources() -> pd.DataFrame:
    """One row per facility address per source, columns = SOURCE_COLUMNS."""
    frames: List[pd.DataFrame] = []

    def read(name: str) -> pd.DataFrame:
        return pd.read_csv(DEST / name, dtype=str).fillna("")

    ccn = "CMS Certification Number (CCN)"
    frames.append(
        _frame(
            "nursing_home",
            "care_compare_nh",
            read("care_compare_nh.csv"),
            {
                "source_id": ccn,
                "name": "Provider Name",
                "street": "Provider Address",
                "city": "City/Town",
                "state": "State",
                "zip": "ZIP Code",
                "beds": "Number of Certified Beds",
            },
        )
    )
    frames.append(
        _frame(
            "hospital",
            "care_compare_hospital",
            read("care_compare_hospital.csv"),
            {
                "source_id": "Facility ID",
                "name": "Facility Name",
                "street": "Address",
                "city": "City/Town",
                "state": "State",
                "zip": "ZIP Code",
                "beds": None,
            },
        )
    )
    hospice = read("care_compare_hospice.csv")
    hospice = hospice.assign(
        street=(hospice["Address Line 1"] + " " + hospice["Address Line 2"]).str.strip()
    )
    frames.append(
        _frame(
            "hospice",
            "care_compare_hospice",
            hospice,
            {
                "source_id": ccn,
                "name": "Facility Name",
                "street": "street",
                "city": "City/Town",
                "state": "State",
                "zip": "ZIP Code",
                "beds": None,
            },
        )
    )

    pos = read("pos_iqies.csv")
    pos = pos[pos["prvdr_type_id"].isin(POS_TYPES) & (pos["pgm_trmntn_cd"] == "00")]
    for type_id, institution_type in POS_TYPES.items():
        frames.append(
            _frame(
                institution_type,
                "pos_iqies",
                pos[pos["prvdr_type_id"] == type_id],
                {
                    "source_id": "prvdr_num",
                    "name": "fac_name",
                    "street": "st_adr",
                    "city": "city_name",
                    "state": "state_cd",
                    "zip": "zip_cd",
                    "beds": "crtfd_bed_cnt",
                },
            )
        )

    frames.append(
        _frame(
            "higher_education_campus",
            "ipeds_campus",
            read("ipeds_hd.csv"),
            {
                "source_id": "UNITID",
                "name": "INSTNM",
                "street": "ADDR",
                "city": "CITY",
                "state": "STABBR",
                "zip": "ZIP",
                "beds": None,
            },
        )
    )
    bop = pd.DataFrame(json.loads((DEST / "bop.json").read_text()))
    frames.append(
        _frame(
            "federal_correctional",
            "bop_physical",
            bop,
            {
                "source_id": "code",
                "name": "name",
                "street": "street",
                "city": "city",
                "state": "state",
                "zip": "zipCode",
                "beds": None,
            },
        )
    )
    return pd.concat(frames, ignore_index=True)


def add_keys(sources: pd.DataFrame) -> pd.DataFrame:
    keys = [address_key(r.street, r.city, r.state, r.zip) for r in sources.itertuples()]
    out = sources.copy()
    out["match_street"] = [k[0] for k in keys]
    out["match_zip5"] = [k[1] for k in keys]
    out["usable"] = (out["match_street"] != "") & (out["match_zip5"].str.len() == 5)
    return out


def build() -> pd.DataFrame:
    """Dedupe to one row per (institution type, match key); drop rows with no usable key."""
    keyed = add_keys(load_sources())
    keyed = keyed[keyed["usable"]].drop(columns="usable")
    group = ["institution_type", "match_street", "match_zip5"]
    grouped = keyed.groupby(group, sort=True)
    first = grouped[["name", "street", "city", "state", "zip", "beds"]].first()
    first["sources"] = grouped["source"].agg(lambda s: "|".join(sorted(set(s))))
    first["source_ids"] = grouped["source_id"].agg(lambda s: "|".join(sorted(set(s))))
    return first.reset_index()[
        [
            "institution_type",
            "name",
            "street",
            "city",
            "state",
            "zip",
            "beds",
            "match_street",
            "match_zip5",
            "sources",
            "source_ids",
        ]
    ]


def main() -> None:
    registry = build()
    registry.to_csv(OUTPUT, index=False)
    print(f"wrote {len(registry)} rows to {OUTPUT}")
    print(registry["institution_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
