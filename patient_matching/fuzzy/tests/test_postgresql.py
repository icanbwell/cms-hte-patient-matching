"""Tests for the PostgreSQL backend (mocked)."""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from patient_matching.fuzzy.fuzzy_db.backends.postgresql import PostgreSQLBackend
from patient_matching.fuzzy.fuzzy_db.core import FuzzySearchConfig, SimilarityAlgorithm


@pytest.fixture
def mock_pg() -> Generator[PostgreSQLBackend, None, None]:
    """Create a PostgreSQL backend with mocked psycopg2."""
    with patch(
        "patient_matching.fuzzy.fuzzy_db.backends.postgresql.PostgreSQLBackend.connect"
    ):
        backend = PostgreSQLBackend(
            host="localhost", port=5432, database="test", user="test", password="test"
        )
        mock_conn = MagicMock()
        mock_conn.closed = False
        backend._connection = mock_conn
        yield backend


class TestPostgreSQLBackend:
    def test_supports_levenshtein(self, mock_pg: PostgreSQLBackend) -> None:
        assert mock_pg.supports_algorithm(SimilarityAlgorithm.LEVENSHTEIN)

    def test_supports_damerau_levenshtein(self, mock_pg: PostgreSQLBackend) -> None:
        assert mock_pg.supports_algorithm(SimilarityAlgorithm.DAMERAU_LEVENSHTEIN)

    def test_does_not_support_jaro(self, mock_pg: PostgreSQLBackend) -> None:
        assert not mock_pg.supports_algorithm(SimilarityAlgorithm.JARO)
        assert not mock_pg.supports_algorithm(SimilarityAlgorithm.JARO_WINKLER)

    def test_search_returns_results(self, mock_pg: PostgreSQLBackend) -> None:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "value": "John Smith", "similarity_score": 0.9},
            {"id": 2, "value": "Jon Smyth", "similarity_score": 0.7},
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_pg._connection.cursor.return_value = mock_cursor

        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.5,
            max_distance=5,
        )
        results = mock_pg.search("John Smith", "name", "users", config)
        assert len(results) == 2
        assert results[0].value == "John Smith"

    def test_search_unsupported_algorithm_raises(
        self, mock_pg: PostgreSQLBackend
    ) -> None:
        config = FuzzySearchConfig(algorithm=SimilarityAlgorithm.JARO_WINKLER)
        with pytest.raises(ValueError, match="does not support"):
            mock_pg.search("test", "name", "users", config)

    def test_search_not_connected_raises(self) -> None:
        backend = PostgreSQLBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            backend.search("test", "name", "users")

    def test_disconnect_closes_connection(self, mock_pg: PostgreSQLBackend) -> None:
        mock_pg.disconnect()
        mock_pg._connection.close.assert_called_once()

    def test_disconnect_when_already_closed(self, mock_pg: PostgreSQLBackend) -> None:
        mock_pg._connection.closed = True
        mock_pg.disconnect()
        mock_pg._connection.close.assert_not_called()

    @pytest.mark.parametrize(
        "field,table",
        [
            ("name) UNION SELECT ssn FROM users--", "users"),
            ("name", "users; DROP TABLE users;--"),
        ],
    )
    def test_search_rejects_sql_injection_via_field_or_table(
        self, mock_pg: PostgreSQLBackend, field: str, table: str
    ) -> None:
        """A malicious field/table must be rejected before it ever reaches the SQL
        string - the mocked cursor must never see an execute() call at all."""
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            mock_pg.search("x", field, table)
        mock_pg._connection.cursor.assert_not_called()
