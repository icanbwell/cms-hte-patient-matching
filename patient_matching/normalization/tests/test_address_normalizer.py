"""Tests for address normalization."""

from patient_matching.normalization.address_normalizer import AddressNormalizer


class TestAddressNormalizer:
    def setup_method(self) -> None:
        self.normalizer = AddressNormalizer()

    def test_basic_address_normalization(self) -> None:
        patient = {
            "address": [
                {
                    "use": "home",
                    "line": ["123 Main Street", "Apt 4B"],
                    "city": "Springfield",
                    "state": "IL",
                    "postalCode": "62704",
                    "country": "US",
                }
            ]
        }
        result = self.normalizer.normalize_patient_addresses(patient)

        assert len(result) == 1
        addr = result[0]
        assert addr["use"] == "home"
        assert "line" in addr
        assert addr["city"] is not None
        assert addr["postalCode"] == "62704"

    def test_postal_code_normalization(self) -> None:
        patient = {
            "address": [
                {
                    "line": ["123 Main St"],
                    "city": "Portland",
                    "state": "OR",
                    "postalCode": "972011234",
                }
            ]
        }
        result = self.normalizer.normalize_patient_addresses(patient)
        assert result[0]["postalCode"] == "97201-1234"

    def test_five_digit_zip_preserved(self) -> None:
        patient = {
            "address": [
                {
                    "line": ["456 Oak Ave"],
                    "city": "Salem",
                    "state": "OR",
                    "postalCode": "97301",
                }
            ]
        }
        result = self.normalizer.normalize_patient_addresses(patient)
        assert result[0]["postalCode"] == "97301"

    def test_placeholder_address_filtered(self) -> None:
        patient = {
            "address": [
                {
                    "line": ["Unknown"],
                    "city": "Springfield",
                    "state": "IL",
                },
                {
                    "line": ["123 Main St"],
                    "city": "Springfield",
                    "state": "IL",
                },
            ]
        }
        result = self.normalizer.normalize_patient_addresses(patient)
        assert len(result) == 1

    def test_homeless_address_filtered(self) -> None:
        patient = {
            "address": [{"line": ["Homeless"], "city": "Portland", "state": "OR"}]
        }
        result = self.normalizer.normalize_patient_addresses(patient)
        assert len(result) == 0

    def test_address_type_preserved(self) -> None:
        patient = {
            "address": [
                {
                    "use": "home",
                    "type": "physical",
                    "line": ["789 Elm St"],
                    "city": "Portland",
                    "state": "OR",
                    "postalCode": "97201",
                }
            ]
        }
        result = self.normalizer.normalize_patient_addresses(patient)

        # C.2: type is preserved but won't affect matching
        assert result[0]["type"] == "physical"
        assert result[0]["use"] == "home"

    def test_empty_addresses(self) -> None:
        assert self.normalizer.normalize_patient_addresses({}) == []
        assert self.normalizer.normalize_patient_addresses({"address": []}) == []

    def test_city_state_normalized(self) -> None:
        patient = {
            "address": [
                {
                    "line": ["100 Broadway"],
                    "city": "  New  York  ",
                    "state": "  NY  ",
                    "postalCode": "10001",
                }
            ]
        }
        result = self.normalizer.normalize_patient_addresses(patient)
        assert result[0]["city"] == "new york"
        assert result[0]["state"] == "ny"
