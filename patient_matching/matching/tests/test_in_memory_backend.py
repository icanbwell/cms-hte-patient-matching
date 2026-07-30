"""Tests for the in-memory matching backend and end-to-end engine wiring."""

from __future__ import annotations

from typing import Any, Dict

from patient_matching.matching import (
    FieldCriterion,
    InMemoryBackend,
    MatchingManager,
    MatchOutcome,
    MatchType,
)


def _patient(
    pid: str, given: str, family: str, dob: str, street: str
) -> Dict[str, Any]:
    """Build a minimal already-normalized FHIR Patient dict."""
    return {
        "resourceType": "Patient",
        "id": pid,
        "name": [{"given": [given], "family": family}],
        "birthDate": dob,
        "address": [{"line": [street]}],
    }


# --- backend.search() semantics -------------------------------------------------


def test_search_exact_match_and_semantics() -> None:
    backend = InMemoryBackend(
        [
            _patient("1", "john", "smith", "1985-03-15", "123 main st"),
            _patient("2", "john", "doe", "1990-01-01", "9 oak ave"),
        ]
    )
    # Both criteria must be satisfied by the SAME record (AND).
    results = backend.search(
        [
            FieldCriterion("first_name", "john"),
            FieldCriterion("last_name", "smith"),
        ]
    )
    assert [p["id"] for p in results] == ["1"]


def test_search_fuzzy_only_when_requested() -> None:
    backend = InMemoryBackend([_patient("1", "john", "smith", "1985-03-15", "1 a st")])
    # "smyth" is Damerau-Levenshtein distance 1 from "smith" (>=5 chars).
    exact = backend.search([FieldCriterion("last_name", "smyth", MatchType.EXACT)])
    fuzzy = backend.search([FieldCriterion("last_name", "smyth", MatchType.FUZZY)])
    assert exact == []
    assert [p["id"] for p in fuzzy] == ["1"]


def test_search_empty_criteria_returns_nothing() -> None:
    backend = InMemoryBackend([_patient("1", "john", "smith", "1985-03-15", "1 a st")])
    assert backend.search([]) == []


def test_search_missing_field_does_not_match() -> None:
    backend = InMemoryBackend([_patient("1", "john", "smith", "1985-03-15", "1 a st")])
    # No email on the record -> criterion cannot be satisfied.
    assert backend.search([FieldCriterion("email", "a@b.com")]) == []


# --- end-to-end via the MatchingManager ----------------------------------------


def test_engine_unique_match() -> None:
    backend = InMemoryBackend(
        [
            _patient("1", "john", "smith", "1985-03-15", "123 main st"),
            _patient("2", "maria", "garcia", "1990-07-22", "500 oak ave"),
        ]
    )
    manager = MatchingManager(backend=backend)
    result = manager.match(_patient("q", "john", "smith", "1985-03-15", "123 main st"))
    assert result.outcome == MatchOutcome.MATCH
    assert result.is_unique
    assert result.matched_rule_id == "01"  # First + Last + DOB + Street
    assert [p["id"] for p in result.matched_patients] == ["1"]


def test_engine_fuzzy_match() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1985-03-15", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    # One-character typo in the (fuzzy-eligible) last name.
    result = manager.match(_patient("q", "john", "smyth", "1985-03-15", "123 main st"))
    assert result.outcome == MatchOutcome.MATCH
    assert result.match_type == "fuzzy"


def test_engine_escalate_is_not_released() -> None:
    # Two different people sharing First + DOB + Phone (Rule 11).
    def with_phone(pid: str, given: str, family: str) -> Dict[str, Any]:
        p = _patient(pid, given, family, "2000-01-01", f"{pid} st")
        p["telecom"] = [{"system": "phone", "value": "+16175550000"}]
        return p

    backend = InMemoryBackend(
        [with_phone("1", "alex", "lee"), with_phone("2", "alex", "park")]
    )
    manager = MatchingManager(backend=backend)
    query = {
        "resourceType": "Patient",
        "id": "q",
        "name": [{"given": ["alex"]}],
        "birthDate": "2000-01-01",
        "telecom": [{"system": "phone", "value": "+16175550000"}],
    }
    result = manager.match(query)
    assert result.outcome == MatchOutcome.ESCALATE
    assert not result.is_unique
    assert result.candidate_count == 2


def test_engine_no_match() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1985-03-15", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = manager.match(
        _patient("q", "nancy", "nobody", "1999-09-09", "999 nowhere ln")
    )
    assert result.outcome == MatchOutcome.NO_MATCH


def test_engine_suffix_conflict_negates_match() -> None:
    candidate = _patient("1", "william", "brownlee", "1960-06-06", "12 king st")
    candidate["name"][0]["suffix"] = ["sr"]
    backend = InMemoryBackend([candidate])
    manager = MatchingManager(backend=backend)
    query = _patient("q", "william", "brownlee", "1960-06-06", "12 king st")
    query["name"][0]["suffix"] = ["jr"]
    result = manager.match(query)
    assert result.outcome == MatchOutcome.NO_MATCH
