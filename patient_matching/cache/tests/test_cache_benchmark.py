"""Benchmark: MongoAtlasCache vs. DuckDBCache round-trip count & latency.

Session 12, Task 6 / Open Question 2: MatchingEngine.match() calls
backend.search() once per Table 2 rule (~38 rules total: 30 flat +
8 household/individual), and CacheMatchingBackend.search() calls
cache.search_by_field() once per criterion within each rule. With
DuckDBCache this is in-process SQL; with MongoAtlasCache each call is a
real network round-trip. This is exploratory data for that open question,
not a pass/fail gate (session_12.md's Validation section: "no fixed
pass/fail threshold required for this session").

Pool size: Imran decided ~1,000,000+ candidates is the realistic size for
cms-hte-patient-matching-service's expected production load. Actually
inserting/indexing 1M documents on every `make tests` run would make the
default test suite impractically slow (Atlas Search index builds are not
instant, and DuckDB's fuzzy path is a real O(n) Python scan over that many
rows). Per conventions.md's "no silent caps" rule, this is flagged rather
than silently downsized: the default run here uses
BENCHMARK_POOL_SIZE_DEFAULT candidates so `make tests` stays fast; run with
BENCHMARK_POOL_SIZE=1000000 (env var) for the actual decided-on size.
"""

from __future__ import annotations

import logging
import os
import statistics
import time
from collections.abc import Iterator
from typing import List
from unittest.mock import patch

import pytest

from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache
from patient_matching.cache.matching_adapter import CacheMatchingBackend
from patient_matching.cache.mongo_atlas_cache import MongoAtlasCache
from patient_matching.cache.tests.containers.mongodb import MongoDBService
from patient_matching.cache.tests.test_mongo_atlas_cache import _ensure_search_index
from patient_matching.matching.matching_engine import MatchingEngine

logger = logging.getLogger(__name__)

BENCHMARK_POOL_SIZE_DEFAULT = 1_000
_UPSERT_CHUNK_SIZE = 2_000


def _pool_size() -> int:
    return int(os.environ.get("BENCHMARK_POOL_SIZE", BENCHMARK_POOL_SIZE_DEFAULT))


def _generate_patients(n: int) -> Iterator[CachedPatient]:
    """Synthetic patients spread across a realistic field-value range.

    Every 97th patient shares the query patient's exact name/DOB (see
    _QUERY_PATIENT below) so blocking keys actually return a non-trivial
    candidate set, not just misses.
    """
    for i in range(n):
        pid = f"bench-{i}"
        if i % 97 == 0:
            first, last, dob = "john", "smith", "1980-05-15"
        else:
            first, last, dob = (
                f"first{i % 5000}",
                f"last{i % 5000}",
                (f"19{50 + i % 50:02d}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"),
            )
        yield CachedPatient(
            patient_id=pid,
            first_names={first},
            last_names={last},
            dob={dob},
            phones={f"+1212555{i % 10000:04d}"},
            emails={f"{first}.{last}{i}@example.com"},
            ssn_last4={f"{i % 10000:04d}"},
            street_lines={f"{i} main st"},
            fhir_resource={
                "resourceType": "Patient",
                "id": pid,
                "name": [{"family": last, "given": [first]}],
                "birthDate": dob,
                "telecom": [
                    {"system": "phone", "value": f"+1212555{i % 10000:04d}"},
                    {"system": "email", "value": f"{first}.{last}{i}@example.com"},
                ],
                "address": [{"line": [f"{i} main st"], "postalCode": "10001"}],
                "identifier": [
                    {
                        "system": "http://hl7.org/fhir/sid/us-ssn",
                        "value": f"000-00-{i % 10000:04d}",
                    }
                ],
            },
        )


_QUERY_PATIENT = {
    "resourceType": "Patient",
    "id": "query-patient",
    "name": [{"family": "smith", "given": ["john"]}],
    "birthDate": "1980-05-15",
    "telecom": [
        {"system": "phone", "value": "+12125550000"},
        {"system": "email", "value": "john.smith@example.com"},
    ],
    "address": [{"line": ["1 main st"], "postalCode": "10001"}],
    "identifier": [
        {"system": "http://hl7.org/fhir/sid/us-ssn", "value": "000-00-0000"}
    ],
}


