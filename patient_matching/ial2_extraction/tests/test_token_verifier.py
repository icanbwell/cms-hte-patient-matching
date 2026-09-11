"""Tests for TokenVerifier's pinned-connection OIDC discovery fetch.

Covers only the pinned_ip path added to close a DNS-rebinding TOCTOU gap
in MultiIssuerTokenVerifier's issuer-driven discovery -- not full
TokenVerifier coverage.
"""

from unittest.mock import MagicMock, patch

from patient_matching.ial2_extraction.token_verifier import _PinnedHTTPSConnection


class TestPinnedHTTPSConnection:
    def test_connects_to_pinned_ip_with_original_hostname_as_sni(self) -> None:
        """The TCP connection must go to the pinned IP (not a fresh DNS
        lookup of the hostname), while TLS SNI and certificate verification
        must still use the original hostname -- otherwise cert validation
        would fail, or worse, silently validate against the wrong host."""
        fake_raw_sock = MagicMock(name="raw_socket")
        fake_wrapped_sock = MagicMock(name="tls_socket")

        with patch(
            "patient_matching.ial2_extraction.token_verifier.socket.create_connection",
            return_value=fake_raw_sock,
        ) as create_conn_mock:
            conn = _PinnedHTTPSConnection(
                "issuer.example.com", "203.0.113.5", timeout=5
            )
            conn._context = MagicMock(name="ssl_context")
            conn._context.wrap_socket.return_value = fake_wrapped_sock

            conn.connect()

        create_conn_mock.assert_called_once_with(
            ("203.0.113.5", 443), 5, conn.source_address
        )
        conn._context.wrap_socket.assert_called_once_with(
            fake_raw_sock, server_hostname="issuer.example.com"
        )
        assert conn.sock is fake_wrapped_sock
