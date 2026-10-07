"""Measure how well exact address matching against the institutional registry works.

Feasibility report for Proposal v3.3.6 (Appendix A); findings are written up in
docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md. Reads the files `scripts/institutional_registry/
download.py` fetched -- public data only, no PHI.

Usage:
    uv run python -m scripts.institutional_registry.download
    uv run python -m scripts.institutional_address_feasibility
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

from scripts.institutional_registry.build_registry import (
    Record,
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
    return bool(
        re.search(
            r"\bP\.?\s?O\.?\s?BOX\b|\bRT\b|\bRTE\b|\bMI\b\s+[NSEW]\b|\bHWY\b",
            street.upper(),
        )
    )


def _typo(s: str, rng: random.Random) -> str:
    if len(s) < 6:
        return s
    i = rng.randrange(1, len(s) - 1)
    return s[:i] + s[i + 1 :]


def _key(r: Record) -> Tuple[str, str]:
    return (r.match_street, r.match_zip5)


def _ccn_index(records: List[Record], source: str) -> Dict[str, Record]:
    return {r.source_id.zfill(6): r for r in reversed(records) if r.source == source}


def report() -> None:
    # Report only on the original CMS/IPEDS/BOP sources, so the numbers stay comparable
    # to the findings doc; Overture, Princeton and manual files are covered in the doc.
    core = {
        "care_compare_nh",
        "care_compare_hospital",
        "care_compare_hospice",
        "pos_iqies",
        "ipeds_campus",
        "bop_physical",
    }
    reg = [r for r in add_keys(load_sources()) if r.source in core]
    by_source: Dict[str, List[Record]] = defaultdict(list)
    for r in reg:
        by_source[r.source].append(r)

    print("## Registry size and usable-key rate\n")
    rows = []
    for src, g in sorted(by_source.items()):
        usable = [r for r in g if r.usable]
        rows.append(
            (
                src,
                len(g),
                f"{len(usable) / len(g):.1%}",
                len({_key(r) for r in usable}),
                f"{sum(_unusable_street(r.street) for r in g) / len(g):.1%}",
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
    lookup: Set[Tuple[str, str]] = {_key(r) for r in reg if r.usable}
    print(f"\nUnion across sources: {len(lookup)} distinct (street, ZIP5) keys.\n")

    print("## Same facility, two sources: do normalized keys agree?\n")
    nh = _ccn_index(reg, "care_compare_nh")
    pos = _ccn_index(reg, "pos_iqies")
    common = sorted(nh.keys() & pos.keys())
    same = [c for c in common if nh[c].usable and _key(nh[c]) == _key(pos[c])]
    print(
        f"Nursing homes in both Care Compare and POS: {len(common)}; "
        f"identical (street, ZIP5) key: {len(same) / len(common):.1%}\n"
    )
    same_set = set(same)
    diff = [(nh[c].street, pos[c].street) for c in common if c not in same_set][:8]
    print("Sample disagreements:\n\n" + _md_table(diff, ("Care Compare", "POS")) + "\n")

    print("## Match robustness to patient-side address variation\n")
    rng = random.Random(0)
    sample = rng.sample([r for r in reg if r.usable], 3000)
    variants: Dict[str, Callable[[Record], Tuple[str, str]]] = {
        "unit appended (', APT 4B')": lambda r: (r.street + ", APT 4B", r.zip),
        "room appended (' RM 114')": lambda r: (r.street + " RM 114", r.zip),
        "lowercased": lambda r: (r.street.lower(), r.zip),
        "ZIP+4": lambda r: (r.street, r.zip[:5] + "-1234"),
        "ZIP dropped": lambda r: (r.street, ""),
        "one-char street typo": lambda r: (_typo(r.street, rng), r.zip),
    }
    variant_rows: List[Tuple[str, str]] = []
    for label, fn in variants.items():
        hits = 0
        for r in sample:
            street, zip_code = fn(r)
            hits += address_key(street, r.city, r.state, zip_code) in lookup
        variant_rows.append((label, f"{hits / len(sample):.1%}"))
    print(_md_table(variant_rows, ("variation", "still matches registry")))
    print("\n(Baseline unperturbed = 100% by construction.)")


if __name__ == "__main__":
    report()
