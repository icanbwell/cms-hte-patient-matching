"""FHIR R4 client for fetching Patient resources with pagination.

Connects to any standards-compliant FHIR R4 server (Epic, Cerner,
Meditech, HAPI, etc.) and retrieves Patient resources as dicts,
validated through fhirschemapy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

import httpx
from fhirschemapy.R4B.patient import Patient

from .auth import ClientCredentialsAuth

logger = logging.getLogger(__name__)


@dataclass
class FhirClientConfig:
    """Configuration for the FHIR client.

    Attributes:
        base_url: The FHIR server base URL (e.g. ``https://fhir.example.com/R4``).
        auth: Optional OAuth2 client credentials authenticator.
            If None, no authentication is used (for open servers).
        timeout: HTTP request timeout in seconds.
        page_size: Number of resources per page when fetching.
        max_pages: Maximum number of pages to fetch (0 = unlimited).
        verify_ssl: Whether to verify SSL certificates.
        extra_headers: Additional headers to include in requests.
    """

    base_url: str
    auth: Optional[ClientCredentialsAuth] = None
    timeout: float = 30.0
    page_size: int = 100
    max_pages: int = 0
    verify_ssl: bool = True
    extra_headers: Dict[str, str] = field(default_factory=dict)


class FhirClient:
    """Client for fetching FHIR Patient resources from a server.

    Supports OAuth2 authentication, pagination, and validates
    Patient resources through fhirschemapy.

    Args:
        config: Client configuration.

    Example::

        auth = ClientCredentialsAuth(
            token_url="https://auth.example.com/token",
            client_id="my-app",
            client_secret="secret",  # pragma: allowlist secret
        )
        config = FhirClientConfig(
            base_url="https://fhir.example.com/R4",
            auth=auth,
        )
        client = FhirClient(config)
        for patient in client.fetch_all_patients():
            print(patient["id"])
    """

    def __init__(self, config: FhirClientConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")

    def fetch_all_patients(
        self,
        *,
        search_params: Optional[Dict[str, str]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Fetch all Patient resources from the FHIR server.

        Paginates through all available pages using FHIR Bundle
        ``next`` links.

        Args:
            search_params: Additional FHIR search parameters
                (e.g. ``{"_lastUpdated": "gt2024-01-01"}``).

        Yields:
            Patient resource dicts (JSON-compatible).
        """
        params: Dict[str, str] = {"_count": str(self._config.page_size)}
        if search_params:
            params.update(search_params)

        url: Optional[str] = f"{self._base_url}/Patient"
        page_count = 0

        with self._create_http_client() as client:
            while url:
                page_count += 1
                if self._config.max_pages > 0 and page_count > self._config.max_pages:
                    logger.info(
                        "Reached max_pages limit (%d)",
                        self._config.max_pages,
                    )
                    break

                logger.debug("Fetching page %d from %s", page_count, url)
                response = self._authenticated_get(
                    client, url, params=params if page_count == 1 else None
                )
                response.raise_for_status()

                bundle_dict = response.json()

                entries = bundle_dict.get("entry", [])
                for entry in entries:
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "Patient":
                        yield resource

                if entries:
                    logger.info("Page %d: %d entries", page_count, len(entries))

                # Follow the 'next' link for pagination
                url = _get_next_link(bundle_dict)

        logger.info("Fetched %d pages total", page_count)

    def fetch_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single Patient resource by ID.

        Validates the response through fhirschemapy before returning.

        Args:
            patient_id: The FHIR Patient resource ID.

        Returns:
            The Patient resource dict, or None if not found.
        """
        url = f"{self._base_url}/Patient/{patient_id}"
        with self._create_http_client() as client:
            response = self._authenticated_get(client, url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            # Validate through fhirschemapy, then return as dict
            patient = Patient.from_json(response.text)
            result: Dict[str, Any] = patient.model_dump(
                exclude_none=True, by_alias=True
            )
            return result

    def _create_http_client(self) -> httpx.Client:
        """Create an HTTP client with configured defaults."""
        headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        headers.update(self._config.extra_headers)

        return httpx.Client(
            timeout=self._config.timeout,
            verify=self._config.verify_ssl,
            headers=headers,
        )

    def _authenticated_get(
        self,
        client: httpx.Client,
        url: str,
        *,
        params: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Perform a GET request with OAuth authentication if configured."""
        headers: Dict[str, str] = {}
        if self._config.auth:
            token = self._config.auth.get_access_token(client)
            headers["Authorization"] = f"Bearer {token}"

        return client.get(url, params=params, headers=headers)


def _get_next_link(bundle_dict: Dict[str, Any]) -> Optional[str]:
    """Extract the 'next' pagination URL from a Bundle dict."""
    for link in bundle_dict.get("link", []):
        if link.get("relation") == "next":
            url: Optional[str] = link.get("url")
            return url
    return None
