"""Tests for the CacheMatchingBackend adapter."""

from typing import Iterator

import pytest

from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache
from patient_matching.cache.matching_adapter import CacheMatchingBackend
from patient_matching.matching.backend import FieldCriterion, MatchType


@pytest.fixture
def cache() -> Iterator[DuckDBCache]:
    c = DuckDBCache(database=":memory:")
    yield c
    c.close()


def _make_cached_patient(
    pid: str, first: str = "john", last: str = "smith", dob: str = "1990-01-15"
) -> CachedPatient:
    return CachedPatient(
        patient_id=pid,
        first_names={first},
        last_names={last},
        dob={dob},
        fhir_resource={
            "resourceType": "Patient",
            "id": pid,
            "name": [{"family": last, "given": [first]}],
            "birthDate": dob,
        },
    )


class TestCacheMatchingBackend:
    def test_search_exact_match(self, cache: DuckDBCache) -> None:
        cache.upsert_patients([_make_cached_patient("p1")])
        adapter = CacheMatchingBackend(cache)

        results = adapter.search(
            [
                FieldCriterion(field_name="first_name", value="john"),
                FieldCriterion(field_name="last_name", value="smith"),
            ]
        )
        assert len(results) == 1
        assert results[0]["id"] == "p1"

    def test_search_no_match(self, cache: DuckDBCache) -> None:
        cache.upsert_patients([_make_cached_patient("p1")])
        adapter = CacheMatchingBackend(cache)

        results = adapter.search(
            [
                FieldCriterion(field_name="first_name", value="alice"),
            ]
        )
        assert len(results) == 0

    def test_search_and_semantics(self, cache: DuckDBCache) -> None:
        """All criteria must match (AND semantics)."""
        cache.upsert_patients([_make_cached_patient("p1")])
        adapter = CacheMatchingBackend(cache)

        results = adapter.search(
            [
                FieldCriterion(field_name="first_name", value="john"),
                FieldCriterion(field_name="last_name", value="jones"),  # wrong
            ]
        )
        assert len(results) == 0

    def test_search_fuzzy(self, cache: DuckDBCache) -> None:
        cache.upsert_patients([_make_cached_patient("p1", last="smith")])
        adapter = CacheMatchingBackend(cache)

        results = adapter.search(
            [
                FieldCriterion(
                    field_name="last_name",
                    value="smtih",
                    match_type=MatchType.FUZZY,
                ),
            ]
        )
        assert len(results) == 1

    def test_search_empty_criteria(self, cache: DuckDBCache) -> None:
        cache.upsert_patients([_make_cached_patient("p1")])
        adapter = CacheMatchingBackend(cache)

        results = adapter.search([])
        assert len(results) == 0

    def test_search_returns_fhir_resource(self, cache: DuckDBCache) -> None:
        cache.upsert_patients([_make_cached_patient("p1")])
        adapter = CacheMatchingBackend(cache)

        results = adapter.search(
            [
                FieldCriterion(field_name="dob", value="1990-01-15"),
            ]
        )
        assert len(results) == 1
        assert results[0]["resourceType"] == "Patient"
        assert results[0]["id"] == "p1"
