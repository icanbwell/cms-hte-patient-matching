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

import calendar
import json
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta

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


def top_n_by_count(
    names: list[str], counts: np.ndarray, n: int = 10
) -> tuple[tuple[str, float], ...]:
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
    nst = pd.read_excel(
        config.DATA_RAW / "NST-EST2025-POP.xlsx", header=None, skiprows=4
    )
    nst.columns = [
        "area",
        "base2020",
        "y2020",
        "y2021",
        "y2022",
        "y2023",
        "y2024",
        "y2025",
    ]
    nst = nst.dropna(subset=["area"])
    # Census's raw layout prefixes every real state/DC/PR row with a leading
    # "." (e.g. ".Alabama") to distinguish it from the workbook's title,
    # region/division subtotal, and footnote rows, none of which get a ".".
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
    # The Census API returns a JSON array of rows, not objects: data[0] is the
    # header row (variable names), data[1:] are the actual value rows.
    df = pd.DataFrame(data[1:], columns=data[0])
    df["B01003_001E"] = pd.to_numeric(df["B01003_001E"], errors="coerce").fillna(0)
    df = df[df["B01003_001E"] > 0]
    return df.rename(
        columns={"zip code tabulation area": "zcta", "B01003_001E": "population"}
    )


def load_mdcr_enrollment_total(year: int = config.MDCR_ENROLLMENT_YEAR) -> float:
    """Return total Medicare enrollment (person-year count) for `year` from the
    downloaded CMS Program Statistics workbook."""
    zpath = config.DATA_RAW / "mdcr_enrollment.zip"
    with zipfile.ZipFile(zpath) as z:
        with z.open(config.MDCR_ENROLLMENT_XLSX_NAME) as f:
            df = pd.read_excel(f, sheet_name="MDCR ENROLL AB 1_CPS_02ENR", header=3)
    row = df[df["Year"] == year]
    if row.empty:
        raise ValueError(f"No Medicare enrollment row found for year {year}")
    return float(row["Total Enrollment"].iloc[0])


def load_zcta_household_size() -> pd.DataFrame:
    """Return ZCTA-level household-size distribution + avg household size (ACS5 B11016/B25010)."""
    with open(config.DATA_RAW / "acs5_zcta_household_size.json") as f:
        data = json.load(f)
    # Same header-row-then-data-rows shape as load_zcta_population(); see its comment.
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
    return FieldResult(
        field, "exact", u_unbiased_a, u_simple_a, source_file, notes, top10
    )


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

    # Deliberately built from eligible names ONLY: a name below min_len must
    # get zero ball mass (see docstring), which requires the exclusion to be
    # symmetric. Matching against the full name set here would let an
    # eligible name's ball silently absorb an ineligible name's probability
    # mass (e.g. real Census data: "CHENG" would inherit all of "CHEN"'s
    # mass) without "CHEN" ever reciprocating, since ineligible names never
    # get their own ball computed -- a one-directional, inflation-only leak.
    eligible_name_set = {names[i] for i in eligible_idx}

    for i in eligible_idx:
        v = names[i]
        candidates: set[int] = set()
        # Case: some longer name's deletion equals v.
        candidates.update(deletion_index.get(v, ()))
        # Case: same-length substitution/transposition (shared deletion).
        for d in _deletions(v):
            candidates.update(deletion_index.get(d, ()))
            # Case: v's own deletion is itself a listed (shorter) name --
            # only counts if that shorter name is itself eligible.
            if d in eligible_name_set:
                candidates.add(name_to_idx[d])
        candidates.discard(i)

        mass = 0.0
        for j in candidates:
            if DamerauLevenshtein.distance(v, names[j], score_cutoff=1) <= 1:
                mass += probs[j]
        ball_mass[i] = mass

    return ball_mass


