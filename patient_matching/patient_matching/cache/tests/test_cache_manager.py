"""Tests for the CacheManager pipeline."""

import pytest
from unittest.mock import MagicMock, patch

from patient_matching.cache.cache_manager import CacheManager, CacheManagerConfig
from patient_matching.cache.duckdb_cache import DuckDBCache


def _make_fhir_patient(pid, first="john", last="smith", dob="1990-01-15"):
    return {
        "resourceType": "Patient",
        "id": pid,
        "name": [{"family": last, "given": [first]}],
        "birthDate": dob,
        "telecom": [{"system": "phone", "value": "+12125551234"}],
        "address": [{"line": ["123 main st"]}],
    }


@pytest.fixture
def cache():
    c = DuckDBCache(database=":memory:")
    yield c
    c.close()


class TestCacheManager:
    def test_build_cache(self, cache):
        patients = [_make_fhir_patient("p1"), _make_fhir_patient("p2")]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        stats = manager.build_cache()

        assert stats["patients_fetched"] == 2
        assert stats["patients_cached"] == 2
        assert stats["patients_skipped"] == 0
        assert cache.count() == 2

    def test_build_cache_skips_no_id(self, cache):
        patients = [
            {"resourceType": "Patient", "name": [{"family": "smith"}]},
        ]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        stats = manager.build_cache()

        assert stats["patients_fetched"] == 1
        assert stats["patients_skipped"] == 1
        assert cache.count() == 0

    def test_build_cache_clears_existing(self, cache):
        from patient_matching.cache.cache_backend import CachedPatient

        cache.upsert_patients([
            CachedPatient(
                patient_id="old",
                first_names={"old"},
                fhir_resource={"id": "old"},
            )
        ])
        assert cache.count() == 1

        patients = [_make_fhir_patient("new")]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        manager.build_cache()
        assert cache.count() == 1
        assert cache.get_patient("old") is None
        assert cache.get_patient("new") is not None

    def test_refresh_cache_does_not_clear(self, cache):
        from patient_matching.cache.cache_backend import CachedPatient

        cache.upsert_patients([
            CachedPatient(
                patient_id="existing",
                first_names={"existing"},
                fhir_resource={"id": "existing"},
            )
        ])

        patients = [_make_fhir_patient("new")]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        manager.refresh_cache()

        assert cache.count() == 2
        assert cache.get_patient("existing") is not None
        assert cache.get_patient("new") is not None

    def test_batch_processing(self, cache):
        patients = [_make_fhir_patient(f"p{i}") for i in range(10)]
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter(patients)

        config = CacheManagerConfig(batch_size=3)
        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
            config=config,
        )
        stats = manager.build_cache()

        assert stats["patients_cached"] == 10
        assert cache.count() == 10

    def test_patient_count_property(self, cache):
        mock_fhir_client = MagicMock()
        mock_fhir_client.fetch_all_patients.return_value = iter([
            _make_fhir_patient("p1"),
        ])

        manager = CacheManager(
            fhir_client=mock_fhir_client,
            cache=cache,
        )
        assert manager.patient_count == 0
        manager.build_cache()
        assert manager.patient_count == 1
