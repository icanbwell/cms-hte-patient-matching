"""Cache manager: orchestrates the fetch → normalize → store pipeline.

Connects the FHIR client, normalization engine, field extractor, and
cache backend into a single pipeline that builds and refreshes the
patient matching cache.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..fhir_client.client import FhirClient
from ..matching.field_extractor import FieldExtractor, PatientFields
from ..normalization.manager import NormalizationManager
from .cache_backend import CacheBackend, CachedPatient

logger = logging.getLogger(__name__)


@dataclass
class CacheManagerConfig:
    """Configuration for the cache manager.

    Attributes:
        refresh_interval_minutes: How often to refresh the cache
            (0 = no automatic refresh).
        search_params: Optional FHIR search parameters to filter
            which patients to fetch (e.g. ``{"_lastUpdated": "gt2024-01-01"}``).
        batch_size: Number of patients to upsert per batch.
    """

    refresh_interval_minutes: int = 0
    search_params: Optional[Dict[str, str]] = None
    batch_size: int = 500


class CacheManager:
    """Manages the patient matching cache lifecycle.

    Orchestrates:
      1. Fetching patients from a FHIR server
      2. Normalizing demographics using CMS rules
      3. Extracting canonical fields for matching
      4. Storing in the cache backend

    Args:
        fhir_client: Client for fetching patients from a FHIR server.
        normalizer: Normalization manager for CMS demographic rules.
        cache: The cache backend for storage.
        config: Cache manager configuration.

    Example::

        manager = CacheManager(
            fhir_client=fhir_client,
            normalizer=NormalizationManager(),
            cache=DuckDBCache(),
        )
        stats = await manager.build_cache()
        print(f"Cached {stats['patients_cached']} patients")
    """

    def __init__(
        self,
        *,
        fhir_client: FhirClient,
        normalizer: Optional[NormalizationManager] = None,
        cache: CacheBackend,
        config: Optional[CacheManagerConfig] = None,
    ) -> None:
        self._fhir_client = fhir_client
        self._normalizer = normalizer or NormalizationManager()
        self._cache = cache
        self._config = config or CacheManagerConfig()
        self._extractor = FieldExtractor()
        self._scheduler: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def build_cache(self) -> Dict[str, int]:
        """Build the patient cache from scratch.

        Fetches all patients from the FHIR server, normalizes them,
        and stores them in the cache.

        Returns:
            Stats dict with keys: patients_fetched, patients_cached,
            patients_skipped.
        """
        async with self._lock:
            logger.info("Starting cache build...")
            await self._cache.clear()
            return await self._refresh_internal()

    async def refresh_cache(self) -> Dict[str, int]:
        """Incrementally refresh the cache.

        Fetches patients from the FHIR server and upserts them
        into the cache without clearing existing data.

        Returns:
            Stats dict with keys: patients_fetched, patients_cached,
            patients_skipped.
        """
        async with self._lock:
            logger.info("Starting cache refresh...")
            return await self._refresh_internal()

    async def _refresh_internal(self) -> Dict[str, int]:
        """Internal refresh logic shared by build and refresh."""
        stats = {
            "patients_fetched": 0,
            "patients_cached": 0,
            "patients_skipped": 0,
        }

        batch: List[CachedPatient] = []

        async for patient_dict in self._fhir_client.fetch_all_patients(
            search_params=self._config.search_params,
        ):
            stats["patients_fetched"] += 1

            try:
                cached = self._process_patient(patient_dict)
                if cached:
                    batch.append(cached)
                else:
                    stats["patients_skipped"] += 1
            except Exception:
                logger.exception(
                    "Failed to process patient %s",
                    patient_dict.get("id", "unknown"),
                )
                stats["patients_skipped"] += 1
                continue

            # Flush batch
            if len(batch) >= self._config.batch_size:
                count = await self._cache.upsert_patients(batch)
                stats["patients_cached"] += count
                batch = []

        # Flush remaining
        if batch:
            count = await self._cache.upsert_patients(batch)
            stats["patients_cached"] += count

        logger.info(
            "Cache refresh complete: fetched=%d, cached=%d, skipped=%d",
            stats["patients_fetched"],
            stats["patients_cached"],
            stats["patients_skipped"],
        )
        return stats

    def _process_patient(self, patient_dict: Dict[str, Any]) -> Optional[CachedPatient]:
        """Normalize a patient and extract fields for caching.

        Returns None if the patient has no usable fields.
        """
        patient_id = patient_dict.get("id", "")
        if not patient_id:
            return None

        # Step 1: Normalize demographics
        normalized = self._normalizer.normalize(patient_dict)

        # Step 2: Extract canonical fields
        fields = self._extractor.extract(normalized)

        # Skip patients with no matchable fields
        if not self._has_any_field(fields):
            return None

        # Step 3: Build CachedPatient
        return CachedPatient(
            patient_id=patient_id,
            first_names=fields.first_names,
            last_names=fields.last_names,
            suffixes=fields.suffixes,
            dob=fields.dob,
            street_lines=fields.street_lines,
            phones=fields.phones,
            emails=fields.emails,
            ssn_last4=fields.ssn_last4,
            itin_last4=fields.itin_last4,
            mbi=fields.mbi,
            legal_ids=fields.legal_ids,
            namespace_ids=fields.namespace_ids,
            fhir_resource=normalized,
        )

    @staticmethod
    def _has_any_field(fields: PatientFields) -> bool:
        """Check if a patient has at least one matchable field."""
        return bool(
            fields.first_names
            or fields.last_names
            or fields.dob
            or fields.phones
            or fields.emails
            or fields.ssn_last4
            or fields.itin_last4
            or fields.mbi
            or fields.legal_ids
            or fields.namespace_ids
        )

    def start_scheduled_refresh(self) -> None:
        """Start automatic cache refresh on a schedule.

        Uses APScheduler to run ``refresh_cache()`` at the configured
        interval. Does nothing if ``refresh_interval_minutes`` is 0.

        ``refresh_cache`` is now a coroutine function, so this needs
        ``AsyncIOScheduler`` (which can schedule and await coroutine jobs
        directly) instead of ``BackgroundScheduler`` (which runs jobs in a
        plain thread and can't await one). Must be called from within a
        running event loop -- e.g. a FastAPI startup hook.
        """
        interval = self._config.refresh_interval_minutes
        if interval <= 0:
            logger.info("Scheduled refresh disabled (interval=0)")
            return

        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.refresh_cache,
            "interval",
            minutes=interval,
            id="cache_refresh",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Scheduled cache refresh every %d minutes", interval)

    def stop_scheduled_refresh(self) -> None:
        """Stop the automatic cache refresh scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Stopped scheduled cache refresh")

    @property
    def cache(self) -> CacheBackend:
        """The underlying cache backend."""
        return self._cache

    async def patient_count(self) -> int:
        """Number of patients currently in the cache."""
        return await self._cache.count()
