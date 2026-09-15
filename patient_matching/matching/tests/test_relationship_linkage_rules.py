"""Tests for CMS v3.4.0 Relationship Linkage rules (C2-39, C2-40) - session 17."""

from typing import Any, Dict, List

import pytest

from patient_matching.matching.backend import FieldCriterion, MatchingBackend
from patient_matching.matching.household_rules import CATEGORY_2_RULES
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.matching.relationship_linkage_rules import (
    RELATIONSHIP_LINKAGE_RULES,
)
from patient_matching.matching.table2_rules import APPROVED_RULES

_RELATIONSHIP_LINKAGE_EXTENSION_URL = (
    "https://cms-hte-patient-matching.icanbwell.com/fhir/StructureDefinition/"
    "relationship-linkage"
)


class _InMemoryBackend(MatchingBackend):
    """Backend that returns all stored patients - the engine's own
    field-verification logic does the actual enforcement being tested,
    same convention test_matching_engine.py's InMemoryBackend uses."""

    def __init__(self, patients: List[Dict[str, Any]]):
        self._patients = patients

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return list(self._patients)


def _relationship_extension(relationship_type: str, source: str) -> Dict[str, Any]:
    return {
        "url": _RELATIONSHIP_LINKAGE_EXTENSION_URL,
        "extension": [
            {"url": "type", "valueCode": relationship_type},
            {"url": "source", "valueCode": source},
        ],
    }


def _identifier(
    code: str, value: str, system: str = "urn:cms-hte:example"
) -> Dict[str, Any]:
    return {
        "system": system,
        "type": {"coding": [{"code": code}]},
        "value": value,
    }


def _guardian_child_patient(
    *,
    first: str = "sam",
    dob: str = "2015-06-01",
    street: str = "123 main st",
    guardian_id: str = "GRD001",
    include_relationship_claim: bool = True,
) -> Dict[str, Any]:
    patient: Dict[str, Any] = {
        "resourceType": "Patient",
        "name": [{"given": [first]}],
        "birthDate": dob,
        "address": [{"line": [street]}],
        "telecom": [],
        "identifier": [_identifier("CMS-GRDN", guardian_id)],
    }
    if include_relationship_claim:
        patient["extension"] = [_relationship_extension("child-of", "clinical")]
    return patient


def _newborn_patient(
    *,
    dob: str = "2026-01-01",
    mother_id: str = "MOM001",
    encounter_id: str = "ENC12345",
    encounter_system: str = "urn:hospital:abc",
) -> Dict[str, Any]:
    identifiers = [_identifier("CMS-MTHR", mother_id)]
    if encounter_system:
        identifiers.append(
            _identifier("CMS-BEID", encounter_id, system=encounter_system)
        )
    else:
        # No system/namespace - must be excluded from extraction entirely
        # (same principle as an unscoped Member/Subscriber ID).
        identifiers.append(
            {"type": {"coding": [{"code": "CMS-BEID"}]}, "value": encounter_id}
        )
    return {
        "resourceType": "Patient",
        "name": [],
        "birthDate": dob,
        "address": [],
        "telecom": [],
        "identifier": identifiers,
        "extension": [_relationship_extension("newborn-of", "clinical")],
    }


class TestRuleFigures:
    def test_c2_39_matches_spec_figure(self) -> None:
        rule = next(r for r in RELATIONSHIP_LINKAGE_RULES if r.rule_id == "C2-39")
        assert rule.p_collision_exact == pytest.approx(6.0e-13, rel=1e-6)
        assert rule.p_collision_fuzzy == pytest.approx(6.0e-13, rel=1e-6)

    def test_c2_40_matches_spec_figure(self) -> None:
        rule = next(r for r in RELATIONSHIP_LINKAGE_RULES if r.rule_id == "C2-40")
        assert rule.p_collision_exact == pytest.approx(1.0e-21, rel=1e-6)
        assert rule.p_collision_fuzzy == pytest.approx(1.0e-21, rel=1e-6)

    def test_all_rules_clear_the_approval_threshold(self) -> None:
        for rule in RELATIONSHIP_LINKAGE_RULES:
            assert rule.p_collision_exact <= 2e-12


