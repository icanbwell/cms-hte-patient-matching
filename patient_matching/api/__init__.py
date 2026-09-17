"""api: end-to-end patient matching orchestration.

Provides ``PatientMatcherService``, which chains normalization and
matching against a cache into a single async entry point over FHIR
Patient resources. Callers holding an IAL2 token must convert it
themselves first, e.g. with ``cms-hte-ial2-reader``. No HTTP layer here
-- that's the sibling ``cms-hte-patient-matching-service`` repo's job;
this package is only the library it consumes.
"""

from .service import PatientMatcherService, ServiceConfig

__all__ = [
    "PatientMatcherService",
    "ServiceConfig",
]
