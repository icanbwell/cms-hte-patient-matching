"""Feasibility spike for the institutional-address registry (Proposal v3.3.6, Appendix A).

Retrieves the public facility sources the proposal names, builds one normalized
registry, and measures how well exact address matching against it would work.
Everything here is public data -- no PHI -- and nothing is committed: raw downloads go
to `data/institutional_registry/` (gitignored).

Sources (see docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md for access notes and findings):
- CMS Care Compare: nursing homes, hospitals, hospices (Provider Data Catalog API, no key)
- CMS Provider of Services (POS) iQIES file (data.cms.gov catalog -> CSV, no key)
- NCES IPEDS HD directory (campus address)
- Federal Bureau of Prisons facility API (per-facility JSON, discovered from bop.gov)
HIFLD, state DOC rosters, BJS jail census and CASS validation are not retrievable
anonymously/in bulk -- see the doc.

Usage:
    uv run python scripts/institutional_address_feasibility.py fetch
    uv run python scripts/institutional_address_feasibility.py report
"""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from patient_matching.normalization.address_normalizer import AddressNormalizer

DEST = Path("data/institutional_registry")
CMS_CATALOG = "https://data.cms.gov/data.json"
PDC_DOWNLOAD = "https://data.cms.gov/provider-data/api/1/datastore/query/{id}/0/download?format=csv"
CARE_COMPARE = {
    "care_compare_nh": "4pq5-n9py",
    "care_compare_hospital": "xubh-q36u",
    "care_compare_hospice": "yc9t-dgbk",
}
BOP_LIST = "https://www.bop.gov/locations/list.jsp"
BOP_API = (
    "https://www.bop.gov/PublicInfo/execute/phyloc?todo=query&output=json&code={code}"
)
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"
# POS iQIES `prvdr_type_id` values, decoded by joining to Care Compare on CCN
# (every Care Compare nursing home is type 20, every hospice type 12).
POS_TYPES = {"20": "nursing_home", "12": "hospice"}
USER_AGENT = "Mozilla/5.0 (cms-hte-patient-matching feasibility spike)"

REGISTRY_COLUMNS = [
    "source",
    "key_id",
    "name",
    "street",
    "city",
    "state",
    "zip",
    "beds",
]


def _curl(url: str, out: Optional[Path] = None, *, timeout: int = 300) -> bytes:
    """GET `url` with curl (as scripts/fetch_onc_test_data.py does); write to `out` if given."""
    cmd = [
        "curl",
        "-sSL",
        "--fail",
        "--retry",
        "3",
        "-m",
        str(timeout),
        "-A",
        USER_AGENT,
        url,
    ]
    body = subprocess.run(cmd, check=True, capture_output=True).stdout
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
    return body


# --------------------------------------------------------------------------- fetch


def latest_pos_csv_url() -> str:
    """Resolve the newest POS iQIES CSV from the catalog (never hardcode: URLs change quarterly)."""
    catalog = json.loads(_curl(CMS_CATALOG, timeout=120))
    entries = [
        d
        for d in catalog["dataset"]
        if d["title"].startswith("Provider of Services File - Internet Quality")
    ]
    newest = max(entries, key=lambda d: d["title"].rsplit(" : ", 1)[-1])
    for dist in newest["distribution"]:
        if dist.get("mediaType") == "text/csv":
            return str(dist["downloadURL"])
    raise RuntimeError(f"no CSV distribution on {newest['title']}")


def fetch_ipeds() -> None:
    """Newest IPEDS HD file; the current year 404s until NCES publishes it."""
    for year in range(time.localtime().tm_year, time.localtime().tm_year - 4, -1):
        try:
            body = _curl(IPEDS_URL.format(year=year), timeout=120)
        except subprocess.CalledProcessError:
            continue
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            (DEST / "ipeds_hd.csv").write_bytes(zf.read(name))
        print(f"ipeds: HD{year}")
        return
    raise RuntimeError("no IPEDS HD file found for the last 4 years")


def fetch_bop() -> None:
    """BOP has no bulk export; scrape facility codes from the list page, then hit its JSON API."""
    page = _curl(BOP_LIST, timeout=60).decode("utf-8", "replace")
    codes = sorted(set(re.findall(r"/locations/institutions/([a-z0-9]+)/", page)))
    rows: List[Dict[str, Any]] = []
    for code in codes:
        data = json.loads(_curl(BOP_API.format(code=code.upper()), timeout=30))
        rows.extend(
            a for a in data.get("Addresses") or [] if a.get("addressType") == "1"
        )
        time.sleep(0.2)
    (DEST / "bop.json").write_text(json.dumps(rows))
    print(f"bop: {len(codes)} codes on list page -> {len(rows)} physical addresses")


def fetch_all() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, dataset_id in CARE_COMPARE.items():
        _curl(PDC_DOWNLOAD.format(id=dataset_id), DEST / f"{name}.csv", timeout=120)
        print(f"{name}: ok")
    _curl(latest_pos_csv_url(), DEST / "pos_iqies.csv")
    print("pos_iqies: ok")
    fetch_ipeds()
    fetch_bop()


# --------------------------------------------------------------------------- load


def _frame(source: str, df: pd.DataFrame, cols: Dict[str, str]) -> pd.DataFrame:
    out = pd.DataFrame({k: df[v] if v else "" for k, v in cols.items()})
    out.insert(0, "source", source)
    return out.reindex(columns=REGISTRY_COLUMNS).fillna("")


