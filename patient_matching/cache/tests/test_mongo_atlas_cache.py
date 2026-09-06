"""Tests for the MongoDB Atlas Search-backed cache backend (session_12).

Every test here needs a real Mongo connection (unlike DuckDBCache's
``:memory:`` option) -- they all run against the ``mongodb-atlas-local``
testcontainer (see ``tests/containers/mongodb.py``), skipped automatically
if Docker isn't available.
"""

import asyncio
import sys
import time
from collections.abc import AsyncIterator
from typing import List
from unittest.mock import patch

import pytest
import pytest_asyncio
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


async def _search_fuzzy_eventually(
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
        results = await cache.search_by_field(field_name, value, fuzzy=True)
        if results:
            return results
        await asyncio.sleep(0.5)
    return results


async def _ensure_search_index(cache: MongoAtlasCache) -> None:
    """Create (if missing) and wait for the Atlas Search index to be queryable.

    Atlas Search index creation requires the collection to already exist
    (unlike a regular index, which auto-creates it) -- cache._ensure_indexes()
    creates the collection as a side effect of creating the two regular
    indexes, so it must run first.
    """
    await cache._ensure_indexes()
    definition = search_index_definition()
    existing_cursor = await cache._field_values.list_search_indexes(SEARCH_INDEX_NAME)
    existing = [idx async for idx in existing_cursor]
    if not existing:
        await cache._field_values.create_search_index(
            SearchIndexModel(
                definition=definition["definition"], name=SEARCH_INDEX_NAME
            )
        )

    deadline = time.monotonic() + _INDEX_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        indexes_cursor = await cache._field_values.list_search_indexes(
            SEARCH_INDEX_NAME
        )
        indexes = [idx async for idx in indexes_cursor]
        if indexes and indexes[0].get("queryable"):
            return
        await asyncio.sleep(1)
    raise TimeoutError(
        f"Atlas Search index {SEARCH_INDEX_NAME!r} not queryable after "
        f"{_INDEX_READY_TIMEOUT_SECONDS}s"
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _atlas_cache_session(
    mongodb: MongoDBService,
) -> AsyncIterator[MongoAtlasCache]:
    cache = MongoAtlasCache(
        connection_string=mongodb.connection_string, database="test_patient_cache"
    )
    await _ensure_search_index(cache)
    yield cache
    await cache.close()


@pytest_asyncio.fixture(loop_scope="session")
async def cache(
    _atlas_cache_session: MongoAtlasCache,
) -> AsyncIterator[MongoAtlasCache]:
    yield _atlas_cache_session
    await _atlas_cache_session.clear()


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


class TestMongoAtlasCacheImportGuard:
    def test_missing_pymongo_raises_helpful_import_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No real Mongo/Docker needed: the ImportError is raised before any
        connection attempt, from the ``from pymongo import ...`` in __init__.
        """
        monkeypatch.setitem(sys.modules, "pymongo", None)
        with pytest.raises(ImportError, match=r"pip install patient_matching\[mongo\]"):
            MongoAtlasCache()


# AsyncMongoClient is bound to the event loop it's created on, and
# _atlas_cache_session shares one across a whole test session (to avoid
# paying the ~60s Atlas Search index setup per test) -- so every test
# using it must run on that same session-scoped loop, not pytest-asyncio's
# per-test default.
@pytest.mark.asyncio(loop_scope="session")
class TestMongoAtlasCacheUpsert:
    async def test_upsert_single(self, cache: MongoAtlasCache) -> None:
        patient = _make_cached_patient()
        count = await cache.upsert_patients([patient])
        assert count == 1
        assert await cache.count() == 1

    async def test_upsert_multiple(self, cache: MongoAtlasCache) -> None:
        p1 = _make_cached_patient("p1")
        p2 = _make_cached_patient("p2", first="jane", last="doe")
        count = await cache.upsert_patients([p1, p2])
        assert count == 2
        assert await cache.count() == 2

    async def test_upsert_is_idempotent(self, cache: MongoAtlasCache) -> None:
        """Upserting the same patient twice doesn't duplicate field_values."""
        p1 = _make_cached_patient("p1", first="john")
        await cache.upsert_patients([p1])
        await cache.upsert_patients([p1])

        assert await cache.count() == 1
        result = await cache.get_patient("p1")
        assert result is not None
        assert result.first_names == {"john"}

    async def test_upsert_replaces_existing(self, cache: MongoAtlasCache) -> None:
        p1 = _make_cached_patient("p1", first="john")
        await cache.upsert_patients([p1])

        p1_updated = _make_cached_patient("p1", first="jonathan")
        await cache.upsert_patients([p1_updated])

        assert await cache.count() == 1
        result = await cache.get_patient("p1")
        assert result is not None
        assert "jonathan" in result.first_names

    async def test_upsert_empty_list(self, cache: MongoAtlasCache) -> None:
        count = await cache.upsert_patients([])
        assert count == 0


@pytest.mark.asyncio(loop_scope="session")
class TestMongoAtlasCacheSearch:
    async def test_search_exact_first_name(self, cache: MongoAtlasCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        results = await cache.search_by_field("first_name", "john")
        assert len(results) == 1
        assert results[0].patient_id == "patient-1"

    async def test_search_no_match(self, cache: MongoAtlasCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        results = await cache.search_by_field("first_name", "alice")
        assert len(results) == 0

    async def test_search_fuzzy_match(self, cache: MongoAtlasCache) -> None:
        await cache.upsert_patients([_make_cached_patient(last="smith")])
        # "smtih" is edit distance 1 from "smith"
        results = await _search_fuzzy_eventually(cache, "last_name", "smtih")
        assert len(results) == 1

    async def test_search_fuzzy_excludes_non_match(
        self, cache: MongoAtlasCache
    ) -> None:
        await cache.upsert_patients([_make_cached_patient(last="smith")])
        await cache.upsert_patients([_make_cached_patient("p2", last="jones")])
        results = await _search_fuzzy_eventually(cache, "last_name", "smtih")
        ids = {p.patient_id for p in results}
        assert ids == {"patient-1"}

    async def test_search_fuzzy_rejects_short_strings(
        self, cache: MongoAtlasCache
    ) -> None:
        await cache.upsert_patients([_make_cached_patient(first="jon")])
        results = await cache.search_by_field("first_name", "jon", fuzzy=True)
        assert len(results) == 1  # exact fallback for <5 chars

    async def test_search_multiple_patients(self, cache: MongoAtlasCache) -> None:
        p1 = _make_cached_patient("p1", last="smith")
        p2 = _make_cached_patient("p2", last="smith")
        p3 = _make_cached_patient("p3", last="jones")
        await cache.upsert_patients([p1, p2, p3])
        results = await cache.search_by_field("last_name", "smith")
        assert len(results) == 2

    async def test_multivalued_field_searchable_by_each_value(
        self, cache: MongoAtlasCache
    ) -> None:
        """A patient with >1 value for a field (e.g. two phone numbers) is
        findable by any one of them, and get_patient() returns the full set.
        """
        patient = _make_cached_patient("p1")
        patient.phones = {"+12125551234", "+13105559876"}
        await cache.upsert_patients([patient])

        for phone in patient.phones:
            results = await cache.search_by_field("phone", phone)
            assert {p.patient_id for p in results} == {"p1"}

        stored = await cache.get_patient("p1")
        assert stored is not None
        assert stored.phones == patient.phones


@pytest.mark.asyncio(loop_scope="session")
class TestMongoAtlasCacheGet:
    async def test_get_existing(self, cache: MongoAtlasCache) -> None:
        await cache.upsert_patients([_make_cached_patient("p1")])
        result = await cache.get_patient("p1")
        assert result is not None
        assert result.patient_id == "p1"
        assert "john" in result.first_names

    async def test_get_nonexistent(self, cache: MongoAtlasCache) -> None:
        result = await cache.get_patient("nonexistent")
        assert result is None


@pytest.mark.asyncio(loop_scope="session")
class TestMongoAtlasCacheLifecycle:
    async def test_clear(self, cache: MongoAtlasCache) -> None:
        await cache.upsert_patients([_make_cached_patient()])
        assert await cache.count() == 1
        await cache.clear()
        assert await cache.count() == 0

    async def test_count_empty(self, cache: MongoAtlasCache) -> None:
        assert await cache.count() == 0


@pytest.mark.asyncio(loop_scope="session")
class TestMongoAtlasCacheGracefulDegradation:
    async def test_fuzzy_search_without_index_returns_empty(
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
            await cache.upsert_patients([_make_cached_patient(last="smith")])
            results = await cache.search_by_field("last_name", "smtih", fuzzy=True)
            assert results == []
        finally:
            await cache.clear()
            await cache.close()

    async def test_fuzzy_search_atlas_error_returns_empty_and_logs(
        self, cache: MongoAtlasCache, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A genuine Atlas $search failure -> [] + logged error, not a raise.

        Forces the failure deterministically (an actual malformed $search,
        e.g. an out-of-range fuzzy.maxEdits, was confirmed separately to
        raise pymongo.errors.OperationFailure against mongodb-atlas-local --
        mocked here for a fast, deterministic unit test of the except path
        itself).
        """
        await cache.upsert_patients([_make_cached_patient(last="smith")])
        with patch.object(
            cache._field_values, "aggregate", side_effect=OperationFailure("boom")
        ):
            results = await cache.search_by_field("last_name", "smtih", fuzzy=True)
        assert results == []
        assert any(
            "Atlas $search failed" in record.message for record in caplog.records
        )


@pytest.mark.asyncio(loop_scope="session")
class TestMongoAtlasCacheEquivalence:
    """Proves MongoAtlasCache is a drop-in for DuckDBCache (conventions.md's
    "a behavior-preserving change... carries an equivalence test" rule)."""

    async def test_same_match_outcome_as_duckdb_cache(
        self, cache: MongoAtlasCache
    ) -> None:
        duckdb_cache = DuckDBCache(database=":memory:")
        try:
            fixture_patients = [
                _make_cached_patient("p1", first="john", last="smith"),
                _make_cached_patient("p2", first="jane", last="doe", ssn_last4="1234"),
                _make_cached_patient(
                    "p3", first="john", last="smyth", ssn_last4="6789"
                ),
            ]
            await cache.upsert_patients(fixture_patients)
            await duckdb_cache.upsert_patients(fixture_patients)
            # Let Atlas Search's async indexing catch up before asserting.
            await _search_fuzzy_eventually(cache, "last_name", "smtih")

            criteria = [
                FieldCriterion("first_name", "john", MatchType.EXACT),
                FieldCriterion("last_name", "smtih", MatchType.FUZZY),
            ]

            mongo_backend = CacheMatchingBackend(cache)
            duckdb_backend = CacheMatchingBackend(duckdb_cache)

            mongo_ids = {c["id"] for c in await mongo_backend.search(criteria)}
            duckdb_ids = {c["id"] for c in await duckdb_backend.search(criteria)}

            assert mongo_ids == duckdb_ids == {"p1"}
        finally:
            await duckdb_cache.close()
