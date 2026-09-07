"""Tests for the DuckDB cache backend."""

from typing import AsyncIterator

import pytest

from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache


@pytest.fixture
async def cache() -> AsyncIterator[DuckDBCache]:
    c = DuckDBCache(database=":memory:")
    yield c
    await c.close()


def _make_cached_patient(
    pid: str = "patient-1",
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
    async def test_upsert_single(self, cache: DuckDBCache) -> None:
        patient = _make_cached_patient()
        count = await cache.upsert_patients([patient])
        assert count == 1
        assert await cache.count() == 1

    async def test_upsert_multiple(self, cache: DuckDBCache) -> None:
        p1 = _make_cached_patient("p1")
        p2 = _make_cached_patient("p2", first="jane", last="doe")
        count = await cache.upsert_patients([p1, p2])
        assert count == 2
        assert await cache.count() == 2

    async def test_upsert_replaces_existing(self, cache: DuckDBCache) -> None:
        p1 = _make_cached_patient("p1", first="john")
        await cache.upsert_patients([p1])

        p1_updated = _make_cached_patient("p1", first="jonathan")
        await cache.upsert_patients([p1_updated])

        assert await cache.count() == 1
        result = await cache.get_patient("p1")
        assert result is not None
        assert "jonathan" in result.first_names

    async def test_upsert_empty_list(self, cache: DuckDBCache) -> None:
        count = await cache.upsert_patients([])
        assert count == 0


class TestDuckDBCacheSearch:
    async def test_search_exact_first_name(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        results = await cache.search_by_field("first_name", "john")
        assert len(results) == 1
        assert results[0].patient_id == "patient-1"

    async def test_search_exact_dob(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        results = await cache.search_by_field("dob", "1990-01-15")
        assert len(results) == 1

    async def test_search_no_match(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        results = await cache.search_by_field("first_name", "alice")
        assert len(results) == 0

    async def test_search_fuzzy_match(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient(last="smith")])
        # "smtih" is DL distance 1 from "smith"
        results = await cache.search_by_field("last_name", "smtih", fuzzy=True)
        assert len(results) == 1

    async def test_search_fuzzy_rejects_short_strings(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient(first="jon")])
        # "jon" is < 5 chars, fuzzy should fall back to exact
        results = await cache.search_by_field("first_name", "jon", fuzzy=True)
        assert len(results) == 1  # exact match works
        results = await cache.search_by_field("first_name", "john", fuzzy=True)
        assert len(results) == 0  # "john" != "jon" exact, both < 5

    async def test_search_fuzzy_rejects_distance_2(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient(last="smith")])
        results = await cache.search_by_field("last_name", "snack", fuzzy=True)
        assert len(results) == 0

    async def test_search_multiple_patients(self, cache: DuckDBCache) -> None:
        p1 = _make_cached_patient("p1", last="smith")
        p2 = _make_cached_patient("p2", last="smith")
        p3 = _make_cached_patient("p3", last="jones")
        await cache.upsert_patients([p1, p2, p3])
        results = await cache.search_by_field("last_name", "smith")
        assert len(results) == 2


class TestDuckDBCacheGet:
    async def test_get_existing(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient("p1")])
        result = await cache.get_patient("p1")
        assert result is not None
        assert result.patient_id == "p1"
        assert "john" in result.first_names

    async def test_get_nonexistent(self, cache: DuckDBCache) -> None:
        result = await cache.get_patient("nonexistent")
        assert result is None


class TestDuckDBCacheLifecycle:
    async def test_clear(self, cache: DuckDBCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        assert await cache.count() == 1
        await cache.clear()
        assert await cache.count() == 0

    async def test_count_empty(self, cache: DuckDBCache) -> None:
        assert await cache.count() == 0
