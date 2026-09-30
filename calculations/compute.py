"""Pure functions that compute empirical u-probabilities from raw Census data.

`u = Σ p_v^2` is the probability two independently-drawn people share the same
value of a field. For a finite population of N people with n_v people sharing
value v, the *unbiased* estimator for the probability two DISTINCT people
(sampled without replacement) share a value is:

    u_unbiased = Σ n_v (n_v - 1) / (N (N - 1))

We report both the "simple" plug-in estimator (Σ (n_v/N)^2) and the unbiased
one; the unbiased one is the headline number (they are nearly identical for
N in the tens of millions, but diverge for small/blocked populations).

Every function here is a pure function of its (already-loaded) input data —
no I/O, no network calls — to keep them unit-testable. `run_all.py` wires
these to `download.py` and file loading.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz.distance import DamerauLevenshtein

import config


# ---------------------------------------------------------------------------
# Core math
# ---------------------------------------------------------------------------


def u_from_counts(counts: np.ndarray) -> tuple[float, float]:
    """Return (u_unbiased, u_simple) for an array of value counts n_v.

    u_simple    = Σ (n_v / N)^2
    u_unbiased  = Σ n_v (n_v - 1) / (N (N - 1))   [pairs of distinct people]
    """
    counts = np.asarray(counts, dtype=np.float64)
    n = counts.sum()
    if n <= 1:
        return (0.0, 0.0)
    u_simple = float(np.sum((counts / n) ** 2))
    u_unbiased = float(np.sum(counts * (counts - 1)) / (n * (n - 1)))
    return u_unbiased, u_simple


def u_from_probabilities(probs: np.ndarray) -> float:
    """Σ p_v^2 given probabilities that already sum to (approximately) 1."""
    probs = np.asarray(probs, dtype=np.float64)
    return float(np.sum(probs**2))


@dataclass
class FieldResult:
    """One field's (e.g. last_name/exact) computed u-probabilities plus reporting metadata."""

    field: str
    variant: str  # "exact" | "fuzzy"
    u_unbiased: float
    u_simple: float
    source_file: str
    notes: str = ""
    top10: tuple[tuple[str, float], ...] = field(default_factory=tuple)

    @property
    def current_conservative_u(self) -> float | None:
        return config.CONSERVATIVE_U.get((self.field, self.variant))

    @property
    def ratio_current_to_empirical(self) -> float | None:
        c = self.current_conservative_u
        if c is None or self.u_unbiased == 0:
            return None
        return c / self.u_unbiased

    def as_row(self) -> dict:
        return {
            "field": self.field,
            "variant": self.variant,
            "u_unbiased": self.u_unbiased,
            "u_simple": self.u_simple,
            "current_conservative_u": self.current_conservative_u,
            "ratio_current_to_empirical": self.ratio_current_to_empirical,
            "source_file": self.source_file,
            "notes": self.notes,
        }


def top_n_by_count(names: list[str], counts: np.ndarray, n: int = 10) -> tuple[tuple[str, float], ...]:
    """Return the top-`n` (name, share_of_total) pairs, ordered by descending count."""
    total = counts.sum()
    order = np.argsort(-counts)[:n]
    return tuple((names[i], float(counts[i] / total)) for i in order)


# ---------------------------------------------------------------------------
# Loaders (each reads one raw file into a tidy, name-agnostic shape)
# ---------------------------------------------------------------------------


def load_surnames_2010() -> tuple[pd.DataFrame, int]:
    """Return (listed_df[name, count], unlisted_count) for the 2010 surname file."""
    zpath = config.DATA_RAW / "names_2010census.zip"
    with zipfile.ZipFile(zpath) as z:
        with z.open("Names_2010Census.csv") as f:
            df = pd.read_csv(f)
    df = df.dropna(subset=["name"])
    all_other = df[df["name"] == "ALL OTHER NAMES"]
    unlisted_count = int(all_other["count"].iloc[0]) if len(all_other) else 0
    listed = df[df["name"] != "ALL OTHER NAMES"][["name", "count"]].copy()
    listed["count"] = listed["count"].astype(np.int64)
    return listed, unlisted_count


