"""DuckDB backend with native support for all major similarity algorithms."""

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

# DuckDB supports all four algorithms natively.
_SUPPORTED_ALGORITHMS = {
    SimilarityAlgorithm.LEVENSHTEIN,
    SimilarityAlgorithm.JARO_WINKLER,
    SimilarityAlgorithm.JARO,
    SimilarityAlgorithm.DAMERAU_LEVENSHTEIN,
}

# Mapping from algorithm enum to DuckDB function name.
_FUNCTION_MAP: Dict[SimilarityAlgorithm, str] = {
    SimilarityAlgorithm.LEVENSHTEIN: "levenshtein",
    SimilarityAlgorithm.JARO_WINKLER: "jaro_winkler_similarity",
    SimilarityAlgorithm.JARO: "jaro_similarity",
    SimilarityAlgorithm.DAMERAU_LEVENSHTEIN: "damerau_levenshtein",
}

# Algorithms that return a distance (lower = better) vs. a similarity score (higher = better).
_DISTANCE_BASED = {
    SimilarityAlgorithm.LEVENSHTEIN,
    SimilarityAlgorithm.DAMERAU_LEVENSHTEIN,
}


class DuckDBBackend(FuzzySearchBackend):
    """Fuzzy search backend for DuckDB.

    DuckDB provides native implementations of Levenshtein, Jaro, Jaro-Winkler,
    and Damerau-Levenshtein, making it the most feature-complete backend.

    Args:
        database: Path to a DuckDB database file, or ``":memory:"`` for an
            in-memory database (default).
    """

    def __init__(self, database: str = ":memory:") -> None:
        self._database = database
        self._connection: Any = None

    def connect(self) -> None:
        """Open or create the DuckDB database."""
        try:
            import duckdb
        except ImportError as exc:
            raise ImportError(
                "duckdb is required for the DuckDB backend. "
                "Install it with: pip install fuzzy[duckdb]"
            ) from exc

        logger.info("Connecting to DuckDB database: %s", self._database)
        self._connection = duckdb.connect(self._database)

    def disconnect(self) -> None:
        """Close the DuckDB connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("DuckDB connection closed")

    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        return algorithm in _SUPPORTED_ALGORITHMS

    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy search using DuckDB native string-similarity functions.

        Distance-based algorithms (Levenshtein, Damerau-Levenshtein) are
        normalized to a 0-1 similarity score. Similarity-based algorithms
        (Jaro, Jaro-Winkler) already return values in [0, 1].
        """
        if self._connection is None:
            raise RuntimeError("Not connected. Call connect() first.")

        config = config or FuzzySearchConfig()
        if not self.supports_algorithm(config.algorithm):
            raise ValueError(f"DuckDB does not support {config.algorithm.value}")

        func = _FUNCTION_MAP[config.algorithm]
        is_distance = config.algorithm in _DISTANCE_BASED

        compare_field = field if config.case_sensitive else f"LOWER({field})"
        compare_query = query if config.case_sensitive else query.lower()

        if is_distance:
            # Normalize distance to a 0-1 similarity score.
            score_expr = (
                f"1.0 - (CAST({func}({compare_field}, $query) AS FLOAT) "
                f"/ GREATEST(LENGTH($query), LENGTH({field}), 1))"
            )
            where_clause = f"{func}({compare_field}, $query) <= $max_distance"
        else:
            score_expr = f"{func}({compare_field}, $query)"
            where_clause = f"{func}({compare_field}, $query) >= $threshold"

        sql = f"""
            SELECT
                id,
                {field} AS value,
                {score_expr} AS similarity_score
            FROM {table}
            WHERE {where_clause}
            ORDER BY similarity_score DESC
            LIMIT $limit
        """

        params: Dict[str, Any] = {"query": compare_query, "limit": config.limit}
        if is_distance:
            params["max_distance"] = config.max_distance
        else:
            params["threshold"] = config.threshold

        rows = self._connection.execute(sql, params).fetchall()
        columns = ["id", "value", "similarity_score"]

        results: List[SearchResult] = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            score = max(0.0, min(1.0, float(row_dict["similarity_score"])))
            if score >= config.threshold:
                results.append(
                    SearchResult(
                        id=row_dict["id"],
                        value=row_dict["value"],
                        similarity_score=round(score, 4),
                    )
                )

        logger.debug("DuckDB search returned %d results for query=%r", len(results), query)
        return results