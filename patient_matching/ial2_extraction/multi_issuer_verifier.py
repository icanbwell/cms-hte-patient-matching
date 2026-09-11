"""Multi-issuer JWT verification restricted to a whitelist of JWKS URLs.

Resolves an incoming token's issuer via OIDC discovery, then only proceeds
with signature verification if the discovered JWKS URL is on an explicit
allow list -- an unrecognized issuer is rejected before any signing key is
fetched.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import jwt

from .token_verifier import TokenVerificationError, TokenVerifier

_IpAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

ALLOWED_JWKS_URLS_ENV_VAR = "IAL2_ALLOWED_JWKS_URLS"


class MultiIssuerTokenVerifier:
    """Verifies IAL2 JWTs from any issuer whose JWKS URL is whitelisted.

    Unlike TokenVerifier, which is pinned to a single jwks_uri, this class
    accepts tokens from multiple issuers by resolving each token's issuer
    via OIDC discovery and checking the discovered JWKS URL against an
    explicit allow list before trusting it.

    Args:
        audience: Expected ``aud`` claim value, applied to every issuer.
        allowed_jwks_uris: JWKS URLs this instance will trust.
        algorithms: Allowed signing algorithms. Defaults to RS256.

    Example::

        verifier = MultiIssuerTokenVerifier.from_env(audience="my-client-id")
        claims = await verifier.verify(token_string)
    """

    def __init__(
        self,
        *,
        audience: str,
        allowed_jwks_uris: List[str],
        algorithms: Optional[List[str]] = None,
    ) -> None:
        self._audience = audience
        self._allowed_jwks_uris = set(allowed_jwks_uris)
        self._algorithms = algorithms
        self._verifiers_by_issuer: Dict[str, TokenVerifier] = {}

    @classmethod
    def from_env(
        cls,
        *,
        audience: str,
        env_var: str = ALLOWED_JWKS_URLS_ENV_VAR,
        algorithms: Optional[List[str]] = None,
    ) -> MultiIssuerTokenVerifier:
        """Build the verifier from a comma-separated env var of JWKS URLs.

        Args:
            audience: Expected ``aud`` claim value.
            env_var: Name of the env var holding the whitelist.
            algorithms: Allowed signing algorithms.

        Raises:
            ValueError: If the env var is unset or contains no URLs.
        """
        raw = os.environ.get(env_var, "")
        allowed = [url.strip() for url in raw.split(",") if url.strip()]
        if not allowed:
            raise ValueError(f"{env_var} is not set or contains no JWKS URLs")
        return cls(audience=audience, allowed_jwks_uris=allowed, algorithms=algorithms)

    async def verify(self, token: str) -> Dict[str, Any]:
        """Verify a token from any whitelisted issuer.

        Args:
            token: The encoded JWT string.

        Returns:
            The decoded claims dictionary.

        Raises:
            TokenVerificationError: If the issuer's JWKS URL isn't
                whitelisted, or the token fails verification.
        """
        issuer = self._peek_issuer(token)

        verifier = self._verifiers_by_issuer.get(issuer)
        if verifier is None:
            verifier = await self._build_verifier_for_issuer(issuer)
            self._verifiers_by_issuer[issuer] = verifier

        return await verifier.verify(token)

    @staticmethod
    def _peek_issuer(token: str) -> str:
        """Read the ``iss`` claim without verifying the signature.

        This claim is untrusted at this point -- it is only used to select
        which JWKS URL to check against the whitelist, never to make a
        trust decision on its own. The real verification happens in
        TokenVerifier.verify() once the whitelist check passes.
        """
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.InvalidTokenError as e:
            raise TokenVerificationError(f"Could not parse token: {e}") from e

        issuer = unverified.get("iss")
        if not issuer:
            raise TokenVerificationError("Token is missing the 'iss' claim")
        return str(issuer)

    async def _build_verifier_for_issuer(self, issuer: str) -> TokenVerifier:
        """Discover the issuer's JWKS URL and check it against the whitelist."""
        pinned_ip = await self._validate_issuer_url(issuer)

        verifier = await TokenVerifier.from_oidc_discovery(
            discovery_url=f"{issuer.rstrip('/')}/.well-known/openid-configuration",
            audience=self._audience,
            issuer=issuer,
            algorithms=self._algorithms,
            pinned_ip=pinned_ip,
        )
        if verifier.jwks_uri not in self._allowed_jwks_uris:
            raise TokenVerificationError(
                f"Issuer '{issuer}' resolved to JWKS URL "
                f"'{verifier.jwks_uri}', which is not whitelisted"
            )
        return verifier

    @staticmethod
    async def _validate_issuer_url(issuer: str) -> str:
        """Reject issuer URLs that could be used for SSRF before any
        discovery or JWKS request is made, and return the validated IP to
        pin the actual discovery connection to.

        The issuer claim is unverified at this point -- read via
        _peek_issuer() before signature verification, purely to select a
        JWKS URL. Without this check, an attacker could set 'iss' to an
        internal service or cloud metadata endpoint and have this process
        make a request to it during OIDC discovery. Returning the validated
        IP (rather than just validating and discarding it) lets the caller
        pin the actual connection to it, closing the DNS-rebinding window
        between this check and the request.
        """
        parsed = urlparse(issuer)
        if parsed.scheme != "https":
            raise TokenVerificationError(f"Issuer URL must use https, got: {issuer!r}")

        hostname = parsed.hostname
        if not hostname:
            raise TokenVerificationError(f"Issuer URL is missing a host: {issuer!r}")

        addresses = await MultiIssuerTokenVerifier._resolve_addresses(hostname)
        for address in addresses:
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise TokenVerificationError(
                    f"Issuer '{issuer}' resolves to a non-public address "
                    f"({address}); rejected"
                )
        return str(addresses[0])

    @staticmethod
    async def _resolve_addresses(hostname: str) -> List[_IpAddress]:
        """Resolve a hostname to the IP address(es) it points to.

        Guards against DNS rebinding: a hostname that looks external in
        text form can still resolve to an internal address.
        """
        try:
            return [ipaddress.ip_address(hostname)]
        except ValueError:
            pass

        try:
            infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        except socket.gaierror as e:
            raise TokenVerificationError(
                f"Could not resolve issuer host '{hostname}': {e}"
            ) from e
        return [ipaddress.ip_address(info[4][0]) for info in infos]
