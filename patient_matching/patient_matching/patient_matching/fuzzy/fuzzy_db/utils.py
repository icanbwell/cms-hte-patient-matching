"""Utilities: benchmarking, recommendations, and test data helpers."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import (
    DatabaseBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)
from .manager import FuzzySearchManager

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run.

    Attributes:
        backend: The database backend that was benchmarked.
        query: The search query used.
        elapsed_seconds: Wall-clock time for the search.
        result_count: Number of results returned.
        results: The actual search results.
    """

    backend: DatabaseBackend
    query: str
    elapsed_seconds: float
    result_count: int
    results: List[SearchResult] = field(default_factory=list)


class FuzzySearchBenchmark:
    """Benchmark fuzzy search across multiple backends.

    Example::

        bench = FuzzySearchBenchmark()
        bench.add_manager("duckdb", duckdb_manager)
        bench.add_manager("pg", pg_manager)
        results = bench.run("john", "name", "users")
        for r in results:
            print(f"{r.backend.value}: {r.elapsed_seconds:.4f}s, {r.result_count} results")
    """

    def __init__(self) -> None:
        self._managers: Dict[str, FuzzySearchManager] = {}

    def add_manager(self, name: str, manager: FuzzySearchManager) -> None:
        """Register a manager to benchmark.

        Args:
            name: A human-readable label for this manager.
            manager: The manager instance.
        """
        self._managers[name] = manager

    def run(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[BenchmarkResult]:
        """Run the search across all registered managers and collect timings.

        Args:
            query: The search string.
            field: The field/column to search.
            table: The table/collection to search.
            config: Search configuration (uses each manager's default if None).

        Returns:
            A list of ``BenchmarkResult`` objects, one per manager.
        """
        benchmark_results: List[BenchmarkResult] = []

        for name, manager in self._managers.items():
            logger.info("Benchmarking %s ...", name)
            start = time.perf_counter()
            try:
                results = manager.search(query, field, table, config)
            except Exception:
                logger.exception("Benchmark failed for %s", name)
                results = []
            elapsed = time.perf_counter() - start

            benchmark_results.append(
                BenchmarkResult(
                    backend=manager._backend_type,
                    query=query,
                    elapsed_seconds=round(elapsed, 6),
                    result_count=len(results),
                    results=results,
                )
            )
            logger.info("%s: %.4fs, %d results", name, elapsed, len(results))

        return benchmark_results


def get_recommended_backend(
    requirements: Dict[str, Any],
) -> DatabaseBackend:
    """Recommend a database backend based on stated requirements.

    Examines keys in *requirements* to produce a recommendation:

    * ``algorithm`` — if the required algorithm is Jaro/Jaro-Winkler, only
      DuckDB supports it natively.
    * ``dataset_size`` — ``"small"`` favours DuckDB (in-memory); ``"large"``
      favours Elasticsearch or PostgreSQL.
    * ``realtime`` — if True, Elasticsearch or Redis are recommended.
    * ``existing_infrastructure`` — prefer backends the caller already runs.

    Args:
        requirements: A dict describing the caller's needs.

    Returns:
        The recommended ``DatabaseBackend`` enum value.
    """
    algo = requirements.get("algorithm")
    if algo in (SimilarityAlgorithm.JARO, SimilarityAlgorithm.JARO_WINKLER):
        return DatabaseBackend.DUCKDB

    existing = requirements.get("existing_infrastructure", [])
    if isinstance(existing, str):
        existing = [existing]

    size = requirements.get("dataset_size", "medium")
    realtime = requirements.get("realtime", False)

    if realtime:
        if "elasticsearch" in existing:
            return DatabaseBackend.ELASTICSEARCH
        if "redis" in existing:
            return DatabaseBackend.REDIS
        return DatabaseBackend.ELASTICSEARCH

    if size == "small":
        return DatabaseBackend.DUCKDB
    if size == "large":
        if "postgresql" in existing:
            return DatabaseBackend.POSTGRESQL
        if "elasticsearch" in existing:
            return DatabaseBackend.ELASTICSEARCH
        return DatabaseBackend.POSTGRESQL

    # Default: DuckDB for medium datasets and general use.
    return DatabaseBackend.DUCKDB


def create_test_data(manager: FuzzySearchManager, table: str) -> None:
    """Insert sample records into the given backend for testing.

    Creates a small set of name records suitable for validating fuzzy
    matching behaviour.

    Args:
        manager: A configured ``FuzzySearchManager``.
        table: The table/collection name to populate.
    """
    sample_names = [
        (1, "John Smith"),
        (2, "Jon Smyth"),
        (3, "Jonathan Smith"),
        (4, "Jane Doe"),
        (5, "Janet Doe"),
        (6, "James Johnson"),
        (7, "Jim Johnson"),
        (8, "Robert Williams"),
        (9, "Bob Williams"),
        (10, "Elizabeth Taylor"),
    ]

    backend = manager.backend

    if manager._backend_type == DatabaseBackend.DUCKDB:
        backend.connect()
        conn = backend._connection  # type: ignore[attr-defined]
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER, name VARCHAR)")
        for rid, name in sample_names:
            conn.execute(f"INSERT INTO {table} VALUES (?, ?)", [rid, name])  # nosec B608
        backend.disconnect()
        logger.info("Created test data in DuckDB table %s", table)

    elif manager._backend_type == DatabaseBackend.POSTGRESQL:
        backend.connect()
        conn = backend._connection  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {table} (id SERIAL PRIMARY KEY, name VARCHAR)"
            )
            for rid, name in sample_names:
                cur.execute(
                    f"INSERT INTO {table} (id, name) VALUES (%s, %s)",  # nosec B608
                    (rid, name),
                )
        backend.disconnect()
        logger.info("Created test data in PostgreSQL table %s", table)

    elif manager._backend_type == DatabaseBackend.MONGODB:
        backend.connect()
        db = backend._db  # type: ignore[attr-defined]
        collection = db[table]
        collection.drop()
        docs = [{"_id": rid, "name": name} for rid, name in sample_names]
        collection.insert_many(docs)
        backend.disconnect()
        logger.info("Created test data in MongoDB collection %s", table)

    elif manager._backend_type == DatabaseBackend.REDIS:
        backend.connect()
        client = backend._client  # type: ignore[attr-defined]
        for rid, name in sample_names:
            client.hset(f"{table}:{rid}", mapping={"name": name})
        backend.disconnect()
        logger.info("Created test data in Redis with key pattern %s:*", table)

    elif manager._backend_type == DatabaseBackend.ELASTICSEARCH:
        backend.connect()
        es = backend._client  # type: ignore[attr-defined]
        for rid, name in sample_names:
            es.index(index=table, id=rid, document={"name": name})
        # Refresh so documents are searchable immediately.
        es.indices.refresh(index=table)
        backend.disconnect()
        logger.info("Created test data in Elasticsearch index %s", table)

    else:
        raise NotImplementedError(
            f"create_test_data does not support {manager._backend_type.value} yet"
        )