def fuzzy_u_from_ball_mass(
    counts: np.ndarray, probs: np.ndarray, ball_mass: np.ndarray, eligible: np.ndarray
) -> tuple[float, float]:
    """Combine per-name fuzzy-neighbor ball mass into (u_unbiased, u_simple).

    "Fuzzy match" is a superset of exact match (edit distance 0 or 1), so the
    eligible-name term needs both the exact-match mass (p_v^2) and the
    near-miss mass (ball_mass, which build_fuzzy_ball_mass deliberately
    excludes self/distance-0 from) -- omitting p_v^2 here would make fuzzy u
    come out *lower* than exact-match u, which is definitionally impossible.
    Short (ineligible) names fall back to exact-match probability only.
    """
    # u_simple = Sigma_v p_v * q_v, where q_v is "probability a second random
    # draw is within fuzzy distance of v": p_v (self) + ball_mass_v (others)
    # for eligible v, or just p_v (self only, no fuzzy neighbors) for short v.
    u_simple = float(
        np.sum(probs[eligible] * (probs[eligible] + ball_mass[eligible]))
        + np.sum(probs[~eligible] ** 2)
    )

    # u_unbiased is the same three-term split, but as ordered-pair counts of
    # distinct PEOPLE (not probability mass) over all N*(N-1) ordered pairs --
    # same finite-population correction as u_from_counts, just with "same
    # value" widened to "same value OR a fuzzy neighbor" for eligible names.
    n_total = counts.sum()
    pair_denom = n_total * (n_total - 1) if n_total > 1 else 1.0
    exact_pairs = np.sum(counts[eligible] * (counts[eligible] - 1))
    # ball_mass_v * n_total recovers the neighbor headcount Sigma_{w in ball(v)} n_w
    # from the neighbor probability mass; summing over every eligible v (not
    # just v < w) double-counts each unordered {v, w} pair once per direction,
    # which is exactly what "ordered pairs of distinct people" requires.
    near_miss_pairs = np.sum(counts[eligible] * (ball_mass[eligible] * n_total))
    short_pairs = np.sum(counts[~eligible] * (counts[~eligible] - 1))
    u_unbiased = (
        float((exact_pairs + near_miss_pairs + short_pairs) / pair_denom)
        if pair_denom
        else 0.0
    )
    return u_unbiased, u_simple


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

    u_unbiased, u_simple = fuzzy_u_from_ball_mass(counts, probs, ball_mass, eligible)

    notes = (
        f"Ball = names within Damerau-OSA edit distance 1 (insert/delete/substitute/"
        f"adjacent-transposition), found via a SymSpell-style deletion-neighborhood "
        f"index over the {len(names):,} listed names (>= {min_len} chars eligible: "
        f"{int(eligible.sum()):,}); verified exactly with rapidfuzz, not approximated. "
        f"Fuzzy match is edit distance <= 1, i.e. exact match (p_v^2) plus the "
        f"distance-1 near-miss ball mass. Names < {min_len} chars fall back to "
        f"exact-match probability (p_v^2) only. Restricted to listed (>=100-occurrence) "
        f"names -- same coverage caveat as the exact-match calculation applies."
    )
    top10 = top_n_by_count(names, counts, 10)
    return FieldResult(field, "fuzzy", u_unbiased, u_simple, source_file, notes, top10)


# ---------------------------------------------------------------------------
# 4 & 5. Year of birth / full DOB
# ---------------------------------------------------------------------------


def year_of_birth_u(
    agesex: pd.DataFrame, reference_year: int = 2025
) -> dict[str, FieldResult]:
    """Headline = all ages (0-100) -- this tool covers the whole population to
    be matched, not just adults; newborns and minors are real patients too.
    The adults-18+ variant is still computed and reported in `notes` as a
    reference point, since it's a commonly-cited alternative population cut.
    """
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
        f"Adults-only (18+) variant, for reference: u_unbiased={u_unbiased_adult:.3e}, "
        f"u_simple={u_simple_adult:.3e} -- higher than the all-ages headline because "
        f"excluding ages 0-17 removes birth years with a flatter, less-concentrated "
        f"distribution than the adult population's age pyramid. National population, "
        f"not a specific payer's member population -- true u could differ for an "
        f"age-skewed membership (e.g. Medicare Advantage)."
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
    """Derive full-DOB u from year-of-birth u, assuming a uniform day-within-year spread."""
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
# 5b. Widened-match variants: fuzzy DOB and initial-only first name
#
# The conservative u-values in Table 3 price EXACT agreement (and the spec's own
# fuzzy variants for names/street). The rule changes proposed in
# docs/TEST_SET_0.0.5_ACCURACY_ANALYSIS.md widen what counts as agreement, so each
# needs its own u. These are the same sum-of-squares quantity as everywhere else
# in this module, taken over the widened match set.
# ---------------------------------------------------------------------------

