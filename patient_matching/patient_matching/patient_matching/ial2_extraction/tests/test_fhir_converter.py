"""Tests for FHIR Patient resource conversion."""

from patient_matching.ial2_extraction.claims_model import (
    IAL2Address,
    IAL2Claims,
    IAL2LegalId,
)
from patient_matching.ial2_extraction.fhir_converter import IAL2ToFhirConverter


class TestIAL2ToFhirConverter:
    def setup_method(self) -> None:
        self.converter = IAL2ToFhirConverter()

    def test_minimal_patient(self) -> None:
        claims = IAL2Claims(
            iss="https://idp.example.com",
            sub="u1",
            aud="c1",
            name_first="Jane",
            name_last="Doe",
            birth_date="1990-01-15",
        )
        patient = self.converter.convert(claims)

        assert patient["resourceType"] == "Patient"
        assert patient["birthDate"] == "1990-01-15"
        assert len(patient["name"]) == 1
        assert patient["name"][0]["family"] == "Doe"
        assert patient["name"][0]["given"] == ["Jane"]
        assert patient["name"][0]["use"] == "official"

    def test_full_name_with_middle_and_suffix(self) -> None:
        claims = IAL2Claims(
            name_first="John",
            name_middle="Michael",
            name_last="Smith",
            suffix="III",
            name_full="John Michael Smith III",
            birth_date="1975-03-20",
        )
        patient = self.converter.convert(claims)

        name = patient["name"][0]
        assert name["given"] == ["John", "Michael"]
        assert name["family"] == "Smith"
        assert name["suffix"] == ["III"]
        assert name["text"] == "John Michael Smith III"

    def test_historical_names(self) -> None:
        claims = IAL2Claims(
            name_first="Jane",
            name_last="Doe",
            birth_date="1990-01-01",
            name_historical=["Jane Maiden", "Jane Previous"],
        )
        patient = self.converter.convert(claims)

        assert len(patient["name"]) == 3
        assert patient["name"][1]["use"] == "old"
        assert patient["name"][1]["text"] == "Jane Maiden"
        assert patient["name"][2]["use"] == "old"
        assert patient["name"][2]["text"] == "Jane Previous"

    def test_gender_mapping(self) -> None:
        for sex_input, expected in [
            ("male", "male"),
            ("Female", "female"),
            ("M", "male"),
            ("f", "female"),
            ("other", "other"),
            ("nonbinary", "unknown"),
        ]:
            claims = IAL2Claims(
                name_first="X",
                name_last="Y",
                birth_date="2000-01-01",
                sex_legal=sex_input,
            )
            patient = self.converter.convert(claims)
            assert patient["gender"] == expected, (
                f"Expected {expected} for input '{sex_input}'"
            )

    def test_telecoms(self) -> None:
        claims = IAL2Claims(
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
            email="user@example.com",
            phone_number="+15551234567",
            phone_number_historical=["+15559876543"],
        )
        patient = self.converter.convert(claims)

        assert len(patient["telecom"]) == 3
        assert patient["telecom"][0]["system"] == "email"
        assert patient["telecom"][0]["value"] == "user@example.com"
        assert patient["telecom"][1]["system"] == "phone"
        assert patient["telecom"][1]["value"] == "+15551234567"
        assert patient["telecom"][2]["system"] == "phone"
        assert patient["telecom"][2]["use"] == "old"

    def test_address(self) -> None:
        claims = IAL2Claims(
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
            address=IAL2Address(
                address_line1="123 Main St",
                address_line2="Apt 4B",
                city="Springfield",
                state="IL",
                postal_code="62704",
                country="US",
            ),
        )
        patient = self.converter.convert(claims)

        addr = patient["address"][0]
        assert addr["use"] == "home"
        assert addr["line"] == ["123 Main St", "Apt 4B"]
        assert addr["city"] == "Springfield"
        assert addr["state"] == "IL"
        assert addr["postalCode"] == "62704"
        assert addr["country"] == "US"

    def test_historical_address(self) -> None:
        claims = IAL2Claims(
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
            address_historical=[
                IAL2Address(
                    address_line1="456 Old Rd",
                    city="Portland",
                    state="OR",
                    postal_code="97201",
                ),
            ],
        )
        patient = self.converter.convert(claims)

        addr = patient["address"][0]
        assert addr["use"] == "old"
        assert addr["line"] == ["456 Old Rd"]
        assert addr["city"] == "Portland"

    def test_identifiers_uuid_and_ssn(self) -> None:
        claims = IAL2Claims(
            iss="https://idp.example.com",
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
            uuid="csp-uuid-001",
            ssn="123-45-6789",
        )
        patient = self.converter.convert(claims)

        ids = patient["identifier"]
        assert len(ids) == 2

        csp_id = ids[0]
        assert csp_id["system"] == "https://idp.example.com"
        assert csp_id["value"] == "csp-uuid-001"

        ssn_id = ids[1]
        assert ssn_id["system"] == "http://hl7.org/fhir/sid/us-ssn"
        assert ssn_id["value"] == "123-45-6789"

    def test_identifier_legal_id(self) -> None:
        claims = IAL2Claims(
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
            legal_id=IAL2LegalId(
                issuer="State of Oregon",
                id_type="drivers_license",
                identifier="DL12345",
            ),
        )
        patient = self.converter.convert(claims)

        lid = patient["identifier"][0]
        assert lid["value"] == "DL12345"
        assert lid["assigner"]["display"] == "State of Oregon"

    def test_no_gender_when_absent(self) -> None:
        claims = IAL2Claims(
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
        )
        patient = self.converter.convert(claims)
        assert "gender" not in patient

    def test_no_telecom_when_absent(self) -> None:
        claims = IAL2Claims(
            name_first="X",
            name_last="Y",
            birth_date="2000-01-01",
        )
        patient = self.converter.convert(claims)
        assert "telecom" not in patient
