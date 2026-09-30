"""Unit tests for compute.py's pure functions, using small synthetic fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import compute


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


def test_name_fuzzy_u_blends_short_and_long_names():
    # "AL" (2 chars, below min_len) should contribute p^2; "SMITH"/"SMYTH"
    # (5 chars) should contribute fuzzy ball mass.
    listed = pd.DataFrame(
        {"name": ["SMITH", "SMYTH", "AL"], "count": [50, 30, 20]}
    )
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
