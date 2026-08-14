"""Unit tests for labeled_pairs.py (session 9).

Depends on numpy transitively via rule_eval - see test_rule_eval.py's module
docstring for why these importorskip("numpy") rather than failing hard.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")

from labeled_pairs import build_labeled_pairs  # noqa: E402


def _patient(id_: str, family: str = "Smith", given: str = "Katherine"):
    return {
        "resourceType": "Patient",
        "id": id_,
        "name": [{"family": family, "given": [given]}],
        "birthDate": "1980-06-15",
        "telecom": [],
        "address": [{"line": ["1 Main St"], "city": "NY", "state": "NY", "postalCode": "10001"}],
        "identifier": [],
    }


class TestBuildLabeledPairs:
    def test_produces_one_true_match_pair_per_patient_by_default(self) -> None:
        patients = [_patient("p1"), _patient("p2", family="Jones", given="Robert")]
        pairs = build_labeled_pairs(patients, seed=0)
        true_matches = [p for p in pairs if p.is_true_match]
        assert len(true_matches) == len(patients)
        assert all(p.strata["pair_type"] == "fuzzy_variant" for p in true_matches)

    def test_true_match_pairs_are_labeled_with_the_mutation_applied(self) -> None:
        pairs = build_labeled_pairs([_patient("p1")], seed=0)
        (pair,) = [p for p in pairs if p.is_true_match]
        assert pair.strata["mutation"]
        assert pair.pair_id == f"p1::{pair.strata['mutation']}"

    def test_hard_negative_pairs_are_labeled_non_match(self) -> None:
        # Same ZIP+DOB, distinct family names -> one mined hard negative.
        patients = [_patient("p1", family="Smith"), _patient("p2", family="Jones")]
        pairs = build_labeled_pairs(patients, seed=0)
        hard_negatives = [p for p in pairs if p.strata.get("pair_type") == "hard_negative"]
        assert len(hard_negatives) == 1
        assert hard_negatives[0].is_true_match is False

    def test_more_variants_per_patient_scales_true_match_count(self) -> None:
        pairs = build_labeled_pairs([_patient("p1")], n_fuzzy_variants_per_patient=3, seed=0)
        assert sum(p.is_true_match for p in pairs) == 3

    def test_is_deterministic_given_a_seed(self) -> None:
        patients = [_patient("p1"), _patient("p2", family="Jones", given="Robert")]
        first = build_labeled_pairs(patients, seed=42)
        second = build_labeled_pairs(patients, seed=42)
        assert [p.pair_id for p in first] == [p.pair_id for p in second]
