"""Unit tests for compute.py's pure functions, using small synthetic fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import compute
import config


# ---------------------------------------------------------------------------
# Core math: Sigma p^2 and the unbiased pair formula
# ---------------------------------------------------------------------------


def test_u_from_counts_uniform_population():
    # 4 distinct values, each occurring 25 times out of N=100.
    counts = np.array([25, 25, 25, 25], dtype=np.float64)
    u_unbiased, u_simple = compute.u_from_counts(counts)
    assert u_simple == pytest.approx(4 * (25 / 100) ** 2)
    assert u_simple == pytest.approx(0.25)
    # Unbiased: 4 * 25*24 / (100*99)
    expected_unbiased = 4 * 25 * 24 / (100 * 99)
    assert u_unbiased == pytest.approx(expected_unbiased)
    # Unbiased should be slightly less than simple for a finite population.
    assert u_unbiased < u_simple


def test_u_from_counts_single_value_is_one():
    counts = np.array([50], dtype=np.float64)
    u_unbiased, u_simple = compute.u_from_counts(counts)
    assert u_simple == pytest.approx(1.0)
    assert u_unbiased == pytest.approx(1.0)


def test_u_from_counts_all_singletons_approaches_zero():
    # N singleton values: u_simple = N * (1/N)^2 = 1/N; u_unbiased = 0 exactly
    # (no value has a repeat, so no pair can share it).
    n = 1000
    counts = np.ones(n, dtype=np.float64)
    u_unbiased, u_simple = compute.u_from_counts(counts)
    assert u_unbiased == pytest.approx(0.0)
    assert u_simple == pytest.approx(1 / n)


def test_u_from_counts_matches_brute_force_pair_counting():
    # Brute-force check of the unbiased pair formula against literal pair
    # enumeration over a tiny synthetic population.
    values = ["A", "A", "A", "B", "B", "C"]
    n = len(values)
    same_value_pairs = 0
    total_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_pairs += 1
            if values[i] == values[j]:
                same_value_pairs += 1
    expected = same_value_pairs / total_pairs

    counts = pd.Series(values).value_counts().to_numpy(dtype=np.float64)
    u_unbiased, _ = compute.u_from_counts(counts)
    assert u_unbiased == pytest.approx(expected)


def test_u_from_counts_empty_or_single_person_population_is_zero():
    # No pairs exist when there are 0 or 1 total people, so u is defined as 0
    # (not 1) in that degenerate case -- distinct from a population of many
    # people who all share one value (see test_u_from_counts_single_value_is_one).
    assert compute.u_from_counts(np.array([])) == (0.0, 0.0)
    assert compute.u_from_counts(np.array([1.0])) == (0.0, 0.0)


def test_u_from_probabilities_sigma_p_squared():
    probs = np.array([0.5, 0.3, 0.2])
    assert compute.u_from_probabilities(probs) == pytest.approx(0.25 + 0.09 + 0.04)


# ---------------------------------------------------------------------------
# Fuzzy-ball logic on a small toy name list
# ---------------------------------------------------------------------------


def test_fuzzy_ball_mass_finds_single_substitution_neighbor():
    # SMITH vs SMYTH: one substitution (I->Y), both len 5 (eligible).
    names = ["SMITH", "SMYTH", "JONES"]
    probs = np.array([0.5, 0.3, 0.2])
    mass = compute.build_fuzzy_ball_mass(names, probs, min_len=5)
    # SMITH's ball should include SMYTH's mass (0.3) but not JONES.
    assert mass[0] == pytest.approx(0.3)
    assert mass[1] == pytest.approx(0.5)
    assert mass[2] == pytest.approx(0.0)


def test_fuzzy_ball_mass_finds_insertion_deletion_neighbor():
    # ALLEN (5) vs ALLENS (6): one insertion.
    names = ["ALLEN", "ALLENS", "SMITH"]
    probs = np.array([0.4, 0.4, 0.2])
    mass = compute.build_fuzzy_ball_mass(names, probs, min_len=5)
    assert mass[0] == pytest.approx(0.4)  # ALLEN's ball includes ALLENS
    assert mass[1] == pytest.approx(0.4)  # ALLENS' ball includes ALLEN
    assert mass[2] == pytest.approx(0.0)


def test_fuzzy_ball_mass_finds_adjacent_transposition():
    # KEVIN vs KEIVN: transposing adjacent V/I.
    names = ["KEVIN", "KEIVN"]
    probs = np.array([0.6, 0.4])
    mass = compute.build_fuzzy_ball_mass(names, probs, min_len=5)
    assert mass[0] == pytest.approx(0.4)
    assert mass[1] == pytest.approx(0.6)


def test_fuzzy_ball_mass_excludes_distance_two():
    # SMITH vs SMYTHE differ by two edits (substitution + insertion) -> not in ball.
    names = ["SMITH", "SMYTHE"]
    probs = np.array([0.7, 0.3])
    mass = compute.build_fuzzy_ball_mass(names, probs, min_len=5)
    assert mass[0] == pytest.approx(0.0)
    assert mass[1] == pytest.approx(0.0)


def test_fuzzy_ball_mass_respects_min_len():
    # "AL" and "AM" are 1 edit apart but below min_len=5, so should get mass 0
    # from this function (caller blends short names with exact match instead).
    names = ["AL", "AM", "SMITH"]
    probs = np.array([0.4, 0.4, 0.2])
    mass = compute.build_fuzzy_ball_mass(names, probs, min_len=5)
    assert mass[0] == pytest.approx(0.0)
    assert mass[1] == pytest.approx(0.0)


def test_fuzzy_ball_mass_excludes_ineligible_names_from_eligible_balls():
    # "SMIT" (4 chars, below min_len=5) is one deletion away from "SMITH" (5
    # chars, eligible). Per the min_len contract, "SMIT" must get zero mass
    # -- but that exclusion has to be symmetric: "SMITH"'s ball must not
    # silently absorb "SMIT"'s probability either, or a name below min_len
    # would still contaminate a fuzzy-match estimate it was supposed to be
    # fully excluded from.
    names = ["SMITH", "SMIT", "JONES"]
    probs = np.array([0.5, 0.3, 0.2])
    mass = compute.build_fuzzy_ball_mass(names, probs, min_len=5)
    assert mass[0] == pytest.approx(0.0)  # SMITH's ball excludes ineligible SMIT
    assert mass[1] == pytest.approx(0.0)  # SMIT itself: no ball at all
    assert mass[2] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# name_exact_u and name_fuzzy_u end-to-end on tiny fixtures
# ---------------------------------------------------------------------------


def test_name_exact_u_bounds_and_coverage():
    listed = pd.DataFrame({"name": ["SMITH", "JONES"], "count": [60, 40]})
    unlisted_count = 10  # e.g. 10 more people with unique rare names
    result = compute.name_exact_u(listed, unlisted_count, "last_name", "fixture.csv")
    # Bound (a): renormalized to listed total of 100.
    expected_a_simple = (60 / 100) ** 2 + (40 / 100) ** 2
    assert result.u_simple == pytest.approx(expected_a_simple)
    assert "coverage" in result.notes.lower() or "Coverage" in result.notes
    assert "bound (b)" in result.notes.lower() or "Bound (b)" in result.notes


def test_year_of_birth_u_headlines_all_ages_not_just_adults():
    # This tool covers the whole population to be matched (newborns and
    # minors are real patients too), so the headline must include ages 0-17,
    # not just adults. Two children (ages 0, 1) are added as large,
    # evenly-sized extra buckets on top of a concentrated adult population
    # (one age with most of the mass): children dilute concentration, so the
    # all-ages headline must come out lower than the adults-only reference
    # figure.
    agesex = pd.DataFrame(
        {
            "SEX": [0, 0, 0, 0, 0],
            "AGE": [0, 1, 18, 19, 999],
            "POPESTIMATE2025": [50, 50, 90, 10, 200],
        }
    )
    result = compute.year_of_birth_u(agesex)
    headline = result["all_ages"]
    adult_unbiased, adult_simple = result["adults_18plus"]

    assert headline.field == "year_of_birth"
    # Headline = all ages: children (50, 50) plus adults (90, 10).
    expected_all_unbiased, _ = compute.u_from_counts(np.array([50.0, 50.0, 90.0, 10.0]))
    assert headline.u_unbiased == pytest.approx(expected_all_unbiased)
    # Adults-only (for reference only) excludes the two even child buckets.
    expected_adult_unbiased, _ = compute.u_from_counts(np.array([90.0, 10.0]))
    assert adult_unbiased == pytest.approx(expected_adult_unbiased)
    assert adult_unbiased > headline.u_unbiased
    assert "all-ages" in headline.notes.lower()


def test_city_u_uses_national_total_not_places_only_total():
    # Places/CDPs cover only part of the national population (people outside
    # any place/CDP are excluded from the places table entirely). Renormalizing
    # to the places-only total (as if it were everyone) instead of the true
    # national total overstates city concentration -- same failure mode
    # name_exact_u's bound (a)/(b) split exists to avoid for names.
    places = pd.DataFrame(
        {
            "NAME": ["Springfield", "Shelbyville"],
            "STNAME": ["Ohio", "Ohio"],
            "POPESTIMATE2025": [60, 40],
        }
    )
    national_total = 200  # 100 more people live outside any place/CDP.
    result = compute.city_u(places, national_total)
    # Headline (bound a) is unchanged: renormalized to the places-only total.
    expected_a_simple = (60 / 100) ** 2 + (40 / 100) ** 2
    assert result.u_simple == pytest.approx(expected_a_simple)
    # But bound (b), padding the other 100 people in as singletons, must be
    # reported and must be lower than bound (a).
    assert "coverage" in result.notes.lower()
    assert "bound (b)" in result.notes.lower()
    unbiased_a, _ = compute.u_from_counts(np.array([60.0, 40.0]))
    assert result.u_unbiased == pytest.approx(unbiased_a)


def test_name_fuzzy_u_blends_short_and_long_names():
    # "AL" (2 chars, below min_len) should contribute p^2; "SMITH"/"SMYTH"
    # (5 chars) should contribute fuzzy ball mass.
    listed = pd.DataFrame({"name": ["SMITH", "SMYTH", "AL"], "count": [50, 30, 20]})
    result = compute.name_fuzzy_u(listed, "last_name", "fixture.csv", min_len=5)
    total = 100
    p_smith, p_smyth, p_al = 50 / total, 30 / total, 20 / total
    # Fuzzy match = exact match (p_v^2) + distance-1 near-miss mass, for eligible names.
    expected_simple = (
        p_smith * (p_smith + p_smyth) + p_smyth * (p_smyth + p_smith) + p_al**2
    )
    assert result.u_simple == pytest.approx(expected_simple)
    # Sanity: fuzzy match is a superset of exact match, so u_fuzzy >= u_exact.
    expected_exact_simple = p_smith**2 + p_smyth**2 + p_al**2
    assert result.u_simple >= expected_exact_simple


# ---------------------------------------------------------------------------
# top_n_by_count
# ---------------------------------------------------------------------------


def test_top_n_by_count_orders_descending():
    names = ["A", "B", "C"]
    counts = np.array([10, 50, 40], dtype=np.float64)
    top = compute.top_n_by_count(names, counts, n=2)
    assert top[0][0] == "B"
    assert top[1][0] == "C"
    assert top[0][1] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# sanity_check
# ---------------------------------------------------------------------------


def test_sanity_check_flags_out_of_range_state_u():
    bad_state = compute.FieldResult("state", "exact", 0.9, 0.9, "fixture", "")
    warnings = compute.sanity_check([bad_state])
    assert any("State" in w for w in warnings)


def test_sanity_check_passes_in_range_values():
    ok_state = compute.FieldResult("state", "exact", 0.04, 0.04, "fixture", "")
    ok_yob = compute.FieldResult("year_of_birth", "exact", 0.014, 0.014, "fixture", "")
    ok_last = compute.FieldResult("last_name", "exact", 0.003, 0.003, "fixture", "")
    warnings = compute.sanity_check([ok_state, ok_yob, ok_last])
    assert warnings == []


def test_sanity_check_passes_real_all_ages_year_of_birth_value():
    # Regression guard: the real all-ages NC-EST2025 headline (~0.0118) must
    # not trip the sanity check. An earlier, un-derived range (0.012-0.016)
    # was calibrated against an adults-only population and false-flagged this
    # correct value -- see docs/LEARNINGS.md.
    real_all_ages_yob = compute.FieldResult(
        "year_of_birth", "exact", 0.01178, 0.01178, "fixture", ""
    )
    warnings = compute.sanity_check([real_all_ages_yob])
    assert warnings == []


# ---------------------------------------------------------------------------
# middle_name_proxy_u
# ---------------------------------------------------------------------------


def test_middle_name_proxy_u_reuses_first_name_math_but_relabels_field():
    listed = pd.DataFrame({"name": ["JAMES", "MARY"], "count": [60, 40]})
    direct = compute.name_exact_u(listed, 10, "first_name", "fixture.xlsx")
    proxy = compute.middle_name_proxy_u(listed, 10, "fixture.xlsx")
    assert proxy.field == "middle_name"
    assert proxy.u_unbiased == pytest.approx(direct.u_unbiased)
    assert proxy.u_simple == pytest.approx(direct.u_simple)
    assert "PROXY" in proxy.notes


# ---------------------------------------------------------------------------
# ssn_itin_last4_u
# ---------------------------------------------------------------------------


def test_ssn_itin_last4_u_is_uniform_over_9999_values():
    result = compute.ssn_itin_last4_u()
    expected = 1.0 / 9999
    assert result["ssn_last4"].u_unbiased == pytest.approx(expected)
    assert result["itin_last4"].u_unbiased == pytest.approx(expected)
    assert "2011" in result["ssn_last4"].notes
    assert "unverified" in result["itin_last4"].notes.lower()


# ---------------------------------------------------------------------------
# mbi_u
# ---------------------------------------------------------------------------


def test_mbi_u_is_one_over_total_enrollment():
    result = compute.mbi_u(total_enrollment=50_000_000.0, year=2024)
    assert result.field == "mbi"
    assert result.u_unbiased == pytest.approx(1 / 50_000_000.0)
    assert "2024" in result.notes


# ---------------------------------------------------------------------------
# phone_u
# ---------------------------------------------------------------------------


def test_phone_u_scales_co_resident_probability_by_landline_household_share():
    street_and_zip = compute.FieldResult(
        "street_line_with_zip",
        "exact",
        u_unbiased=4.0e-9,
        u_simple=8.0e-9,
        source_file="fixture",
    )
    result = compute.phone_u(street_and_zip)
    expected_landline_share = (
        config.NCHS_ADULT_DUAL_USER_HOUSEHOLD_PCT
        + config.NCHS_ADULT_LANDLINE_ONLY_HOUSEHOLD_PCT
    ) / 100.0
    assert result.field == "phone"
    assert result.u_unbiased == pytest.approx(4.0e-9 * expected_landline_share)
    assert result.u_simple == pytest.approx(8.0e-9 * expected_landline_share)
    # Sanity: this is a floor on a floor, so it must be strictly smaller than
    # the co-resident probability it's derived from (landline share < 1).
    assert result.u_unbiased < street_and_zip.u_unbiased
    assert "NCHS" in result.notes
    assert "floor" in result.notes.lower()


# ---------------------------------------------------------------------------
# Widened-match variants: DOB neighbors, date-level DOB u, initial-only first name
# ---------------------------------------------------------------------------


def test_dob_neighbors_pm1day_is_adjacent_days_only():
    from datetime import date

    assert compute.dob_neighbors(date(2000, 3, 7), "pm1day") == {
        date(2000, 3, 6),
        date(2000, 3, 8),
    }


def test_dob_neighbors_swap_adds_month_day_transposition():
    from datetime import date

    n = compute.dob_neighbors(date(2000, 3, 7), "swap")
    assert date(2000, 7, 3) in n
    # 2000-03-17 is a digit replacement, not a swap: not a neighbor here.
    assert date(2000, 3, 17) not in n
    # No valid swap when the day exceeds 12.
    assert compute.dob_neighbors(date(2000, 3, 25), "swap") == compute.dob_neighbors(
        date(2000, 3, 25), "pm1day"
    )


def test_dob_neighbors_dl1_includes_digit_replacement_and_transposition():
    from datetime import date

    n = compute.dob_neighbors(date(2000, 3, 7), "dl1")
    assert date(2000, 3, 17) in n  # one digit replaced
    assert date(2001, 3, 7) in n  # year digit replaced
    assert date(2000, 7, 3) in n  # month/day swap
    assert date(2000, 3, 7) not in n  # never itself


def test_dob_neighbors_rejects_unknown_variant():
    from datetime import date

    with pytest.raises(ValueError):
        compute.dob_neighbors(date(2000, 3, 7), "bogus")


def _one_year_agesex(birth_year: int = 2000) -> pd.DataFrame:
    return pd.DataFrame(
        {"SEX": [0], "AGE": [2025 - birth_year], "POPESTIMATE2025": [1000.0]}
    )


def test_dob_fuzzy_u_exact_is_one_over_days_in_year():
    # One birth year (2000, a leap year): every date equally likely, u = 1/366.
    u = compute.dob_fuzzy_u(_one_year_agesex(), None)
    assert u.field == "dob_full" and u.variant == "exact_datelevel"
    assert u.u_simple == pytest.approx(1 / 366)


def test_dob_fuzzy_u_widening_is_monotone_and_above_exact():
    agesex = _one_year_agesex()
    exact = compute.dob_fuzzy_u(agesex, None).u_simple
    pm1 = compute.dob_fuzzy_u(agesex, "pm1day").u_simple
    swap = compute.dob_fuzzy_u(agesex, "swap").u_simple
    dl1 = compute.dob_fuzzy_u(agesex, "dl1").u_simple
    assert exact < pm1 < swap < dl1


def test_first_initial_u_groups_by_first_letter():
    listed = pd.DataFrame(
        {"name": ["ANNA", "ALEX", "BOB", "BETH"], "count": [50, 50, 50, 50]}
    )
    r = compute.first_initial_u(listed, "x")
    assert (r.field, r.variant) == ("first_name", "initial")
    # Two letters, each 50%: u_simple = 0.5^2 + 0.5^2.
    assert r.u_simple == pytest.approx(0.5)
