"""Tests for IAL2 claims model and alias resolution."""

from patient_matching.ial2_extraction.claims_model import (
    IAL2Claims,
)


class TestIAL2ClaimsFromTokenClaims:
    def test_basic_required_fields(self) -> None:
        raw = {
            "iss": "https://idp.example.com",
            "sub": "user-123",
            "aud": "my-client",
            "exp": 1700000000,
            "iat": 1699999000,
            "jti": "token-abc",
            "name_first": "Jane",
            "name_last": "Doe",
            "birth_date": "1990-01-15",
        }
        claims = IAL2Claims.from_token_claims(raw)

        assert claims.iss == "https://idp.example.com"
        assert claims.sub == "user-123"
        assert claims.name_first == "Jane"
        assert claims.name_last == "Doe"
        assert claims.birth_date == "1990-01-15"

    def test_alias_given_name(self) -> None:
        raw = {
            "iss": "https://login.gov",
            "sub": "u1",
            "aud": "c1",
            "exp": 0,
            "iat": 0,
            "jti": "j1",
            "given_name": "Alice",
            "last_name": "Smith",
            "date_birth": "1985-06-01",
            "middle_name": "Marie",
        }
        claims = IAL2Claims.from_token_claims(raw)

        assert claims.name_first == "Alice"
        assert claims.name_last == "Smith"
        assert claims.name_middle == "Marie"
        assert claims.birth_date == "1985-06-01"

    def test_address_extraction(self) -> None:
        raw = {
            "iss": "",
            "sub": "",
            "aud": "",
            "exp": 0,
            "iat": 0,
            "jti": "",
            "name_first": "Bob",
            "name_last": "Jones",
            "birth_date": "2000-01-01",
            "address_line1": "123 Main St",
            "address_line2": "Apt 4B",
            "city": "Springfield",
            "state": "IL",
            "postal_code": "62704",
            "country": "US",
        }
        claims = IAL2Claims.from_token_claims(raw)

        assert claims.address is not None
        assert claims.address.address_line1 == "123 Main St"
        assert claims.address.address_line2 == "Apt 4B"
        assert claims.address.city == "Springfield"
        assert claims.address.state == "IL"
        assert claims.address.postal_code == "62704"
        assert claims.address.country == "US"

    def test_address_aliases(self) -> None:
        raw = {
            "iss": "",
            "sub": "",
            "aud": "",
            "exp": 0,
            "iat": 0,
            "jti": "",
            "name_first": "X",
            "name_last": "Y",
            "birth_date": "",
            "street_address": "456 Oak Ave",
            "locality": "Portland",
            "region": "OR",
            "code_postal": "97201",
            "formatted": "456 Oak Ave, Portland, OR 97201",
        }
        claims = IAL2Claims.from_token_claims(raw)

        assert claims.address is not None
        assert claims.address.address_line1 == "456 Oak Ave"
        assert claims.address.city == "Portland"
        assert claims.address.state == "OR"
        assert claims.address.postal_code == "97201"
        assert claims.address.full_address == "456 Oak Ave, Portland, OR 97201"

    def test_historical_addresses(self) -> None:
        raw = {
            "iss": "",
            "sub": "",
            "aud": "",
            "exp": 0,
            "iat": 0,
            "jti": "",
            "name_first": "X",
            "name_last": "Y",
            "birth_date": "",
            "address_historical": [
                {"street_address": "789 Elm St", "locality": "Salem", "region": "OR"},
            ],
        }
        claims = IAL2Claims.from_token_claims(raw)

        assert claims.address_historical is not None
        assert len(claims.address_historical) == 1
        assert claims.address_historical[0].address_line1 == "789 Elm St"
        assert claims.address_historical[0].city == "Salem"

    def test_optional_fields(self) -> None:
        raw = {
            "iss": "https://clear.me",
            "sub": "u1",
            "aud": "c1",
            "exp": 0,
            "iat": 0,
            "jti": "j1",
            "name_first": "A",
            "name_last": "B",
            "birth_date": "1990-01-01",
            "sex_legal": "female",
            "suffix": "Jr",
            "email": "a@example.com",
            "phone_number": "+15551234567",
            "ssn": "123-45-6789",
            "UUID": "csp-uuid-001",
            "name_historical": ["Alice Maiden"],
            "legal_id": {
                "issuer": "State of Oregon",
                "type": "drivers_license",
                "identifier": "DL12345",
            },
        }
        claims = IAL2Claims.from_token_claims(raw)

        assert claims.sex_legal == "female"
        assert claims.suffix == "Jr"
        assert claims.email == "a@example.com"
        assert claims.phone_number == "+15551234567"
        assert claims.ssn == "123-45-6789"
        assert claims.uuid == "csp-uuid-001"
        assert claims.name_historical == ["Alice Maiden"]
        assert claims.legal_id is not None
        assert claims.legal_id.issuer == "State of Oregon"
        assert claims.legal_id.id_type == "drivers_license"
        assert claims.legal_id.identifier == "DL12345"

    def test_no_address_when_empty(self) -> None:
        raw = {
            "iss": "",
            "sub": "",
            "aud": "",
            "exp": 0,
            "iat": 0,
            "jti": "",
            "name_first": "X",
            "name_last": "Y",
            "birth_date": "",
        }
        claims = IAL2Claims.from_token_claims(raw)
        assert claims.address is None
