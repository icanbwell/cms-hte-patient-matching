"""Tests for the PatientMatcherService."""

from typing import AsyncIterator, List

import pytest
from unittest.mock import MagicMock

from patient_matching.api.service import (
    PatientMatcherService,
    _compute_confidence,
)
from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache
from patient_matching.ial2_extraction.ial2_extractor import IAL2Extractor
from patient_matching.matching.match_result import MatchOutcome, MatchResult


async def _populate_cache(cache: DuckDBCache, patients: List[CachedPatient]) -> None:
    await cache.upsert_patients(patients)


def _make_cached(
    pid: str,
    first: str = "john",
    last: str = "smith",
    dob: str = "1990-01-15",
    phone: str = "+12125551234",
    email: str = "john@gmail.com",
    ssn_last4: str = "6789",
    street: str = "123 main st",
) -> CachedPatient:
    return CachedPatient(
        patient_id=pid,
        first_names={first},
        last_names={last},
        dob={dob},
        phones={phone},
        emails={email},
        ssn_last4={ssn_last4},
        street_lines={street},
        fhir_resource={
            "resourceType": "Patient",
            "id": pid,
            "name": [{"family": last, "given": [first]}],
            "birthDate": dob,
            "telecom": [
                {"system": "phone", "value": phone},
                {"system": "email", "value": email},
            ],
            "address": [{"line": [street]}],
            "identifier": [
                {
                    "system": "http://hl7.org/fhir/sid/us-ssn",
                    "value": f"xxx-xx-{ssn_last4}",
                },
            ],
        },
    )


@pytest.fixture
async def cache() -> AsyncIterator[DuckDBCache]:
    c = DuckDBCache(database=":memory:")
    yield c
    await c.close()