DOB_FUZZY_VARIANTS = ("pm1day", "swap", "dl1")


def _dob_digits(d: date) -> str:
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"


def _parse_dob_digits(s: str) -> date | None:
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def dob_neighbors(d: date, variant: str) -> set[date]:
    """Dates (other than `d`) that count as a DOB match under `variant`.

    pm1day: within one calendar day (the spec's existing DOB* tolerance).
    swap:   pm1day, plus month/day transposed (2000-03-07 <-> 2000-07-03).
    dl1:    swap, plus any date one Damerau-Levenshtein edit away on the 8-digit
            YYYYMMDD string (one digit replaced, or two adjacent digits swapped).
            Equal-length strings, so insert/delete cannot apply.
    """
    if variant not in DOB_FUZZY_VARIANTS:
        raise ValueError(f"unknown DOB variant {variant!r}")
    out: set[date] = set()
    for delta in (-1, 1):
        try:
            out.add(d + timedelta(days=delta))
        except OverflowError:
            pass
    if variant in ("swap", "dl1"):
        swapped = _parse_dob_digits(f"{d.year:04d}{d.day:02d}{d.month:02d}")
        if swapped is not None:
            out.add(swapped)
    if variant == "dl1":
        s = _dob_digits(d)
        for i in range(8):
            for c in "0123456789":
                if c != s[i]:
                    n = _parse_dob_digits(s[:i] + c + s[i + 1 :])
                    if n is not None:
                        out.add(n)
        for i in range(7):
            if s[i] != s[i + 1]:
                n = _parse_dob_digits(s[:i] + s[i + 1] + s[i] + s[i + 2 :])
                if n is not None:
                    out.add(n)
    out.discard(d)
    return out


def dob_fuzzy_u(
    agesex: pd.DataFrame, variant: str | None, reference_year: int = 2025
) -> FieldResult:
    """u for DOB agreement at the date level, exact (`variant=None`) or widened.

    u = sum over dates d of p(d) * sum over {d} + neighbors(d) of p(n), with
    p(d) = P(birth year) / days in that year (uniform within a year, as in
    `dob_full_u`). Uses real calendar lengths, so the exact (`variant=None`)
    value differs slightly from `dob_full_u`'s 365.25 approximation; the
    widened u must be compared with this function's own exact value
    (field `dob_full`, variant `exact_datelevel`) to get the multiplier.
    """
    both = agesex[(agesex["SEX"] == 0) & (agesex["AGE"] != 999)]
    pop = both[f"POPESTIMATE{reference_year}"].to_numpy(dtype=np.float64)
    years = (reference_year - both["AGE"]).to_numpy()
    pmf = {int(y): float(c) for y, c in zip(years, pop / pop.sum())}

    def days_in(y: int) -> int:
        return 366 if calendar.isleap(y) else 365

    def p_date(d: date) -> float:
        return pmf.get(d.year, 0.0) / days_in(d.year)

    u = 0.0
    n_dates = 0
    neighbor_total = 0
    for y in sorted(pmf):
        d = date(y, 1, 1)
        end = date(y, 12, 31)
        while d <= end:
            p = p_date(d)
            if variant is None:
                u += p * p
            else:
                nbrs = dob_neighbors(d, variant)
                u += p * (p + sum(p_date(n) for n in nbrs))
                neighbor_total += len(nbrs)
            n_dates += 1
            d += timedelta(days=1)
    if variant is None:
        notes = (
            "Date-level exact DOB agreement, uniform within each birth year using "
            "real calendar lengths; the baseline the widened DOB variants are "
            "divided by."
        )
        name = "exact_datelevel"
    else:
        notes = (
            f"DOB agreement widened to variant '{variant}' (see compute.dob_neighbors); "
            f"mean {neighbor_total / n_dates:.1f} neighbor dates per date. Same uniform-"
            f"within-year assumption as dob_full; neighbors in a different birth year "
            f"are weighted by that year's mass. u_unbiased = u_simple here (N is in "
            f"the hundreds of millions, so the finite-population correction is below "
            f"1e-8)."
        )
        name = f"fuzzy_{variant}"
    return FieldResult("dob_full", name, u, u, "nc-est2025-agesex-res.csv", notes)


