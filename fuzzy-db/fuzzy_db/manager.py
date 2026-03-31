"""High-level manager that wraps factory + backend usage."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .core import (
    DatabaseBackend,
    FuzzySearchBackend,
    FuzzySearchConfig,
    SearchResult,
    SimilarityAlgorithm,
)
from .factory import FuzzySearchFactory

logger = logging.getLogger(__name__)


class FuzzySearchManager:
    """Simplified interface for performing fuzzy searches.

    Wraps the factory and backend lifecycle so callers don't need to
    manage connections manually.

    Args:
        backend_type: Which database backend to use.
        connection_params: Connection parameters for the backend.
        default_config: Default search configuration used when none is
            supplied to ``search()``.
        **kwargs: Extra keyword arguments forwarded to the backend constructor.

    Example::

        manager = FuzzySearchManager(
            backend_type=DatabaseBackend.DUCKDB,
            connection_params={"database": ":memory:"},
        )
        results = manager.search("john", "name", "users")
    """

    def __init__(
        self,
        backend_type: DatabaseBackend,
        connection_params: Dict[str, Any],
        default_config: Optional[FuzzySearchConfig] = None,
        **kwargs: Any,
    ) -> None:
        self._backend_type = backend_type
        self._connection_params = connection_params
        self._kwargs = kwargs
        self._default_config = default_config or FuzzySearchConfig()
        self._factory = FuzzySearchFactory()
        self._backend: Optional[FuzzySearchBackend] = None

    @property
    def backend(self) -> FuzzySearchBackend:
        """Return the underlying backend, creating it lazily if needed."""
        if self._backend is None:
            self._backend = self._factory.create(
                self._backend_type,
                self._connection_params,
                **self._kwargs,
            )
        return self._backend

    def search(
        self,
        query: str,
        field: str,
        table: str,
        config: Optional[FuzzySearchConfig] = None,
    ) -> List[SearchResult]:
        """Perform a fuzzy search using a managed backend connection.

        Opens a connection, executes the search, and closes the connection.
        For repeated searches consider holding the backend open via the
        context manager on the backend directly.

        Args:
            query: The search string.
            field: The field/column to search.
            table: The table/collection/index to search.
            config: Override the default search configuration.

        Returns:
            List of matching results sorted by descending similarity.
        """
        effective_config = config or self._default_config
        with self.backend as b:
            return b.search(query, field, table, effective_config)

    def supports_algorithm(self, algorithm: SimilarityAlgorithm) -> bool:
        """Check if the configured backend supports an algorithm."""
        return self.backend.supports_algorithm(algorithm)