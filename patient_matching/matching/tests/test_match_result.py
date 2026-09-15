"""Tests for the SS VII per-query audit record (session 18, CMS v3.4.0).

Each of the 7 required fields gets its own named test here, so a future
spec revision touching this section trips an obvious, specific failure
rather than a generic regression somewhere else in the suite.
"""

from typing import Any, Dict, List

from patient_matching.matching.backend import FieldCriterion, MatchingBackend
from patient_matching.matching.in_memory_backend import InMemoryBackend
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine


class _EmptyBackend(MatchingBackend):
    """No candidates on file - used to exercise the zero-rule-evaluations
    path (e.g. an empty query patient matches no rule's field requirements
    at all)."""

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []


def _mbi_patient(
    *, first: str = "john", dob: str = "1990-01-15", mbi: str = "1EG4TE5MK73"
) -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "name": [{"given": [first]}],
        "birthDate": dob,
        "telecom": [],
        "address": [],
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-mbi", "value": mbi}],
    }


class TestQueryInitiator:
    async def test_is_captured_when_supplied(self) -> None:
        engine = MatchingEngine(backend=_EmptyBackend())
        result = await engine.match(
            {"resourceType": "Patient"}, query_initiator="svc-eligibility-check"
        )
        assert result.query_initiator == "svc-eligibility-check"

    async def test_defaults_to_none_when_omitted(self) -> None:
        engine = MatchingEngine(backend=_EmptyBackend())
        result = await engine.match({"resourceType": "Patient"})
        assert result.query_initiator is None


class TestTable2CombinationEvaluated:
    async def test_matched_rule_id_identifies_the_combination(self) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "08"  # First Name + DOB + MBI

    async def test_rule_evaluations_record_the_combination_per_rule(self) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        matched_evals = [ev for ev in result.rule_evaluations if ev.matched]
        assert any(ev.rule_id == "08" for ev in matched_evals)


class TestMatchType:
    async def test_exact_match_is_recorded(self) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.match_type == "exact"


class TestIdentifiersOfRecordsMatched:
    """Satisfied by RuleEvaluation.field_outcomes - its keys are canonical
    field names, several of which are literally identifiers in the HL7
    sense (mbi, ssn_last4, legal_id, namespace_id, etc.)."""

    async def test_field_outcomes_records_which_identifiers_were_compared(
        self,
    ) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        matched_eval = next(ev for ev in result.rule_evaluations if ev.matched)
        assert matched_eval.field_outcomes.get("mbi") == "exact"


class TestUniquenessCheckResult:
    async def test_is_unique_true_for_single_candidate(self) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.is_unique is True

    async def test_is_unique_false_for_no_candidates(self) -> None:
        engine = MatchingEngine(backend=_EmptyBackend())
        result = await engine.match(_mbi_patient())
        assert result.is_unique is False


class TestFinalMatchDetermination:
    async def test_outcome_reflects_the_determination(self) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH

        no_match_engine = MatchingEngine(backend=_EmptyBackend())
        no_match_result = await no_match_engine.match(_mbi_patient())
        assert no_match_result.outcome == MatchOutcome.NO_MATCH


class TestTimestamp:
    async def test_is_populated_on_a_match(self) -> None:
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.timestamp != ""

    async def test_is_populated_even_with_zero_rule_evaluations(self) -> None:
        """An empty query patient satisfies no rule's field requirements,
        so rule_evaluations is empty - the query-level timestamp must still
        exist for the audit record to be complete."""
        engine = MatchingEngine(backend=_EmptyBackend())
        result = await engine.match({})
        assert result.rule_evaluations == []
        assert result.timestamp != ""
