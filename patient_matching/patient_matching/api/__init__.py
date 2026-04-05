"""api: HTTP service exposing FHIR $match and IAL2 matching endpoints.

Provides a FastAPI application that:
  - Accepts FHIR $match requests (Parameters resource in, Bundle out)
  - Accepts raw IAL2 JWT tokens and returns matched FHIR Patient IDs
  - Manages the patient matching cache lifecycle
"""

from .app import create_app
from .service import PatientMatcherService, ServiceConfig

__all__ = [
    "PatientMatcherService",
    "ServiceConfig",
    "create_app",
]
