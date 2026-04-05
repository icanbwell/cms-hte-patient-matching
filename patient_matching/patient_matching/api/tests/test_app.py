"""Tests for the FastAPI application endpoints."""

import json

import pytest
from fastapi.testclient import TestClient

from patient_matching.api.app import create_app
from patient_matching.api.service import PatientMatcherService
from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache


def _make_cached(pid="p1"):
    return CachedPatient(
        patient_id=pid,
        first_names={"john"},
        last_names={"smith"},
        dob={"1990-01-15"},
        phones={"+12125551234"},
        emails={"john@gmail.com"},
        ssn_last4={"6789"},
        street_lines={"123 main st"},
        fhir_resource={
            "resourceType": "Patient",
            "id": pid,
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
        },
    )


@pytest.fixture
def test_client():
    cache = DuckDBCache(database=":memory:")
    cache.upsert_patients([_make_cached()])
    service = PatientMatcherService(cache=cache)
    app = create_app(service=service)
    client = TestClient(app)
    yield client
    cache.close()


class TestHealthEndpoint:
    def test_health(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestFhirMatchEndpoint:
    def test_match_success(self, test_client):
        params = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "resource",
                    "resource": {
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
                            },
                        ],
                    },
                }
            ],
        }
        resp = test_client.post(
            "/Patient/$match",
            content=json.dumps(params),
            headers={"Content-Type": "application/fhir+json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["resourceType"] == "Bundle"
        assert body["type"] == "searchset"
        assert body["total"] >= 1

    def test_match_no_match(self, test_client):
        params = {
            "resourceType": "Parameters",
            "parameter": [
                {
                    "name": "resource",
                    "resource": {
                        "resourceType": "Patient",
                        "name": [{"family": "jones", "given": ["alice"]}],
                        "birthDate": "2000-12-25",
                    },
                }
            ],
        }
        resp = test_client.post(
            "/Patient/$match",
            content=json.dumps(params),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "searchset"
        assert body.get("total", 0) == 0

    def test_match_invalid_body(self, test_client):
        resp = test_client.post(
            "/Patient/$match",
            content="not json",
        )
        assert resp.status_code == 400

    def test_match_missing_patient(self, test_client):
        params = {
            "resourceType": "Parameters",
            "parameter": [{"name": "count", "valueInteger": 5}],
        }
        resp = test_client.post(
            "/Patient/$match",
            content=json.dumps(params),
        )
        assert resp.status_code == 400


class TestIal2MatchEndpoint:
    def test_ial2_no_extractor_returns_400(self, test_client):
        resp = test_client.post(
            "/match/ial2",
            content=json.dumps({"token": "fake.jwt.token"}),
        )
        # Should return 400 because no IAL2 extractor is configured
        assert resp.status_code == 400

    def test_ial2_empty_token_returns_400(self, test_client):
        resp = test_client.post(
            "/match/ial2",
            content=json.dumps({"token": ""}),
        )
        assert resp.status_code == 400
