"""Basic usage examples for fuzzy."""

from __future__ import annotations

from typing import Any

from patient_matching.fuzzy.fuzzy_db import (
    DatabaseBackend,
    FuzzySearchConfig,
    FuzzySearchFactory,
    SimilarityAlgorithm,
)
from patient_matching.fuzzy.fuzzy_db.core import FuzzySearchBackend, SearchResult


def duckdb_example() -> None:
    """Quick start: in-memory DuckDB fuzzy search using backend directly."""
    from patient_matching.fuzzy.fuzzy_db.backends.duckdb_backend import DuckDBBackend

    with DuckDBBackend(database=":memory:") as backend:
        # Create and populate a table.
        backend._connection.execute("CREATE TABLE users (id INTEGER, name VARCHAR)")  # type: ignore[attr-defined]
        for i, name in enumerate(
            ["John Smith", "Jon Smyth", "Jonathan Smith", "Jane Doe", "Janet Doe"],
            start=1,
        ):
            backend._connection.execute("INSERT INTO users VALUES (?, ?)", [i, name])  # type: ignore[attr-defined]

        # Search with Jaro-Winkler.
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.JARO_WINKLER,
            threshold=0.7,
            limit=5,
        )
        results = backend.search("John Smith", "name", "users", config)
        for r in results:
            print(f"  {r.value:20s}  score={r.similarity_score:.4f}")


def factory_example() -> None:
    """Using the factory directly for more control."""
    factory = FuzzySearchFactory()
    backend = factory.create(DatabaseBackend.DUCKDB, {"database": ":memory:"})

    with backend:
        backend._connection.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")  # type: ignore[attr-defined]
        backend._connection.execute("INSERT INTO t VALUES (1, 'hello world')")  # type: ignore[attr-defined]

        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.4,
            max_distance=5,
        )
        results = backend.search("hello wrld", "name", "t", config)
        for r in results:
            print(f"  {r.value}: {r.similarity_score:.4f}")


def custom_backend_example() -> None:
    """Registering a custom backend."""
    from patient_matching.fuzzy.fuzzy_db import SimilarityAlgorithm

    class InMemoryBackend(FuzzySearchBackend):
        def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
            self.data = data or []

        def connect(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        def search(
            self,
            query: str,
            field: str,
            table: str,
            config: FuzzySearchConfig | None = None,
        ) -> list[SearchResult]:
            from rapidfuzz.distance import Levenshtein

            cfg = config or FuzzySearchConfig()
            results: list[SearchResult] = []
            for record in self.data:
                value = record.get(field, "")
                score = Levenshtein.normalized_similarity(query.lower(), value.lower())
                if score >= cfg.threshold:
                    results.append(
                        SearchResult(
                            id=record.get("id"),
                            value=value,
                            similarity_score=round(score, 4),
                        )
                    )
            results.sort(key=lambda r: r.similarity_score, reverse=True)
            return results[: cfg.limit]

        def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
            return algorithm == SimilarityAlgorithm.LEVENSHTEIN

    factory = FuzzySearchFactory()
    factory.register_backend(DatabaseBackend.MYSQL, InMemoryBackend)

    backend = factory.create(
        DatabaseBackend.MYSQL,
        {
            "data": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Alicia"},
                {"id": 3, "name": "Bob"},
            ]
        },
    )

    with backend:
        results = backend.search("Alic", "name", "whatever")
        for r in results:
            print(f"  {r.value}: {r.similarity_score:.4f}")


if __name__ == "__main__":
    print("=== DuckDB Example ===")
    duckdb_example()
    print("\n=== Factory Example ===")
    factory_example()
    print("\n=== Custom Backend Example ===")
    custom_backend_example()
