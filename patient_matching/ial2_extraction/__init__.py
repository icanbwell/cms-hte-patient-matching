"""ial2_extraction: Extract and verify IAL2 token demographics as FHIR Patient resources.

Accepts a signed JWT (ID Token) from a Credential Service Provider (CSP),
verifies the signature via JWKS, extracts demographics per the CSP payload
specification V7.1, and returns a FHIR R4 Patient resource.
"""

from .claims_model import IAL2Claims, IAL2Address, IAL2LegalId
from .fhir_converter import IAL2ToFhirConverter
from .ial2_extractor import IAL2Extractor
from .token_verifier import TokenVerifier, TokenVerificationError

__all__ = [
    "IAL2Address",
    "IAL2Claims",
    "IAL2Extractor",
    "IAL2LegalId",
    "IAL2ToFhirConverter",
    "TokenVerificationError",
    "TokenVerifier",
]
