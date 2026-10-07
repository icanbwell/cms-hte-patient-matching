"""Which Table 2 rules can absorb a widened field match and stay under the 2e-12 threshold?

The accuracy analysis (docs/TEST_SET_0.0.5_ACCURACY_ANALYSIS.md) proposes widening what
counts as agreement for a field: initial-only first names, DOB within one edit, and
4-character fuzzy names. Each widening raises that field's u-probability, and
P(collision) = product of the fields' u-probabilities must stay at or under
`collision.APPROVAL_THRESHOLD` (2e-12) for a rule to be approvable.

This script prices each proposed lever per rule, using the multipliers measured by
`calculations/` (`make calculate` writes calculations/outputs/u_probabilities.csv), on two bases:

* **scaled-conservative** (the spec-compliant test): each widened field's Table 3 value is
  multiplied by (empirical widened u / empirical exact u), so the spec's own margin of
  pessimism carries over, capped at u = 1. The rule's published P(collision) (worst of exact
  and fuzzy) supplies the other fields.
* **empirical** (evidence for a waiver, not a pass of the spec's test): the fields the Census
  data actually measures (first/last name, DOB, ZIP, SSN/ITIN last 4) use their empirical u;
  every other field (street, phone, email, MBI, legal/insurance/namespace IDs) stays at its
  Table 3 value because the tool only has a floor, or no estimate, for those.

A lever is only applied to a rule where the resulting P(collision) is at or under the
threshold. `assign()` picks, per rule, the largest subset of a lever combination that fits.

Usage:
    uv run python scripts/collision_feasibility.py [--json OUT.json]

Reads the rule definitions from `patient_matching` and the multipliers from the CSV; writes
nothing unless --json is given.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from patient_matching.matching.collision import APPROVAL_THRESHOLD, FIELD_U_PROBS
from patient_matching.matching.household_rules import CATEGORY_2_RULES
from patient_matching.matching.table2_rules import APPROVED_RULES, FieldRole

DEFAULT_CSV = (
    Path(__file__).resolve().parent.parent
    / "calculations"
    / "outputs"
    / "u_probabilities.csv"
)

BASES = ("scaled_conservative", "empirical")

# Fields whose empirical u comes from a real point estimate in calculations/. Everything
# else is at the Table 3 value on the empirical basis (street/phone/MBI are floors).
CENSUS_MEASURED = {
    "first_name",
    "last_name",
    "dob",
    "zip_code",
    "ssn_last4",
    "itin_last4",
}


@dataclass(frozen=True)
class FieldView:
    name: str
    fuzzy_eligible: bool
    step: str  # "flat" | "household" | "individual"


@dataclass(frozen=True)
class RuleView:
    rule_id: str
    category: str  # "C1" | "C2"
    fields: Tuple[FieldView, ...]
    max_fuzzy: int
    p_exact: float
    p_fuzzy: float
    step_field_count: int  # fields in the step where first name / DOB are compared

    def has(self, name: str) -> bool:
        return any(f.name == name for f in self.fields)

    def fuzzy_eligible(self, name: str) -> bool:
        return any(f.name == name and f.fuzzy_eligible for f in self.fields)


@dataclass(frozen=True)
class Lever:
    key: str
    description: str
    field_to_widening: Dict[str, str]  # field -> widening id (see Multipliers.widening)
    scope: str  # "all" | "c2" | "ge4" | "fuzzy_eligible"

    def applies(self, rule: RuleView, field: str) -> bool:
        if field not in self.field_to_widening or not rule.has(field):
            return False
        if self.scope == "all":
            return True
        if self.scope == "c2":
            return rule.category == "C2"
        if self.scope == "ge4":
            return rule.step_field_count >= 4
        if self.scope == "fuzzy_eligible":
            return rule.fuzzy_eligible(field)
        raise ValueError(self.scope)


LEVERS: Dict[str, Lever] = {
    lv.key: lv
    for lv in (
        Lever(
            "initial_all",
            "Initial-only first name, every rule",
            {"first_name": "initial"},
            "all",
        ),
        Lever(
            "initial_c2",
            "Initial-only first name, household (Category 2) rules only",
            {"first_name": "initial"},
            "c2",
        ),
        Lever(
            "initial_ge4",
            "Initial-only first name, rules whose step has >= 4 fields",
            {"first_name": "initial"},
            "ge4",
        ),
        Lever(
            "dob_dl1_fuzzy",
            "DOB within one edit, rules where DOB is already fuzzy-eligible",
            {"dob": "dob_dl1"},
            "fuzzy_eligible",
        ),
        Lever(
            "dob_dl1_all",
            "DOB within one edit, every rule that uses DOB",
            {"dob": "dob_dl1"},
            "all",
        ),
        Lever(
            "dob_dl1_c2",
            "DOB within one edit, household rules only",
            {"dob": "dob_dl1"},
            "c2",
        ),
        Lever(
            "dob_swap_fuzzy",
            "DOB month/day swap, rules where DOB is already fuzzy-eligible",
            {"dob": "dob_swap"},
            "fuzzy_eligible",
        ),
        Lever(
            "min4",
            "Fuzzy first/last name at 4 characters (minimum 5 -> 4)",
            {"first_name": "min4_first_name", "last_name": "min4_last_name"},
            "fuzzy_eligible",
        ),
    )
}

# Lever combinations whose recall is measured by scripts/lever_recall.py. Order is priority
# when a rule cannot absorb the whole combination.
COMBOS: Dict[str, Tuple[str, ...]] = {
    "dob_dl1_all + initial_c2": ("dob_dl1_all", "initial_c2"),
    "dob_dl1_all + initial_all": ("dob_dl1_all", "initial_all"),
    "dob_dl1_all + initial_ge4": ("dob_dl1_all", "initial_ge4"),
    "initial_all + dob_dl1_fuzzy": ("initial_all", "dob_dl1_fuzzy"),
    "initial_all + dob_dl1_fuzzy + min4": ("initial_all", "dob_dl1_fuzzy", "min4"),
}


class Multipliers:
    """Widened-match u-probabilities, read from calculations/outputs/u_probabilities.csv."""

    def __init__(self, rows: Dict[Tuple[str, str], float]):
        self._rows = rows

    @classmethod
    def from_csv(cls, path: Path = DEFAULT_CSV) -> "Multipliers":
        with path.open() as f:
            rows = {
                (r["field"], r["variant"]): float(r["u_unbiased"])
                for r in csv.DictReader(f)
            }
        return cls(rows)

    def u(self, field: str, variant: str) -> float:
        try:
            return self._rows[(field, variant)]
        except KeyError as exc:
            raise KeyError(
                f"{field}/{variant} missing from the u-probability CSV; run "
                f"`make calculate` in calculations/ (the widened variants were added "
                f"with this script)"
            ) from exc

    # widening id -> (empirical widened u, empirical baseline u it is a multiple of)
    def widening(self, wid: str) -> Tuple[float, float]:
        if wid == "initial":
            return self.u("first_name", "initial"), self.u("first_name", "exact")
        if wid == "dob_dl1":
            return self.u("dob_full", "fuzzy_dl1"), self.u(
                "dob_full", "exact_datelevel"
            )
        if wid == "dob_swap":
            return self.u("dob_full", "fuzzy_swap"), self.u(
                "dob_full", "exact_datelevel"
            )
        if wid == "min4_first_name":
            return self.u("first_name", "fuzzy_min4"), self.u("first_name", "fuzzy")
        if wid == "min4_last_name":
            return self.u("last_name", "fuzzy_min4"), self.u("last_name", "fuzzy")
        raise KeyError(wid)

    def multiplier(self, wid: str) -> float:
        widened, base = self.widening(wid)
        return widened / base

    def empirical_base(self, field: str, fuzzy: bool) -> Optional[float]:
        """Empirical u for a Census-measured field, else None (use Table 3)."""
        if field not in CENSUS_MEASURED:
            return None
        key = {
            "first_name": ("first_name", "fuzzy" if fuzzy else "exact"),
            "last_name": ("last_name", "fuzzy" if fuzzy else "exact"),
            "dob": ("dob_full", "exact_datelevel"),
            "zip_code": ("zip5", "exact"),
            "ssn_last4": ("ssn_last4", "exact"),
            "itin_last4": ("itin_last4", "exact"),
        }[field]
        return self._rows.get(key)


def rule_views() -> List[RuleView]:
    """One `RuleView` per Table 2 Category 1 rule and per Category 2 (household) rule."""
    views: List[RuleView] = []
    for r in APPROVED_RULES:
        fields = tuple(
            FieldView(f.name, f.role == FieldRole.FUZZY_ELIGIBLE, "flat")
            for f in r.fields
        )
        views.append(
            RuleView(
                r.rule_id,
                "C1",
                fields,
                r.max_fuzzy_fields,
                r.p_collision_exact,
                r.p_collision_fuzzy,
                len(fields),
            )
        )
    for hr in CATEGORY_2_RULES:
        fields = tuple(
            FieldView(f.name, False, "household") for f in hr.household_row.fields
        ) + tuple(
            FieldView(f.name, f.role == FieldRole.FUZZY_ELIGIBLE, "individual")
            for f in hr.individual_row.fields
        )
        views.append(
            RuleView(
                hr.rule_id,
                "C2",
                fields,
                1,
                hr.p_collision_exact,
                hr.p_collision_fuzzy,
                len(hr.individual_row.fields),
            )
        )
    return views


def _overrides(
    rule: RuleView, levers: Iterable[str], mult: Multipliers
) -> Dict[str, str]:
    """field -> widening id, taking the larger multiplier if two levers hit one field."""
    out: Dict[str, str] = {}
    for key in levers:
        lever = LEVERS[key]
        for field, wid in lever.field_to_widening.items():
            if not lever.applies(rule, field):
                continue
            if field not in out or mult.multiplier(wid) > mult.multiplier(out[field]):
                out[field] = wid
    return out


_FUZZY_NAME_FIELDS = ("first_name", "last_name")
_FUZZY_SPEC_FIELDS = ("first_name", "last_name", "street_line")


def _empirical_fuzzy_names(rule: RuleView, mult: Multipliers) -> Set[str]:
    """Name fields assumed to go fuzzy: up to `max_fuzzy` fuzzy-eligible ones, picking those
    whose fuzzy u is largest relative to exact (the worst case for the rule)."""
    ratios = []
    for f in rule.fields:
        if not (f.fuzzy_eligible and f.name in _FUZZY_NAME_FIELDS):
            continue
        exact, fuzzy = (
            mult.empirical_base(f.name, False),
            mult.empirical_base(f.name, True),
        )
        if exact and fuzzy:
            ratios.append((fuzzy / exact, f.name))
    return {name for _, name in sorted(ratios, reverse=True)[: rule.max_fuzzy]}


def _empirical_field_u(
    rule: RuleView, field: FieldView, fuzzy_names: Set[str], mult: Multipliers
) -> float:
    """Empirical u for a Census-measured field, else its Table 3 value (fuzzy where the
    rule can make that field fuzzy)."""
    measured = mult.empirical_base(field.name, field.name in fuzzy_names)
    if measured is not None:
        return measured
    can_be_fuzzy = (
        field.fuzzy_eligible and rule.max_fuzzy > 0 and field.name in _FUZZY_SPEC_FIELDS
    )
    return _spec_u(field.name, can_be_fuzzy)


def p_collision(
    rule: RuleView, levers: Iterable[str], mult: Multipliers, basis: str
) -> float:
    """P(collision) of `rule` with `levers` applied, on `basis`."""
    over = _overrides(rule, levers, mult)
    if basis == "scaled_conservative":
        p = max(rule.p_exact, rule.p_fuzzy)
        for field, wid in over.items():
            fuzzy_name = wid.startswith("min4")
            exact_u, fuzzy_u = FIELD_U_PROBS[field]
            spec_u = fuzzy_u if (fuzzy_name and fuzzy_u) else exact_u
            p *= min(mult.multiplier(wid), 1.0 / spec_u)
        return p
    if basis == "empirical":
        fuzzy_names = _empirical_fuzzy_names(rule, mult)
        p = 1.0
        for f in rule.fields:
            if f.name in over:
                p *= mult.widening(over[f.name])[0]
            else:
                p *= _empirical_field_u(rule, f, fuzzy_names, mult)
        return p
    raise ValueError(basis)


def _spec_u(name: str, fuzzy: bool) -> float:
    """Table 3 u for `name`: its fuzzy value when `fuzzy` and one exists, else its exact value."""
    exact_u, fuzzy_u = FIELD_U_PROBS[name]
    return fuzzy_u if (fuzzy and fuzzy_u) else exact_u


def assign(
    rules: Iterable[RuleView],
    combo: Tuple[str, ...],
    mult: Multipliers,
    basis: str,
    threshold: float = APPROVAL_THRESHOLD,
) -> Dict[str, Tuple[str, ...]]:
    """Per rule, the levers of `combo` that fit under `threshold` (largest subset first,
    then single levers in the combo's priority order, then none)."""
    out: Dict[str, Tuple[str, ...]] = {}
    for rule in rules:
        applicable = tuple(
            k
            for k in combo
            if any(LEVERS[k].applies(rule, f) for f in LEVERS[k].field_to_widening)
        )
        options: List[Tuple[str, ...]] = []
        if len(applicable) > 1:
            options.append(applicable)
        options.extend((k,) for k in applicable)
        chosen: Tuple[str, ...] = ()
        for opt in options:
            if p_collision(rule, opt, mult, basis) <= threshold:
                chosen = opt
                break
        out[rule.rule_id] = chosen
    return out


def feasibility_report(mult: Multipliers) -> Dict[str, Any]:
    """Price every lever, alone and in `COMBOS`, on both bases and return the full report."""
    rules = rule_views()
    report: Dict[str, Any] = {
        "threshold": APPROVAL_THRESHOLD,
        "multipliers": {},
        "single": {},
        "combos": {},
    }
    for wid in ("initial", "dob_dl1", "dob_swap", "min4_first_name", "min4_last_name"):
        widened, base = mult.widening(wid)
        report["multipliers"][wid] = {
            "widened_u": widened,
            "base_u": base,
            "multiplier": widened / base,
        }
    for basis in BASES:
        report["single"][basis] = {}
        for key in LEVERS:
            applicable = [r for r in rules if _overrides(r, [key], mult)]
            ok = [
                r.rule_id
                for r in applicable
                if p_collision(r, [key], mult, basis) <= APPROVAL_THRESHOLD
            ]
            report["single"][basis][key] = {
                "applicable": [r.rule_id for r in applicable],
                "feasible": ok,
            }
        report["combos"][basis] = {
            name: assign(rules, combo, mult, basis) for name, combo in COMBOS.items()
        }
    return report


def _fmt(rules: List[str]) -> str:
    """Comma-separated rule ids, or `none`."""
    return ", ".join(rules) if rules else "none"


def print_report(report: Dict[str, Any]) -> None:
    """Print the multipliers and, per basis, where each lever and combination fits."""
    print(f"Threshold: {report['threshold']:.0e}\n")
    print("Empirical multipliers (widened u / baseline u):")
    for wid, m in report["multipliers"].items():
        print(
            f"  {wid:<16} widened={m['widened_u']:.4g} base={m['base_u']:.4g} x{m['multiplier']:.2f}"
        )
    for basis in BASES:
        print(f"\n== {basis} ==")
        for key, v in report["single"][basis].items():
            n_app, n_ok = len(v["applicable"]), len(v["feasible"])
            print(f"{key:<16} feasible in {n_ok}/{n_app} rules: {_fmt(v['feasible'])}")
        print("combos (rules where the full or partial combo fits):")
        for name, assigned in report["combos"][basis].items():
            used = {rid: lv for rid, lv in assigned.items() if lv}
            print(f"  {name}: {len(used)} rules touched")


def main() -> None:
    """Print the feasibility report from the u-probability CSV; optionally write it as JSON."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--json", type=Path, default=None, help="write the full report here"
    )
    args = parser.parse_args()
    report = feasibility_report(Multipliers.from_csv(args.csv))
    print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=list))


if __name__ == "__main__":
    main()
