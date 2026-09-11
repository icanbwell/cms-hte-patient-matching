"""Tests for MultiIssuerTokenVerifier."""

import socket
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import jwt
import pytest

from patient_matching.ial2_extraction.multi_issuer_verifier import (
    ALLOWED_JWKS_URLS_ENV_VAR,
    MultiIssuerTokenVerifier,
)
from patient_matching.ial2_extraction.token_verifier import (
    TokenVerificationError,
    TokenVerifier,
)

_PUBLIC_IP = "93.184.216.34"  # example.com's real address; just needs to be public


def _make_token(iss: str) -> str:
    return jwt.encode(
        {"iss": iss, "sub": "u1"},
        key="unused-test-signing-key-32-bytes-min",
        algorithm="HS256",
    )


def _fake_discovered_verifier(jwks_uri: str, claims: Dict[str, Any]) -> TokenVerifier:
    """A TokenVerifier standing in for one built via from_oidc_discovery,
    with its actual signature-verifying .verify() replaced so tests don't
    need a real JWKS endpoint."""
    verifier = TokenVerifier(jwks_uri=jwks_uri, audience="my-client-id")
    verifier.verify = AsyncMock(return_value=claims)  # type: ignore[method-assign]
    return verifier


@pytest.fixture
def mock_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every hostname to a public IP, so issuer-validation tests
    for the accept path don't depend on real DNS."""

    def _fake_getaddrinfo(host: str, *args: Any, **kwargs: Any) -> Any:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_IP, 0))]

    monkeypatch.setattr(
        "patient_matching.ial2_extraction.multi_issuer_verifier.socket.getaddrinfo",
        _fake_getaddrinfo,
    )


class TestMultiIssuerTokenVerifier:
    async def test_accepts_whitelisted_issuer(self, mock_public_dns: None) -> None:
        token = _make_token("https://good.example.com")
        expected_claims = {"iss": "https://good.example.com", "sub": "u1"}
        fake_verifier = _fake_discovered_verifier(
            "https://good.example.com/jwks.json", expected_claims
        )

        discovery_mock = AsyncMock(return_value=fake_verifier)
        with patch.object(TokenVerifier, "from_oidc_discovery", discovery_mock):
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            claims = await verifier.verify(token)

        assert claims == expected_claims
        assert discovery_mock.call_args.kwargs["pinned_ip"] == _PUBLIC_IP

    async def test_rejects_non_whitelisted_issuer(self, mock_public_dns: None) -> None:
        token = _make_token("https://untrusted.example.com")
        fake_verifier = _fake_discovered_verifier(
            "https://untrusted.example.com/jwks.json", {}
        )

        with patch.object(
            TokenVerifier,
            "from_oidc_discovery",
            AsyncMock(return_value=fake_verifier),
        ):
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )

            with pytest.raises(TokenVerificationError, match="not whitelisted"):
                await verifier.verify(token)

        fake_verifier.verify.assert_not_called()  # type: ignore[attr-defined]

    async def test_caches_verifier_per_issuer(self, mock_public_dns: None) -> None:
        token = _make_token("https://good.example.com")
        fake_verifier = _fake_discovered_verifier(
            "https://good.example.com/jwks.json", {"iss": "https://good.example.com"}
        )
        discovery_mock = AsyncMock(return_value=fake_verifier)

        with patch.object(TokenVerifier, "from_oidc_discovery", discovery_mock):
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            await verifier.verify(token)
            await verifier.verify(token)

        assert discovery_mock.call_count == 1

    async def test_missing_iss_claim_rejected(self) -> None:
        token = jwt.encode(
            {"sub": "u1"},
            key="unused-test-signing-key-32-bytes-min",
            algorithm="HS256",
        )

        with patch.object(
            TokenVerifier, "from_oidc_discovery", AsyncMock()
        ) as discovery_mock:
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )

            with pytest.raises(TokenVerificationError, match="iss"):
                await verifier.verify(token)

        discovery_mock.assert_not_called()

    async def test_malformed_token_rejected(self) -> None:
        verifier = MultiIssuerTokenVerifier(
            audience="my-client-id",
            allowed_jwks_uris=["https://good.example.com/jwks.json"],
        )

        with pytest.raises(TokenVerificationError, match="Could not parse token"):
            await verifier.verify("not-a-jwt")

    def test_from_env_raises_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ALLOWED_JWKS_URLS_ENV_VAR, raising=False)

        with pytest.raises(ValueError, match=ALLOWED_JWKS_URLS_ENV_VAR):
            MultiIssuerTokenVerifier.from_env(audience="my-client-id")

    async def test_from_env_supports_multiple_comma_separated_urls(
        self, monkeypatch: pytest.MonkeyPatch, mock_public_dns: None
    ) -> None:
        monkeypatch.setenv(
            ALLOWED_JWKS_URLS_ENV_VAR,
            " https://a.example.com/jwks.json, https://b.example.com/jwks.json ",
        )
        token = _make_token("https://b.example.com")
        fake_verifier = _fake_discovered_verifier(
            "https://b.example.com/jwks.json", {"iss": "https://b.example.com"}
        )

        with patch.object(
            TokenVerifier,
            "from_oidc_discovery",
            AsyncMock(return_value=fake_verifier),
        ):
            verifier = MultiIssuerTokenVerifier.from_env(audience="my-client-id")
            claims = await verifier.verify(token)

        assert claims == {"iss": "https://b.example.com"}


