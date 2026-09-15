"""Tests for the SS VII per-query audit record (session 18, CMS v3.4.0).

Each of the 7 required fields gets its own named test here, so a future
spec revision touching this section trips an obvious, specific failure
rather than a generic regression somewhere else in the suite.
"""

from datetime import datetime, timedelta
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

    async def test_fuzzy_match_is_recorded(self) -> None:
        """The other half of this field's stated purpose ("exact" or
        "fuzzy") was untested. Rule 08 (used elsewhere in this file) has no
        fuzzy-eligible field, so this uses rule 01 (First+Last*+DOB+Street)
        via a last-name transposition."""

        def _street_patient(last: str) -> Dict[str, Any]:
            return {
                "resourceType": "Patient",
                "name": [{"given": ["john"], "family": last}],
                "birthDate": "1990-01-15",
                "telecom": [],
                "address": [{"line": ["123 main st"]}],
            }

        candidate = _street_patient("smtih")
        query = _street_patient("smith")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.match_type == "fuzzy"


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


class TestQueryInitiatorAndTimestampOnEveryOutcomeBranch:
    """Adversarial-review finding (session 18 post-review fix):
    query_initiator/timestamp are hand-copied into 4 separate MatchResult
    construction sites in _build_result (NO_MATCH, single-MATCH, ESCALATE,
    AMBIGUOUS) - only the first two were exercised by any existing test,
    leaving the copy-paste-prone ESCALATE/AMBIGUOUS branches unverified."""

    async def test_present_on_escalate(self) -> None:
        # Two distinct patient records (different id) that both, per the
        # engine's own field-verification, satisfy rule 08 against the same
        # query - identical demographics is the simplest way to construct
        # this without relying on fuzzy matching.
        candidate_a = {**_mbi_patient(), "id": "a"}
        candidate_b = {**_mbi_patient(), "id": "b"}
        engine = MatchingEngine(backend=InMemoryBackend([candidate_a, candidate_b]))
        result = await engine.match(
            _mbi_patient(), query_initiator="svc-eligibility-check"
        )
        assert result.outcome == MatchOutcome.ESCALATE
        assert result.query_initiator == "svc-eligibility-check"
        assert result.timestamp != ""

    async def test_present_on_ambiguous(self) -> None:
        candidates = [{**_mbi_patient(), "id": str(i)} for i in range(3)]
        engine = MatchingEngine(backend=InMemoryBackend(candidates))
        result = await engine.match(
            _mbi_patient(), query_initiator="svc-eligibility-check"
        )
        assert result.outcome == MatchOutcome.AMBIGUOUS
        assert result.query_initiator == "svc-eligibility-check"
        assert result.timestamp != ""


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

    async def test_is_a_well_formed_iso8601_utc_timestamp(self) -> None:
        """Every prior assertion in this class only checked `!= ""` - the
        docstring promises "ISO 8601 UTC" specifically (adversarial-review
        finding, session 18 post-review fix); a malformed string or a naive
        (non-UTC) local timestamp would have passed every existing test."""
        candidate = _mbi_patient()
        query = _mbi_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        parsed = datetime.fromisoformat(result.timestamp)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)
