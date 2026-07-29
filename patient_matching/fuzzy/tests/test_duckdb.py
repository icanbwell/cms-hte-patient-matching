"""Tests for the DuckDB backend."""

from __future__ import annotations

from typing import Generator

import pytest

from patient_matching.fuzzy.fuzzy_db.backends.duckdb_backend import DuckDBBackend
from patient_matching.fuzzy.fuzzy_db.core import FuzzySearchConfig, SimilarityAlgorithm


@pytest.fixture
def backend() -> Generator[DuckDBBackend, None, None]:
    """Create an in-memory DuckDB backend with sample data."""
    b = DuckDBBackend(database=":memory:")
    b.connect()
    b._connection.execute("CREATE TABLE users (id INTEGER, name VARCHAR)")
    sample = [
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
    for rid, name in sample:
        b._connection.execute("INSERT INTO users VALUES (?, ?)", [rid, name])
    yield b
    b.disconnect()


class TestDuckDBBackend:
    def test_supports_all_algorithms(self, backend: DuckDBBackend) -> None:
        for algo in SimilarityAlgorithm:
            assert backend.supports_algorithm(algo)

    def test_levenshtein_search(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.5,
            max_distance=5,
            limit=5,
        )
        results = backend.search("John Smith", "name", "users", config)
        assert len(results) > 0
        assert results[0].value == "John Smith"
        assert results[0].similarity_score == 1.0

    def test_jaro_winkler_search(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.JARO_WINKLER,
            threshold=0.7,
            limit=5,
        )
        results = backend.search("John Smith", "name", "users", config)
        assert len(results) > 0
        assert results[0].value == "John Smith"

    def test_jaro_search(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.JARO,
            threshold=0.7,
            limit=5,
        )
        results = backend.search("John Smith", "name", "users", config)
        assert len(results) > 0

    def test_damerau_levenshtein_search(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.DAMERAU_LEVENSHTEIN,
            threshold=0.5,
            max_distance=5,
            limit=5,
        )
        results = backend.search("John Smith", "name", "users", config)
        assert len(results) > 0

    def test_case_insensitive(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.5,
            max_distance=5,
            case_sensitive=False,
        )
        results = backend.search("john smith", "name", "users", config)
        assert any(r.value == "John Smith" for r in results)

    def test_case_sensitive(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.9,
            max_distance=2,
            case_sensitive=True,
        )
        results = backend.search("john smith", "name", "users", config)
        assert not any(r.similarity_score == 1.0 for r in results)

    def test_threshold_filtering(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.99,
            max_distance=1,
            limit=10,
        )
        results = backend.search("John Smith", "name", "users", config)
        for r in results:
            assert r.similarity_score >= 0.99

    def test_limit(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.0,
            max_distance=100,
            limit=3,
        )
        results = backend.search("John", "name", "users", config)
        assert len(results) <= 3

    def test_empty_results(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.99,
            max_distance=0,
        )
        results = backend.search("ZZZZZZZZZ", "name", "users", config)
        assert results == []

    def test_not_connected_raises(self) -> None:
        b = DuckDBBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            b.search("x", "name", "users")

    def test_context_manager(self) -> None:
        b = DuckDBBackend(database=":memory:")
        with b:
            b._connection.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
            b._connection.execute("INSERT INTO t VALUES (1, 'hello')")
            config = FuzzySearchConfig(threshold=0.0, max_distance=100)
            results = b.search("hello", "name", "t", config)
            assert len(results) == 1

    def test_score_range(self, backend: DuckDBBackend) -> None:
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.JARO_WINKLER,
            threshold=0.0,
            limit=100,
        )
        results = backend.search("John", "name", "users", config)
        for r in results:
            assert 0.0 <= r.similarity_score <= 1.0

    @pytest.mark.parametrize(
        "field,table",
        [
            ("name) UNION SELECT ssn FROM users--", "users"),
            ("name", "users; DROP TABLE users;--"),
            ("name", "users) UNION SELECT ssn FROM users--"),
        ],
    )
    def test_search_rejects_sql_injection_via_field_or_table(
        self, backend: DuckDBBackend, field: str, table: str
    ) -> None:
        """A malicious field/table (e.g. sourced from an HTTP query param, as in
        examples/fastapi_integration.py) must be rejected before it ever reaches
        the SQL string, not executed against the database."""
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            backend.search("x", field, table)