def load_lastnames_2020() -> tuple[pd.DataFrame, int]:
    """Return (listed_df[name, count], unlisted_count) for the 2020 last-names file."""
    xpath = config.DATA_RAW / "Names2020_LastNames_RaceHispanic.xlsx"
    df = pd.read_excel(xpath, header=2)
    df = df.rename(columns={"LAST NAME": "name", "FREQUENCY (COUNT)": "count"})
    df = df.dropna(subset=["name"])
    all_other = df[df["name"] == "ALL OTHER NAMES"]
    unlisted_count = int(all_other["count"].iloc[0]) if len(all_other) else 0
    listed = df[df["name"] != "ALL OTHER NAMES"][["name", "count"]].copy()
    listed["count"] = listed["count"].astype(np.int64)
    return listed, unlisted_count


def load_firstnames_2020() -> tuple[pd.DataFrame, int]:
    """Return (listed_df[name, count], unlisted_count) for the 2020 first-names file."""
    xpath = config.DATA_RAW / "Names2020_FirstNames_Sex.xlsx"
    df = pd.read_excel(xpath, header=2)
    df = df.rename(columns={"FIRST NAME": "name"})
    df = df.dropna(subset=["name"])
    df["count"] = df["MALE"].fillna(0) + df["FEMALE"].fillna(0)
    all_other = df[df["name"] == "ALL OTHER NAMES"]
    unlisted_count = int(all_other["count"].iloc[0]) if len(all_other) else 0
    listed = df[df["name"] != "ALL OTHER NAMES"][["name", "count"]].copy()
    listed["count"] = listed["count"].astype(np.int64)
    return listed, unlisted_count


def load_agesex() -> pd.DataFrame:
    """Return the national single-year-of-age-by-sex population estimates file."""
    return pd.read_csv(config.DATA_RAW / "nc-est2025-agesex-res.csv")


def load_state_pop() -> pd.DataFrame:
    """Return per-state population estimates (NST-EST2025-POP), tidied to area/y2025."""
    nst = pd.read_excel(config.DATA_RAW / "NST-EST2025-POP.xlsx", header=None, skiprows=4)
    nst.columns = ["area", "base2020", "y2020", "y2021", "y2022", "y2023", "y2024", "y2025"]
    nst = nst.dropna(subset=["area"])
    nst = nst[nst["area"].astype(str).str.startswith(".")]
    nst["area"] = nst["area"].str.lstrip(".")
    nst = nst[pd.to_numeric(nst["y2025"], errors="coerce").notna()]
    nst["y2025"] = nst["y2025"].astype(np.int64)
    return nst.reset_index(drop=True)


def load_places() -> pd.DataFrame:
    """Return incorporated places + CDPs (SUB-EST2025) as [NAME, STNAME, FUNCSTAT, POPESTIMATE2025]."""
    df = pd.read_csv(config.DATA_RAW / "sub-est2025.csv", encoding="latin1")
    # SUMLEV 162 = incorporated place or Census Designated Place (CDP);
    # FUNCSTAT distinguishes active government (A) vs statistical/CDP (S).
    places = df[df["SUMLEV"] == 162].copy()
    return places[["NAME", "STNAME", "FUNCSTAT", "POPESTIMATE2025"]]


def load_zcta_population() -> pd.DataFrame:
    """Return ZCTA-level population (ACS5 B01003) as [zcta, population], population > 0 only."""
    with open(config.DATA_RAW / "acs5_zcta_population.json") as f:
        data = json.load(f)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["B01003_001E"] = pd.to_numeric(df["B01003_001E"], errors="coerce").fillna(0)
    df = df[df["B01003_001E"] > 0]
    return df.rename(columns={"zip code tabulation area": "zcta", "B01003_001E": "population"})


def load_zcta_household_size() -> pd.DataFrame:
    """Return ZCTA-level household-size distribution + avg household size (ACS5 B11016/B25010)."""
    with open(config.DATA_RAW / "acs5_zcta_household_size.json") as f:
        data = json.load(f)
    df = pd.DataFrame(data[1:], columns=data[0])
    num_cols = [c for c in df.columns if c.startswith("B")]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df.rename(columns={"zip code tabulation area": "zcta"})


# ---------------------------------------------------------------------------
# 1 & 3. Last name / first name, exact
# ---------------------------------------------------------------------------