class TestIssuerUrlSsrfProtection:
    """The `iss` claim is read before signature verification, purely to pick
    a JWKS URL -- so it's attacker-controlled input reaching a server-side
    HTTP request (OIDC discovery). These lock in that unrecognized/internal
    targets are rejected before any such request is made."""

    async def test_rejects_non_https_issuer(self) -> None:
        token = _make_token("http://good.example.com")

        with patch.object(
            TokenVerifier, "from_oidc_discovery", AsyncMock()
        ) as discovery_mock:
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            with pytest.raises(TokenVerificationError, match="https"):
                await verifier.verify(token)

        discovery_mock.assert_not_called()

    async def test_rejects_issuer_with_literal_link_local_ip(self) -> None:
        """169.254.169.254 is the AWS/GCP/Azure cloud metadata endpoint."""
        token = _make_token("https://169.254.169.254")

        with patch.object(
            TokenVerifier, "from_oidc_discovery", AsyncMock()
        ) as discovery_mock:
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            with pytest.raises(TokenVerificationError, match="non-public address"):
                await verifier.verify(token)

        discovery_mock.assert_not_called()

    async def test_rejects_issuer_with_literal_loopback_ip(self) -> None:
        token = _make_token("https://127.0.0.1")

        with patch.object(
            TokenVerifier, "from_oidc_discovery", AsyncMock()
        ) as discovery_mock:
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            with pytest.raises(TokenVerificationError, match="non-public address"):
                await verifier.verify(token)

        discovery_mock.assert_not_called()

    async def test_rejects_issuer_hostname_resolving_to_private_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guards against DNS rebinding: a hostname that looks external but
        resolves to an internal address must still be rejected."""

        def _fake_getaddrinfo(host: str, *args: Any, **kwargs: Any) -> Any:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]

        monkeypatch.setattr(
            "patient_matching.ial2_extraction.multi_issuer_verifier.socket.getaddrinfo",
            _fake_getaddrinfo,
        )
        token = _make_token("https://looks-external.example.com")

        with patch.object(
            TokenVerifier, "from_oidc_discovery", AsyncMock()
        ) as discovery_mock:
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            with pytest.raises(TokenVerificationError, match="non-public address"):
                await verifier.verify(token)

        discovery_mock.assert_not_called()

    async def test_rejects_issuer_hostname_that_fails_to_resolve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise_gaierror(host: str, *args: Any, **kwargs: Any) -> Any:
            raise socket.gaierror("nodename nor servname provided")

        monkeypatch.setattr(
            "patient_matching.ial2_extraction.multi_issuer_verifier.socket.getaddrinfo",
            _raise_gaierror,
        )
        token = _make_token("https://does-not-resolve.example.com")

        with patch.object(
            TokenVerifier, "from_oidc_discovery", AsyncMock()
        ) as discovery_mock:
            verifier = MultiIssuerTokenVerifier(
                audience="my-client-id",
                allowed_jwks_uris=["https://good.example.com/jwks.json"],
            )
            with pytest.raises(TokenVerificationError, match="Could not resolve"):
                await verifier.verify(token)

        discovery_mock.assert_not_called()
