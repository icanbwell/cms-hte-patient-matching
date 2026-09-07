"""Tests for the IAL2Extractor orchestrator."""

import time
from unittest.mock import MagicMock

import pytest

from patient_matching.ial2_extraction.ial2_extractor import IAL2Extractor
from patient_matching.ial2_extraction.token_verifier import (
    TokenVerifier,
    TokenVerificationError,
)


class TestIAL2ExtractorWithMockedVerifier:
    async def test_extract_returns_fhir_patient(self) -> None:
        mock_verifier = MagicMock(spec=TokenVerifier)
        mock_verifier.verify.return_value = {
            "iss": "https://idp.example.com",
            "sub": "user-123",
            "aud": "my-client",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "jti": "token-abc",
            "name_first": "Jane",
            "name_last": "Doe",
            "birth_date": "1990-01-15",
            "email": "jane@example.com",
            "phone_number": "+15551234567",
            "city": "Springfield",
            "state": "IL",
            "postal_code": "62704",
            "address_line1": "123 Main St",
            "UUID": "csp-uuid-001",
        }

        extractor = IAL2Extractor(verifier=mock_verifier)
        patient = await extractor.extract("fake-token")

        assert patient["resourceType"] == "Patient"
        assert patient["birthDate"] == "1990-01-15"
        assert patient["name"][0]["family"] == "Doe"
        assert patient["name"][0]["given"] == ["Jane"]
        assert any(t["value"] == "jane@example.com" for t in patient["telecom"])
        assert patient["address"][0]["city"] == "Springfield"
        assert patient["identifier"][0]["value"] == "csp-uuid-001"

    async def test_extract_claims_returns_ial2_claims(self) -> None:
        mock_verifier = MagicMock(spec=TokenVerifier)
        mock_verifier.verify.return_value = {
            "iss": "https://login.gov",
            "sub": "u2",
            "aud": "c2",
            "exp": 0,
            "iat": 0,
            "jti": "j2",
            "given_name": "Alice",
            "last_name": "Smith",
            "date_birth": "1985-06-01",
        }

        extractor = IAL2Extractor(verifier=mock_verifier)
        claims = await extractor.extract_claims("fake-token")

        assert claims.name_first == "Alice"
        assert claims.name_last == "Smith"
        assert claims.birth_date == "1985-06-01"

    async def test_extract_propagates_verification_error(self) -> None:
        mock_verifier = MagicMock(spec=TokenVerifier)
        mock_verifier.verify.side_effect = TokenVerificationError("Token expired")

        extractor = IAL2Extractor(verifier=mock_verifier)

        with pytest.raises(TokenVerificationError, match="Token expired"):
            await extractor.extract("bad-token")