def name_exact_u(
    listed: pd.DataFrame, unlisted_count: int, field: str, source_file: str
) -> FieldResult:
    """Bound (a): listed names only, renormalized to their own total -- headline.
    Bound (b) is reported in `notes` as a lower bound (listed + unlisted-as-singletons).
    """
    counts = listed["count"].to_numpy(dtype=np.float64)
    listed_total = counts.sum()
    grand_total = listed_total + unlisted_count
    coverage = listed_total / grand_total if grand_total else float("nan")

    u_unbiased_a, u_simple_a = u_from_counts(counts)

    # Bound (b): unlisted remainder treated as all-singletons (each occurs once).
    if unlisted_count > 0:
        counts_b = np.concatenate([counts, np.ones(unlisted_count, dtype=np.float64)])
        u_unbiased_b, u_simple_b = u_from_counts(counts_b)
    else:
        u_unbiased_b, u_simple_b = u_unbiased_a, u_simple_a

    top10 = top_n_by_count(listed["name"].tolist(), counts, 10)
    notes = (
        f"Headline = bound (a): listed names ({len(listed):,}) renormalized to their own "
        f"total, ignoring the unlisted remainder. Coverage = listed/total population = "
        f"{coverage:.4f} ({listed_total:,.0f} / {grand_total:,.0f}). "
        f"Bound (b) lower bound, treating all unlisted individuals as unique singleton "
        f"names: u_unbiased={u_unbiased_b:.3e}, u_simple={u_simple_b:.3e}. "
        f"Names below the Census suppression threshold (<100 occurrences, or <11 for "
        f"race/ethnicity cross-tabs) are not separately listed; this is the standard "
        f"disclosure-avoidance suppression, not missing data."
    )
    return FieldResult(field, "exact", u_unbiased_a, u_simple_a, source_file, notes, top10)


# ---------------------------------------------------------------------------
# 2 & 3. Fuzzy name matching via a SymSpell-style deletion-neighborhood index
# ---------------------------------------------------------------------------


def _deletions(s: str) -> list[str]:
    return [s[:i] + s[i + 1 :] for i in range(len(s))]


def build_fuzzy_ball_mass(
    names: list[str], probs: np.ndarray, min_len: int = 5
) -> np.ndarray:
    """For each name, compute the probability mass of *other* names within
    Damerau-OSA edit distance 1 (insert/delete/substitute/adjacent-transpose).

    Uses a deletion-neighborhood index (SymSpell-style) to generate a small
    candidate set per name in O(len) lookups, then verifies true edit
    distance with rapidfuzz (only candidates within distance 1 are kept, so
    this returns exact -- not approximate -- ball masses).

    Names shorter than `min_len` get ball mass 0 (caller should blend these
    with exact-match probability instead, per the project spec).
    """
    n = len(names)
    ball_mass = np.zeros(n, dtype=np.float64)
    name_to_idx: dict[str, int] = {name: i for i, name in enumerate(names)}
    eligible_idx = [i for i, name in enumerate(names) if len(name) >= min_len]

    # deletion_index: deletion-string -> list of indices of names whose
    # deletion produces that string (only names with len >= min_len).
    deletion_index: dict[str, list[int]] = {}
    for i in eligible_idx:
        for d in _deletions(names[i]):
            deletion_index.setdefault(d, []).append(i)

    name_set = set(names)

    for i in eligible_idx:
        v = names[i]
        candidates: set[int] = set()
        # Case: some longer name's deletion equals v.
        candidates.update(deletion_index.get(v, ()))
        # Case: same-length substitution/transposition (shared deletion).
        for d in _deletions(v):
            candidates.update(deletion_index.get(d, ()))
            # Case: v's own deletion is itself a listed (shorter) name.
            if d in name_set:
                candidates.add(name_to_idx[d])
        candidates.discard(i)

        mass = 0.0
        for j in candidates:
            if DamerauLevenshtein.distance(v, names[j], score_cutoff=1) <= 1:
                mass += probs[j]
        ball_mass[i] = mass

    return ball_mass


