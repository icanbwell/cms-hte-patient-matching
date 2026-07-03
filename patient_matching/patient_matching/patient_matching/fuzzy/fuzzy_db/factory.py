"""Factory pattern for creating fuzzy search backend instances."""

from __future__ import annotations

import logging
from typing import Any, Dict, Type

from .core import DatabaseBackend, FuzzySearchBackend

logger = logging.getLogger(__name__)


class FuzzySearchFactory:
    """Factory for creating fuzzy search backend instances.

    Maintains an internal registry mapping ``DatabaseBackend`` enum values
    to concrete backend classes.  Custom backends can be registered at
    runtime via ``register_backend()``.

    Example::

        factory = FuzzySearchFactory()
        backend = factory.create(
            DatabaseBackend.DUCKDB,
            {"database": ":memory:"},
        )
    """

    def __init__(self) -> None:
        self._registry: Dict[DatabaseBackend, Type[FuzzySearchBackend]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Lazily register built-in backends.

        Imports are deferred so that missing optional dependencies don't
        prevent the factory from being instantiated.
        """
        self._default_paths: Dict[DatabaseBackend, str] = {
            DatabaseBackend.POSTGRESQL: "patient_matching.fuzzy.fuzzy_db.backends.postgresql.PostgreSQLBackend",
            DatabaseBackend.DUCKDB: "patient_matching.fuzzy.fuzzy_db.backends.duckdb_backend.DuckDBBackend",
            DatabaseBackend.MONGODB: "patient_matching.fuzzy.fuzzy_db.backends.mongodb.MongoDBBackend",
            DatabaseBackend.REDIS: "patient_matching.fuzzy.fuzzy_db.backends.redis_backend.RedisBackend",
            DatabaseBackend.ELASTICSEARCH: "patient_matching.fuzzy.fuzzy_db.backends.elasticsearch_backend.ElasticsearchBackend",
        }

    def _resolve_class(self, backend: DatabaseBackend) -> Type[FuzzySearchBackend]:
        """Resolve a backend enum value to its concrete class.

        Checks the explicit registry first, then falls back to the default
        import path.
        """
        if backend in self._registry:
            return self._registry[backend]

        path = self._default_paths.get(backend)
        if path is None:
            raise ValueError(
                f"No backend registered for {backend.value}. "
                f"Available: {list(self._registry.keys()) + list(self._default_paths.keys())}"
            )

        module_path, class_name = path.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        # Cache it for subsequent calls.
        self._registry[backend] = cls
        return cls

    def create(
        self,
        backend: DatabaseBackend,
        connection_params: Dict[str, Any],
        **kwargs: Any,
    ) -> FuzzySearchBackend:
        """Create a backend instance.

        Args:
            backend: The database backend to instantiate.
            connection_params: Connection parameters passed to the backend
                constructor.
            **kwargs: Additional keyword arguments forwarded to the backend
                constructor.

        Returns:
            An unconnected backend instance. Call ``connect()`` or use it
            as a context manager to establish the connection.
        """
        cls = self._resolve_class(backend)
        logger.info("Creating %s backend", backend.value)
        return cls(**connection_params, **kwargs)

    def register_backend(
        self,
        backend: DatabaseBackend,
        backend_class: Type[FuzzySearchBackend],
    ) -> None:
        """Register a custom backend class for a database type.

        This overwrites any previously registered class for the same
        backend enum value.

        Args:
            backend: The database backend enum value.
            backend_class: A concrete subclass of ``FuzzySearchBackend``.
        """
        if not issubclass(backend_class, FuzzySearchBackend):
            raise TypeError(
                f"{backend_class.__name__} must be a subclass of FuzzySearchBackend"
            )
        self._registry[backend] = backend_class
        logger.info(
            "Registered custom backend %s -> %s", backend.value, backend_class.__name__
        )
