"""Configuration loading from YAML, JSON, and environment variables."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from .core import DatabaseBackend, FuzzySearchConfig, SimilarityAlgorithm
from .manager import FuzzySearchManager

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load fuzzy configuration from various sources."""

    @staticmethod
    def from_yaml(filepath: str) -> Dict[str, Any]:
        """Load configuration from a YAML file.

        Args:
            filepath: Path to the YAML configuration file.

        Returns:
            Parsed configuration dictionary.
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for YAML configuration. "
                "Install it with: pip install fuzzy[yaml]"
            ) from exc

        with open(filepath, "r") as f:
            config: Dict[str, Any] = yaml.safe_load(f)
        logger.info("Loaded configuration from YAML: %s", filepath)
        return config

    @staticmethod
    def from_json(filepath: str) -> Dict[str, Any]:
        """Load configuration from a JSON file.

        Args:
            filepath: Path to the JSON configuration file.

        Returns:
            Parsed configuration dictionary.
        """
        with open(filepath, "r") as f:
            config: Dict[str, Any] = json.load(f)
        logger.info("Loaded configuration from JSON: %s", filepath)
        return config

    @staticmethod
    def from_env(prefix: str = "FUZZY_SEARCH") -> Dict[str, Any]:
        """Load configuration from environment variables.

        Environment variables are expected in the form
        ``{PREFIX}_BACKEND``, ``{PREFIX}_HOST``, etc.

        Args:
            prefix: The environment variable prefix.

        Returns:
            Configuration dictionary built from environment variables.
        """
        config: Dict[str, Any] = {}
        prefix_upper = prefix.upper()

        mapping = {
            "BACKEND": "backend",
            "HOST": "host",
            "PORT": "port",
            "DATABASE": "database",
            "USER": "user",
            "PASSWORD": "password",  # pragma: allowlist secret
            "ALGORITHM": "algorithm",
            "THRESHOLD": "threshold",
            "MAX_DISTANCE": "max_distance",
            "LIMIT": "limit",
            "CASE_SENSITIVE": "case_sensitive",
            "CONNECTION_STRING": "connection_string",
        }

        for env_suffix, config_key in mapping.items():
            env_var = f"{prefix_upper}_{env_suffix}"
            value = os.environ.get(env_var)
            if value is not None:
                # Coerce numeric and boolean types.
                if config_key in ("port", "max_distance", "limit"):
                    value = int(value)
                elif config_key == "threshold":
                    value = float(value)
                elif config_key == "case_sensitive":
                    value = value.lower() in ("true", "1", "yes")
                config[config_key] = value

        logger.info(
            "Loaded %d config values from environment (prefix=%s)", len(config), prefix
        )
        return config


def create_from_config(config: Dict[str, Any]) -> FuzzySearchManager:
    """Instantiate a ``FuzzySearchManager`` from a configuration dictionary.

    Expected keys::

        backend: str          # e.g. "duckdb", "postgresql"
        algorithm: str        # optional, default "levenshtein"
        threshold: float      # optional, default 0.6
        max_distance: int     # optional, default 3
        limit: int            # optional, default 10
        case_sensitive: bool  # optional, default False
        # Plus any backend-specific connection params (host, port, etc.)

    Args:
        config: Configuration dictionary.

    Returns:
        A configured ``FuzzySearchManager`` instance.
    """
    backend_name = config.get("backend", "duckdb")
    backend_type = DatabaseBackend(backend_name)

    # Build search config.
    algo_name = config.get("algorithm", "levenshtein")
    search_config = FuzzySearchConfig(
        algorithm=SimilarityAlgorithm(algo_name),
        threshold=float(config.get("threshold", 0.6)),
        max_distance=int(config.get("max_distance", 3)),
        limit=int(config.get("limit", 10)),
        case_sensitive=bool(config.get("case_sensitive", False)),
    )

    # Everything else is treated as connection params.
    reserved = {
        "backend",
        "algorithm",
        "threshold",
        "max_distance",
        "limit",
        "case_sensitive",
    }
    connection_params = {k: v for k, v in config.items() if k not in reserved}

    return FuzzySearchManager(
        backend_type=backend_type,
        connection_params=connection_params,
        default_config=search_config,
    )
