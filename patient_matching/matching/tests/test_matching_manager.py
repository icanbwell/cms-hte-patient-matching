"""Tests for MatchingManager."""

from typing import Any, Dict, List

from patient_matching.matching.backend import FieldCriterion, MatchingBackend
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_manager import MatchingManager
from patient_matching.matching.table2_rules import APPROVED_RULES


class InMemoryBackend(MatchingBackend):
    def __init__(self, patients: List[Dict[str, Any]]):
        self._patients = patients

    def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return list(self._patients)


def _make_patient(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "resourceType": "Patient",
        "name": [{"family": "smith", "given": ["john"]}],
        "birthDate": "1990-01-15",
        "telecom": [
            {"system": "phone", "value": "+12125551234"},
            {"system": "email", "value": "john@gmail.com"},
        ],
        "address": [{"line": ["123 main st"]}],
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/us-ssn",
                "value": "xxx-xx-6789",
            }
        ],
    }
    base.update(overrides)
    return base


class TestMatchingManager:
    def test_match_returns_result(self) -> None:
        backend = InMemoryBackend([_make_patient()])
        manager = MatchingManager(backend=backend)
        result = manager.match(_make_patient())
        assert result.outcome == MatchOutcome.MATCH

    def test_match_batch(self) -> None:
        backend = InMemoryBackend([_make_patient()])
        manager = MatchingManager(backend=backend)
        results = manager.match_batch([_make_patient(), _make_patient()])
        assert len(results) == 2
        assert all(r.outcome == MatchOutcome.MATCH for r in results)

    def test_rule_count(self) -> None:
        backend = InMemoryBackend([])
        manager = MatchingManager(backend=backend)
        assert manager.rule_count == 26

    def test_custom_rules(self) -> None:
        backend = InMemoryBackend([])
        subset = APPROVED_RULES[:5]
        manager = MatchingManager(backend=backend, rules=subset)
        assert manager.rule_count == 5
        assert manager.rules == subset

    def test_no_match_empty_backend(self) -> None:
        backend = InMemoryBackend([])
        manager = MatchingManager(backend=backend)
        result = manager.match(_make_patient())
        assert result.outcome == MatchOutcome.NO_MATCH
