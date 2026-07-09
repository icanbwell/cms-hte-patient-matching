"""Tests for the MongoDB backend (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from patient_matching.fuzzy.fuzzy_db.backends.mongodb import MongoDBBackend
from patient_matching.fuzzy.fuzzy_db.core import FuzzySearchConfig, SimilarityAlgorithm


@pytest.fixture
def mock_mongo():
    """Create a MongoDB backend with mocked pymongo."""
    backend = MongoDBBackend(
        connection_string="mongodb://localhost:27017",
        database="test",
        use_atlas_search=False,
    )
    backend._client = MagicMock()
    backend._db = MagicMock()
    return backend


@pytest.fixture
def mock_mongo_atlas():
    """Create a MongoDB backend configured for Atlas Search."""
    backend = MongoDBBackend(
        connection_string="mongodb+srv://test",
        database="test",
        use_atlas_search=True,
    )
    backend._client = MagicMock()
    backend._db = MagicMock()
    return backend


class TestMongoDBBackend:
    def test_supports_all_algorithms(self, mock_mongo):
        for algo in SimilarityAlgorithm:
            assert mock_mongo.supports_algorithm(algo)

    def test_app_level_search(self, mock_mongo):
        mock_collection = MagicMock()
        mock_collection.find.return_value = [
            {"_id": "1", "name": "John Smith"},
            {"_id": "2", "name": "Jon Smyth"},
            {"_id": "3", "name": "Jane Doe"},
        ]
        mock_mongo._db.__getitem__ = MagicMock(return_value=mock_collection)

        config = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            threshold=0.5,
            limit=10,
        )
        results = mock_mongo.search("John Smith", "name", "users", config)
        assert len(results) > 0
        assert results[0].value == "John Smith"
        assert results[0].similarity_score == 1.0

    def test_atlas_search(self, mock_mongo_atlas):
        mock_collection = MagicMock()
        mock_collection.aggregate.return_value = [
            {"_id": "1", "name": "John Smith", "score": 0.95, "age": 30},
            {"_id": "2", "name": "Jon Smyth", "score": 0.75, "age": 25},
        ]
        mock_mongo_atlas._db.__getitem__ = MagicMock(return_value=mock_collection)

        config = FuzzySearchConfig(threshold=0.5, limit=10)
        results = mock_mongo_atlas.search("John Smith", "name", "users", config)
        assert len(results) == 2
        assert results[0].metadata == {"age": 30}

    def test_not_connected_raises(self):
        backend = MongoDBBackend()
        with pytest.raises(RuntimeError, match="Not connected"):
            backend.search("test", "name", "users")

    def test_disconnect(self, mock_mongo):
        # Capture the mock client before disconnect sets it to None.
        client_mock = mock_mongo._client
        mock_mongo.disconnect()
        client_mock.close.assert_called_once()
        assert mock_mongo._client is None

    def test_threshold_filtering(self, mock_mongo):
        mock_collection = MagicMock()
        mock_collection.find.return_value = [
            {"_id": "1", "name": "ZZZZZ"},
        ]
        mock_mongo._db.__getitem__ = MagicMock(return_value=mock_collection)

        config = FuzzySearchConfig(threshold=0.9, limit=10)
        results = mock_mongo.search("John", "name", "users", config)
        assert results == []
