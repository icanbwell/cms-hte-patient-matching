"""Tests for phone number normalization."""

import pytest

from patient_matching.normalization.phone_normalizer import PhoneNormalizer


class TestPhoneNormalizer:
    def setup_method(self) -> None:
        self.normalizer = PhoneNormalizer()

    def test_us_number_to_e164(self) -> None:
        assert self.normalizer.normalize_phone("(503) 555-1234") == "+15035551234"

    def test_already_e164(self) -> None:
        assert self.normalizer.normalize_phone("+15035551234") == "+15035551234"

    def test_ten_digit(self) -> None:
        assert self.normalizer.normalize_phone("5035551234") == "+15035551234"

    def test_with_dashes(self) -> None:
        assert self.normalizer.normalize_phone("503-555-1234") == "+15035551234"

    def test_invalid_number_returns_none(self) -> None:
        assert self.normalizer.normalize_phone("123") is None
        assert self.normalizer.normalize_phone("abcdef") is None

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Well-formed 10-digit numbers whose exchange is not assigned (starts
            # with 0/1) fail phonenumbers' is_valid_number but are still usable
            # identifiers: two records holding the same number are linked by it.
            ("917-130-8285", "+19171308285"),
            ("(718) 124-7797", "+17181247797"),
            ("+1 610 167 5298", "+16101675298"),
            ("347-034-1234", "+13470341234"),
        ],
    )
    def test_well_formed_number_with_unassigned_exchange_is_kept(
        self, raw: str, expected: str
    ) -> None:
        assert self.normalizer.normalize_phone(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "012-345-6789",  # area code cannot start with 0
            "199-555-1234",  # area code cannot start with 1
            "555-130-1234",  # unassigned area code, not just exchange
            "917-130-82851",  # too long
            "917-130-828",  # too short
            "+44 20 7946 0958 123",  # not a possible number
        ],
    )
    def test_malformed_number_is_still_rejected(self, raw: str) -> None:
        assert self.normalizer.normalize_phone(raw) is None

    def test_placeholder_phone_returns_none(self) -> None:
        assert self.normalizer.normalize_phone("0000000000") is None
        assert self.normalizer.normalize_phone("5555555555") is None

    def test_empty_returns_none(self) -> None:
        assert self.normalizer.normalize_phone("") is None

    def test_normalize_telecoms(self) -> None:
        patient = {
            "telecom": [
                {"system": "phone", "value": "(503) 555-1234", "use": "home"},
                {"system": "email", "value": "John@Gmail.COM", "use": "home"},
                {"system": "phone", "value": "0000000000", "use": "work"},
            ]
        }
        result = self.normalizer.normalize_patient_telecoms(patient)

        # Placeholder phone should be filtered
        assert len(result) == 2
        assert result[0]["value"] == "+15035551234"
        assert result[0]["use"] == "home"
        assert result[1]["value"] == "john@gmail.com"

    def test_placeholder_email_filtered(self) -> None:
        patient = {
            "telecom": [
                {"system": "email", "value": "test@example.com"},
            ]
        }
        result = self.normalizer.normalize_patient_telecoms(patient)
        assert len(result) == 0

    def test_empty_telecoms(self) -> None:
        assert self.normalizer.normalize_patient_telecoms({}) == []
        assert self.normalizer.normalize_patient_telecoms({"telecom": []}) == []

    def test_phone_type_preserved(self) -> None:
        patient = {
            "telecom": [
                {"system": "phone", "value": "+15035551234", "use": "mobile"},
                {"system": "phone", "value": "+15035554321", "use": "work"},
            ]
        }
        result = self.normalizer.normalize_patient_telecoms(patient)

        assert len(result) == 2
        # C.4: type preserved but should not affect matching
        assert result[0]["use"] == "mobile"
        assert result[1]["use"] == "work"
