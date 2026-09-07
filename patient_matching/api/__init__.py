"""api: end-to-end patient matching orchestration.

Provides ``PatientMatcherService``, which chains IAL2 extraction,
normalization, and matching against a cache into a single async entry
point. No HTTP layer here -- that's the sibling
``cms-hte-patient-matching-service`` repo's job; this package is only
the library it consumes.
"""

from .service import PatientMatcherService, ServiceConfig

__all__ = [
    "PatientMatcherService",
    "ServiceConfig",
]
