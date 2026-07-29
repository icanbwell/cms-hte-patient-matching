"""fhir_client: FHIR server communication with OAuth and pagination.

Provides a client for fetching Patient resources from any
standards-compliant FHIR R4 server using OAuth2 client credentials.
"""

from .auth import ClientCredentialsAuth
from .client import FhirClient, FhirClientConfig

__all__ = [
    "ClientCredentialsAuth",
    "FhirClient",
    "FhirClientConfig",
]
