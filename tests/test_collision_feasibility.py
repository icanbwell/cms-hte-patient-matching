"""Tests for scripts/collision_feasibility.py: pricing widened matches against 2e-12."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from patient_matching.matching.collision import APPROVAL_THRESHOLD
from scripts.collision_feasibility import (
    LEVERS,
    Multipliers,
    assign,
    p_collision,
    rule_views,
)

# Round numbers so expected products are easy to check by hand.
ROWS = [
    ("first_name", "exact", 0.001),
    ("first_name", "fuzzy", 0.002),
    ("first_name", "initial", 0.05),  # x50 vs exact
    ("first_name", "fuzzy_min4", 0.0022),
    ("last_name", "exact", 0.0007),
    ("last_name", "fuzzy", 0.0008),
    ("last_name", "fuzzy_min4", 0.00088),
    ("dob_full", "exact_datelevel", 0.00003),
    ("dob_full", "fuzzy_dl1", 0.0009),  # x30
    ("dob_full", "fuzzy_swap", 0.0001),
    ("zip5", "exact", 0.0001),
    ("ssn_last4", "exact", 0.0001),
    ("itin_last4", "exact", 0.0001),
]


@pytest.fixture
def mult(tmp_path: Path) -> Multipliers:
    path = tmp_path / "u.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["field", "variant", "u_unbiased"])
        w.writerows(ROWS)
    return Multipliers.from_csv(path)


@pytest.fixture
def rules():
    return {r.rule_id: r for r in rule_views()}


def test_multipliers_are_widened_over_baseline(mult: Multipliers):
    assert mult.multiplier("initial") == pytest.approx(50)
    assert mult.multiplier("dob_dl1") == pytest.approx(30)
    assert mult.multiplier("min4_first_name") == pytest.approx(1.1)


def test_missing_widened_variant_names_the_fix(tmp_path: Path):
    path = tmp_path / "u.csv"
    path.write_text("field,variant,u_unbiased\nfirst_name,exact,0.001\n")
    with pytest.raises(KeyError, match="make calculate"):
        Multipliers.from_csv(path).multiplier("initial")


def test_rule_with_no_headroom_cannot_absorb_any_widening(mult: Multipliers, rules):
    # Rule 11 (First Name + DOB + Phone) is exactly at the threshold.
    r = rules["11"]
    assert r.p_exact == pytest.approx(APPROVAL_THRESHOLD)
    assert (
        p_collision(r, ["dob_dl1_all"], mult, "scaled_conservative")
        > APPROVAL_THRESHOLD
    )
    assert (
        p_collision(r, ["initial_all"], mult, "scaled_conservative")
        > APPROVAL_THRESHOLD
    )


def test_scaled_conservative_multiplies_published_p_by_field_multiplier(
    mult: Multipliers, rules
):
    r = rules["02"]  # First + Last* + DOB* + Phone, published P = 1e-14
    base = max(r.p_exact, r.p_fuzzy)
    got = p_collision(r, ["dob_dl1_fuzzy"], mult, "scaled_conservative")
    assert got == pytest.approx(base * 30)


def test_lever_scope_is_respected(mult: Multipliers, rules):
    # dob_dl1_fuzzy only applies where DOB is already fuzzy-eligible; rule 11 has exact DOB.
    assert p_collision(
        rules["11"], ["dob_dl1_fuzzy"], mult, "scaled_conservative"
    ) == pytest.approx(max(rules["11"].p_exact, rules["11"].p_fuzzy))
    assert not LEVERS["initial_c2"].applies(rules["02"], "first_name")
    assert LEVERS["initial_c2"].applies(rules["C2-13"], "first_name")


def test_assign_never_exceeds_threshold(mult: Multipliers, rules):
    combo = ("dob_dl1_all", "initial_all")
    for basis in ("scaled_conservative", "empirical"):
        assigned = assign(rules.values(), combo, mult, basis)
        for rule_id, levers in assigned.items():
            if levers:
                assert (
                    p_collision(rules[rule_id], levers, mult, basis)
                    <= APPROVAL_THRESHOLD
                )


def test_assign_falls_back_to_a_single_lever_when_both_do_not_fit(
    mult: Multipliers, rules
):
    # Rule 02: 1e-14 * 50 (initial) = 5e-13 fits; * 30 (dob) = 3e-13 fits; both = 1.5e-11 does not.
    assigned = assign(
        [rules["02"]], ("dob_dl1_all", "initial_all"), mult, "scaled_conservative"
    )
    assert len(assigned["02"]) == 1
    assert assigned["02"][0] == "dob_dl1_all"  # first in the combo's priority order
