"""OAuth2 client credentials authentication for FHIR servers.

Handles token acquisition and refresh for server-to-server OAuth2
flows commonly used by Epic, Cerner, and other FHIR server vendors.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TokenResponse:
    """Cached OAuth2 token with expiry tracking."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: float = 0.0
    scope: str = ""

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired (with 30s buffer)."""
        return time.time() >= (self.expires_at - 30)


class ClientCredentialsAuth:
    """OAuth2 client credentials flow for FHIR server authentication.

    Acquires and caches access tokens. Automatically refreshes when
    the token is expired.

    Args:
        token_url: The OAuth2 token endpoint URL.
        client_id: The client ID.
        client_secret: The client secret.
        scope: Optional space-separated scopes to request.
        extra_params: Additional parameters to include in the token
            request (e.g. ``{"resource": "https://fhir.example.com"}``).
    """

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "",
        extra_params: Optional[Dict[str, str]] = None,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._extra_params = extra_params or {}
        self._token: Optional[TokenResponse] = None

    async def get_access_token(self, client: httpx.AsyncClient) -> str:
        """Get a valid access token, refreshing if necessary.

        Args:
            client: An httpx.AsyncClient to use for the token request.

        Returns:
            A valid Bearer access token string.

        Raises:
            httpx.HTTPStatusError: If the token request fails.
        """
        if self._token is None or self._token.is_expired:
            self._token = await self._request_token(client)
        return self._token.access_token

    async def _request_token(self, client: httpx.AsyncClient) -> TokenResponse:
        """Request a new access token from the token endpoint."""
        data: Dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scope:
            data["scope"] = self._scope
        data.update(self._extra_params)

        logger.debug("Requesting OAuth2 token from %s", self._token_url)
        response = await client.post(self._token_url, data=data)
        response.raise_for_status()

        body = response.json()
        expires_in = int(body.get("expires_in", 3600))

        token = TokenResponse(
            access_token=body["access_token"],
            token_type=body.get("token_type", "Bearer"),
            expires_at=time.time() + expires_in,
            scope=body.get("scope", ""),
        )
        logger.debug(
            "Acquired token (expires in %ds, scope=%s)",
            expires_in,
            token.scope,
        )
        return token

    def invalidate(self) -> None:
        """Force token refresh on next call."""
        self._token = None
