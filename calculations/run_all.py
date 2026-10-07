"""Entry point: download all raw data, compute every u-probability, and write
outputs/u_probabilities.csv and outputs/u_probabilities.md.

Checkpointing: the fuzzy name-matching step (surnames especially, ~160k
names) is the slowest part of the pipeline. Its ball-mass array is cached to
data/processed/*_ball_mass.npy keyed off the input file, so re-running after
an interruption does not repeat completed work.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

import compute
import config
import download

log_lines: list[str] = []


def _log(msg: str) -> None:
    print(msg)
    log_lines.append(msg)


def _cached_ball_mass(
    cache_name: str, names: list[str], probs: np.ndarray, min_len: int
) -> np.ndarray:
    """Load `build_fuzzy_ball_mass`'s output from disk if a same-size cache exists,
    else compute it and save it. Invalidated by a name-count mismatch (e.g. a
    re-downloaded source file with a different row count), not by content changes."""
    cache_path = config.DATA_PROCESSED / f"{cache_name}_ball_mass.npy"
    if cache_path.exists():
        arr = np.load(cache_path)
        if len(arr) == len(names):
            _log(f"  [checkpoint] loaded cached fuzzy ball mass: {cache_path.name}")
            return arr
        _log(f"  [checkpoint] cache size mismatch for {cache_path.name}, recomputing")
    _log(f"  computing fuzzy ball mass for {len(names):,} names (min_len={min_len})...")
    arr = compute.build_fuzzy_ball_mass(names, probs, min_len=min_len)
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, arr)
    _log(f"  [checkpoint] saved {cache_path.name}")
    return arr


def name_fuzzy_u_cached(
    listed: pd.DataFrame,
    field: str,
    source_file: str,
    cache_name: str,
    min_len: int = 5,
) -> compute.FieldResult:
    """Same computation as `compute.name_fuzzy_u`, but routed through `_cached_ball_mass`
    instead of always recomputing the ball mass -- kept separate (rather than adding a
    cache seam to name_fuzzy_u itself) so compute.py stays pure/IO-free and unit-testable."""
    names = listed["name"].astype(str).tolist()
    counts = listed["count"].to_numpy(dtype=np.float64)
    total = counts.sum()
    probs = counts / total

    ball_mass = _cached_ball_mass(cache_name, names, probs, min_len)
    lengths = np.array([len(nm) for nm in names])
    eligible = lengths >= min_len

    u_unbiased, u_simple = compute.fuzzy_u_from_ball_mass(
        counts, probs, ball_mass, eligible
    )

    notes = (
        f"Ball = names within Damerau-OSA edit distance 1 (insert/delete/substitute/"
        f"adjacent-transposition), found via a SymSpell-style deletion-neighborhood "
        f"index over the {len(names):,} listed names (>= {min_len} chars eligible: "
        f"{int(eligible.sum()):,}); verified exactly with rapidfuzz. Fuzzy match is edit "
        f"distance <= 1, i.e. exact match (p_v^2) plus the distance-1 near-miss ball mass. "
        f"Names < {min_len} chars fall back to exact-match probability (p_v^2) only. "
        f"Restricted to listed (>=100-occurrence) names -- same coverage caveat as the "
        f"exact-match calculation."
    )
    top10 = compute.top_n_by_count(names, counts, 10)
    return compute.FieldResult(
        field, "fuzzy", u_unbiased, u_simple, source_file, notes, top10
    )


def main(*, do_download: bool = True, do_compute: bool = True) -> None:
    """Run the pipeline. `do_download`/`do_compute` gate the download and compute steps
    independently (`--download-only` passes do_compute=False, `--compute-only` passes
    do_download=False).
    """
    _log(f"=== u-probability pipeline run started {dt.datetime.now().isoformat()} ===")

    if do_download:
        _log("\n--- Step 1: download ---")
        download.download_all()
    else:
        _log("\n--- Step 1: download skipped (--compute-only) ---")

    if not do_compute:
        _log(
            f"\n=== Pipeline run finished {dt.datetime.now().isoformat()} (download only) ==="
        )
        return

    _log("\n--- Step 2: compute ---")
    results: list[compute.FieldResult] = []

    # Last name, exact + fuzzy (2020 headline; 2010 as comparison)
    _log("Loading surnames...")
    last2020, last2020_unlisted = compute.load_lastnames_2020()
    last2010, last2010_unlisted = compute.load_surnames_2010()

    _log("Last name exact (2020)...")
    r = compute.name_exact_u(
        last2020,
        last2020_unlisted,
        "last_name",
        "Names2020_LastNames_RaceHispanic.xlsx",
    )
    results.append(r)
    _log("Last name exact (2010, comparison)...")
    r2010 = compute.name_exact_u(
        last2010, last2010_unlisted, "last_name_2010_comparison", "names_2010census.zip"
    )
    results.append(r2010)

    _log("Last name fuzzy (2020)... (checkpointed)")
    r = name_fuzzy_u_cached(
        last2020, "last_name", "Names2020_LastNames_RaceHispanic.xlsx", "lastname_2020"
    )
    results.append(r)

    # First name, exact + fuzzy (2020 Census; SSA fallback not needed since
    # first names ARE present in the 2020 release)
    _log("Loading first names (2020)...")
    first2020, first2020_unlisted = compute.load_firstnames_2020()
    _log("First name exact (2020)...")
    r = compute.name_exact_u(
        first2020, first2020_unlisted, "first_name", "Names2020_FirstNames_Sex.xlsx"
    )
    results.append(r)
    _log("First name fuzzy (2020)... (checkpointed)")
    r = name_fuzzy_u_cached(
        first2020, "first_name", "Names2020_FirstNames_Sex.xlsx", "firstname_2020"
    )
    results.append(r)

    # Widened-match variants used by the collision-feasibility check
    # (scripts/collision_feasibility.py): initial-only first name, and name fuzzy
    # matching with the 5-character minimum lowered to 4.
    _log("First name initial-only (2020)...")
    results.append(compute.first_initial_u(first2020, "Names2020_FirstNames_Sex.xlsx"))
    _log("Last name fuzzy, 4-char minimum (2020)... (checkpointed)")
    r = name_fuzzy_u_cached(
        last2020,
        "last_name",
        "Names2020_LastNames_RaceHispanic.xlsx",
        "lastname_2020_min4",
        min_len=4,
    )
    results.append(dataclasses.replace(r, variant="fuzzy_min4"))
    _log("First name fuzzy, 4-char minimum (2020)... (checkpointed)")
    r = name_fuzzy_u_cached(
        first2020,
        "first_name",
        "Names2020_FirstNames_Sex.xlsx",
        "firstname_2020_min4",
        min_len=4,
    )
    results.append(dataclasses.replace(r, variant="fuzzy_min4"))

    # Middle name (proxy: reuses the first-name distribution just loaded above)
    _log("Middle name (proxy via first-name distribution)...")
    r = compute.middle_name_proxy_u(
        first2020, first2020_unlisted, "Names2020_FirstNames_Sex.xlsx"
    )
    results.append(r)

    # Year of birth / DOB (headline = all ages; see compute.year_of_birth_u docstring)
    _log("Year of birth...")
    agesex = compute.load_agesex()
    yob = compute.year_of_birth_u(agesex)
    results.append(yob["all_ages"])
    u_adult_unbiased, u_adult_simple = yob["adults_18plus"]

    _log("DOB full (derived)...")
    dob = compute.dob_full_u(yob["all_ages"].u_unbiased, yob["all_ages"].u_simple)
    results.append(dob)
    _log("Date-level DOB exact + widened variants (pm1day, swap, dl1)...")
    results.append(compute.dob_fuzzy_u(agesex, None))
    for _variant in compute.DOB_FUZZY_VARIANTS:
        results.append(compute.dob_fuzzy_u(agesex, _variant))

    # ZIP
    _log("ZIP (ZCTA proxy)...")
    zcta_pop = compute.load_zcta_population()
    zresult = compute.zip_u(zcta_pop)
    results.append(zresult)

    # State
    _log("State...")
    state_pop = compute.load_state_pop()
    sresult = compute.state_u(state_pop)
    results.append(sresult["no_pr"])

    # City (national_total from the State step above, needed for the
    # places/CDPs coverage bound -- see compute.city_u docstring)
    _log("City (places)...")
    places = compute.load_places()
    national_total = float(
        state_pop.loc[state_pop["area"] != "Puerto Rico", "y2025"].sum()
    )
    cresult = compute.city_u(places, national_total)
    results.append(cresult)

    # Street line + ZIP
    _log("Street line + ZIP (co-resident floor)...")
    zcta_hh = compute.load_zcta_household_size()
    street = compute.street_line_and_zip_u(zcta_pop, zcta_hh, zresult)
    results.append(street["given_zip"])
    results.append(street["and_zip"])

    # Phone (co-resident landline floor via NCHS; see compute.phone_u docstring)
    _log("Phone (co-resident landline-sharing floor, NCHS survey data)...")
    results.append(compute.phone_u(street["and_zip"]))

    # SSN / ITIN last 4 (closed-form; see compute.ssn_itin_last4_u docstring
    # for the pre-2011-randomization limitation)
    _log("SSN / ITIN last 4 (closed-form, post-2011-randomization cohort only)...")
    ssn_itin = compute.ssn_itin_last4_u()
    results.append(ssn_itin["ssn_last4"])
    results.append(ssn_itin["itin_last4"])

    # MBI (namespace-size floor via CMS total Medicare enrollment)
    _log("MBI (namespace-size floor via CMS Medicare enrollment)...")
    mdcr_total = compute.load_mdcr_enrollment_total()
    results.append(compute.mbi_u(mdcr_total))

    _log("\n--- Step 3: sanity checks ---")
    warnings = compute.sanity_check(results)
    if warnings:
        for w in warnings:
            _log(f"  WARNING: {w}")
    else:
        _log("  All sanity checks passed.")

    _log("\n--- Step 4: write outputs ---")
    rows = [r.as_row() for r in results]
    df = pd.DataFrame(rows)
    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    csv_path = config.OUTPUTS / "u_probabilities.csv"
    df.to_csv(csv_path, index=False)
    _log(f"  wrote {csv_path}")

    md_path = config.OUTPUTS / "u_probabilities.md"
    _write_markdown(md_path, results, warnings, u_adult_unbiased, u_adult_simple)
    _log(f"  wrote {md_path}")

    _print_headline_table(results)

    _log(f"\n=== Pipeline run finished {dt.datetime.now().isoformat()} ===")


def _print_headline_table(results: list[compute.FieldResult]) -> None:
    print("\n--- Headline results (empirical vs. conservative u) ---")
    header = f"{'field':<24} {'variant':<8} {'u_unbiased':>12} {'conservative':>12} {'ratio':>10}"
    print(header)
    print("-" * len(header))
    for r in results:
        row = r.as_row()
        cons = (
            f"{row['current_conservative_u']:.4g}"
            if row["current_conservative_u"] is not None
            else "n/a"
        )
        ratio = (
            f"{row['ratio_current_to_empirical']:.2f}x"
            if row["ratio_current_to_empirical"] is not None
            else "n/a"
        )
        print(
            f"{row['field']:<24} {row['variant']:<8} {row['u_unbiased']:>12.4g} {cons:>12} {ratio:>10}"
        )


def _write_markdown(
    path: Path,
    results: list[compute.FieldResult],
    warnings: list[str],
    u_adult_unbiased: float,
    u_adult_simple: float,
) -> None:
    # path is always config.OUTPUTS / "u_probabilities.md" (see call site), never
    # user/remote input, but this keeps that invariant enforced rather than assumed.
    resolved = path.resolve()
    outputs_dir = config.OUTPUTS.resolve()
    if outputs_dir not in resolved.parents and resolved != outputs_dir:
        raise ValueError(f"Refusing to write outside OUTPUTS: {resolved}")

    today = dt.date.today().isoformat()
    lines: list[str] = []
    lines.append("# Empirical u-probabilities vs. conservative model values\n")
    lines.append(
        "u = probability two randomly chosen, distinct people agree on a field. "
        "`u_unbiased` uses the finite-population pairs formula "
        "`Σ n_v(n_v-1) / (N(N-1))` and is the headline number; `u_simple` is the "
        "plug-in estimator `Σ (n_v/N)^2`.\n"
    )

    lines.append("## Headline results\n")
    lines.append(
        "| Field | Variant | u_unbiased | u_simple | Conservative u | Ratio (conservative/empirical) | Source |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        row = r.as_row()
        cons = (
            f"{row['current_conservative_u']:.5g}"
            if row["current_conservative_u"] is not None
            else "n/a"
        )
        ratio = (
            f"{row['ratio_current_to_empirical']:.2f}x"
            if row["ratio_current_to_empirical"] is not None
            else "n/a"
        )
        lines.append(
            f"| {row['field']} | {row['variant']} | {row['u_unbiased']:.4g} | "
            f"{row['u_simple']:.4g} | {cons} | {ratio} | {row['source_file']} |"
        )
    lines.append("")

    lines.append("## Per-field notes and caveats\n")
    for r in results:
        lines.append(f"### {r.field} ({r.variant})\n")
        lines.append(r.notes + "\n")
        if r.top10:
            lines.append("Top 10 by frequency (value, share of listed population):\n")
            lines.append("```")
            for name, share in r.top10:
                lines.append(f"{name}: {share:.4%}")
            lines.append("```\n")

    lines.append("## Sanity checks\n")
    if warnings:
        for w in warnings:
            lines.append(f"- WARNING: {w}")
    else:
        state_lo, state_hi = config.SANITY_RANGES["state"]
        yob_lo, yob_hi = config.SANITY_RANGES["year_of_birth"]
        last_hi = config.SANITY_RANGES["last_name_exact"][1]
        lines.append(
            f"- All sanity checks passed (state u in [{state_lo}, {state_hi}], "
            f"year-of-birth u in [{yob_lo}, {yob_hi}], exact last-name u below {last_hi})."
        )
    lines.append(
        f"- Year-of-birth, adults 18+ variant, for reference: u_unbiased={u_adult_unbiased:.4g}, "
        f"u_simple={u_adult_simple:.4g}."
    )
    lines.append("")

    lines.append("## Methods\n")
    lines.append(
        "- **Exact-match names**: Census only lists names occurring >=100 times "
        "nationally (2020) or >=100 times (2010); listed names are renormalized to "
        "their own total for the headline bound (a). A lower bound (b), treating the "
        "unlisted remainder as all-singleton names, is reported in each field's notes.\n"
        "- **Fuzzy-match names**: for listed names of >=5 normalized characters, a "
        "SymSpell-style deletion-neighborhood index finds all other listed names within "
        "Damerau-OSA edit distance 1 (insert/delete/substitute/adjacent transposition); "
        "candidates are verified exactly with rapidfuzz (not approximated). Names <5 "
        "characters fall back to their exact-match probability.\n"
        "- **Year of birth**: NC-EST2025-AGESEX-RES single-year-of-age population, "
        "converted to birth year assuming the July 1, 2025 reference date.\n"
        "- **Full DOB**: u_yob / 365.25, assuming uniform distribution of birthdates "
        "within a birth year (see caveat below).\n"
        "- **ZIP**: ACS 5-year ("
        + str(config.ACS5_YEAR)
        + ") table B01003 at the ZCTA "
        "level, used as a proxy for USPS ZIP code.\n"
        "- **State**: NST-EST2025-POP, July 1, 2025 estimate, 50 states + DC headline "
        "(Puerto Rico variant also computed).\n"
        "- **City**: SUB-EST2025 incorporated places + CDPs.\n"
        "- **Street line + ZIP**: co-resident floor, P(share an address | same ZCTA) "
        "estimated two ways -- (avg household size - 1)/(population - 1) from B25010, "
        "and the full household-size distribution from B11016 -- combined with "
        "P(same ZIP) from the ZCTA population distribution. This is a FLOOR: it ignores "
        "street-name collisions between unrelated households in the same ZIP, so true "
        "street-line agreement is >= this estimate.\n"
        "- **Phone**: co-resident landline-sharing FLOOR -- P(co-resident) (from "
        "street_line_with_zip) times P(shared household has a landline) (NCHS Wireless "
        "Substitution survey, household-level). Excludes non-co-resident sharing and "
        "mobile number reassignment/recycling; see caveat below.\n"
        "- **Middle name**: PROXY -- reuses the 2020 first-name distribution (Census "
        "publishes no middle-name table); see caveat below.\n"
        "- **SSN/ITIN last 4**: closed-form 1/9999, not Census-derived; valid only for "
        "the post-2011-randomization cohort (see caveat below).\n"
        "- **MBI**: namespace-size floor u = 1/N using CMS's total Medicare enrollment "
        "(N), not a frequency distribution.\n"
    )

    lines.append("## Sources and download dates\n")
    lines.append(f"All data downloaded/re-verified on {today}.\n")
    lines.append(f"- 2010 Census surnames: {config.SURNAMES_2010_ZIP_URL}")
    lines.append(f"- 2020 Census first names: {config.FIRSTNAMES_2020_SEX_XLSX_URL}")
    lines.append(
        f"- 2020 Census last names: {config.LASTNAMES_2020_RACEHISPANIC_XLSX_URL}"
    )
    lines.append(
        f"- National single-year-of-age/sex estimates: {config.NC_EST2025_AGESEX_RES_URL}"
    )
    lines.append(f"- State population totals: {config.NST_EST2025_POP_XLSX_URL}")
    lines.append(f"- Places (SUB-EST2025): {config.SUB_EST2025_CSV_URL}")
    lines.append(
        f"- ACS {config.ACS5_YEAR} 5-year, ZCTA level (population B01003, household "
        f"size B11016/B25010, housing units B25001): {config.CENSUS_API_BASE}"
    )
    lines.append(
        "- HUD USPS ZIP crosswalk: skipped (no HUD_TOKEN configured); see download.py "
        "for manual setup instructions.\n"
    )
    lines.append(
        f"- CMS Medicare total enrollment ({config.MDCR_ENROLLMENT_YEAR}), used for "
        f"the MBI namespace-size floor: {config.MDCR_ENROLLMENT_ZIP_URL}\n"
    )
    lines.append(
        "- SSA SSN Randomization policy (used for the SSN/ITIN last-4 closed form, "
        "no data file downloaded): https://www.ssa.gov/employer/randomization.html\n"
    )
    lines.append(
        f"- NCHS Wireless Substitution survey ({config.NCHS_WIRELESS_SUBSTITUTION_REPORT_PERIOD}, "
        f"used for the phone co-resident-landline floor, no data file downloaded): "
        f"{config.NCHS_WIRELESS_SUBSTITUTION_DOI}\n"
    )
    lines.append(
        f"- {config.FCC_REASSIGNMENT_ORDER_CITATION} (cited in the phone floor's notes as a "
        f"named but deliberately unquantified gap -- mobile number reassignment -- not used "
        f"in the computed value; no data file downloaded)\n"
    )

    lines.append("## Caveats\n")
    lines.append(
        "- **Suppression**: Census name files only list names above an occurrence "
        "threshold; unlisted names are a long tail of rare names. Two bounds are given "
        "per name field (see per-field notes).\n"
        "- **ZCTA vs ZIP**: ZCTAs approximate but do not equal USPS ZIP code areas.\n"
        "- **Uniform-DOB assumption**: real birth dates are not perfectly uniform "
        "within a year (seasonal effects), so u_dob is a slight underestimate.\n"
        "- **National vs. member population**: all inputs are U.S. national "
        "population estimates, not a specific payer/provider's member population, "
        "which may have different age/geographic distributions.\n"
        "- **Street line + ZIP is a floor**: see street-line notes above.\n"
        "- **Phone is a floor**: see phone notes above -- only quantifies co-resident "
        "landline sharing, not the full universe of real-world phone-sharing scenarios.\n"
        "- **Middle name is a proxy**, not a direct measurement (see per-field notes); "
        "true middle-name concentration could be higher or lower than the first-name "
        "distribution used here.\n"
        "- **SSN/ITIN last-4 closed form covers only the post-2011-randomization "
        "cohort**: most currently-insured adults have a pre-2011 SSN, for which the "
        "last 4 digits were assigned sequentially (not randomly) within area/group "
        "blocks, and the true population-wide u is likely somewhat higher than 1/9999 "
        "(see per-field notes and docs/LEARNINGS.md).\n"
        "- **MBI is a namespace-size floor**, not an empirical frequency distribution, "
        "and ignores duplicate-issuance/reissuance/transcription-error collisions "
        "(see per-field notes).\n"
    )

    resolved.write_text("\n".join(lines))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--download-only",
        action="store_true",
        help="Download raw sources into data/raw/ and stop (no computation).",
    )
    mode.add_argument(
        "--compute-only",
        action="store_true",
        help="Skip downloading; compute u-probabilities from data/raw/ as it stands and print/write results.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(do_download=not args.compute_only, do_compute=not args.download_only)
