"""Tests for MatchingEngine."""

from typing import Any, Dict, List, Optional

from patient_matching.matching.backend import (
    FieldCriterion,
    MatchingBackend,
)
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
)


# ── helpers ──────────────────────────────────────────────────────────


def _make_patient(
    *,
    first: str = "john",
    last: str = "smith",
    dob: str = "1990-01-15",
    phone: Optional[str] = "+12125551234",
    email: Optional[str] = "john@gmail.com",
    ssn_last4: Optional[str] = "6789",
    street: Optional[str] = "123 main st",
    suffix: Optional[str] = None,
    mbi: Optional[str] = None,
    legal_id: Optional[str] = None,
    namespace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a minimal normalized FHIR Patient dict."""
    patient: Dict[str, Any] = {
        "resourceType": "Patient",
        "name": [
            {
                "family": last,
                "given": [first],
            }
        ],
        "birthDate": dob,
        "telecom": [],
        "address": [{"line": [street]}] if street else [],
        "identifier": [],
    }
    if suffix:
        patient["name"][0]["suffix"] = [suffix]
    if phone:
        patient["telecom"].append({"system": "phone", "value": phone})
    if email:
        patient["telecom"].append({"system": "email", "value": email})
    if ssn_last4:
        patient["identifier"].append(
            {
                "system": "http://hl7.org/fhir/sid/us-ssn",
                "value": f"xxx-xx-{ssn_last4}",
            }
        )
    if mbi:
        patient["identifier"].append(
            {"system": "http://hl7.org/fhir/sid/us-mbi", "value": mbi}
        )
    if legal_id:
        patient["identifier"].append(
            {
                "type": {"coding": [{"code": "DL"}]},
                "value": legal_id,
                "assigner": {"display": "CA-DMV"},
            }
        )
    if namespace_id:
        patient["identifier"].append(
            {
                "system": "urn:hospital:abc",
                "type": {"coding": [{"code": "MR"}]},
                "value": namespace_id,
            }
        )
    return patient


class InMemoryBackend(MatchingBackend):
    """Simple in-memory backend that returns all stored patients."""

    def __init__(self, patients: List[Dict[str, Any]]):
        self._patients = patients

    def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return list(self._patients)


class EmptyBackend(MatchingBackend):
    """Backend that always returns no candidates."""

    def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []


# ── tests ────────────────────────────────────────────────────────────


class TestMatchingEngineExactMatch:
    def test_exact_match_single_candidate(self) -> None:
        candidate = _make_patient()
        query = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.is_unique is True
        assert len(result.matched_patients) == 1

    def test_no_match_different_names(self) -> None:
        candidate = _make_patient(first="alice", last="jones")
        query = _make_patient(first="john", last="smith")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    def test_no_candidates_from_backend(self) -> None:
        query = _make_patient()
        engine = MatchingEngine(backend=EmptyBackend())
        result = engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH


class TestMatchingEngineAmbiguous:
    def test_ambiguous_multiple_candidates(self) -> None:
        c1 = _make_patient()
        c2 = _make_patient(phone="+12125559999")
        query = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([c1, c2]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.AMBIGUOUS
        assert result.is_unique is False
        assert result.candidate_count >= 2


class TestMatchingEngineFuzzyMatch:
    def test_fuzzy_match_last_name(self) -> None:
        """Last name 'smtih' (transposition) should fuzzy-match 'smith'."""
        candidate = _make_patient(last="smtih")
        query = _make_patient(last="smith")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.match_type == "fuzzy"

    def test_fuzzy_match_short_string_rejected(self) -> None:
        """Short first name 'jon' vs 'john' — should NOT fuzzy match."""
        candidate = _make_patient(first="jon", last="jones", dob="2000-01-01")
        query = _make_patient(first="john", last="jones", dob="2000-01-01")
        # Rule 02: First Name + Last Name* + DOB + Phone
        # first_name is EXACT in rule 02, so 'jon' vs 'john' fails.
        # Rule 04: First Name* + Last Name + DOB + SSN Last 4
        # first_name* is fuzzy eligible but 'jon'/'john' are < 5 chars.
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        # Should still match on rules that don't require first_name match
        # (e.g. rule 13: Last Name + Phone + SSN Last 4)
        # but first_name fuzzy should not work for short strings
        has_fuzzy_first = any(
            "first_name" in ev.fuzzy_fields
            for ev in result.rule_evaluations
            if ev.matched
        )
        assert has_fuzzy_first is False


class TestMatchingEngineSuffixConflict:
    def test_suffix_conflict_negates_match(self) -> None:
        """B.5: Different suffixes should negate the match."""
        candidate = _make_patient(suffix="jr")
        query = _make_patient(suffix="sr")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH
        negated = [ev for ev in result.rule_evaluations if ev.negated_by_suffix]
        assert len(negated) > 0

    def test_same_suffix_no_conflict(self) -> None:
        candidate = _make_patient(suffix="jr")
        query = _make_patient(suffix="jr")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.MATCH

    def test_no_suffix_no_conflict(self) -> None:
        candidate = _make_patient()
        query = _make_patient(suffix="jr")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert result.outcome == MatchOutcome.MATCH


class TestMatchingEngineRuleSubset:
    def test_custom_rule_subset(self) -> None:
        """Engine should respect a custom subset of rules."""
        single_rule = (APPROVED_RULES[25],)  # Rule 26: namespace_id
        candidate = _make_patient(namespace_id="MRN001")
        query = _make_patient(namespace_id="MRN001")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=single_rule,
        )
        result = engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "26"

    def test_rule_skipped_when_query_missing_fields(self) -> None:
        """Rule should be skipped if query lacks required fields."""
        single_rule = (APPROVED_RULES[7],)  # Rule 08: First Name + DOB + MBI
        query = _make_patient(mbi=None)  # No MBI
        candidate = _make_patient(mbi="1EG4TE5MK73")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=single_rule,
        )
        result = engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH


class TestMatchingEngineRuleEvaluations:
    def test_evaluations_are_recorded(self) -> None:
        candidate = _make_patient()
        query = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = engine.match(query)
        assert len(result.rule_evaluations) > 0

    def test_evaluation_field_outcomes(self) -> None:
        """Rule 26 eval should have namespace_id as exact."""
        single_rule = (APPROVED_RULES[25],)
        candidate = _make_patient(namespace_id="MRN001")
        query = _make_patient(namespace_id="MRN001")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=single_rule,
        )
        result = engine.match(query)
        evals = [e for e in result.rule_evaluations if e.rule_id == "26"]
        assert len(evals) == 1
        assert evals[0].field_outcomes.get("namespace_id") == "exact"
