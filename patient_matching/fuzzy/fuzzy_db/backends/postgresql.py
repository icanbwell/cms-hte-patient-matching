"""PostgreSQL backend using psycopg2 and the fuzzystrmatch extension."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..core import (
    FuzzySearchBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)

logger = logging.getLogger(__name__)

_SUPPORTED_ALGORITHMS = {
    SimilarityAlgorithm.LEVENSHTEIN,
    SimilarityAlgorithm.DAMERAU_LEVENSHTEIN,
}


class PostgreSQLBackend(FuzzySearchBackend):
    """Fuzzy search backend for PostgreSQL.

    Uses the ``fuzzystrmatch`` extension which provides ``levenshtein()`` and
    related functions. The extension is automatically enabled on connect.

    Args:
        host: Database host.
        port: Database port (default 5432).
        database: Database name.
        user: Database user.
        password: Database password.
        **kwargs: Additional keyword arguments forwarded to ``psycopg2.connect``.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: str = "",
        **kwargs: Any,
    ) -> None:
        self._conn_params: Dict[str, Any] = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            **kwargs,
        }
        self._connection: Any = None

    def connect(self) -> None:
        """Connect to PostgreSQL and enable the fuzzystrmatch extension."""
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as exc:
            raise ImportError(
                "psycopg2 is required for the PostgreSQL backend. "
                "Install it with: pip install fuzzy[postgresql]"
            ) from exc

        logger.info(
            "Connecting to PostgreSQL at %s:%s",
            self._conn_params["host"],
            self._conn_params["port"],
        )
        self._connection = psycopg2.connect(
            **self._conn_params,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        self._connection.autocommit = True

        with self._connection.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")
        logger.info("PostgreSQL fuzzystrmatch extension enabled")

    def disconnect(self) -> None:
        """Close the PostgreSQL connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            logger.info("PostgreSQL connection closed")

    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        return algorithm in _SUPPORTED_ALGORITHMS

    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy search using PostgreSQL's levenshtein functions.

        The similarity score is normalized to a 0-1 range using::

            1 - (distance / GREATEST(LENGTH(query), LENGTH(field)))
        """
        if self._connection is None or self._connection.closed:
            raise RuntimeError("Not connected. Call connect() first.")

        config = config or FuzzySearchConfig()
        if not self.supports_algorithm(config.algorithm):
            raise ValueError(
                f"PostgreSQL does not support {config.algorithm.value}. "
                f"Supported: {[a.value for a in _SUPPORTED_ALGORITHMS]}"
            )

        func = (
            "levenshtein"
            if config.algorithm == SimilarityAlgorithm.LEVENSHTEIN
            else "levenshtein"  # PostgreSQL fuzzystrmatch uses levenshtein for both
        )

        compare_field = field if config.case_sensitive else f"LOWER({field})"
        compare_query = query if config.case_sensitive else query.lower()

        sql = f"""
            SELECT
                id,
                {field} AS value,
                1.0 - (
                    {func}({compare_field}, %(query)s)::float
                    / GREATEST(LENGTH(%(query)s), LENGTH({field}), 1)
                ) AS similarity_score
            FROM {table}
            WHERE {func}({compare_field}, %(query)s) <= %(max_distance)s
            ORDER BY similarity_score DESC
            LIMIT %(limit)s
        """  # nosec B608 - table/field names are not user input

        results: List[SearchResult] = []
        with self._connection.cursor() as cur:
            cur.execute(
                sql,
                {
                    "query": compare_query,
                    "max_distance": config.max_distance,
                    "limit": config.limit,
                },
            )
            for row in cur.fetchall():
                score = max(0.0, min(1.0, float(row["similarity_score"])))
                if score >= config.threshold:
                    results.append(
                        SearchResult(
                            id=row["id"],
                            value=row["value"],
                            similarity_score=round(score, 4),
                        )
                    )

        logger.debug(
            "PostgreSQL search returned %d results for query=%r", len(results), query
        )
        return results
