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


async def test_search_exact_match_and_semantics() -> None:
    backend = InMemoryBackend(
        [
            _patient("1", "john", "smith", "1985-03-15", "123 main st"),
            _patient("2", "john", "doe", "1990-01-01", "9 oak ave"),
        ]
    )
    # Both criteria must be satisfied by the SAME record (AND).
    results = await backend.search(
        [
            FieldCriterion("first_name", "john"),
            FieldCriterion("last_name", "smith"),
        ]
    )
    assert [p["id"] for p in results] == ["1"]


async def test_search_fuzzy_only_when_requested() -> None:
    backend = InMemoryBackend([_patient("1", "john", "smith", "1985-03-15", "1 a st")])
    # "smyth" is Damerau-Levenshtein distance 1 from "smith" (>=5 chars).
    exact = await backend.search(
        [FieldCriterion("last_name", "smyth", MatchType.EXACT)]
    )
    fuzzy = await backend.search(
        [FieldCriterion("last_name", "smyth", MatchType.FUZZY)]
    )
    assert exact == []
    assert [p["id"] for p in fuzzy] == ["1"]


async def test_search_empty_criteria_returns_nothing() -> None:
    backend = InMemoryBackend([_patient("1", "john", "smith", "1985-03-15", "1 a st")])
    assert await backend.search([]) == []


async def test_search_missing_field_does_not_match() -> None:
    backend = InMemoryBackend([_patient("1", "john", "smith", "1985-03-15", "1 a st")])
    # No email on the record -> criterion cannot be satisfied.
    assert await backend.search([FieldCriterion("email", "a@b.com")]) == []


# --- end-to-end via the MatchingManager ----------------------------------------


async def test_engine_unique_match() -> None:
    backend = InMemoryBackend(
        [
            _patient("1", "john", "smith", "1985-03-15", "123 main st"),
            _patient("2", "maria", "garcia", "1990-07-22", "500 oak ave"),
        ]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "john", "smith", "1985-03-15", "123 main st")
    )
    assert result.outcome == MatchOutcome.MATCH
    assert result.is_unique
    assert result.matched_rule_id == "01"  # First + Last + DOB + Street
    assert [p["id"] for p in result.matched_patients] == ["1"]


async def test_engine_fuzzy_match() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1985-03-15", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    # One-character typo in the (fuzzy-eligible) last name.
    result = await manager.match(
        _patient("q", "john", "smyth", "1985-03-15", "123 main st")
    )
    assert result.outcome == MatchOutcome.MATCH
    assert result.match_type == "fuzzy"


async def test_engine_escalate_is_not_released() -> None:
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
    result = await manager.match(query)
    assert result.outcome == MatchOutcome.ESCALATE
    assert not result.is_unique
    assert result.candidate_count == 2


async def test_engine_no_match() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1985-03-15", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "nancy", "nobody", "1999-09-09", "999 nowhere ln")
    )
    assert result.outcome == MatchOutcome.NO_MATCH


async def test_engine_suffix_conflict_negates_match() -> None:
    candidate = _patient("1", "william", "brownlee", "1960-06-06", "12 king st")
    candidate["name"][0]["suffix"] = ["sr"]
    backend = InMemoryBackend([candidate])
    manager = MatchingManager(backend=backend)
    query = _patient("q", "william", "brownlee", "1960-06-06", "12 king st")
    query["name"][0]["suffix"] = ["jr"]
    result = await manager.match(query)
    assert result.outcome == MatchOutcome.NO_MATCH


# --- DOB +/-1 day tolerance boundary cases (adversarial-review fix) ------------
#
# These exercise the *real* backend-blocking path (InMemoryBackend.search),
# not a stub that returns every candidate unconditionally - the original
# bug (DOB fuzzy blocking routed through Damerau-Levenshtein string edit
# distance instead of calendar-day distance) was invisible to any test
# that bypasses blocking, which is exactly what test_matching_engine.py's
# local `InMemoryBackend` stub does (its `search()` ignores criteria
# entirely and returns every candidate). A date string's edit distance has
# no relationship to its calendar distance - these all describe legitimate
# CMS v3.3 DOB* matches that a string-fuzzy blocking path silently drops.


async def test_dob_month_boundary_one_day_apart_matches() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1990-01-31", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "john", "smith", "1990-02-01", "123 main st")
    )
    assert result.outcome == MatchOutcome.MATCH


async def test_dob_year_boundary_one_day_apart_matches() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1999-12-31", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "john", "smith", "2000-01-01", "123 main st")
    )
    assert result.outcome == MatchOutcome.MATCH


async def test_dob_leap_day_boundary_matches() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "2000-02-29", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "john", "smith", "2000-03-01", "123 main st")
    )
    assert result.outcome == MatchOutcome.MATCH


async def test_dob_digit_rollover_one_day_apart_matches() -> None:
    """ "...-09" -> "...-10" has a large Damerau-Levenshtein distance despite
    being 1 calendar day apart - exactly the class of pair silently dropped
    by routing DOB through the generic string-fuzzy blocking path."""
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1990-01-09", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "john", "smith", "1990-01-10", "123 main st")
    )
    assert result.outcome == MatchOutcome.MATCH


async def test_dob_two_days_apart_still_does_not_match() -> None:
    backend = InMemoryBackend(
        [_patient("1", "john", "smith", "1990-01-15", "123 main st")]
    )
    manager = MatchingManager(backend=backend)
    result = await manager.match(
        _patient("q", "john", "smith", "1990-01-17", "123 main st")
    )
    assert result.outcome == MatchOutcome.NO_MATCH