def load_registry() -> pd.DataFrame:
    """One row per facility address per source, columns = REGISTRY_COLUMNS."""
    frames: List[pd.DataFrame] = []

    def read(name: str) -> pd.DataFrame:
        return pd.read_csv(DEST / name, dtype=str).fillna("")

    nh = read("care_compare_nh.csv")
    frames.append(
        _frame(
            "care_compare_nh",
            nh,
            {
                "key_id": "CMS Certification Number (CCN)",
                "name": "Provider Name",
                "street": "Provider Address",
                "city": "City/Town",
                "state": "State",
                "zip": "ZIP Code",
                "beds": "Number of Certified Beds",
            },
        )
    )
    hosp = read("care_compare_hospital.csv")
    frames.append(
        _frame(
            "care_compare_hospital",
            hosp,
            {
                "key_id": "Facility ID",
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
            "care_compare_hospice",
            hospice,
            {
                "key_id": "CMS Certification Number (CCN)",
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
    frames.append(
        _frame(
            "pos_iqies",
            pos,
            {
                "key_id": "prvdr_num",
                "name": "fac_name",
                "street": "st_adr",
                "city": "city_name",
                "state": "state_cd",
                "zip": "zip_cd",
                "beds": "crtfd_bed_cnt",
            },
        )
    )

    hd = read("ipeds_hd.csv")
    frames.append(
        _frame(
            "ipeds_campus",
            hd,
            {
                "key_id": "UNITID",
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
            "bop_physical",
            bop,
            {
                "key_id": "code",
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


# --------------------------------------------------------------------------- matching

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

    Goes through the engine's own AddressNormalizer so the registry and patient
    addresses are canonicalized identically; line 2 (unit/suite) is deliberately not
    part of the key, since an institution's residents sit behind unit numbers.
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


def add_keys(registry: pd.DataFrame) -> pd.DataFrame:
    keys = [
        address_key(r.street, r.city, r.state, r.zip) for r in registry.itertuples()
    ]
    registry = registry.copy()
    registry["k_street"] = [k[0] for k in keys]
    registry["k_zip"] = [k[1] for k in keys]
    registry["usable"] = (registry["k_street"] != "") & (
        registry["k_zip"].str.len() == 5
    )
    return registry


def _md_table(rows: Iterable[Tuple[Any, ...]], header: Tuple[str, ...]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _unusable_street(street: str) -> bool:
    """True for PO boxes / rural-route style lines that carry no street number."""
    s = street.upper()
    return bool(
        re.search(r"\bP\.?\s?O\.?\s?BOX\b|\bRT\b|\bRTE\b|\bMI\b\s+[NSEW]\b|\bHWY\b", s)
    )


# --------------------------------------------------------------------------- report


def report() -> None:
    reg = add_keys(load_registry())

    print("## Registry size and usable-key rate\n")
    rows = []
    for src, g in reg.groupby("source"):
        distinct = g[g.usable].drop_duplicates(["k_street", "k_zip"])
        rows.append(
            (
                src,
                len(g),
                f"{g.usable.mean():.1%}",
                len(distinct),
                f"{(g.street.map(_unusable_street)).mean():.1%}",
            )
        )
    print(
        _md_table(
            rows,
            (
                "source",
                "rows",
                "usable key",
                "distinct addresses",
                "rural-route / PO-box style",
            ),
        )
    )
    allk = reg[reg.usable].drop_duplicates(["k_street", "k_zip"])
    print(f"\nUnion across sources: {len(allk)} distinct (street, ZIP5) keys.\n")

    # Cross-source agreement: same CCN, two sources, do the keys agree?
    print("## Same facility, two sources: do normalized keys agree?\n")
    nh = reg[reg.source == "care_compare_nh"].set_index(
        reg[reg.source == "care_compare_nh"].key_id.str.zfill(6)
    )
    pos = reg[(reg.source == "pos_iqies")]
    pos = pos.set_index(pos.key_id.str.zfill(6))
    pos = pos[~pos.index.duplicated()]
    common = nh.index.intersection(pos.index)
    a, b = nh.loc[common], pos.loc[common]
    same = (a.k_street == b.k_street) & (a.k_zip == b.k_zip) & a.usable
    print(
        f"Nursing homes in both Care Compare and POS: {len(common)}; "
        f"identical (street, ZIP5) key: {same.mean():.1%}\n"
    )
    diff = pd.DataFrame({"care_compare": a.street[~same], "pos": b.street[~same]}).head(
        8
    )
    print(
        "Sample disagreements:\n\n"
        + _md_table(diff.itertuples(index=False), ("Care Compare", "POS"))
        + "\n"
    )

    # Match robustness: perturb registry addresses the way patient records vary.
    print("## Match robustness to patient-side address variation\n")
    rng = random.Random(0)
    sample = reg[reg.usable].sample(3000, random_state=0)
    lookup = set(zip(allk.k_street, allk.k_zip))
    variants = {
        "unit appended (', APT 4B')": lambda r: (r.street + ", APT 4B", r.zip),
        "room appended (' RM 114')": lambda r: (r.street + " RM 114", r.zip),
        "lowercased": lambda r: (r.street.lower(), r.zip),
        "ZIP+4": lambda r: (r.street, r.zip[:5] + "-1234"),
        "ZIP dropped": lambda r: (r.street, ""),
        "one-char street typo": lambda r: (_typo(r.street, rng), r.zip),
    }
    rows = []
    for label, fn in variants.items():
        hits = 0
        for r in sample.itertuples():
            street, zip_code = fn(r)
            hits += address_key(street, r.city, r.state, zip_code) in lookup
        rows.append((label, f"{hits / len(sample):.1%}"))
    print(_md_table(rows, ("variation", "still matches registry")))
    print("\n(Baseline unperturbed = 100% by construction.)")


def _typo(s: str, rng: random.Random) -> str:
    if len(s) < 6:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1 :]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["fetch", "report"])
    args = parser.parse_args()
    fetch_all() if args.command == "fetch" else report()


if __name__ == "__main__":
    main()
