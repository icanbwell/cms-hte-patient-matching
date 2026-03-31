"""Elasticsearch backend using native fuzzy query support."""

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

# Elasticsearch's fuzzy query is Levenshtein-based.
_SUPPORTED_ALGORITHMS = {
    SimilarityAlgorithm.LEVENSHTEIN,
}


class ElasticsearchBackend(FuzzySearchBackend):
    """Fuzzy search backend for Elasticsearch.

    Uses Elasticsearch's built-in fuzzy query which is based on Levenshtein
    distance. The ``fuzziness`` parameter maps to ``max_distance`` in the
    search config (clamped to the Elasticsearch maximum of ``AUTO`` or 0-2).

    Args:
        hosts: List of Elasticsearch host URLs.
        **kwargs: Additional keyword arguments forwarded to the
            ``Elasticsearch`` client constructor (e.g., ``api_key``,
            ``basic_auth``).
    """

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        self._hosts = hosts or ["http://localhost:9200"]
        self._kwargs = kwargs
        self._client: Any = None

    def connect(self) -> None:
        """Connect to Elasticsearch."""
        try:
            from elasticsearch import Elasticsearch
        except ImportError as exc:
            raise ImportError(
                "elasticsearch is required for the Elasticsearch backend. "
                "Install it with: pip install fuzzy[elasticsearch]"
            ) from exc

        logger.info("Connecting to Elasticsearch: %s", self._hosts)
        self._client = Elasticsearch(self._hosts, **self._kwargs)
        if not self._client.ping():
            raise ConnectionError("Failed to connect to Elasticsearch")
        logger.info("Elasticsearch connection established")

    def disconnect(self) -> None:
        """Close the Elasticsearch connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Elasticsearch connection closed")

    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        return algorithm in _SUPPORTED_ALGORITHMS

    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy search using an Elasticsearch fuzzy query.

        Args:
            table: The Elasticsearch index name.
        """
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")

        config = config or FuzzySearchConfig()
        if not self.supports_algorithm(config.algorithm):
            raise ValueError(
                f"Elasticsearch does not support {config.algorithm.value}. "
                f"Supported: {[a.value for a in _SUPPORTED_ALGORITHMS]}"
            )

        # Elasticsearch fuzziness: 0, 1, 2, or "AUTO".
        fuzziness = min(config.max_distance, 2)

        body = {
            "query": {
                "fuzzy": {
                    field: {
                        "value": query if config.case_sensitive else query.lower(),
                        "fuzziness": fuzziness,
                        "prefix_length": 0,
                    }
                }
            },
            "size": config.limit,
        }

        response = self._client.search(index=table, body=body)
        hits = response.get("hits", {}).get("hits", [])

        # Normalize scores: Elasticsearch scores vary, so we scale
        # relative to the max score in the result set.
        max_score = response.get("hits", {}).get("max_score") or 1.0

        results: List[SearchResult] = []
        for hit in hits:
            raw_score = float(hit.get("_score", 0))
            normalized = raw_score / max_score if max_score > 0 else 0.0
            normalized = max(0.0, min(1.0, normalized))

            if normalized >= config.threshold:
                source = hit.get("_source", {})
                value = str(source.get(field, ""))
                metadata = {
                    k: v for k, v in source.items() if k != field
                }
                results.append(
                    SearchResult(
                        id=hit["_id"],
                        value=value,
                        similarity_score=round(normalized, 4),
                        metadata=metadata if metadata else None,
                    )
                )

        logger.debug(
            "Elasticsearch search returned %d results for query=%r",
            len(results),
            query,
        )
        return results