def name_fuzzy_u(
    listed: pd.DataFrame, field: str, source_file: str, min_len: int = 5
) -> FieldResult:
    names = listed["name"].astype(str).tolist()
    counts = listed["count"].to_numpy(dtype=np.float64)
    total = counts.sum()
    probs = counts / total

    ball_mass = build_fuzzy_ball_mass(names, probs, min_len=min_len)
    lengths = np.array([len(nm) for nm in names])
    eligible = lengths >= min_len

    # Fuzzy contribution for eligible names; exact (p_v^2) for short names.
    u_simple = float(np.sum(probs[eligible] * ball_mass[eligible]) + np.sum(probs[~eligible] ** 2))

    # Unbiased version: same idea but on counts/pairs rather than probabilities.
    n_total = total
    pair_denom = n_total * (n_total - 1) if n_total > 1 else 1.0
    fuzzy_pairs = np.sum(counts[eligible] * (ball_mass[eligible] * n_total))
    short_pairs = np.sum(counts[~eligible] * (counts[~eligible] - 1))
    u_unbiased = float((fuzzy_pairs + short_pairs) / pair_denom) if pair_denom else 0.0

    notes = (
        f"Ball = names within Damerau-OSA edit distance 1 (insert/delete/substitute/"
        f"adjacent-transposition), found via a SymSpell-style deletion-neighborhood "
        f"index over the {len(names):,} listed names (>= {min_len} chars eligible: "
        f"{int(eligible.sum()):,}); verified exactly with rapidfuzz, not approximated. "
        f"Names < {min_len} chars fall back to exact-match probability (p_v^2). "
        f"Restricted to listed (>=100-occurrence) names -- same coverage caveat as the "
        f"exact-match calculation applies."
    )
    top10 = top_n_by_count(names, counts, 10)
    return FieldResult(field, "fuzzy", u_unbiased, u_simple, source_file, notes, top10)


# ---------------------------------------------------------------------------
# 4 & 5. Year of birth / full DOB
# ---------------------------------------------------------------------------


def year_of_birth_u(agesex: pd.DataFrame, reference_year: int = 2025) -> dict[str, FieldResult]:
    both = agesex[(agesex["SEX"] == 0) & (agesex["AGE"] != 999)].copy()
    pop_col = f"POPESTIMATE{reference_year}"
    both["birth_year"] = reference_year - both["AGE"]
    counts_all = both[pop_col].to_numpy(dtype=np.float64)
    u_unbiased_all, u_simple_all = u_from_counts(counts_all)

    adults = both[both["AGE"] >= 18]
    counts_adult = adults[pop_col].to_numpy(dtype=np.float64)
    u_unbiased_adult, u_simple_adult = u_from_counts(counts_adult)

    top10 = top_n_by_count(both["birth_year"].astype(str).tolist(), counts_all, 10)
    notes = (
        f"Single year of age (0-100, where AGE=100 is a '100 and over' open-ended top "
        f"bucket) from NC-EST{reference_year}-AGESEX-RES, both sexes, converted to "
        f"birth year = {reference_year} - age (as of July 1, {reference_year}). "
        f"Adults-only (18+) variant: u_unbiased={u_unbiased_adult:.3e}, "
        f"u_simple={u_simple_adult:.3e}. National population, not a specific payer's "
        f"member population -- true u could differ for an age-skewed membership "
        f"(e.g. Medicare Advantage)."
    )
    main = FieldResult(
        "year_of_birth",
        "exact",
        u_unbiased_all,
        u_simple_all,
        "nc-est2025-agesex-res.csv",
        notes,
        top10,
    )
    return {"all_ages": main, "adults_18plus": (u_unbiased_adult, u_simple_adult)}


def dob_full_u(u_yob_unbiased: float, u_yob_simple: float) -> FieldResult:
    days_per_year = 365.25
    notes = (
        "Assumes birthdates are uniformly distributed within a birth year: "
        "u_dob = u_yob / 365.25 (365.25 approximates the leap-day effect; real "
        "birth-date distributions have mild seasonal non-uniformity -- e.g. "
        "September birth clustering -- which would raise this slightly above "
        "the uniform-model estimate)."
    )
    return FieldResult(
        "dob_full",
        "exact",
        u_yob_unbiased / days_per_year,
        u_yob_simple / days_per_year,
        "derived from year_of_birth",
        notes,
    )


# ---------------------------------------------------------------------------
# 6. ZIP (ZCTA proxy)
# ---------------------------------------------------------------------------


