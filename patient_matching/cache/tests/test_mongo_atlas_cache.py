"""Tests for the MongoDB Atlas Search-backed cache backend (session_12).

Every test here needs a real Mongo connection (unlike DuckDBCache's
``:memory:`` option) -- they all run against the ``mongodb-atlas-local``
testcontainer (see ``tests/containers/mongodb.py``), skipped automatically
if Docker isn't available.
"""

import time
from collections.abc import Iterator
from typing import List
from unittest.mock import patch

import pytest
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache
from patient_matching.cache.matching_adapter import CacheMatchingBackend
from patient_matching.cache.mongo_atlas_cache import (
    SEARCH_INDEX_NAME,
    MongoAtlasCache,
    search_index_definition,
)
from patient_matching.cache.tests.containers.mongodb import MongoDBService
from patient_matching.matching.backend import FieldCriterion, MatchType

_INDEX_READY_TIMEOUT_SECONDS = 60
_INDEXING_LAG_TIMEOUT_SECONDS = 15


def _search_fuzzy_eventually(
    cache: "MongoAtlasCache", field_name: str, value: str
) -> List[CachedPatient]:
    """Poll fuzzy search until it sees freshly-upserted data.

    Atlas Search indexes asynchronously off the oplog: a document being
    present in ``field_values`` doesn't mean mongot has indexed it yet, even
    once the index itself is "queryable" (that flag means the index exists
    and can be searched, not that it's caught up with the very latest
    write). A short poll -- not a fixed sleep -- absorbs that lag.
    """
    deadline = time.monotonic() + _INDEXING_LAG_TIMEOUT_SECONDS
    results: List[CachedPatient] = []
    while time.monotonic() < deadline:
        results = cache.search_by_field(field_name, value, fuzzy=True)
        if results:
            return results
        time.sleep(0.5)
    return results


def _ensure_search_index(cache: MongoAtlasCache) -> None:
    """Create (if missing) and wait for the Atlas Search index to be queryable."""
    definition = search_index_definition()
    existing = list(cache._field_values.list_search_indexes(SEARCH_INDEX_NAME))
    if not existing:
        cache._field_values.create_search_index(
            SearchIndexModel(
                definition=definition["definition"], name=SEARCH_INDEX_NAME
            )
        )

    deadline = time.monotonic() + _INDEX_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        indexes = list(cache._field_values.list_search_indexes(SEARCH_INDEX_NAME))
        if indexes and indexes[0].get("queryable"):
            return
        time.sleep(1)
    raise TimeoutError(
        f"Atlas Search index {SEARCH_INDEX_NAME!r} not queryable after "
        f"{_INDEX_READY_TIMEOUT_SECONDS}s"
    )


@pytest.fixture(scope="session")
def _atlas_cache_session(mongodb: MongoDBService) -> Iterator[MongoAtlasCache]:
    cache = MongoAtlasCache(
        connection_string=mongodb.connection_string, database="test_patient_cache"
    )
    _ensure_search_index(cache)
    yield cache
    cache.close()


@pytest.fixture
def cache(_atlas_cache_session: MongoAtlasCache) -> Iterator[MongoAtlasCache]:
    yield _atlas_cache_session
    _atlas_cache_session.clear()


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


class TestMongoAtlasCacheUpsert:
    def test_upsert_single(self, cache: MongoAtlasCache) -> None:
        patient = _make_cached_patient()
        count = cache.upsert_patients([patient])
        assert count == 1
        assert cache.count() == 1

    def test_upsert_multiple(self, cache: MongoAtlasCache) -> None:
        p1 = _make_cached_patient("p1")
        p2 = _make_cached_patient("p2", first="jane", last="doe")
        count = cache.upsert_patients([p1, p2])
        assert count == 2
        assert cache.count() == 2

    def test_upsert_is_idempotent(self, cache: MongoAtlasCache) -> None:
        """Upserting the same patient twice doesn't duplicate field_values."""
        p1 = _make_cached_patient("p1", first="john")
        cache.upsert_patients([p1])
        cache.upsert_patients([p1])

        assert cache.count() == 1
        result = cache.get_patient("p1")
        assert result is not None
        assert result.first_names == {"john"}

    def test_upsert_replaces_existing(self, cache: MongoAtlasCache) -> None:
        p1 = _make_cached_patient("p1", first="john")
        cache.upsert_patients([p1])

        p1_updated = _make_cached_patient("p1", first="jonathan")
        cache.upsert_patients([p1_updated])

        assert cache.count() == 1
        result = cache.get_patient("p1")
        assert result is not None
        assert "jonathan" in result.first_names

    def test_upsert_empty_list(self, cache: MongoAtlasCache) -> None:
        count = cache.upsert_patients([])
        assert count == 0


