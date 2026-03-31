"""Tests for the Redis backend (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fuzzy_db.backends.redis_backend import RedisBackend
from fuzzy_db.core import FuzzySearchConfig, SimilarityAlgorithm


@pytest.fixture
def mock_redis():
    """Create a Redis backend with mocked redis client."""
    backend = RedisBackend(host="localhost", port=6379)
    client = MagicMock()

    client.scan.side_effect = [
        (0, ["users:1", "users:2", "users:3"]),
    ]
    client.hget.side_effect = lambda key, field: {
        "users:1": "John Smith",
        "users:2": "Jon Smyth",
        "users:3": "Jane Doe",
    }.get(key)
    client.hgetall.side_effect = lambda key: {
        "users:1": {"name": "John Smith", "age": "30"},
        "users:2": {"name": "Jon Smyth", "age": "25"},
        "users:3": {"name": "Jane Doe", "age": "28"},
    }.get(key, {})

    backend._client = client
    return backend


class TestRedisBackend:
    def test_supports_all_algorithms(self, mock_redis):
        for algo in SimilarityAlgorithm:
            assert mock_redis.supports_algorithm(algo)

    def test_search_returns_results(self, mock_redis):
        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.5,
            limit=10,
        )
        results = mock_redis.search("John Smith", "name", "users", config)
        assert len(results) > 0
        assert results[0].value == "John Smith"

    def test_metadata_included(self, mock_redis):
        config = FuzzySearchConfig(threshold=0.5)
        results = mock_redis.search("John Smith", "name", "users", config)
        match = [r for r in results if r.value == "John Smith"]
        assert len(match) == 1
        assert match[0].metadata is not None
        assert "age" in match[0].metadata

    def test_not_connected_raises(self):
        backend = RedisBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            backend.search("test", "name", "users")

    def test_disconnect(self, mock_redis):
        mock_redis.disconnect()
        assert mock_redis._client is None

    def test_threshold_filtering(self, mock_redis):
        mock_redis._client.scan.side_effect = [
            (0, ["users:1"]),
        ]
        mock_redis._client.hget.side_effect = lambda key, field: "ZZZZZ"
        config = FuzzySearchConfig(threshold=0.99, max_distance=0)
        results = mock_redis.search("John", "name", "users", config)
        assert results == []
