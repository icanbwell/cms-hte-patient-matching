"""Tests for the PatientNormalizer orchestrator."""

from patient_matching.normalization.normalizer import PatientNormalizer


class TestPatientNormalizer:
    def setup_method(self) -> None:
        self.normalizer = PatientNormalizer()

    def test_full_patient_normalization(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [
                {
                    "use": "official",
                    "family": "García-López",
                    "given": ["María", "Elena"],
                    "suffix": ["Junior"],
                }
            ],
            "birthDate": "1990-01-15",
            "gender": "female",
            "telecom": [
                {"system": "phone", "value": "(503) 555-1234", "use": "home"},
                {"system": "email", "value": "Maria@Gmail.COM"},
            ],
            "address": [
                {
                    "use": "home",
                    "line": ["123 Main Street"],
                    "city": "Springfield",
                    "state": "IL",
                    "postalCode": "62704",
                    "country": "US",
                }
            ],
            "identifier": [
                {
                    "system": "http://hl7.org/fhir/sid/us-ssn",
                    "value": "123-45-6789",
                }
            ],
        }

        result = self.normalizer.normalize(patient)

        assert result["resourceType"] == "Patient"

        # Name normalized
        name = result["name"][0]
        assert name["family"] == "garcialopez"
        assert name["given"][0] == "maria"
        assert name["suffix"] == ["jr"]

        # Date preserved
        assert result["birthDate"] == "1990-01-15"

        # Gender untouched
        assert result["gender"] == "female"

        # Phone E.164
        phones = [t for t in result["telecom"] if t["system"] == "phone"]
        assert phones[0]["value"] == "+15035551234"

        # Email lowercased
        emails = [t for t in result["telecom"] if t["system"] == "email"]
        assert emails[0]["value"] == "maria@gmail.com"

        # Address present
        assert len(result["address"]) == 1
        assert result["address"][0]["postalCode"] == "62704"

        # SSN preserved (not a placeholder)
        assert len(result["identifier"]) == 1

    def test_placeholder_ssn_removed(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1990-01-01",
            "identifier": [
                {
                    "system": "http://hl7.org/fhir/sid/us-ssn",
                    "value": "000-00-0000",
                }
            ],
        }
        result = self.normalizer.normalize(patient)
        assert "identifier" not in result

    def test_placeholder_birth_date_removed(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1800-01-01",
        }
        result = self.normalizer.normalize(patient)
        assert "birthDate" not in result

    def test_placeholder_names_removed(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Doe", "given": ["Baby Boy"]}],
            "birthDate": "2024-01-01",
        }
        result = self.normalizer.normalize(patient)
        assert "name" not in result

    def test_original_not_mutated(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1990-01-01",
        }
        original_family = patient["name"][0]["family"]
        self.normalizer.normalize(patient)

        # Original should be unchanged
        assert patient["name"][0]["family"] == original_family

    def test_partial_date_preserved(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1990-01",
        }
        result = self.normalizer.normalize(patient)
        assert result["birthDate"] == "1990-01"

    def test_historical_names_kept(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [
                {"use": "official", "family": "Johnson", "given": ["Sarah"]},
                {"use": "old", "family": "Williams", "given": ["Sarah"]},
            ],
        }
        result = self.normalizer.normalize(patient)
        assert len(result["name"]) == 2
        assert result["name"][1]["use"] == "old"

    def test_empty_patient(self) -> None:
        patient = {"resourceType": "Patient"}
        result = self.normalizer.normalize(patient)
        assert result["resourceType"] == "Patient"

    def test_general_placeholder_identifier_removed(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "identifier": [
                {
                    "system": "http://example.com",
                    "value": "unknown",
                }
            ],
        }
        result = self.normalizer.normalize(patient)
        assert "identifier" not in result
