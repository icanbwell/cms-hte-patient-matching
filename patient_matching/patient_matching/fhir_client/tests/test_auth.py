"""Tests for OAuth2 client credentials authentication."""

import time
from unittest.mock import MagicMock


from patient_matching.fhir_client.auth import (
    ClientCredentialsAuth,
    TokenResponse,
)


class TestTokenResponse:
    def test_is_expired_when_past(self):
        token = TokenResponse(access_token="tok", expires_at=time.time() - 60)
        assert token.is_expired is True

    def test_is_not_expired_when_future(self):
        token = TokenResponse(access_token="tok", expires_at=time.time() + 300)
        assert token.is_expired is False

    def test_is_expired_within_buffer(self):
        """Token expiring within 30s buffer should be considered expired."""
        token = TokenResponse(access_token="tok", expires_at=time.time() + 10)
        assert token.is_expired is True


class TestClientCredentialsAuth:
    def _make_auth(self) -> ClientCredentialsAuth:
        return ClientCredentialsAuth(
            token_url="https://auth.example.com/token",
            client_id="my-client",
            client_secret="my-secret",
            scope="system/*.read",
        )

    def test_get_access_token_requests_new(self):
        auth = self._make_auth()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        token = auth.get_access_token(mock_client)
        assert token == "new-token-123"
        mock_client.post.assert_called_once()

    def test_get_access_token_caches(self):
        auth = self._make_auth()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "cached-token",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        # First call requests a token
        token1 = auth.get_access_token(mock_client)
        # Second call should use cached token
        token2 = auth.get_access_token(mock_client)

        assert token1 == token2 == "cached-token"
        assert mock_client.post.call_count == 1

    def test_get_access_token_refreshes_expired(self):
        auth = self._make_auth()
        mock_client = MagicMock()

        # First response
        resp1 = MagicMock()
        resp1.json.return_value = {
            "access_token": "token-1",
            "expires_in": 0,  # Expires immediately
        }
        # Second response
        resp2 = MagicMock()
        resp2.json.return_value = {
            "access_token": "token-2",
            "expires_in": 3600,
        }
        mock_client.post.side_effect = [resp1, resp2]

        token1 = auth.get_access_token(mock_client)
        assert token1 == "token-1"

        # Should refresh because token is expired
        token2 = auth.get_access_token(mock_client)
        assert token2 == "token-2"
        assert mock_client.post.call_count == 2

    def test_invalidate_forces_refresh(self):
        auth = self._make_auth()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "token-a",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        auth.get_access_token(mock_client)
        auth.invalidate()
        auth.get_access_token(mock_client)

        assert mock_client.post.call_count == 2

    def test_post_includes_scope_and_grant_type(self):
        auth = self._make_auth()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "tok",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        auth.get_access_token(mock_client)

        call_args = mock_client.post.call_args
        data = call_args.kwargs.get("data") or call_args[1].get("data")
        assert data["grant_type"] == "client_credentials"
        assert data["client_id"] == "my-client"
        assert data["client_secret"] == "my-secret"
        assert data["scope"] == "system/*.read"

    def test_extra_params_included(self):
        auth = ClientCredentialsAuth(
            token_url="https://auth.example.com/token",
            client_id="c",
            client_secret="s",
            extra_params={"resource": "https://fhir.example.com"},
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "tok",
            "expires_in": 3600,
        }
        mock_client.post.return_value = mock_response

        auth.get_access_token(mock_client)

        call_args = mock_client.post.call_args
        data = call_args.kwargs.get("data") or call_args[1].get("data")
        assert data["resource"] == "https://fhir.example.com"
