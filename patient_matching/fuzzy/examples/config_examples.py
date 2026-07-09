"""Configuration loading examples for fuzzy."""

from __future__ import annotations

import os
from typing import Any

from patient_matching.fuzzy.fuzzy_db.config import ConfigLoader, create_from_config


def json_config_example() -> None:
    """Load configuration from a JSON file."""
    # Assuming config.json contains:
    # {
    #     "backend": "duckdb",
    #     "database": ":memory:",
    #     "algorithm": "jaro_winkler",
    #     "threshold": 0.7,
    #     "limit": 10
    # }
    config: dict[str, Any] = ConfigLoader.from_json("config.json")
    manager = create_from_config(config)
    print(f"Backend: {manager._backend_type.value}")
    print(f"Algorithm: {manager._default_config.algorithm.value}")


def yaml_config_example() -> None:
    """Load configuration from a YAML file."""
    # Assuming config.yaml contains:
    # backend: postgresql
    # host: localhost
    # port: 5432
    # database: mydb
    # user: admin
    # password: secret
    # algorithm: levenshtein
    # threshold: 0.6
    config: dict[str, Any] = ConfigLoader.from_yaml("config.yaml")
    manager = create_from_config(config)
    print(f"Backend: {manager._backend_type.value}")


def env_config_example() -> None:
    """Load configuration from environment variables."""
    # Set environment variables.
    os.environ["FUZZY_SEARCH_BACKEND"] = "duckdb"
    os.environ["FUZZY_SEARCH_DATABASE"] = ":memory:"
    os.environ["FUZZY_SEARCH_ALGORITHM"] = "levenshtein"
    os.environ["FUZZY_SEARCH_THRESHOLD"] = "0.65"

    config: dict[str, Any] = ConfigLoader.from_env()
    manager = create_from_config(config)
    print(f"Backend: {manager._backend_type.value}")
    print(f"Threshold: {manager._default_config.threshold}")


if __name__ == "__main__":
    print("=== Environment Config ===")
    env_config_example()
