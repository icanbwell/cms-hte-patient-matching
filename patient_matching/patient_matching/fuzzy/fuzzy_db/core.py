"""Core abstractions, data models, and enums for fuzzy."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SimilarityAlgorithm(Enum):
    """Supported fuzzy matching algorithms."""

    LEVENSHTEIN = "levenshtein"
    JARO_WINKLER = "jaro_winkler"
    JARO = "jaro"
    DAMERAU_LEVENSHTEIN = "damerau_levenshtein"


class DatabaseBackend(Enum):
    """Supported database backends."""

    POSTGRESQL = "postgresql"
    DUCKDB = "duckdb"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"


@dataclass
class SearchResult:
    """A single fuzzy search result.

    Attributes:
        id: Unique identifier of the matched record.
        value: The matched string value.
        similarity_score: Normalized similarity score between 0.0 and 1.0.
        metadata: Optional additional fields from the matched record.
    """

    id: Any
    value: str
    similarity_score: float
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.similarity_score <= 1.0:
            raise ValueError(
                f"similarity_score must be between 0 and 1, got {self.similarity_score}"
            )


@dataclass
class FuzzySearchConfig:
    """Configuration for a fuzzy search operation.

    Attributes:
        algorithm: The similarity algorithm to use.
        threshold: Minimum similarity score (0.0-1.0) to include in results.
        max_distance: Maximum edit distance for distance-based algorithms.
        limit: Maximum number of results to return.
        case_sensitive: Whether the search should be case-sensitive.
    """

    algorithm: SimilarityAlgorithm = SimilarityAlgorithm.LEVENSHTEIN
    threshold: float = 0.6
    max_distance: int = 3
    limit: int = 10
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"threshold must be between 0 and 1, got {self.threshold}"
            )
        if self.max_distance < 0:
            raise ValueError(
                f"max_distance must be non-negative, got {self.max_distance}"
            )
        if self.limit < 1:
            raise ValueError(f"limit must be at least 1, got {self.limit}")


class FuzzySearchBackend(ABC):
    """Abstract base class for all fuzzy search database backends.

    Subclasses must implement connect(), disconnect(), search(), and
    supports_algorithm(). The context manager protocol is provided
    automatically via __enter__/__exit__.

    Example::

        with MyBackend(host="localhost") as backend:
            results = backend.search("john", "name", "users", config)
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the database."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the database connection and release resources."""

    @abstractmethod
    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy string search.

        Args:
            query: The search string to match against.
            field: The database field/column to search within.
            table: The table or collection to search.
            config: Search configuration. Uses sensible defaults if None.

        Returns:
            A list of SearchResult objects sorted by descending similarity.
        """

    @abstractmethod
    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        """Check whether this backend supports the given algorithm.

        Args:
            algorithm: The similarity algorithm to check.

        Returns:
            True if the algorithm is supported natively or via application-level matching.
        """

    def __enter__(self) -> FuzzySearchBackend:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()