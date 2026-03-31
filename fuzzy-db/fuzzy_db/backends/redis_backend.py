"""Redis backend using application-level fuzzy matching with rapidfuzz."""

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

_SUPPORTED_ALGORITHMS = set(SimilarityAlgorithm)


class RedisBackend(FuzzySearchBackend):
    """Fuzzy search backend for Redis.

    Redis does not provide native fuzzy string matching, so this backend
    fetches keys matching a pattern and performs application-level matching
    using ``rapidfuzz``.

    Data model assumptions:

    * Each record is stored as a Redis hash.
    * Keys follow the pattern ``{table}:{id}``.
    * The hash contains at least the ``field`` specified in search queries.

    Args:
        host: Redis host.
        port: Redis port.
        db: Redis database number.
        password: Optional Redis password.
        **kwargs: Additional keyword arguments forwarded to ``redis.Redis``.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._conn_params: Dict[str, Any] = {
            "host": host,
            "port": port,
            "db": db,
            "password": password,
            "decode_responses": True,
            **kwargs,
        }
        self._client: Any = None

    def connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis as redis_lib
        except ImportError as exc:
            raise ImportError(
                "redis is required for the Redis backend. "
                "Install it with: pip install fuzzy-db[redis]"
            ) from exc

        logger.info("Connecting to Redis at %s:%s", self._conn_params["host"], self._conn_params["port"])
        self._client = redis_lib.Redis(**self._conn_params)
        self._client.ping()
        logger.info("Redis connection established")

    def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed")

    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        return algorithm in _SUPPORTED_ALGORITHMS

    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy search across Redis hashes.

        Scans for keys matching ``{table}:*``, retrieves the requested
        *field* from each hash, and computes similarity using rapidfuzz.
        """
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")

        config = config or FuzzySearchConfig()

        try:
            from rapidfuzz import fuzz
            from rapidfuzz.distance import DamerauLevenshtein, Levenshtein
        except ImportError as exc:
            raise ImportError(
                "rapidfuzz is required for the Redis backend. "
                "Install it with: pip install fuzzy-db"
            ) from exc

        pattern = f"{table}:*"
        compare_query = query if config.case_sensitive else query.lower()

        scored: List[SearchResult] = []
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            for key in keys:
                value = self._client.hget(key, field)
                if value is None:
                    continue
                compare_value = value if config.case_sensitive else value.lower()
                score = self._compute_score(compare_query, compare_value, config)
                if score >= config.threshold:
                    # Extract the record id from the key pattern "table:id".
                    record_id = key.split(":", 1)[1] if ":" in key else key
                    metadata = self._client.hgetall(key)
                    metadata.pop(field, None)
                    scored.append(
                        SearchResult(
                            id=record_id,
                            value=value,
                            similarity_score=round(score, 4),
                            metadata=metadata if metadata else None,
                        )
                    )
            if cursor == 0:
                break

        scored.sort(key=lambda r: r.similarity_score, reverse=True)
        results = scored[: config.limit]
        logger.debug("Redis search returned %d results for query=%r", len(results), query)
        return results

    @staticmethod
    def _compute_score(
        query: str, value: str, config: FuzzySearchConfig
    ) -> float:
        """Compute a 0-1 similarity score using the configured algorithm."""
        from rapidfuzz import fuzz
        from rapidfuzz.distance import DamerauLevenshtein, Jaro, Levenshtein

        algo = config.algorithm
        if algo == SimilarityAlgorithm.LEVENSHTEIN:
            return Levenshtein.normalized_similarity(query, value)
        if algo == SimilarityAlgorithm.DAMERAU_LEVENSHTEIN:
            return DamerauLevenshtein.normalized_similarity(query, value)
        if algo == SimilarityAlgorithm.JARO_WINKLER:
            return fuzz.token_sort_ratio(query, value) / 100.0
        if algo == SimilarityAlgorithm.JARO:
            return Jaro.similarity(query, value)
        raise ValueError(f"Unsupported algorithm: {algo}")