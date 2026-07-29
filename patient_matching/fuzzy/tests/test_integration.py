"""Integration tests for factory, manager, config, and core components."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, cast

import pytest

from patient_matching.fuzzy.fuzzy_db.backends.duckdb_backend import DuckDBBackend
from patient_matching.fuzzy.fuzzy_db.config import ConfigLoader, create_from_config
from patient_matching.fuzzy.fuzzy_db.core import (
    DatabaseBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)
from patient_matching.fuzzy.fuzzy_db.factory import FuzzySearchFactory
from patient_matching.fuzzy.fuzzy_db.manager import FuzzySearchManager
from patient_matching.fuzzy.fuzzy_db.utils import get_recommended_backend


class TestSearchResult:
    def test_valid_result(self) -> None:
        r = SearchResult(id=1, value="test", similarity_score=0.85)
        assert r.id == 1
        assert r.similarity_score == 0.85

    def test_with_metadata(self) -> None:
        r = SearchResult(
            id=1, value="test", similarity_score=0.5, metadata={"key": "val"}
        )
        assert r.metadata == {"key": "val"}

    def test_score_below_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            SearchResult(id=1, value="x", similarity_score=-0.1)

    def test_score_above_one_raises(self) -> None:
        with pytest.raises(ValueError):
            SearchResult(id=1, value="x", similarity_score=1.1)

    def test_boundary_scores(self) -> None:
        SearchResult(id=1, value="x", similarity_score=0.0)
        SearchResult(id=1, value="x", similarity_score=1.0)


class TestFuzzySearchConfig:
    def test_defaults(self) -> None:
        c = FuzzySearchConfig()
        assert c.algorithm == SimilarityAlgorithm.LEVENSHTEIN
        assert c.threshold == 0.6
        assert c.max_distance == 3
        assert c.limit == 10
        assert c.case_sensitive is False

    def test_custom_config(self) -> None:
        c = FuzzySearchConfig(
            algorithm=SimilarityAlgorithm.JARO_WINKLER,
            threshold=0.8,
            max_distance=2,
            limit=5,
            case_sensitive=True,
        )
        assert c.algorithm == SimilarityAlgorithm.JARO_WINKLER
        assert c.case_sensitive is True

    def test_invalid_threshold(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            FuzzySearchConfig(threshold=1.5)

    def test_invalid_max_distance(self) -> None:
        with pytest.raises(ValueError, match="max_distance"):
            FuzzySearchConfig(max_distance=-1)

    def test_invalid_limit(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            FuzzySearchConfig(limit=0)


class TestFuzzySearchFactory:
    def test_create_duckdb(self) -> None:
        factory = FuzzySearchFactory()
        backend = factory.create(DatabaseBackend.DUCKDB, {"database": ":memory:"})
        assert backend is not None

    def test_register_custom_backend(self) -> None:
        from patient_matching.fuzzy.fuzzy_db.core import FuzzySearchBackend

        class CustomBackend(FuzzySearchBackend):
            def connect(self) -> None:
                pass

            def disconnect(self) -> None:
                pass

            def search(
                self,
                query: str,
                field: str,
                table: str,
                config: Optional[FuzzySearchConfig] = None,
            ) -> list[SearchResult]:
                return []

            def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
                return True

        factory = FuzzySearchFactory()
        factory.register_backend(DatabaseBackend.MYSQL, CustomBackend)
        backend = factory.create(DatabaseBackend.MYSQL, {})
        assert isinstance(backend, CustomBackend)

    def test_register_non_subclass_raises(self) -> None:
        factory = FuzzySearchFactory()
        with pytest.raises(TypeError, match="subclass"):
            factory.register_backend(DatabaseBackend.MYSQL, dict)  # type: ignore[arg-type]

    def test_unknown_backend_raises(self) -> None:
        factory = FuzzySearchFactory()
        with pytest.raises(ValueError, match="No backend registered"):
            factory.create(DatabaseBackend.SQLSERVER, {})


class TestFuzzySearchManager:
    def test_duckdb_end_to_end(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.duckdb")
        manager = FuzzySearchManager(
            backend_type=DatabaseBackend.DUCKDB,
            connection_params={"database": db_path},
        )
        # Seed data via the backend directly.
        backend = cast(DuckDBBackend, manager.backend)
        backend.connect()
        backend._connection.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
        backend._connection.execute("INSERT INTO t VALUES (1, 'hello')")
        backend.disconnect()

        config = FuzzySearchConfig(threshold=0.0, max_distance=100)
        results = manager.search("hello", "name", "t", config)
        assert len(results) == 1
        assert results[0].value == "hello"
        assert results[0].similarity_score == 1.0

    def test_supports_algorithm(self) -> None:
        manager = FuzzySearchManager(
            backend_type=DatabaseBackend.DUCKDB,
            connection_params={"database": ":memory:"},
        )
        assert manager.supports_algorithm(SimilarityAlgorithm.JARO_WINKLER)


class TestConfigLoader:
    def test_from_json(self, tmp_path: Path) -> None:
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

    def test_from_env(self) -> None:
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

    def test_create_from_config(self) -> None:
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
    def test_jaro_recommends_duckdb(self) -> None:
        result = get_recommended_backend({"algorithm": SimilarityAlgorithm.JARO})
        assert result == DatabaseBackend.DUCKDB

    def test_realtime_recommends_elasticsearch(self) -> None:
        result = get_recommended_backend({"realtime": True})
        assert result == DatabaseBackend.ELASTICSEARCH

    def test_small_dataset_recommends_duckdb(self) -> None:
        result = get_recommended_backend({"dataset_size": "small"})
        assert result == DatabaseBackend.DUCKDB

    def test_large_with_pg_infrastructure(self) -> None:
        result = get_recommended_backend(
            {
                "dataset_size": "large",
                "existing_infrastructure": ["postgresql"],
            }
        )
        assert result == DatabaseBackend.POSTGRESQL

    def test_default_is_duckdb(self) -> None:
        result = get_recommended_backend({})
        assert result == DatabaseBackend.DUCKDB
