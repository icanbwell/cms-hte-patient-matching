"""Tests for the CacheManager pipeline."""

from typing import Any, AsyncIterator, Dict

import pytest
from unittest.mock import MagicMock

from patient_matching.cache.cache_manager import CacheManager, CacheManagerConfig
from patient_matching.cache.duckdb_cache import DuckDBCache


def _make_fhir_patient(
    pid: str, first: str = "john", last: str = "smith", dob: str = "1990-01-15"
) -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": pid,
        "name": [{"family": last, "given": [first]}],
        "birthDate": dob,
        "telecom": [{"system": "phone", "value": "+12125551234"}],
        "address": [{"line": ["123 main st"]}],
    }


@pytest.fixture
async def cache() -> AsyncIterator[DuckDBCache]:
    c = DuckDBCache(database=":memory:")
    yield c
    await c.close()


class TestCacheManager:
    async def test_build_cache(self, cache: DuckDBCache) -> None:
        patients = [_make_fhir_patient("p1"), _make_fhir_patient("p2")]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        stats = await manager.build_cache()

        assert stats["patients_fetched"] == 2
        assert stats["patients_cached"] == 2
        assert stats["patients_skipped"] == 0
        assert await cache.count() == 2

    async def test_build_cache_skips_no_id(self, cache: DuckDBCache) -> None:
        patients = [
            {"resourceType": "Patient", "name": [{"family": "smith"}]},
        ]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        stats = await manager.build_cache()

        assert stats["patients_fetched"] == 1
        assert stats["patients_skipped"] == 1
        assert await cache.count() == 0

    async def test_build_cache_clears_existing(self, cache: DuckDBCache) -> None:
        from patient_matching.cache.cache_backend import CachedPatient

        await cache.upsert_patients(
            [
                CachedPatient(
                    patient_id="old",
                    first_names={"old"},
                    fhir_resource={"id": "old"},
                )
            ]
        )
        assert await cache.count() == 1

        patients = [_make_fhir_patient("new")]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        await manager.build_cache()
        assert await cache.count() == 1
        assert await cache.get_patient("old") is None
        assert await cache.get_patient("new") is not None

    async def test_refresh_cache_does_not_clear(self, cache: DuckDBCache) -> None:
        from patient_matching.cache.cache_backend import CachedPatient

        await cache.upsert_patients(
            [
                CachedPatient(
                    patient_id="existing",
                    first_names={"existing"},
                    fhir_resource={"id": "existing"},
                )
            ]
        )

        patients = [_make_fhir_patient("new")]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        await manager.refresh_cache()

        assert await cache.count() == 2
        assert await cache.get_patient("existing") is not None
        assert await cache.get_patient("new") is not None

    async def test_batch_processing(self, cache: DuckDBCache) -> None:
        patients = [_make_fhir_patient(f"p{i}") for i in range(10)]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        config = CacheManagerConfig(batch_size=3)
        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
            config=config,
        )
        stats = await manager.build_cache()

        assert stats["patients_cached"] == 10
        assert await cache.count() == 10

    async def test_patient_count_property(self, cache: DuckDBCache) -> None:
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(
            [
                _make_fhir_patient("p1"),
            ]
        )

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        assert await manager.patient_count() == 0
        await manager.build_cache()
        assert await manager.patient_count() == 1
