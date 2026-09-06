"""Main orchestrator for IAL2 token extraction.

Combines token verification and FHIR conversion into a single
entry point.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .claims_model import IAL2Claims
from .fhir_converter import IAL2ToFhirConverter
from .token_verifier import TokenVerifier

logger = logging.getLogger(__name__)


class IAL2Extractor:
    """Accepts an IAL2 JWT, verifies it, and returns a FHIR Patient resource.

    Args:
        verifier: A configured TokenVerifier for signature validation.
        converter: An IAL2ToFhirConverter instance. If None, a default
            converter is created.

    Example::

        verifier = TokenVerifier(
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="my-client-id",
        )
        extractor = IAL2Extractor(verifier=verifier)
        patient = await extractor.extract(token_string)
        # patient is a FHIR R4 Patient resource dict
    """

    def __init__(
        self,
        *,
        verifier: TokenVerifier,
        converter: Optional[IAL2ToFhirConverter] = None,
    ) -> None:
        self._verifier = verifier
        self._converter = converter or IAL2ToFhirConverter()

    async def extract(self, token: str) -> Dict[str, Any]:
        """Verify an IAL2 token and return a FHIR Patient resource.

        Args:
            token: The encoded JWT string from the CSP.

        Returns:
            A FHIR R4 Patient resource as a dictionary.

        Raises:
            TokenVerificationError: If the token signature or claims
                are invalid.
        """
        logger.debug("Verifying IAL2 token")
        raw_claims = await self._verifier.verify(token)

        logger.debug("Extracting claims from verified token")
        claims = IAL2Claims.from_token_claims(raw_claims)

        logger.debug("Converting claims to FHIR Patient resource")
        patient = self._converter.convert(claims)

        return patient

    async def extract_claims(self, token: str) -> IAL2Claims:
        """Verify an IAL2 token and return the normalized claims.

        Useful when you need the structured claims without FHIR conversion.

        Args:
            token: The encoded JWT string from the CSP.

        Returns:
            An IAL2Claims dataclass with normalized demographics.

        Raises:
            TokenVerificationError: If the token signature or claims
                are invalid.
        """
        raw_claims = await self._verifier.verify(token)
        return IAL2Claims.from_token_claims(raw_claims)
