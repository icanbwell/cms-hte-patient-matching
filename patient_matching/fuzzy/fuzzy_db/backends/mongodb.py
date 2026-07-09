"""MongoDB backend with Atlas Search and application-level fuzzy matching."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from ..core import (
    FuzzySearchBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)

logger = logging.getLogger(__name__)

# All algorithms are supported via rapidfuzz application-level matching.
_SUPPORTED_ALGORITHMS = set(SimilarityAlgorithm)


class MongoDBBackend(FuzzySearchBackend):
    """Fuzzy search backend for MongoDB.

    Supports two modes:

    * **Atlas Search** (``use_atlas_search=True``): Uses MongoDB Atlas Search
      aggregation pipelines with built-in fuzzy matching. Requires an Atlas
      Search index configured on the target field.
    * **Application-level** (default): Fetches documents and performs fuzzy
      matching in Python using ``rapidfuzz``.

    Args:
        connection_string: MongoDB connection URI.
        database: Database name.
        use_atlas_search: Whether to use Atlas Search for fuzzy queries.
    """

    def __init__(
        self,
        connection_string: str = "mongodb://localhost:27017",
        database: str = "fuzzy_db",
        use_atlas_search: bool = False,
    ) -> None:
        self._connection_string = connection_string
        self._database_name = database
        self._use_atlas_search = use_atlas_search
        self._client: Any = None
        self._db: Any = None

    def connect(self) -> None:
        """Connect to MongoDB."""
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise ImportError(
                "pymongo is required for the MongoDB backend. "
                "Install it with: pip install fuzzy[mongodb]"
            ) from exc

        logger.info("Connecting to MongoDB: %s", self._connection_string)
        self._client = MongoClient(self._connection_string)
        self._db = self._client[self._database_name]

    def disconnect(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB connection closed")

    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        return algorithm in _SUPPORTED_ALGORITHMS

    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy search against a MongoDB collection.

        Args:
            table: The MongoDB collection name.
        """
        if self._db is None:
            raise RuntimeError("Not connected. Call connect() first.")

        config = config or FuzzySearchConfig()

        if self._use_atlas_search:
            return self._search_atlas(query, field, table, config)
        return self._search_application(query, field, table, config)

    # ------------------------------------------------------------------
    # Atlas Search path
    # ------------------------------------------------------------------

    def _search_atlas(
        self,
        query: str,
        field: str,
        table: str,
        config: FuzzySearchConfig,
    ) -> List[SearchResult]:
        """Use MongoDB Atlas Search ``$search`` stage with fuzzy matching."""
        collection = self._db[table]
        pipeline = [
            {
                "$search": {
                    "text": {
                        "query": query,
                        "path": field,
                        "fuzzy": {
                            "maxEdits": min(config.max_distance, 2),
                            "prefixLength": 0,
                        },
                    }
                }
            },
            {"$addFields": {"score": {"$meta": "searchScore"}}},
            {"$limit": config.limit},
        ]

        results: List[SearchResult] = []
        for doc in collection.aggregate(pipeline):
            score = float(doc.get("score", 0))
            # Atlas Search scores are not necessarily 0-1; normalize.
            normalized = min(1.0, score)
            if normalized >= config.threshold:
                results.append(
                    SearchResult(
                        id=str(doc.get("_id", "")),
                        value=str(doc.get(field, "")),
                        similarity_score=round(normalized, 4),
                        metadata={
                            k: v
                            for k, v in doc.items()
                            if k not in ("_id", field, "score")
                        },
                    )
                )

        logger.debug(
            "MongoDB Atlas search returned %d results for query=%r",
            len(results),
            query,
        )
        return results

    # ------------------------------------------------------------------
    # Application-level path (rapidfuzz)
    # ------------------------------------------------------------------

    def _search_application(
        self,
        query: str,
        field: str,
        table: str,
        config: FuzzySearchConfig,
    ) -> List[SearchResult]:
        """Fetch documents and match using rapidfuzz."""
        try:
            import rapidfuzz  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "rapidfuzz is required for application-level MongoDB matching. "
                "Install it with: pip install fuzzy"
            ) from exc

        collection = self._db[table]
        # Only fetch the fields we need.
        projection = {"_id": 1, field: 1}
        documents = list(collection.find({field: {"$exists": True}}, projection))

        compare_query = query if config.case_sensitive else query.lower()

        scored: List[SearchResult] = []
        for doc in documents:
            value = str(doc.get(field, ""))
            compare_value = value if config.case_sensitive else value.lower()
            score = self._compute_score(compare_query, compare_value, config)
            if score >= config.threshold:
                scored.append(
                    SearchResult(
                        id=str(doc["_id"]),
                        value=value,
                        similarity_score=round(score, 4),
                    )
                )

        scored.sort(key=lambda r: r.similarity_score, reverse=True)
        logger.debug(
            "MongoDB app-level search returned %d results for query=%r",
            len(scored[: config.limit]),
            query,
        )
        return scored[: config.limit]

    @staticmethod
    def _compute_score(query: str, value: str, config: FuzzySearchConfig) -> float:
        """Compute a 0-1 similarity score using the configured algorithm."""
        from rapidfuzz import fuzz
        from rapidfuzz.distance import DamerauLevenshtein, Levenshtein

        algo = config.algorithm
        if algo == SimilarityAlgorithm.LEVENSHTEIN:
            return Levenshtein.normalized_similarity(query, value)
        if algo == SimilarityAlgorithm.DAMERAU_LEVENSHTEIN:
            return DamerauLevenshtein.normalized_similarity(query, value)
        if algo == SimilarityAlgorithm.JARO_WINKLER:
            return fuzz.token_sort_ratio(query, value) / 100.0
        if algo == SimilarityAlgorithm.JARO:
            # rapidfuzz provides Jaro via the distance module.
            from rapidfuzz.distance import Jaro

            return Jaro.similarity(query, value)
        raise ValueError(f"Unsupported algorithm: {algo}")
