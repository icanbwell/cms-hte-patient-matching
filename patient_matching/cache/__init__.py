"""cache: Normalized patient cache for efficient matching.

Manages the lifecycle of the patient matching cache:
  - Fetch patients from a FHIR server
  - Normalize demographics using CMS rules
  - Store in a pluggable cache backend (DuckDB, etc.)
  - Provide a MatchingBackend adapter for the matching engine
  - Scheduled refresh to maintain data currency
"""

from .cache_backend import CacheBackend, CachedPatient
from .duckdb_cache import DuckDBCache
from .matching_adapter import CacheMatchingBackend
from .mongo_atlas_cache import MongoAtlasCache
from .cache_manager import CacheManager, CacheManagerConfig

__all__ = [
    "CacheBackend",
    "CacheManager",
    "CacheManagerConfig",
    "CacheMatchingBackend",
    "CachedPatient",
    "DuckDBCache",
    "MongoAtlasCache",
]