class TestMongoAtlasCacheSearch:
    def test_search_exact_first_name(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient()])
        results = cache.search_by_field("first_name", "john")
        assert len(results) == 1
        assert results[0].patient_id == "patient-1"

    def test_search_no_match(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient()])
        results = cache.search_by_field("first_name", "alice")
        assert len(results) == 0

    def test_search_fuzzy_match(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient(last="smith")])
        # "smtih" is edit distance 1 from "smith"
        results = _search_fuzzy_eventually(cache, "last_name", "smtih")
        assert len(results) == 1

    def test_search_fuzzy_excludes_non_match(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient(last="smith")])
        cache.upsert_patients([_make_cached_patient("p2", last="jones")])
        results = _search_fuzzy_eventually(cache, "last_name", "smtih")
        ids = {p.patient_id for p in results}
        assert ids == {"patient-1"}

    def test_search_fuzzy_rejects_short_strings(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient(first="jon")])
        results = cache.search_by_field("first_name", "jon", fuzzy=True)
        assert len(results) == 1  # exact fallback for <5 chars

    def test_search_multiple_patients(self, cache: MongoAtlasCache) -> None:
        p1 = _make_cached_patient("p1", last="smith")
        p2 = _make_cached_patient("p2", last="smith")
        p3 = _make_cached_patient("p3", last="jones")
        cache.upsert_patients([p1, p2, p3])
        results = cache.search_by_field("last_name", "smith")
        assert len(results) == 2


class TestMongoAtlasCacheGet:
    def test_get_existing(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient("p1")])
        result = cache.get_patient("p1")
        assert result is not None
        assert result.patient_id == "p1"
        assert "john" in result.first_names

    def test_get_nonexistent(self, cache: MongoAtlasCache) -> None:
        result = cache.get_patient("nonexistent")
        assert result is None


class TestMongoAtlasCacheLifecycle:
    def test_clear(self, cache: MongoAtlasCache) -> None:
        cache.upsert_patients([_make_cached_patient()])
        assert cache.count() == 1
        cache.clear()
        assert cache.count() == 0

    def test_count_empty(self, cache: MongoAtlasCache) -> None:
        assert cache.count() == 0


class TestMongoAtlasCacheGracefulDegradation:
    def test_fuzzy_search_without_index_returns_empty(
        self, mongodb: MongoDBService
    ) -> None:
        """No Atlas Search index created yet -> [], not a raise.

        Verified directly against mongodb-atlas-local: a $search referencing
        a nonexistent index name returns an empty cursor rather than
        erroring -- Mongo itself already degrades gracefully here, so this
        case never reaches MongoAtlasCache's own except block (see the next
        test for that).
        """
        cache = MongoAtlasCache(
            connection_string=mongodb.connection_string,
            database="test_patient_cache_no_index",
        )
        try:
            cache.upsert_patients([_make_cached_patient(last="smith")])
            results = cache.search_by_field("last_name", "smtih", fuzzy=True)
            assert results == []
        finally:
            cache.clear()
            cache.close()

    def test_fuzzy_search_atlas_error_returns_empty_and_logs(
        self, cache: MongoAtlasCache, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A genuine Atlas $search failure -> [] + logged error, not a raise.

        Forces the failure deterministically (an actual malformed $search,
        e.g. an out-of-range fuzzy.maxEdits, was confirmed separately to
        raise pymongo.errors.OperationFailure against mongodb-atlas-local --
        mocked here for a fast, deterministic unit test of the except path
        itself).
        """
        cache.upsert_patients([_make_cached_patient(last="smith")])
        with patch.object(
            cache._field_values, "aggregate", side_effect=OperationFailure("boom")
        ):
            results = cache.search_by_field("last_name", "smtih", fuzzy=True)
        assert results == []
        assert any(
            "Atlas $search failed" in record.message for record in caplog.records
        )


class TestMongoAtlasCacheEquivalence:
    """Proves MongoAtlasCache is a drop-in for DuckDBCache (conventions.md's
    "a behavior-preserving change... carries an equivalence test" rule)."""

    def test_same_match_outcome_as_duckdb_cache(self, cache: MongoAtlasCache) -> None:
        duckdb_cache = DuckDBCache(database=":memory:")
        try:
            fixture_patients = [
                _make_cached_patient("p1", first="john", last="smith"),
                _make_cached_patient("p2", first="jane", last="doe", ssn_last4="1234"),
                _make_cached_patient(
                    "p3", first="john", last="smyth", ssn_last4="6789"
                ),
            ]
            cache.upsert_patients(fixture_patients)
            duckdb_cache.upsert_patients(fixture_patients)
            # Let Atlas Search's async indexing catch up before asserting.
            _search_fuzzy_eventually(cache, "last_name", "smtih")

            criteria = [
                FieldCriterion("first_name", "john", MatchType.EXACT),
                FieldCriterion("last_name", "smtih", MatchType.FUZZY),
            ]

            mongo_backend = CacheMatchingBackend(cache)
            duckdb_backend = CacheMatchingBackend(duckdb_cache)

            mongo_ids = {c["id"] for c in mongo_backend.search(criteria)}
            duckdb_ids = {c["id"] for c in duckdb_backend.search(criteria)}

            assert mongo_ids == duckdb_ids == {"p1"}
        finally:
            duckdb_cache.close()