def zip_u(zcta_pop: pd.DataFrame) -> FieldResult:
    counts = zcta_pop["population"].to_numpy(dtype=np.float64)
    u_unbiased, u_simple = u_from_counts(counts)
    top10 = top_n_by_count(zcta_pop["zcta"].tolist(), counts, 10)
    notes = (
        f"ZCTA (Census's generalized ZIP-code-like tabulation areas from ACS "
        f"{config.ACS5_YEAR} 5-year estimates, table B01003) used as a proxy for USPS "
        f"ZIP code. ZCTAs and ZIP codes are not identical: ZCTAs are built from whole "
        f"census blocks and don't track USPS ZIP boundary changes, P.O.-box-only ZIPs, "
        f"or unique-organization ZIPs, so this slightly misestimates true ZIP-code "
        f"concentration. {len(zcta_pop):,} ZCTAs with population > 0."
    )
    return FieldResult("zip5", "exact", u_unbiased, u_simple, "acs5_zcta_population.json", notes, top10)


# ---------------------------------------------------------------------------
# 7. State
# ---------------------------------------------------------------------------


def state_u(state_pop: pd.DataFrame) -> dict[str, FieldResult]:
    no_pr = state_pop[state_pop["area"] != "Puerto Rico"]
    counts_no_pr = no_pr["y2025"].to_numpy(dtype=np.float64)
    u_unbiased_no_pr, u_simple_no_pr = u_from_counts(counts_no_pr)

    counts_with_pr = state_pop["y2025"].to_numpy(dtype=np.float64)
    u_unbiased_pr, u_simple_pr = u_from_counts(counts_with_pr)

    top10 = top_n_by_count(no_pr["area"].tolist(), counts_no_pr, 10)
    notes = (
        f"NST-EST2025-POP, July 1, 2025 estimate. Headline = 50 states + DC "
        f"({len(no_pr)} areas). With Puerto Rico included ({len(state_pop)} areas): "
        f"u_unbiased={u_unbiased_pr:.3e}, u_simple={u_simple_pr:.3e}."
    )
    return {
        "no_pr": FieldResult(
            "state", "exact", u_unbiased_no_pr, u_simple_no_pr, "NST-EST2025-POP.xlsx", notes, top10
        ),
    }


# ---------------------------------------------------------------------------
# 8. City (Census places + CDPs)
# ---------------------------------------------------------------------------


def city_u(places: pd.DataFrame) -> FieldResult:
    counts = places["POPESTIMATE2025"].to_numpy(dtype=np.float64)
    u_unbiased, u_simple = u_from_counts(counts)
    labels = (places["NAME"] + ", " + places["STNAME"]).tolist()
    top10 = top_n_by_count(labels, counts, 10)
    notes = (
        f"SUB-EST2025 incorporated places + Census Designated Places (SUMLEV 162), "
        f"{len(places):,} places nationwide, July 1, 2025 estimate. Caveat: this is "
        f"Census place geography, not USPS mailing city -- many mailing addresses use "
        f"a ZIP's default USPS city name that differs from (or spans multiple) Census "
        f"places, so this likely understates true mailing-city concentration somewhat. "
        f"No HUD_TOKEN was configured, so the alternate USPS-city-via-ZIP-crosswalk "
        f"calculation was skipped (see download.py's printed manual-setup instructions)."
    )
    return FieldResult("city", "exact", u_unbiased, u_simple, "sub-est2025.csv", notes, top10)


# ---------------------------------------------------------------------------
# 9. Street line + ZIP (co-resident floor)
# ---------------------------------------------------------------------------


