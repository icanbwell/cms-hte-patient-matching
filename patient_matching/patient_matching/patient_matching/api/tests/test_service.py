"""Tests for the PatientMatcherService."""

import pytest
from unittest.mock import MagicMock

from patient_matching.api.service import (
    PatientMatcherService,
    _compute_confidence,
)
from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache
from patient_matching.matching.match_result import MatchOutcome, MatchResult


def _populate_cache(cache, patients):
    cache.upsert_patients(patients)


def _make_cached(
    pid,
    first="john",
    last="smith",
    dob="1990-01-15",
    phone="+12125551234",
    email="john@gmail.com",
    ssn_last4="6789",
    street="123 main st",
):
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
def cache():
    c = DuckDBCache(database=":memory:")
    yield c
    c.close()


class TestPatientMatcherService:
    def test_match_patient_exact(self, cache):
        _populate_cache(cache, [_make_cached("p1")])
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
        result = service.match_patient(query)
        assert result.outcome == "match"
        assert "p1" in result.matched_patient_ids
        assert result.confidence_score > 0.99

    def test_match_patient_no_match(self, cache):
        _populate_cache(cache, [_make_cached("p1")])
        service = PatientMatcherService(cache=cache)

        query = {
            "resourceType": "Patient",
            "name": [{"family": "jones", "given": ["alice"]}],
            "birthDate": "2000-12-25",
            "telecom": [{"system": "phone", "value": "+19995551111"}],
        }
        result = service.match_patient(query)
        assert result.outcome == "no_match"
        assert len(result.matched_patient_ids) == 0

    def test_match_from_token_without_extractor(self, cache):
        service = PatientMatcherService(cache=cache)
        with pytest.raises(ValueError, match="IAL2 extractor not configured"):
            service.match_from_token("some.jwt.token")

    def test_match_from_token_with_extractor(self, cache):
        _populate_cache(cache, [_make_cached("p1")])

        mock_extractor = MagicMock()
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
        result = service.match_from_token("fake.jwt.token")
        assert result.outcome == "match"
        mock_extractor.extract.assert_called_once_with("fake.jwt.token")


class TestComputeConfidence:
    def test_no_match_returns_zero(self):
        result = MatchResult(outcome=MatchOutcome.NO_MATCH)
        assert _compute_confidence(result) == 0.0

    def test_match_returns_high_confidence(self):
        result = MatchResult(
            outcome=MatchOutcome.MATCH,
            matched_rule_id="01",
            match_type="exact",
        )
        score = _compute_confidence(result)
        # P(collision) for rule 01 exact is 3e-13
        assert score > 0.99

    def test_ambiguous_returns_zero(self):
        result = MatchResult(outcome=MatchOutcome.AMBIGUOUS)
        assert _compute_confidence(result) == 0.0
