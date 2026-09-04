"""MongoDB Atlas Search-backed patient cache.

Session 12 (see docs/sessions/pending/session_12.md): an alternative to
DuckDBCache for deployments where multiple service replicas (e.g. behind a
Kubernetes HPA) need a *shared* candidate store instead of N independent
in-process caches, and where DuckDBCache's O(n) Python fuzzy-search loop
(``DuckDBCache._fuzzy_search``) doesn't scale against a large candidate pool.

Tradeoff vs. DuckDBCache (ships as an additional option, not a replacement):
``MatchingEngine.match()`` calls ``backend.search()`` once per Table 2 rule
(~38 rules), and ``CacheMatchingBackend.search()`` calls
``cache.search_by_field()`` once per criterion within each rule. DuckDBCache
answers each of those in-process; this backend makes a real network
round-trip per call, so a full match can mean dozens of round-trips to
Atlas. Recommended default: use this only where the shared-cache benefit
(consistency, no duplicated upstream FHIR load across replicas) outweighs
that per-request latency -- measure with the benchmark in
``tests/test_cache_benchmark.py`` before adopting it for a given
deployment's expected load.

Atlas Search index setup is NOT done by this module -- creating a search
index is a cluster-admin action against a real Atlas deployment (Atlas UI
or Admin API), using ``mongo_atlas_index.json`` (sibling to this file) as
the index definition. Tests create the equivalent index programmatically
against the ``mongodb-atlas-local`` testcontainer instead (see
``tests/test_mongo_atlas_cache.py``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .cache_backend import CacheBackend, CachedPatient

if TYPE_CHECKING:
    from pymongo import MongoClient
    from pymongo.collection import Collection

logger = logging.getLogger(__name__)

# Mirrors DuckDBCache's field_values shape/rules exactly, so the two backends
# are drop-in equivalents (see tests/test_mongo_atlas_cache.py's equivalence
# test).
_FIELD_MAP_ATTRS = (
    "first_names",
    "last_names",
    "suffixes",
    "dob",
    "street_lines",
    "phones",
    "emails",
    "ssn_last4",
    "itin_last4",
    "mbi",
    "legal_ids",
    "namespace_ids",
)
_ATTR_TO_FIELD_NAME = {
    "first_names": "first_name",
    "last_names": "last_name",
    "suffixes": "suffix",
    "dob": "dob",
    "street_lines": "street_line",
    "phones": "phone",
    "emails": "email",
    "ssn_last4": "ssn_last4",
    "itin_last4": "itin_last4",
    "mbi": "mbi",
    "legal_ids": "legal_id",
    "namespace_ids": "namespace_id",
}

_MIN_FUZZY_LENGTH = 5
_MAX_EDITS = 1

SEARCH_INDEX_NAME = "patient_field_search_index"
SEARCH_INDEX_DEFINITION_PATH = Path(__file__).with_name("mongo_atlas_index.json")


class MongoAtlasCache(CacheBackend):
    """MongoDB + Atlas Search implementation of the patient cache.

    Uses two collections (mirroring DuckDBCache's schema):
      - ``patients``: ``{_id: patient_id, fhir_resource: {...}}``.
      - ``field_values``: ``{patient_id, field_name, value}`` documents,
        with a compound index on ``(field_name, value)`` for the exact path
        and an Atlas Search index (see module docstring) for the fuzzy path.

    Args:
        connection_string: MongoDB connection URI.
        database: Database name.
    """

    def __init__(
        self,
        connection_string: str = "mongodb://localhost:27017",
        database: str = "patient_cache",
    ) -> None:
        try:
            from pymongo import MongoClient as _MongoClient
        except ImportError as exc:
            raise ImportError(
                "pymongo is required for MongoAtlasCache. "
                "Install it with: pip install patient_matching[mongo]"
            ) from exc

        self._client: "MongoClient[Dict[str, Any]]" = _MongoClient(connection_string)
        self._db = self._client[database]
        self._patients: "Collection[Dict[str, Any]]" = self._db["patients"]
        self._field_values: "Collection[Dict[str, Any]]" = self._db["field_values"]
        self._field_values.create_index([("field_name", 1), ("value", 1)])
        self._field_values.create_index("patient_id")

    def upsert_patients(self, patients: List[CachedPatient]) -> int:
        """Insert or update normalized patient records in bulk."""
        if not patients:
            return 0

        from pymongo import ReplaceOne

        patient_ops = [
            ReplaceOne(
                {"_id": p.patient_id},
                {"_id": p.patient_id, "fhir_resource": p.fhir_resource},
                upsert=True,
            )
            for p in patients
        ]
        self._patients.bulk_write(patient_ops)

        patient_ids = [p.patient_id for p in patients]
        self._field_values.delete_many({"patient_id": {"$in": patient_ids}})

        rows = []
        for p in patients:
            for attr in _FIELD_MAP_ATTRS:
                field_name = _ATTR_TO_FIELD_NAME[attr]
                for value in getattr(p, attr):
                    if value:
                        rows.append(
                            {
                                "patient_id": p.patient_id,
                                "field_name": field_name,
                                "value": value,
                            }
                        )
        if rows:
            self._field_values.insert_many(rows)

        logger.info("Upserted %d patients into MongoAtlasCache", len(patients))
        return len(patients)

    def search_by_field(
        self,
        field_name: str,
        value: str,
        *,
        fuzzy: bool = False,
    ) -> List[CachedPatient]:
        """Search cached patients by a single field value."""
        if fuzzy and len(value) >= _MIN_FUZZY_LENGTH:
            return self._fuzzy_search(field_name, value)

        patient_ids = {
            doc["patient_id"]
            for doc in self._field_values.find(
                {"field_name": field_name, "value": value},
                {"patient_id": 1},
            )
        }
        return [p for pid in patient_ids if (p := self.get_patient(pid)) is not None]

    def _fuzzy_search(self, field_name: str, query_value: str) -> List[CachedPatient]:
        """Fuzzy search via Atlas ``$search`` (DL-equivalent edit distance <= 1).

        Falls back to an empty result (logging the error) if the Atlas
        Search index is missing or unavailable -- mirrors
        person-matching-service's AtlasSearchStrategy graceful degradation.
        """
        pipeline: List[Dict[str, Any]] = [
            {
                "$search": {
                    "index": SEARCH_INDEX_NAME,
                    "compound": {
                        "filter": [
                            {"equals": {"path": "field_name", "value": field_name}}
                        ],
                        "must": [
                            {
                                "text": {
                                    "path": "value",
                                    "query": query_value,
                                    "fuzzy": {
                                        "maxEdits": _MAX_EDITS,
                                        "prefixLength": 0,
                                    },
                                }
                            }
                        ],
                    },
                }
            },
            {"$project": {"patient_id": 1}},
        ]
        try:
            patient_ids = {
                doc["patient_id"] for doc in self._field_values.aggregate(pipeline)
            }
        except Exception as exc:
            logger.error(
                "Atlas $search failed for field_name=%r (index=%r missing or "
                "unavailable?): %s",
                field_name,
                SEARCH_INDEX_NAME,
                exc,
            )
            return []

        return [p for pid in patient_ids if (p := self.get_patient(pid)) is not None]

    def get_patient(self, patient_id: str) -> Optional[CachedPatient]:
        """Retrieve a single cached patient by ID."""
        doc = self._patients.find_one({"_id": patient_id})
        if doc is None:
            return None

        patient = CachedPatient(
            patient_id=patient_id,
            fhir_resource=doc["fhir_resource"],
        )
        for row in self._field_values.find({"patient_id": patient_id}):
            attr = next(
                a for a, fn in _ATTR_TO_FIELD_NAME.items() if fn == row["field_name"]
            )
            getattr(patient, attr).add(row["value"])
        return patient

    def count(self) -> int:
        """Return the total number of cached patients."""
        return self._patients.count_documents({})

    def clear(self) -> None:
        """Remove all cached patients."""
        self._field_values.delete_many({})
        self._patients.delete_many({})
        logger.info("Cleared MongoAtlasCache")

    def close(self) -> None:
        """Close the MongoDB connection."""
        self._client.close()


def search_index_definition() -> Dict[str, Any]:
    """Load the committed Atlas Search index definition (see module docstring)."""
    definition: Dict[str, Any] = json.loads(SEARCH_INDEX_DEFINITION_PATH.read_text())
    return definition