def street_line_and_zip_u(
    zcta_pop: pd.DataFrame, zcta_hh: pd.DataFrame, zip_result: FieldResult
) -> dict[str, FieldResult]:
    merged = zcta_pop.merge(zcta_hh, on="zcta", how="inner")
    merged = merged[merged["population"] > 1]

    # --- Avg-household-size floor: P(two distinct people, same ZCTA, share
    # an address) ~= (avg_household_size - 1) / (population - 1). ---
    h = merged["B25010_001E"].replace(0, np.nan)
    p = merged["population"]
    per_zcta_prob = ((h - 1) / (p - 1)).clip(lower=0)
    weights = p / p.sum()
    u_given_zip_avgsize = float(np.nansum(per_zcta_prob * weights))
    u_and_zip_avgsize = u_given_zip_avgsize * zip_result.u_unbiased

    # --- Household-size-distribution version, from B11016: for each ZCTA,
    # Σ_s households_of_size_s * s(s-1), summed nationally, over P(P-1). ---
    size_cols = {
        1: ["B11016_010E"],
        2: ["B11016_003E", "B11016_011E"],
        3: ["B11016_004E", "B11016_012E"],
        4: ["B11016_005E", "B11016_013E"],
        5: ["B11016_006E", "B11016_014E"],
        6: ["B11016_007E", "B11016_015E"],
        7: ["B11016_008E", "B11016_016E"],  # "7 or more" treated as exactly 7 (undercounts s(s-1))
    }
    total_pairs = 0.0
    total_people_pairs_denom = 0.0
    for _, row in merged.iterrows():
        P = row["population"]
        if P <= 1:
            continue
        s_pairs = 0.0
        for s, cols in size_cols.items():
            households_of_size_s = sum(row[c] for c in cols)
            s_pairs += households_of_size_s * s * (s - 1)
        total_pairs += s_pairs
        total_people_pairs_denom += P * (P - 1)
    u_given_zip_hhdist = total_pairs / total_people_pairs_denom if total_people_pairs_denom else 0.0
    u_and_zip_hhdist = u_given_zip_hhdist * zip_result.u_unbiased

    notes_floor = (
        "Co-resident FLOOR only: models P(two distinct people share a street address | "
        "same ZCTA) as (avg_household_size - 1) / (population - 1) via ACS B25010, "
        "population-weighted across ZCTAs, times P(same ZIP) from the ZCTA u-value. "
        "This ignores street-name collisions across different households within the "
        "same ZIP (e.g. two unrelated households both on '1st St'), so it UNDERSTATES "
        "true street-line agreement probability; treat as a lower bound, not a point "
        "estimate. u_street_given_zip (avg-size method) reported as u_simple; "
        "u_street_and_zip = u_street_given_zip * u_zip."
    )
    notes_hhdist = (
        "Same floor logic, but using the full household-size distribution (ACS B11016) "
        "instead of the ZCTA average: Σ_s households_of_size_s * s(s-1) / (P(P-1)), "
        "population-weighted implicitly via national summation. The '7-or-more-person' "
        "bucket is treated as exactly 7, which further understates the true value for "
        "that (small) subpopulation."
    )
    given_zip = FieldResult(
        "street_line_given_zip",
        "exact",
        u_given_zip_hhdist,
        u_given_zip_avgsize,
        "acs5_zcta_household_size.json + acs5_zcta_population.json",
        notes_hhdist + " u_unbiased column = household-size-distribution method; "
        "u_simple column = avg-household-size method. " + notes_floor,
    )
    and_zip = FieldResult(
        "street_line_with_zip",
        "exact",
        u_and_zip_hhdist,
        u_and_zip_avgsize,
        "acs5_zcta_household_size.json + acs5_zcta_population.json",
        notes_floor,
    )
    return {"given_zip": given_zip, "and_zip": and_zip}


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------


def sanity_check(results: list[FieldResult]) -> list[str]:
    warnings: list[str] = []
    by_key = {(r.field, r.variant): r for r in results}

    state = by_key.get(("state", "exact"))
    if state is not None:
        lo, hi = config.SANITY_RANGES["state"]
        if not (lo <= state.u_unbiased <= hi):
            warnings.append(
                f"State u_unbiased={state.u_unbiased:.4f} is outside the expected "
                f"[{lo}, {hi}] range -- investigate before reporting."
            )

    yob = by_key.get(("year_of_birth", "exact"))
    if yob is not None:
        lo, hi = config.SANITY_RANGES["year_of_birth"]
        if not (lo <= yob.u_unbiased <= hi):
            warnings.append(
                f"Year-of-birth u_unbiased={yob.u_unbiased:.4f} is outside the expected "
                f"[{lo}, {hi}] range -- investigate before reporting."
            )

    last_exact = by_key.get(("last_name", "exact"))
    if last_exact is not None:
        hi = config.SANITY_RANGES["last_name_exact"][1]
        if last_exact.u_unbiased >= hi:
            warnings.append(
                f"Exact last-name u_unbiased={last_exact.u_unbiased:.4f} is not "
                f"'well below 0.01' as expected -- investigate before reporting."
            )

    return warnings
