"""Tests for the NormalizationManager."""

from typing import Any, Dict

from patient_matching.normalization.manager import NormalizationManager


class TestNormalizationManager:
    def setup_method(self) -> None:
        self.manager = NormalizationManager()

    def test_normalize_full_patient(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [
                {
                    "use": "official",
                    "family": "O'Brien-García",
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

        result = self.manager.normalize(patient)

        assert result["resourceType"] == "Patient"

        # Names: diacritics folded, punctuation removed, lowercase
        name = result["name"][0]
        assert name["family"] == "obriengarcia"
        assert name["given"][0] == "maria"
        assert name["given"][1] == "elena"
        assert name["suffix"] == ["jr"]

        # Date preserved as-is
        assert result["birthDate"] == "1990-01-15"

        # Gender passed through
        assert result["gender"] == "female"

        # Phone normalized to E.164
        phones = [t for t in result["telecom"] if t["system"] == "phone"]
        assert phones[0]["value"] == "+15035551234"

        # Email lowercased
        emails = [t for t in result["telecom"] if t["system"] == "email"]
        assert emails[0]["value"] == "maria@gmail.com"

        # Address normalized
        assert len(result["address"]) == 1

        # SSN kept (valid)
        assert len(result["identifier"]) == 1

    def test_normalize_strips_placeholders(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Doe", "given": ["Baby Boy"]}],
            "birthDate": "1800-01-01",
            "telecom": [
                {"system": "phone", "value": "0000000000"},
            ],
            "address": [
                {"line": ["Unknown"], "city": "X", "state": "Y"},
            ],
            "identifier": [
                {
                    "system": "http://hl7.org/fhir/sid/us-ssn",
                    "value": "000-00-0000",
                }
            ],
        }

        result = self.manager.normalize(patient)

        assert "name" not in result
        assert "birthDate" not in result
        assert "telecom" not in result
        assert "address" not in result
        assert "identifier" not in result

    def test_normalize_batch(self) -> None:
        patients = [
            {
                "resourceType": "Patient",
                "name": [{"family": "Smith", "given": ["John"]}],
                "birthDate": "1985-03-20",
            },
            {
                "resourceType": "Patient",
                "name": [{"family": "García", "given": ["María"]}],
                "birthDate": "1990-07-04",
            },
        ]

        results = self.manager.normalize_batch(patients)

        assert len(results) == 2
        assert results[0]["name"][0]["family"] == "smith"
        assert results[1]["name"][0]["family"] == "garcia"

    def test_normalize_does_not_mutate_original(self) -> None:
        patient: Dict[str, Any] = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1990-01-01",
        }
        original_family = patient["name"][0]["family"]

        self.manager.normalize(patient)

        assert patient["name"][0]["family"] == original_family

    def test_normalize_preserves_historical_names(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [
                {"use": "official", "family": "Johnson", "given": ["Sarah"]},
                {"use": "old", "family": "Williams", "given": ["Sarah"]},
                {"use": "old", "family": "Davis", "given": ["Sarah"]},
            ],
        }

        result = self.manager.normalize(patient)

        assert len(result["name"]) == 3
        assert result["name"][0]["use"] == "official"
        assert result["name"][1]["use"] == "old"
        assert result["name"][2]["use"] == "old"

    def test_normalize_partial_date_preserved(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1990-06",
        }

        result = self.manager.normalize(patient)
        assert result["birthDate"] == "1990-06"

    def test_normalize_year_only_preserved(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "birthDate": "1990",
        }

        result = self.manager.normalize(patient)
        assert result["birthDate"] == "1990"

    def test_suffixes_conflict(self) -> None:
        assert self.manager.suffixes_conflict("Jr", "Sr")
        assert self.manager.suffixes_conflict("II", "III")
        assert not self.manager.suffixes_conflict("Jr", "Junior")
        assert not self.manager.suffixes_conflict("Jr", "")
        assert not self.manager.suffixes_conflict("", "")

    def test_get_nicknames(self) -> None:
        nicks = self.manager.get_nicknames("William")
        assert len(nicks) > 0
        assert "bill" in nicks or "will" in nicks

    def test_table_versions_available(self) -> None:
        assert self.manager.placeholder_table_version
        assert self.manager.nickname_table_version
        assert self.manager.suffix_table_version

    def test_normalize_multiple_phones_all_types(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "telecom": [
                {"system": "phone", "value": "+15035551234", "use": "home"},
                {"system": "phone", "value": "+15035554321", "use": "work"},
                {"system": "phone", "value": "+15035559876", "use": "mobile"},
            ],
        }

        result = self.manager.normalize(patient)

        # C.4: all phone types preserved, all normalized
        assert len(result["telecom"]) == 3
        for t in result["telecom"]:
            assert t["value"].startswith("+1")

    def test_normalize_address_type_irrelevant_for_matching(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["John"]}],
            "address": [
                {
                    "use": "home",
                    "type": "physical",
                    "line": ["100 Broadway"],
                    "city": "New York",
                    "state": "NY",
                    "postalCode": "10001",
                },
                {
                    "use": "work",
                    "type": "postal",
                    "line": ["200 Park Ave"],
                    "city": "New York",
                    "state": "NY",
                    "postalCode": "10002",
                },
            ],
        }

        result = self.manager.normalize(patient)

        # C.2: both address types present, type preserved but
        # matching should ignore type
        assert len(result["address"]) == 2

    def test_normalize_nicknames_attached(self) -> None:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["Robert"]}],
        }

        result = self.manager.normalize(patient)

        nicks = result["name"][0].get("_nicknames", [])
        assert len(nicks) > 0
        assert "bob" in nicks or "rob" in nicks

    def test_normalize_null_identifier_list_does_not_raise(self) -> None:
        """`"identifier" in result` is true even when the value is `null` --
        caught via a live run against `bronze.fhir_lake.patient_4_0_0`."""
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Smith", "given": ["Robert"]}],
            "identifier": None,
        }
        result = self.manager.normalize(patient)
        assert "identifier" not in result