def _load(cache: DuckDBCache | MongoAtlasCache, n: int) -> None:
    chunk: List[CachedPatient] = []
    for patient in _generate_patients(n):
        chunk.append(patient)
        if len(chunk) >= _UPSERT_CHUNK_SIZE:
            cache.upsert_patients(chunk)
            chunk = []
    if chunk:
        cache.upsert_patients(chunk)


def _wait_for_indexing_to_settle(
    cache: MongoAtlasCache, timeout_seconds: float = 30.0
) -> None:
    """Poll until the query patient's own cluster is fuzzy-searchable.

    Bounds (doesn't eliminate) the Atlas Search async-indexing lag noted in
    test_mongo_atlas_cache.py's _search_fuzzy_eventually, so the benchmark
    isn't dominated by indexing catch-up rather than actual query cost.
    """
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        if cache.search_by_field("last_name", "smtih", fuzzy=True):
            return
        time.sleep(0.5)
    logger.warning(
        "[benchmark] Atlas Search index did not settle within %.0fs; "
        "benchmark numbers may include indexing lag",
        timeout_seconds,
    )


def _run_match_counting_round_trips(
    cache: DuckDBCache | MongoAtlasCache,
) -> tuple[int, List[float]]:
    """Run one MatchingEngine.match() call, counting search_by_field calls
    and their individual latencies (each call = one "round trip")."""
    latencies: List[float] = []
    original = cache.search_by_field

    def _timed(*args: object, **kwargs: object) -> object:
        start = time.perf_counter()
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        latencies.append(time.perf_counter() - start)
        return result

    backend = CacheMatchingBackend(cache)
    engine = MatchingEngine(backend=backend)
    with patch.object(cache, "search_by_field", side_effect=_timed):
        engine.match(_QUERY_PATIENT)
    return len(latencies), latencies


def _report(label: str, round_trips: int, latencies: List[float]) -> None:
    total = sum(latencies)
    p50 = statistics.median(latencies) if latencies else 0.0
    p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 2 else total
    logger.info(
        "[benchmark] %s: round_trips=%d total=%.4fs p50=%.5fs p99=%.5fs",
        label,
        round_trips,
        total,
        p50,
        p99,
    )


class TestCacheBenchmark:
    def test_mongo_atlas_vs_duckdb_round_trips_and_latency(
        self, mongodb: MongoDBService
    ) -> None:
        n = _pool_size()
        if n < BENCHMARK_POOL_SIZE_DEFAULT:
            pytest.fail("BENCHMARK_POOL_SIZE must be >= the documented default")
        logger.info(
            "[benchmark] pool_size=%d (set BENCHMARK_POOL_SIZE=1000000 for the "
            "size Imran decided is realistic for cms-hte-patient-matching-service)",
            n,
        )

        duckdb_cache = DuckDBCache(database=":memory:")
        mongo_cache = MongoAtlasCache(
            connection_string=mongodb.connection_string,
            database="test_patient_cache_benchmark",
        )
        try:
            _ensure_search_index(mongo_cache)
            mongo_cache.clear()

            logger.info("[benchmark] loading %d candidates into DuckDBCache...", n)
            _load(duckdb_cache, n)
            logger.info("[benchmark] loading %d candidates into MongoAtlasCache...", n)
            _load(mongo_cache, n)
            _wait_for_indexing_to_settle(mongo_cache)

            duckdb_trips, duckdb_latencies = _run_match_counting_round_trips(
                duckdb_cache
            )
            mongo_trips, mongo_latencies = _run_match_counting_round_trips(mongo_cache)

            _report("DuckDBCache", duckdb_trips, duckdb_latencies)
            _report("MongoAtlasCache", mongo_trips, mongo_latencies)

            # Not a pass/fail gate (session_12.md: "no fixed pass/fail
            # threshold... this is exploratory data for Open Question 2").
            # Round-trip counts can legitimately differ between backends:
            # household/individual (Category 2) rules only issue their
            # second search() call if the first one found candidates, and
            # Atlas Search indexes asynchronously (see
            # _search_fuzzy_eventually in test_mongo_atlas_cache.py) -- a
            # step-1 search can come back empty on Mongo before DuckDB
            # (always immediately consistent) simply because mongot hasn't
            # caught up yet, skipping step 2 on that side. Both counts are
            # still expected to be within the same rough order of magnitude.
            assert duckdb_trips > 0
            assert mongo_trips > 0
        finally:
            duckdb_cache.close()
            mongo_cache.clear()
            mongo_cache.close()
