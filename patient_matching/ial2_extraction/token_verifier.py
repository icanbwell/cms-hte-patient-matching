"""JWT signature verification for IAL2 tokens using JWKS.

Fetches the CSP's public keys from their OIDC discovery endpoint
and verifies the token signature, expiration, and audience.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import logging
import socket
import ssl
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import urlopen

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


class TokenVerificationError(Exception):
    """Raised when an IAL2 token fails signature or claims verification."""


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """An HTTPSConnection that dials a pre-resolved IP instead of
    re-resolving its host via DNS, while still using that original host for
    TLS SNI and certificate verification.

    Used to close the DNS-rebinding TOCTOU window between validating a
    hostname's resolved address and actually connecting to it: a plain
    HTTPSConnection re-resolves the hostname at connect() time, so an
    attacker controlling that hostname's DNS could serve a different
    (internal) address than the one that was validated moments earlier.
    """

    # Declared here for mypy: real attributes set by HTTPSConnection.__init__
    # (typeshed doesn't expose them, since they're conventionally private).
    _context: ssl.SSLContext
    source_address: Optional[Tuple[str, int]]

    def __init__(self, host: str, pinned_ip: str, **kwargs: Any) -> None:
        super().__init__(host, **kwargs)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _fetch_json_pinned(
    url: str, pinned_ip: str, *, timeout: float = 10.0
) -> Dict[str, Any]:
    """Fetch and parse JSON from `url`, connecting to `pinned_ip` rather
    than letting the request re-resolve the URL's hostname via DNS."""
    parsed = urlparse(url)
    conn = _PinnedHTTPSConnection(
        parsed.hostname or "", pinned_ip, port=parsed.port, timeout=timeout
    )
    try:
        conn.request("GET", parsed.path or "/", headers={"Accept": "application/json"})
        response = conn.getresponse()
        body = response.read()
    finally:
        conn.close()
    result: Dict[str, Any] = json.loads(body)
    return result


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

    @property
    def jwks_uri(self) -> str:
        """The JWKS endpoint this verifier fetches signing keys from."""
        return self._jwks_uri

    async def verify(self, token: str) -> Dict[str, Any]:
        """Verify the token signature and standard claims.

        Args:
            token: The encoded JWT string.

        Returns:
            The decoded claims dictionary.

        Raises:
            TokenVerificationError: If the token is invalid, expired,
                or fails audience/issuer checks.
        """
        return await asyncio.to_thread(self._verify_sync, token)

    def _verify_sync(self, token: str) -> Dict[str, Any]:
        """Blocking body of verify() -- PyJWT/PyJWKClient have no async API,
        so verify() offloads this to a thread instead of blocking the event
        loop for the JWKS fetch (network I/O) this does internally."""
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
            raise TokenVerificationError(f"Invalid audience: {e}") from e
        except jwt.InvalidIssuerError as e:
            raise TokenVerificationError(f"Invalid issuer: {e}") from e
        except jwt.PyJWKClientError as e:
            raise TokenVerificationError(
                f"Failed to fetch signing key from JWKS: {e}"
            ) from e
        except jwt.InvalidTokenError as e:
            raise TokenVerificationError(f"Token verification failed: {e}") from e

    @classmethod
    async def from_oidc_discovery(
        cls,
        *,
        discovery_url: str,
        audience: str,
        issuer: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
        pinned_ip: Optional[str] = None,
    ) -> TokenVerifier:
        """Create a verifier by fetching the JWKS URI from OIDC discovery.

        Args:
            discovery_url: The ``/.well-known/openid-configuration`` URL.
            audience: Expected ``aud`` claim value.
            issuer: Expected ``iss`` claim value.
            algorithms: Allowed signing algorithms.
            pinned_ip: If given, connect to this IP instead of letting the
                discovery fetch resolve discovery_url's host via DNS. Used
                by callers (e.g. MultiIssuerTokenVerifier) that have already
                validated an untrusted host's resolved address and need the
                actual connection pinned to it, closing the window between
                that validation and the request.

        Returns:
            A configured TokenVerifier instance.

        Raises:
            TokenVerificationError: If discovery metadata cannot be fetched.
        """

        def _fetch_metadata() -> Dict[str, Any]:
            if pinned_ip:
                return _fetch_json_pinned(discovery_url, pinned_ip)
            with urlopen(discovery_url) as response:  # nosec B310
                result: Dict[str, Any] = json.loads(response.read())
                return result

        try:
            metadata = await asyncio.to_thread(_fetch_metadata)
            jwks_uri = metadata["jwks_uri"]
        except Exception as e:
            raise TokenVerificationError(
                f"Failed to fetch OIDC discovery metadata from {discovery_url}: {e}"
            ) from e

        return cls(
            jwks_uri=jwks_uri,
            audience=audience,
            issuer=issuer or metadata.get("issuer"),
            algorithms=algorithms,
        )
