"""Measure how well exact address matching against the institutional registry works.

Feasibility report for Proposal v3.3.6 (Appendix A); findings are written up in
docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md. Reads the files `scripts/institutional_registry/
download.py` fetched -- public data only, no PHI.

Usage:
    uv run python -m scripts.institutional_registry.download
    uv run --with pandas python -m scripts.institutional_address_feasibility
"""

from __future__ import annotations

import random
import re
from typing import Any, Iterable, Tuple

import pandas as pd

from scripts.institutional_registry.build_registry import (
    add_keys,
    address_key,
    load_sources,
)


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


def _typo(s: str, rng: random.Random) -> str:
    if len(s) < 6:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1 :]


def report() -> None:
    reg = add_keys(load_sources())

    print("## Registry size and usable-key rate\n")
    rows = []
    for src, g in reg.groupby("source"):
        distinct = g[g.usable].drop_duplicates(["match_street", "match_zip5"])
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
    allk = reg[reg.usable].drop_duplicates(["match_street", "match_zip5"])
    print(f"\nUnion across sources: {len(allk)} distinct (street, ZIP5) keys.\n")

    print("## Same facility, two sources: do normalized keys agree?\n")
    nh_all = reg[reg.source == "care_compare_nh"]
    nh = nh_all.set_index(nh_all.source_id.str.zfill(6))
    pos = reg[(reg.source == "pos_iqies")]
    pos = pos.set_index(pos.source_id.str.zfill(6))
    pos = pos[~pos.index.duplicated()]
    common = nh.index.intersection(pos.index)
    a, b = nh.loc[common], pos.loc[common]
    same = (
        (a.match_street == b.match_street) & (a.match_zip5 == b.match_zip5) & a.usable
    )
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

    print("## Match robustness to patient-side address variation\n")
    rng = random.Random(0)
    sample = reg[reg.usable].sample(3000, random_state=0)
    lookup = set(zip(allk.match_street, allk.match_zip5))
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


if __name__ == "__main__":
    report()
