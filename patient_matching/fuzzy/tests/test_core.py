"""Tests for core.py's shared SQL-identifier validation."""

from __future__ import annotations

import pytest

from patient_matching.fuzzy.fuzzy_db.core import validate_sql_identifier


class TestValidateSqlIdentifier:
    @pytest.mark.parametrize(
        "identifier",
        [
            "patients",
            "name",
            "_private",
            "table_1",
            "UPPER_CASE",
        ],
    )
    def test_accepts_bare_identifiers(self, identifier):
        assert validate_sql_identifier(identifier) == identifier

    @pytest.mark.parametrize(
        "identifier",
        [
            "",
            "1table",  # starts with a digit
            "name; DROP TABLE patients;--",
            "name) UNION SELECT ssn FROM patients--",
            "name -- comment",
            "table name",  # whitespace
            "table.name",  # dotted/qualified identifier not allowed
            "table'name",
            'table"name',
            "table/*comment*/name",
        ],
    )
    def test_rejects_unsafe_identifiers(self, identifier):
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            validate_sql_identifier(identifier)