def first_initial_u(listed: pd.DataFrame, source_file: str) -> FieldResult:
    """u for 'initial-only first name matches a full first name': two people agree
    if one record carries just the first letter and the other a name starting
    with it. That is sum over letters L of P(first letter = L)^2, over the listed
    (>=100-occurrence) first names -- same coverage caveat as the name u-values.
    """
    names = listed["name"].astype(str)
    letters = names.str.strip().str[:1].str.upper()
    counts = listed["count"].groupby(letters.to_numpy()).sum()
    counts = counts[counts.index.str.isalpha()].to_numpy(dtype=np.float64)
    u_unbiased, u_simple = u_from_counts(counts)
    notes = (
        "Probability two distinct people share a first LETTER (the match set for an "
        "initial-only first name against a full name). Distribution = counts by first "
        f"letter over the {len(listed):,} listed first names; unlisted names are "
        "ignored, so this assumes they follow the listed letter mix."
    )
    return FieldResult(
        "first_name", "initial", u_unbiased, u_simple, source_file, notes
    )


# ---------------------------------------------------------------------------
# 6. ZIP (ZCTA proxy)
# ---------------------------------------------------------------------------


def zip_u(zcta_pop: pd.DataFrame) -> FieldResult:
    """u for 5-digit ZIP, using ZCTA population as a proxy (see notes for the caveat)."""
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
    return FieldResult(
        "zip5", "exact", u_unbiased, u_simple, "acs5_zcta_population.json", notes, top10
    )


# ---------------------------------------------------------------------------
# 7. State
# ---------------------------------------------------------------------------


def state_u(state_pop: pd.DataFrame) -> dict[str, FieldResult]:
    """u for state of residence. Headline = 50 states + DC; the with-Puerto-Rico variant
    is computed too and reported in notes for reference."""
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
            "state",
            "exact",
            u_unbiased_no_pr,
            u_simple_no_pr,
            "NST-EST2025-POP.xlsx",
            notes,
            top10,
        ),
    }


# ---------------------------------------------------------------------------
# 8. City (Census places + CDPs)
# ---------------------------------------------------------------------------


