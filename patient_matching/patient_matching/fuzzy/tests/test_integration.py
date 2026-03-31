"""Integration tests for factory, manager, config, and core components."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from fuzzy_db.config import ConfigLoader, create_from_config
from fuzzy_db.core import (
    DatabaseBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)
from fuzzy_db.factory import FuzzySearchFactory
from fuzzy_db.manager import FuzzySearchManager
from fuzzy_db.utils import get_recommended_backend


class TestSearchResult:
    def test_valid_result(self):
        r = SearchResult(id=1, value="test", similarity_score=0.85)
        assert r.id == 1
        assert r.similarity_score == 0.85

    def test_with_metadata(self):
        r = SearchResult(id=1, value="test", similarity_score=0.5, metadata={"key": "val"})
        assert r.metadata == {"key": "val"}

    def test_score_below_zero_raises(self):
        with pytest.raises(ValueError):
            SearchResult(id=1, value="x", similarity_score=-0.1)

    def test_score_above_one_raises(self):
        with pytest.raises(ValueError):
            SearchResult(id=1, value="x", similarity_score=1.1)

    def test_boundary_scores(self):
        SearchResult(id=1, value="x", similarity_score=0.0)
        SearchResult(id=1, value="x", similarity_score=1.0)


class TestFuzzySearchConfig:
    def test_defaults(self):
        c = FuzzySearchConfig()
        assert c.algorithm == SimilarityAlgorithm.LEVENSHTEIN
        assert c.threshold == 0.6
        assert c.max_distance == 3
        assert c.limit == 10
        assert c.case_sensitive is False

    def test_custom_config(self):
        c = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.JARO_WINKLER,
            threshold=0.8,
            max_distance=2,
            limit=5,
            case_sensitive=True,
        )
        assert c.algorithm == SimilarityAlgorithm.JARO_WINKLER
        assert c.case_sensitive is True

    def test_invalid_threshold(self):
        with pytest.raises(ValueError, match="threshold"):
            FuzzySearchConfig(threshold=1.5)

    def test_invalid_max_distance(self):
        with pytest.raises(ValueError, match="max_distance"):
            FuzzySearchConfig(max_distance=-1)

    def test_invalid_limit(self):
        with pytest.raises(ValueError, match="limit"):
            FuzzySearchConfig(limit=0)


class TestFuzzySearchFactory:
    def test_create_duckdb(self):
        factory = FuzzySearchFactory()
        backend = factory.create(DatabaseBackend.DUCKDB, {"database": ":memory:"})
        assert backend is not None

    def test_register_custom_backend(self):
        from fuzzy_db.core import FuzzySearchBackend

        class CustomBackend(FuzzySearchBackend):
            def connect(self): pass
            def disconnect(self): pass
            def search(self, query, field, table, config=None): return []
            def supports_algorithm(self, algorithm): return True

        factory = FuzzySearchFactory()
        factory.register_backend(DatabaseBackend.MYSQL, CustomBackend)
        backend = factory.create(DatabaseBackend.MYSQL, {})
        assert isinstance(backend, CustomBackend)

    def test_register_non_subclass_raises(self):
        factory = FuzzySearchFactory()
        with pytest.raises(TypeError, match="subclass"):
            factory.register_backend(DatabaseBackend.MYSQL, dict)

    def test_unknown_backend_raises(self):
        factory = FuzzySearchFactory()
        with pytest.raises(ValueError, match="No backend registered"):
            factory.create(DatabaseBackend.SQLSERVER, {})


class TestFuzzySearchManager:
    def test_duckdb_end_to_end(self, tmp_path):
        db_path = str(tmp_path / "test.duckdb")
        manager = FuzzySearchManager(
            backend_type=DatabaseBackend.DUCKDB,
            connection_params={"database": db_path},
        )
        # Seed data via the backend directly.
        backend = manager.backend
        backend.connect()
        backend._connection.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
        backend._connection.execute("INSERT INTO t VALUES (1, 'hello')")
        backend.disconnect()

        config = FuzzySearchConfig(threshold=0.0, max_distance=100)
        results = manager.search("hello", "name", "t", config)
        assert len(results) == 1
        assert results[0].value == "hello"
        assert results[0].similarity_score == 1.0

    def test_supports_algorithm(self):
        manager = FuzzySearchManager(
            backend_type=DatabaseBackend.DUCKDB,
            connection_params={"database": ":memory:"},
        )
        assert manager.supports_algorithm(SimilarityAlgorithm.JARO_WINKLER)


class TestConfigLoader:
    def test_from_json(self, tmp_path):
        config_data = {
            "backend": "duckdb",
            "database": ":memory:",
            "threshold": 0.7,
        }
        filepath = tmp_path / "config.json"
        filepath.write_text(json.dumps(config_data))

        loaded = ConfigLoader.from_json(str(filepath))
        assert loaded["backend"] == "duckdb"
        assert loaded["threshold"] == 0.7

    def test_from_env(self):
        os.environ["FUZZY_SEARCH_BACKEND"] = "duckdb"
        os.environ["FUZZY_SEARCH_THRESHOLD"] = "0.8"
        os.environ["FUZZY_SEARCH_PORT"] = "5432"
        os.environ["FUZZY_SEARCH_CASE_SENSITIVE"] = "true"
        try:
            config = ConfigLoader.from_env()
            assert config["backend"] == "duckdb"
            assert config["threshold"] == 0.8
            assert config["port"] == 5432
            assert config["case_sensitive"] is True
        finally:
            for key in [
                "FUZZY_SEARCH_BACKEND",
                "FUZZY_SEARCH_THRESHOLD",
                "FUZZY_SEARCH_PORT",
                "FUZZY_SEARCH_CASE_SENSITIVE",
            ]:
                os.environ.pop(key, None)

    def test_create_from_config(self):
        config = {
            "backend": "duckdb",
            "database": ":memory:",
            "algorithm": "jaro_winkler",
            "threshold": 0.75,
        }
        manager = create_from_config(config)
        assert manager._backend_type == DatabaseBackend.DUCKDB
        assert manager._default_config.algorithm == SimilarityAlgorithm.JARO_WINKLER
        assert manager._default_config.threshold == 0.75


class TestRecommendations:
    def test_jaro_recommends_duckdb(self):
        result = get_recommended_backend({"algorithm": SimilarityAlgorithm.JARO})
        assert result == DatabaseBackend.DUCKDB

    def test_realtime_recommends_elasticsearch(self):
        result = get_recommended_backend({"realtime": True})
        assert result == DatabaseBackend.ELASTICSEARCH

    def test_small_dataset_recommends_duckdb(self):
        result = get_recommended_backend({"dataset_size": "small"})
        assert result == DatabaseBackend.DUCKDB

    def test_large_with_pg_infrastructure(self):
        result = get_recommended_backend({
            "dataset_size": "large",
            "existing_infrastructure": ["postgresql"],
        })
        assert result == DatabaseBackend.POSTGRESQL

    def test_default_is_duckdb(self):
        result = get_recommended_backend({})
        assert result == DatabaseBackend.DUCKDB
