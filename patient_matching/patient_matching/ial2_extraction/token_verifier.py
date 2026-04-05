"""JWT signature verification for IAL2 tokens using JWKS.

Fetches the CSP's public keys from their OIDC discovery endpoint
and verifies the token signature, expiration, and audience.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.request import urlopen

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


class TokenVerificationError(Exception):
    """Raised when an IAL2 token fails signature or claims verification."""


class TokenVerifier:
    """Verifies IAL2 JWT tokens against a CSP's JWKS endpoint.

    Args:
        jwks_uri: URL of the JWKS endpoint (e.g.
            ``https://idp.example.com/.well-known/jwks.json``).
        audience: Expected ``aud`` claim value.
        issuer: Expected ``iss`` claim value. If provided, the token's
            issuer must match exactly.
        algorithms: Allowed signing algorithms. Defaults to RS256.
    """

    def __init__(
        self,
        *,
        jwks_uri: str,
        audience: str,
        issuer: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
    ) -> None:
        self._jwks_uri = jwks_uri
        self._audience = audience
        self._issuer = issuer
        self._algorithms = algorithms or ["RS256"]
        self._jwks_client = PyJWKClient(jwks_uri)

    def verify(self, token: str) -> Dict[str, Any]:
        """Verify the token signature and standard claims.

        Args:
            token: The encoded JWT string.

        Returns:
            The decoded claims dictionary.

        Raises:
            TokenVerificationError: If the token is invalid, expired,
                or fails audience/issuer checks.
        """
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)

            decoded: Dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["exp", "iat", "iss", "sub", "aud", "jti"],
                },
            )
            return decoded

        except jwt.ExpiredSignatureError as e:
            raise TokenVerificationError(f"Token has expired: {e}") from e
        except jwt.InvalidAudienceError as e:
            raise TokenVerificationError(
                f"Invalid audience: {e}"
            ) from e
        except jwt.InvalidIssuerError as e:
            raise TokenVerificationError(f"Invalid issuer: {e}") from e
        except jwt.PyJWKClientError as e:
            raise TokenVerificationError(
                f"Failed to fetch signing key from JWKS: {e}"
            ) from e
        except jwt.InvalidTokenError as e:
            raise TokenVerificationError(
                f"Token verification failed: {e}"
            ) from e

    @classmethod
    def from_oidc_discovery(
        cls,
        *,
        discovery_url: str,
        audience: str,
        issuer: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
    ) -> TokenVerifier:
        """Create a verifier by fetching the JWKS URI from OIDC discovery.

        Args:
            discovery_url: The ``/.well-known/openid-configuration`` URL.
            audience: Expected ``aud`` claim value.
            issuer: Expected ``iss`` claim value.
            algorithms: Allowed signing algorithms.

        Returns:
            A configured TokenVerifier instance.

        Raises:
            TokenVerificationError: If discovery metadata cannot be fetched.
        """
        try:
            with urlopen(discovery_url) as response:
                metadata = json.loads(response.read())
            jwks_uri = metadata["jwks_uri"]
        except Exception as e:
            raise TokenVerificationError(
                f"Failed to fetch OIDC discovery metadata from "
                f"{discovery_url}: {e}"
            ) from e

        return cls(
            jwks_uri=jwks_uri,
            audience=audience,
            issuer=issuer or metadata.get("issuer"),
            algorithms=algorithms,
        )