def city_u(places: pd.DataFrame, national_total: float) -> FieldResult:
    """Bound (a): places/CDPs renormalized to their own total -- headline.
    Bound (b) is reported in `notes` as a lower bound (places/CDPs + the
    population outside any place/CDP, as unique singletons) -- same pattern
    as `name_exact_u`'s listed/unlisted split, needed here because places +
    CDPs (SUMLEV 162) cover only a fraction of the national population (many
    people live in unincorporated areas belonging to neither); renormalizing
    to the places-only total like bound (a) does would otherwise silently
    inflate concentration by treating that smaller population as if it were
    everyone.
    """
    counts = places["POPESTIMATE2025"].to_numpy(dtype=np.float64)
    places_total = counts.sum()
    coverage = places_total / national_total if national_total else float("nan")

    u_unbiased_a, u_simple_a = u_from_counts(counts)

    outside_places = national_total - places_total
    if outside_places > 0:
        counts_b = np.concatenate(
            [counts, np.ones(int(round(outside_places)), dtype=np.float64)]
        )
        u_unbiased_b, u_simple_b = u_from_counts(counts_b)
    else:
        u_unbiased_b, u_simple_b = u_unbiased_a, u_simple_a

    labels = (places["NAME"] + ", " + places["STNAME"]).tolist()
    top10 = top_n_by_count(labels, counts, 10)
    notes = (
        f"Headline = bound (a): places/CDPs ({len(places):,}) renormalized to their own "
        f"total, ignoring the population outside any place/CDP. Coverage = places/national "
        f"= {coverage:.4f} ({places_total:,.0f} / {national_total:,.0f}). Bound (b) lower "
        f"bound, treating everyone outside any place/CDP as unique singleton residents: "
        f"u_unbiased={u_unbiased_b:.3e}, u_simple={u_simple_b:.3e}. SUB-EST2025 incorporated "
        f"places + Census Designated Places (SUMLEV 162), July 1, 2025 estimate. Separate "
        f"caveat: this is Census place geography, not USPS mailing city -- many mailing "
        f"addresses use a ZIP's default USPS city name that differs from (or spans "
        f"multiple) Census places, which pulls in the opposite direction from the coverage "
        f"gap above (understates concentration, rather than overstating it). No HUD_TOKEN "
        f"was configured, so the alternate USPS-city-via-ZIP-crosswalk calculation was "
        f"skipped (see download.py's printed manual-setup instructions)."
    )
    return FieldResult(
        "city", "exact", u_unbiased_a, u_simple_a, "sub-est2025.csv", notes, top10
    )


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
    # B11016 splits households into "family" and "nonfamily" tables with
    # separate column codes per size; both get summed together below since a
    # co-resident pair doesn't care whether the household is a "family" in
    # the Census sense.
    size_cols = {
        1: ["B11016_010E"],
        2: ["B11016_003E", "B11016_011E"],
        3: ["B11016_004E", "B11016_012E"],
        4: ["B11016_005E", "B11016_013E"],
        5: ["B11016_006E", "B11016_014E"],
        6: ["B11016_007E", "B11016_015E"],
        7: [
            "B11016_008E",
            "B11016_016E",
        ],  # "7 or more" treated as exactly 7 (undercounts s(s-1))
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
    u_given_zip_hhdist = (
        total_pairs / total_people_pairs_denom if total_people_pairs_denom else 0.0
    )
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
# 10. Phone (co-resident landline-sharing floor, using NCHS survey data)
# ---------------------------------------------------------------------------


def phone_u(street_and_zip_result: FieldResult) -> FieldResult:
    """Co-resident landline-sharing FLOOR for phone-number agreement.

    Unlike names/DOB/ZIP, phone agreement isn't a namespace-collision question
    -- personal mobile numbers are effectively unique per person (no public
    data models two strangers randomly being assigned the same number). The
    only quantifiable sharing mechanism from public data is a landline shared
    by co-resident household members: u_phone ~= P(two distinct people are
    co-resident) * P(their shared household has a landline), using NCHS's
    household-level (not per-person) telephone-status survey for the second
    factor and `street_and_zip_result` (co-residents are, trivially, also
    same-ZIP, so that FieldResult already IS an estimate of P(co-resident))
    for the first.

    This deliberately excludes every other real-world phone-sharing
    mechanism this tool has no public data for -- a parent's mobile number
    listed for a non-co-resident child or elderly parent, a shared
    family-plan "contact" number, and mobile number reassignment (~35
    million US numbers/year per FCC 18-31, see config.py) -- so treat this
    as a lower bound, not a point estimate, same as the street-line floor
    it's built on.
    """
    p_landline_household = (
        config.NCHS_ADULT_DUAL_USER_HOUSEHOLD_PCT
        + config.NCHS_ADULT_LANDLINE_ONLY_HOUSEHOLD_PCT
    ) / 100.0
    u_unbiased = street_and_zip_result.u_unbiased * p_landline_household
    u_simple = street_and_zip_result.u_simple * p_landline_household

    notes = (
        f"Co-resident landline-sharing FLOOR, not a point estimate: "
        f"u_phone = P(co-resident) * P(shared household has a landline). "
        f"P(co-resident) = street_line_with_zip's u ({street_and_zip_result.u_unbiased:.3e} "
        f"unbiased / {street_and_zip_result.u_simple:.3e} simple), since co-residents are "
        f"trivially also same-ZIP. P(household has a landline) = {p_landline_household:.3f} "
        f"({config.NCHS_ADULT_DUAL_USER_HOUSEHOLD_PCT}% dual-user + "
        f"{config.NCHS_ADULT_LANDLINE_ONLY_HOUSEHOLD_PCT}% landline-only households among "
        f"adults, {config.NCHS_WIRELESS_SUBSTITUTION_REPORT_PERIOD}, NCHS National Health "
        f"Interview Survey Table 1, {config.NCHS_WIRELESS_SUBSTITUTION_DOI}) -- a household "
        f"property (if one resident has a landline, so does every co-resident), not an "
        f"independent per-person rate, which is why it multiplies P(co-resident) directly "
        f"rather than being squared. The remaining ~79% of adults have a personal mobile "
        f"number, effectively unique per person -- this floor has no data-backed way to "
        f"model non-co-resident sharing (e.g. a family member's number listed for someone "
        f"living elsewhere), which would push the true value higher than this floor. It also "
        f"doesn't model mobile number reassignment: {config.FCC_ANNUAL_NUMBER_REASSIGNMENT_COUNT:,} "
        f"US numbers/year are disconnected and reassigned to a new subscriber "
        f"({config.FCC_REASSIGNMENT_ORDER_CITATION}) -- a real, cited churn rate for the "
        f"numbering pool, but turning it into a u-value would require knowing how long a "
        f"record system typically goes without refreshing a patient's phone number after it "
        f"changes, which is a record-keeping-practice question with no public data source, "
        f"not a phone-network question; deliberately left unquantified rather than guessed "
        f"(see docs/LEARNINGS.md)."
    )
    return FieldResult(
        "phone",
        "exact",
        u_unbiased,
        u_simple,
        "NCHS Wireless Substitution survey (no data file) + street_line_with_zip",
        notes,
    )


# ---------------------------------------------------------------------------
# 11. Middle name (proxy: reuses the first-name distribution)
# ---------------------------------------------------------------------------


def middle_name_proxy_u(
    listed: pd.DataFrame, unlisted_count: int, source_file: str
) -> FieldResult:
    """Census publishes no middle-name frequency table. As a proxy, reuse the
    2020 first-name distribution (`listed`/`unlisted_count` from
    `load_firstnames_2020()`) under the assumption that middle names are
    drawn from roughly the same cultural name pool as first names. This is an
    approximation, not a direct measurement -- see notes.
    """
    result = name_exact_u(listed, unlisted_count, "middle_name", source_file)
    result.notes = (
        "PROXY, not a direct measurement: Census publishes no middle-name frequency "
        "table, so this reuses the first-name distribution (same source file) under "
        "the assumption that middle names are drawn from a similar cultural name pool "
        "as first names. True middle-name concentration could differ in either "
        "direction -- e.g. parents may deliberately pick a less-common middle name "
        "(lowering u), or lean on a smaller set of family/traditional names "
        "(raising u) -- and this tool cannot distinguish those effects. " + result.notes
    )
    return result


# ---------------------------------------------------------------------------
# 12. SSN / ITIN last 4 digits (closed-form; no Census data involved)
# ---------------------------------------------------------------------------


def ssn_itin_last4_u() -> dict[str, FieldResult]:
    """Closed-form u for the last 4 digits of an SSN or ITIN, valid only for
    the post-randomization (2011-06-25 onward) issuance scheme.

    SSA's SSN Randomization policy made all 9 digits (including the last-4
    "serial number") fully random over 0001-9999 (0000 is never issued) for
    SSNs issued on or after that date -- see config.SSN_RANDOMIZATION_START_DATE.
    u = 1 / 9999 under that policy.

    LIMITATION (see docs/LEARNINGS.md): before 2011-06-25, the last 4 digits
    were assigned *sequentially* within each area/group block, not randomly.
    Since most currently-insured adults were issued their SSN before that
    date, this closed-form value is only directly applicable to the
    post-2011 cohort (people issued an SSN at birth/immigration since then).
    Pooled across the full population, the true u for pre-2011 SSNs is
    likely somewhat *higher* than 1/9999, because low serial numbers
    (0001, 0002, ...) occur in every area/group block ever opened, while
    high serial numbers (9998, 9999) occur only in blocks issued to
    exhaustion -- this skews the aggregate distribution toward low values.
    Quantifying that skew would require SSA's historical "High Group List"
    cross-referenced with population-by-state/year data (the approach used
    by Acquisti & Gross, "Predicting Social Security Numbers from Public
    Data", PNAS 2009), which is out of scope for this Census/ACS-only tool.
    This function deliberately does not fabricate a blended pre/post-2011
    estimate; treat the value below as a floor for the randomized cohort
    only, not a population-wide point estimate.
    """
    u = 1.0 / config.SSN_ITIN_LAST4_VALID_VALUES
    ssn_notes = (
        f"Closed-form, not Census-derived: SSA's SSN Randomization policy "
        f"(effective {config.SSN_RANDOMIZATION_START_DATE}, "
        f"https://www.ssa.gov/employer/randomization.html) made the last 4 digits "
        f"fully random over {config.SSN_ITIN_LAST4_VALID_VALUES} possible values "
        f"(0001-9999; 0000 never issued) for SSNs issued on or after that date. "
        f"NOT valid for pre-2011 SSNs, which used sequential (non-random) serial "
        f"assignment within area/group blocks and likely have a somewhat higher "
        f"true u -- see docs/LEARNINGS.md for why this tool does not attempt to "
        f"quantify that cohort without SSA's historical High Group List data."
    )
    itin_notes = (
        f"Same closed-form math as SSN last-4 ({u:.4g} = 1/{config.SSN_ITIN_LAST4_VALID_VALUES}), "
        f"applied by analogy. Unlike SSA's SSN Randomization, the IRS has not published "
        f"an equivalent policy statement confirming ITIN serial numbers are drawn "
        f"uniformly at random, so treat this as an unverified assumption, not a "
        f"policy-backed closed form."
    )
    return {
        "ssn_last4": FieldResult(
            "ssn_last4",
            "exact",
            u,
            u,
            "SSA SSN Randomization policy (no data file)",
            ssn_notes,
        ),
        "itin_last4": FieldResult(
            "itin_last4",
            "exact",
            u,
            u,
            "assumed uniform by analogy to SSN (no data file)",
            itin_notes,
        ),
    }


# ---------------------------------------------------------------------------
# 13. MBI (namespace-size floor using CMS Medicare enrollment)
# ---------------------------------------------------------------------------


def mbi_u(
    total_enrollment: float, year: int = config.MDCR_ENROLLMENT_YEAR
) -> FieldResult:
    """Namespace-size floor: u = 1 / (total Medicare enrollment), i.e. the
    probability two randomly chosen Medicare beneficiaries happen to hold the
    same MBI, assuming perfectly unique issuance (no duplicates/typos/reissues).
    """
    u = 1.0 / total_enrollment
    notes = (
        f"Namespace-size floor, not a frequency distribution: u = 1 / N where "
        f"N = {total_enrollment:,.0f}, the CMS-reported total Medicare enrollment "
        f"(person-year count) for {year} (MDCR ENROLL AB 1, "
        f"CMS Program Statistics). This assumes perfectly unique MBI issuance; it "
        f"ignores real-world duplicate-issuance, reissuance (e.g. after an MBI is "
        f"compromised), and transcription-error collisions, which is why the "
        f"conservative floor (1e-6) is set far above this theoretical value rather "
        f"than matching it -- the floor is pricing in those operational failure "
        f"modes, not birthday-paradox-style random collision. 'Total enrollment' is "
        f"a person-year count (each beneficiary counted once per year enrolled), "
        f"which approximates but is not exactly the distinct-beneficiary count for "
        f"the year."
    )
    return FieldResult(
        "mbi", "exact", u, u, f"MDCR ENROLL AB 1-8_CPS_02ENR_{year}.xlsx", notes
    )


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
