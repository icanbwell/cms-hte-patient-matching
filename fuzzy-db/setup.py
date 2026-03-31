"""Backwards-compatible setup.py for fuzzy-db."""

from setuptools import find_packages, setup

setup(
    name="fuzzy-db",
    version="0.1.0",
    description="Unified fuzzy string matching across database backends",
    long_description=open("docs/README.md").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(include=["fuzzy_db", "fuzzy_db.*"]),
    install_requires=[
        "rapidfuzz>=3.0.0",
    ],
    extras_require={
        "postgresql": ["psycopg2-binary>=2.9.0"],
        "duckdb": ["duckdb>=0.9.0"],
        "mongodb": ["pymongo>=4.0.0"],
        "redis": ["redis>=5.0.0"],
        "elasticsearch": ["elasticsearch>=8.0.0"],
        "yaml": ["PyYAML>=6.0"],
        "all": [
            "psycopg2-binary>=2.9.0",
            "duckdb>=0.9.0",
            "pymongo>=4.0.0",
            "redis>=5.0.0",
            "elasticsearch>=8.0.0",
            "PyYAML>=6.0",
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "mypy>=1.0",
            "flake8>=6.0",
            "isort>=5.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Database",
        "Topic :: Text Processing",
    ],
)