class TestPatientMatcherService:
    async def test_match_patient_exact(self, cache: DuckDBCache) -> None:
        await _populate_cache(cache, [_make_cached("p1")])
        service = PatientMatcherService(cache=cache)

        query = {
            "resourceType": "Patient",
            "name": [{"family": "smith", "given": ["john"]}],
            "birthDate": "1990-01-15",
            "telecom": [
                {"system": "phone", "value": "+12125551234"},
                {"system": "email", "value": "john@gmail.com"},
            ],
            "address": [{"line": ["123 main st"]}],
            "identifier": [
                {"system": "http://hl7.org/fhir/sid/us-ssn", "value": "xxx-xx-6789"},
            ],
        }
        result = await service.match_patient(query)
        assert result.outcome == "match"
        assert "p1" in result.matched_patient_ids
        assert result.confidence_score > 0.99

    async def test_match_patient_no_match(self, cache: DuckDBCache) -> None:
        await _populate_cache(cache, [_make_cached("p1")])
        service = PatientMatcherService(cache=cache)

        query = {
            "resourceType": "Patient",
            "name": [{"family": "jones", "given": ["alice"]}],
            "birthDate": "2000-12-25",
            "telecom": [{"system": "phone", "value": "+19995551111"}],
        }
        result = await service.match_patient(query)
        assert result.outcome == "no_match"
        assert len(result.matched_patient_ids) == 0

    async def test_match_from_token_without_extractor(self, cache: DuckDBCache) -> None:
        service = PatientMatcherService(cache=cache)
        with pytest.raises(ValueError, match="IAL2 extractor not configured"):
            await service.match_from_token("some.jwt.token")

    async def test_match_from_token_with_extractor(self, cache: DuckDBCache) -> None:
        await _populate_cache(cache, [_make_cached("p1")])

        mock_extractor = MagicMock(spec=IAL2Extractor)
        mock_extractor.extract.return_value = {
            "resourceType": "Patient",
            "name": [{"family": "smith", "given": ["john"]}],
            "birthDate": "1990-01-15",
            "telecom": [
                {"system": "phone", "value": "+12125551234"},
                {"system": "email", "value": "john@gmail.com"},
            ],
            "address": [{"line": ["123 main st"]}],
            "identifier": [
                {"system": "http://hl7.org/fhir/sid/us-ssn", "value": "xxx-xx-6789"},
            ],
        }

        service = PatientMatcherService(cache=cache, ial2_extractor=mock_extractor)
        result = await service.match_from_token("fake.jwt.token")
        assert result.outcome == "match"
        mock_extractor.extract.assert_called_once_with("fake.jwt.token")

    async def test_match_patient_echoes_query_initiator(
        self, cache: DuckDBCache
    ) -> None:
        """SS VII audit field (session 18) - passed through unvalidated."""
        await _populate_cache(cache, [_make_cached("p1")])
        service = PatientMatcherService(cache=cache)

        query = {
            "resourceType": "Patient",
            "name": [{"family": "smith", "given": ["john"]}],
            "birthDate": "1990-01-15",
            "telecom": [
                {"system": "phone", "value": "+12125551234"},
                {"system": "email", "value": "john@gmail.com"},
            ],
            "address": [{"line": ["123 main st"]}],
            "identifier": [
                {"system": "http://hl7.org/fhir/sid/us-ssn", "value": "xxx-xx-6789"},
            ],
        }
        result = await service.match_patient(query, query_initiator="svc-portal")
        assert result.query_initiator == "svc-portal"
        assert result.timestamp != ""

    async def test_match_patient_query_initiator_defaults_to_none(
        self, cache: DuckDBCache
    ) -> None:
        """Absence of a query initiator must not break existing callers."""
        service = PatientMatcherService(cache=cache)
        query = {
            "resourceType": "Patient",
            "name": [{"family": "jones", "given": ["alice"]}],
            "birthDate": "2000-12-25",
        }
        result = await service.match_patient(query)
        assert result.query_initiator is None

    async def test_match_from_token_echoes_query_initiator(
        self, cache: DuckDBCache
    ) -> None:
        mock_extractor = MagicMock(spec=IAL2Extractor)
        mock_extractor.extract.return_value = {
            "resourceType": "Patient",
            "name": [{"family": "jones", "given": ["alice"]}],
            "birthDate": "2000-12-25",
        }
        service = PatientMatcherService(cache=cache, ial2_extractor=mock_extractor)
        result = await service.match_from_token(
            "fake.jwt.token", query_initiator="mobile-app"
        )
        assert result.query_initiator == "mobile-app"


class TestComputeConfidence:
    def test_no_match_returns_zero(self) -> None:
        result = MatchResult(outcome=MatchOutcome.NO_MATCH)
        assert _compute_confidence(result) == 0.0

    def test_match_returns_high_confidence(self) -> None:
        result = MatchResult(
            outcome=MatchOutcome.MATCH,
            matched_rule_id="01",
            match_type="exact",
        )
        score = _compute_confidence(result)
        # P(collision) for rule 01 exact is 3e-13
        assert score > 0.99

    def test_ambiguous_returns_zero(self) -> None:
        result = MatchResult(outcome=MatchOutcome.AMBIGUOUS)
        assert _compute_confidence(result) == 0.0

    def test_c2_39_match_returns_high_confidence(self) -> None:
        """Regression guard for this PR's own headline fix: service.py's
        confidence lookup previously only searched the original 8 Category
        2 rules, so a C2-39/C2-40 match silently scored 0.0 confidence. The
        Execution notes justified skipping this test as needing "the full
        IAL2/cache pipeline," which isn't true - _compute_confidence takes
        a bare MatchResult, same as test_match_returns_high_confidence
        above."""
        result = MatchResult(
            outcome=MatchOutcome.MATCH,
            matched_rule_id="C2-39",
            match_type="exact",
        )
        assert _compute_confidence(result) > 0.99

    def test_c2_40_match_returns_high_confidence(self) -> None:
        result = MatchResult(
            outcome=MatchOutcome.MATCH,
            matched_rule_id="C2-40",
            match_type="exact",
        )
        assert _compute_confidence(result) > 0.99
