"""fuzzy: Unified fuzzy string matching across database backends.

Provides a single interface for performing Levenshtein, Jaro-Winkler, and
other similarity searches against PostgreSQL, DuckDB, MongoDB, Redis,
and Elasticsearch.
"""

from .config import ConfigLoader, create_from_config
from .core import (
    DatabaseBackend,
    FuzzySearchBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)
from .factory import FuzzySearchFactory
from .manager import FuzzySearchManager
from .utils import FuzzySearchBenchmark, get_recommended_backend

__version__ = "0.1.0"

__all__ = [
    "ConfigLoader",
    "create_from_config",
    "DatabaseBackend",
    "FuzzySearchBackend",
    "FuzzySearchBenchmark",
    "FuzzySearchConfig",
    "FuzzySearchFactory",
    "FuzzySearchManager",
    "get_recommended_backend",
    "SearchResult",
    "SimilarityAlgorithm",
]
