"""Tests for the DuckDB cache backend."""

import pytest

from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache


@pytest.fixture
def cache():
    c = DuckDBCache(database=":memory:")
    yield c
    c.close()


def _make_cached_patient(
    pid="patient-1",
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
        first_names={first} if first else set(),
        last_names={last} if last else set(),
        dob={dob} if dob else set(),
        phones={phone} if phone else set(),
        emails={email} if email else set(),
        ssn_last4={ssn_last4} if ssn_last4 else set(),
        street_lines={street} if street else set(),
        fhir_resource={
            "resourceType": "Patient",
            "id": pid,
            "name": [{"family": last, "given": [first]}],
            "birthDate": dob,
        },
    )


class TestDuckDBCacheUpsert:
    def test_upsert_single(self, cache):
        patient = _make_cached_patient()
        count = cache.upsert_patients([patient])
        assert count == 1
        assert cache.count() == 1

    def test_upsert_multiple(self, cache):
        p1 = _make_cached_patient("p1")
        p2 = _make_cached_patient("p2", first="jane", last="doe")
        count = cache.upsert_patients([p1, p2])
        assert count == 2
        assert cache.count() == 2

    def test_upsert_replaces_existing(self, cache):
        p1 = _make_cached_patient("p1", first="john")
        cache.upsert_patients([p1])

        p1_updated = _make_cached_patient("p1", first="jonathan")
        cache.upsert_patients([p1_updated])

        assert cache.count() == 1
        result = cache.get_patient("p1")
        assert result is not None
        assert "jonathan" in result.first_names

    def test_upsert_empty_list(self, cache):
        count = cache.upsert_patients([])
        assert count == 0


class TestDuckDBCacheSearch:
    def test_search_exact_first_name(self, cache):
        cache.upsert_patients([_make_cached_patient()])
        results = cache.search_by_field("first_name", "john")
        assert len(results) == 1
        assert results[0].patient_id == "patient-1"

    def test_search_exact_dob(self, cache):
        cache.upsert_patients([_make_cached_patient()])
        results = cache.search_by_field("dob", "1990-01-15")
        assert len(results) == 1

    def test_search_no_match(self, cache):
        cache.upsert_patients([_make_cached_patient()])
        results = cache.search_by_field("first_name", "alice")
        assert len(results) == 0

    def test_search_fuzzy_match(self, cache):
        cache.upsert_patients([_make_cached_patient(last="smith")])
        # "smtih" is DL distance 1 from "smith"
        results = cache.search_by_field("last_name", "smtih", fuzzy=True)
        assert len(results) == 1

    def test_search_fuzzy_rejects_short_strings(self, cache):
        cache.upsert_patients([_make_cached_patient(first="jon")])
        # "jon" is < 5 chars, fuzzy should fall back to exact
        results = cache.search_by_field("first_name", "jon", fuzzy=True)
        assert len(results) == 1  # exact match works
        results = cache.search_by_field("first_name", "john", fuzzy=True)
        assert len(results) == 0  # "john" != "jon" exact, both < 5

    def test_search_fuzzy_rejects_distance_2(self, cache):
        cache.upsert_patients([_make_cached_patient(last="smith")])
        results = cache.search_by_field("last_name", "snack", fuzzy=True)
        assert len(results) == 0

    def test_search_multiple_patients(self, cache):
        p1 = _make_cached_patient("p1", last="smith")
        p2 = _make_cached_patient("p2", last="smith")
        p3 = _make_cached_patient("p3", last="jones")
        cache.upsert_patients([p1, p2, p3])
        results = cache.search_by_field("last_name", "smith")
        assert len(results) == 2


class TestDuckDBCacheGet:
    def test_get_existing(self, cache):
        cache.upsert_patients([_make_cached_patient("p1")])
        result = cache.get_patient("p1")
        assert result is not None
        assert result.patient_id == "p1"
        assert "john" in result.first_names

    def test_get_nonexistent(self, cache):
        result = cache.get_patient("nonexistent")
        assert result is None


class TestDuckDBCacheLifecycle:
    def test_clear(self, cache):
        cache.upsert_patients([_make_cached_patient()])
        assert cache.count() == 1
        cache.clear()
        assert cache.count() == 0

    def test_count_empty(self, cache):
        assert cache.count() == 0