class TestRuleIdsDoNotCollide:
    def test_no_collision_with_category_1_or_category_2(self) -> None:
        category1_ids = {r.rule_id for r in APPROVED_RULES}
        category2_ids = {r.rule_id for r in CATEGORY_2_RULES}
        new_ids = {r.rule_id for r in RELATIONSHIP_LINKAGE_RULES}
        assert not (category1_ids & new_ids)
        assert not (category2_ids & new_ids)
        assert new_ids == {"C2-39", "C2-40"}


class TestGuardianVerifiedMinorEndToEnd:
    async def test_matching_guardian_child_pair_resolves(self) -> None:
        candidate = _guardian_child_patient()
        query = _guardian_child_patient()
        engine = MatchingEngine(
            backend=_InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-39"

    async def test_different_guardian_does_not_match(self) -> None:
        candidate = _guardian_child_patient(guardian_id="GRD002")
        query = _guardian_child_patient(guardian_id="GRD001")
        engine = MatchingEngine(
            backend=_InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_missing_relationship_linkage_claim_does_not_match(self) -> None:
        candidate = _guardian_child_patient(include_relationship_claim=False)
        query = _guardian_child_patient()
        engine = MatchingEngine(
            backend=_InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_multiple_children_under_same_guardian_narrows_correctly(
        self,
    ) -> None:
        """Household step (guardian identity + Street Line) can legitimately
        surface siblings; the individual step (Relationship Linkage + First
        Name + DOB) must narrow to the one actually being sought."""
        sibling = _guardian_child_patient(first="alex", dob="2013-02-02")
        the_child = _guardian_child_patient(first="sam", dob="2015-06-01")
        query = _guardian_child_patient(first="sam", dob="2015-06-01")
        engine = MatchingEngine(
            backend=_InMemoryBackend([sibling, the_child]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [the_child]


class TestNewbornViaMaternalLinkageEndToEnd:
    async def test_matching_mother_newborn_pair_resolves(self) -> None:
        candidate = _newborn_patient()
        query = _newborn_patient()
        engine = MatchingEngine(
            backend=_InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-40"

    async def test_unscoped_encounter_id_does_not_match(self) -> None:
        """A birth-encounter identifier with no system/namespace can't be
        trusted to mean a genuinely per-encounter value - excluded from
        extraction entirely (field comes back empty), same principle as an
        unscoped Member/Subscriber ID."""
        candidate = _newborn_patient(encounter_system="")
        query = _newborn_patient()
        engine = MatchingEngine(
            backend=_InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_different_mother_does_not_match(self) -> None:
        candidate = _newborn_patient(mother_id="MOM002")
        query = _newborn_patient(mother_id="MOM001")
        engine = MatchingEngine(
            backend=_InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=RELATIONSHIP_LINKAGE_RULES,
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH


class TestNoCrossTalkWithOtherRules:
    async def test_relationship_linkage_rules_do_not_affect_flat_rule_matching(
        self,
    ) -> None:
        """Enabling C2-39/C2-40 (now the engine's default) alongside the
        default flat rule set must not change an unrelated flat-rule match
        outcome."""
        candidate = {
            "resourceType": "Patient",
            "name": [{"given": ["john"], "family": "smith"}],
            "birthDate": "1990-01-15",
            "telecom": [],
            "address": [],
            "identifier": [
                {"system": "http://hl7.org/fhir/sid/us-mbi", "value": "1EG4TE5MK73"}
            ],
        }
        query = dict(candidate)
        engine = MatchingEngine(backend=_InMemoryBackend([candidate]))  # all defaults
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "08"  # First Name + DOB + MBI

    async def test_default_household_individual_rules_include_new_rules(self) -> None:
        """MatchingEngine's default household_individual_rules must include
        C2-39/C2-40, not just the original 8 - otherwise they exist in code
        but are silently inert for any caller relying on the default (e.g.
        PatientMatcherService)."""
        candidate = _guardian_child_patient()
        query = _guardian_child_patient()
        engine = MatchingEngine(backend=_InMemoryBackend([candidate]), rules=())
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-39"
