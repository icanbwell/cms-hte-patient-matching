"""DuckDB-based patient cache for lightweight deployments.

Stores normalized patient records in an in-memory (or file-backed)
DuckDB database with full-text search on multi-valued fields using
a normalized relational schema.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Set

import duckdb
from rapidfuzz.distance import DamerauLevenshtein

from .cache_backend import CacheBackend, CachedPatient

logger = logging.getLogger(__name__)

# Field name → column in the field_values table
_CANONICAL_FIELDS = {
    "first_name",
    "last_name",
    "dob",
    "street_line",
    "phone",
    "email",
    "ssn_last4",
    "itin_last4",
    "mbi",
    "legal_id",
    "namespace_id",
    "suffix",
}

_MIN_FUZZY_LENGTH = 5
_MAX_DL_DISTANCE = 1


class DuckDBCache(CacheBackend):
    """DuckDB implementation of the patient cache.

    Uses two tables:
      - ``patients``: Stores the patient ID and full FHIR resource JSON.
      - ``field_values``: Stores (patient_id, field_name, value) triples
        for efficient field-level lookups.

    Args:
        database: DuckDB database path. Use ``:memory:`` for in-memory.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self._conn = duckdb.connect(database)
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the schema if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id VARCHAR PRIMARY KEY,
                fhir_resource JSON NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS field_values (
                patient_id VARCHAR NOT NULL,
                field_name VARCHAR NOT NULL,
                value VARCHAR NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fv_field_value
            ON field_values (field_name, value)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fv_patient
            ON field_values (patient_id)
        """)

    async def upsert_patients(self, patients: List[CachedPatient]) -> int:
        """Insert or update normalized patient records in bulk."""
        if not patients:
            return 0

        count = 0
        for p in patients:
            # Upsert patient record
            self._conn.execute(
                """
                INSERT OR REPLACE INTO patients (patient_id, fhir_resource)
                VALUES (?, ?)
                """,
                [p.patient_id, json.dumps(p.fhir_resource)],
            )
            # Remove old field values and reinsert
            self._conn.execute(
                "DELETE FROM field_values WHERE patient_id = ?",
                [p.patient_id],
            )
            self._insert_field_values(p)
            count += 1

        logger.info("Upserted %d patients into DuckDB cache", count)
        return count

    def _insert_field_values(self, patient: CachedPatient) -> None:
        """Insert all field values for a patient."""
        field_map: Dict[str, Set[str]] = {
            "first_name": patient.first_names,
            "last_name": patient.last_names,
            "suffix": patient.suffixes,
            "dob": patient.dob,
            "street_line": patient.street_lines,
            "phone": patient.phones,
            "email": patient.emails,
            "ssn_last4": patient.ssn_last4,
            "itin_last4": patient.itin_last4,
            "mbi": patient.mbi,
            "legal_id": patient.legal_ids,
            "namespace_id": patient.namespace_ids,
        }
        rows = []
        for field_name, values in field_map.items():
            for v in values:
                if v:
                    rows.append((patient.patient_id, field_name, v))

        if rows:
            self._conn.executemany(
                """
                INSERT INTO field_values (patient_id, field_name, value)
                VALUES (?, ?, ?)
                """,
                rows,
            )

    async def search_by_field(
        self,
        field_name: str,
        value: str,
        *,
        fuzzy: bool = False,
    ) -> List[CachedPatient]:
        """Search cached patients by a single field value."""
        if fuzzy:
            return await self._fuzzy_search(field_name, value)

        result = self._conn.execute(
            """
            SELECT DISTINCT fv.patient_id, p.fhir_resource
            FROM field_values fv
            JOIN patients p ON fv.patient_id = p.patient_id
            WHERE fv.field_name = ? AND fv.value = ?
            """,
            [field_name, value],
        ).fetchall()

        return [self._row_to_cached_patient(r) for r in result]

    async def _fuzzy_search(
        self, field_name: str, query_value: str
    ) -> List[CachedPatient]:
        """Fuzzy search using Damerau-Levenshtein distance <= 1.

        For values shorter than 5 characters, falls back to exact match
        per CMS rule E.3.
        """
        if len(query_value) < _MIN_FUZZY_LENGTH:
            return await self.search_by_field(field_name, query_value, fuzzy=False)

        # Fetch all distinct values for this field, then filter in Python
        # using rapidfuzz (DuckDB's built-in DL may not match rapidfuzz's
        # behavior for all edge cases).
        candidates = self._conn.execute(
            """
            SELECT DISTINCT fv.patient_id, fv.value, p.fhir_resource
            FROM field_values fv
            JOIN patients p ON fv.patient_id = p.patient_id
            WHERE fv.field_name = ?
            """,
            [field_name],
        ).fetchall()

        matched_ids: set[str] = set()
        results: List[CachedPatient] = []

        for pid, val, fhir_json in candidates:
            if pid in matched_ids:
                continue
            if len(val) < _MIN_FUZZY_LENGTH:
                continue
            dist = DamerauLevenshtein.distance(query_value, val)
            if dist <= _MAX_DL_DISTANCE:
                matched_ids.add(pid)
                results.append(self._row_to_cached_patient((pid, fhir_json)))

        return results

    async def get_patient(self, patient_id: str) -> Optional[CachedPatient]:
        """Retrieve a single cached patient by ID."""
        result = self._conn.execute(
            "SELECT patient_id, fhir_resource FROM patients WHERE patient_id = ?",
            [patient_id],
        ).fetchone()
        if result is None:
            return None
        return self._row_to_cached_patient(result)

    async def count(self) -> int:
        """Return the total number of cached patients."""
        result = self._conn.execute("SELECT COUNT(*) FROM patients").fetchone()
        return result[0] if result else 0

    async def clear(self) -> None:
        """Remove all cached patients."""
        self._conn.execute("DELETE FROM field_values")
        self._conn.execute("DELETE FROM patients")
        logger.info("Cleared DuckDB cache")

    async def close(self) -> None:
        """Close the DuckDB connection."""
        self._conn.close()

    def _row_to_cached_patient(self, row: tuple[str, str]) -> CachedPatient:
        """Convert a (patient_id, fhir_resource_json) row to CachedPatient."""
        patient_id, fhir_json = row
        fhir_resource = json.loads(fhir_json)

        # Reconstruct field sets from the field_values table
        field_rows = self._conn.execute(
            "SELECT field_name, value FROM field_values WHERE patient_id = ?",
            [patient_id],
        ).fetchall()

        patient = CachedPatient(
            patient_id=patient_id,
            fhir_resource=fhir_resource,
        )

        for field_name, value in field_rows:
            if field_name == "first_name":
                patient.first_names.add(value)
            elif field_name == "last_name":
                patient.last_names.add(value)
            elif field_name == "suffix":
                patient.suffixes.add(value)
            elif field_name == "dob":
                patient.dob.add(value)
            elif field_name == "street_line":
                patient.street_lines.add(value)
            elif field_name == "phone":
                patient.phones.add(value)
            elif field_name == "email":
                patient.emails.add(value)
            elif field_name == "ssn_last4":
                patient.ssn_last4.add(value)
            elif field_name == "itin_last4":
                patient.itin_last4.add(value)
            elif field_name == "mbi":
                patient.mbi.add(value)
            elif field_name == "legal_id":
                patient.legal_ids.add(value)
            elif field_name == "namespace_id":
                patient.namespace_ids.add(value)

        return patient
