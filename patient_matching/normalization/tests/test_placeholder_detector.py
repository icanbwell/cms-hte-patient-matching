"""Tests for placeholder value detection."""

from typing import cast

from patient_matching.normalization.placeholder_detector import PlaceholderDetector


class TestPlaceholderNames:
    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_newborn_names(self) -> None:
        assert self.detector.is_placeholder_name("Baby Boy")
        assert self.detector.is_placeholder_name("BabyGirl")
        assert self.detector.is_placeholder_name("Newborn")
        assert self.detector.is_placeholder_name("Infant Boy")

    def test_unidentified_names(self) -> None:
        assert self.detector.is_placeholder_name("Unknown")
        assert self.detector.is_placeholder_name("John Doe")
        assert self.detector.is_placeholder_name("Jane Doe")
        assert self.detector.is_placeholder_name("Unidentified")

    def test_test_names(self) -> None:
        assert self.detector.is_placeholder_name("Test")
        assert self.detector.is_placeholder_name("TestPatient")
        assert self.detector.is_placeholder_name("Demo")
        assert self.detector.is_placeholder_name("ZZTest")

    def test_pattern_match(self) -> None:
        assert self.detector.is_placeholder_name("Baby Boy of Smith")
        assert self.detector.is_placeholder_name("Twin A")
        assert self.detector.is_placeholder_name("zzztestrecord")
        assert self.detector.is_placeholder_name("XXX")

    def test_real_names_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_name("James")
        assert not self.detector.is_placeholder_name("Maria")
        assert not self.detector.is_placeholder_name("Smith")
        assert not self.detector.is_placeholder_name("O'Connor")

    def test_empty_is_placeholder(self) -> None:
        assert self.detector.is_placeholder_name("")
        assert self.detector.is_placeholder_name(cast(str, None))


class TestPlaceholderDates:
    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_valid_date_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_date("1990-01-15")
        assert not self.detector.is_placeholder_date("2000-06-30")

    def test_very_old_date(self) -> None:
        assert self.detector.is_placeholder_date("1800-01-01")

    def test_future_date(self) -> None:
        assert self.detector.is_placeholder_date("2099-01-01")

    def test_empty_date(self) -> None:
        assert self.detector.is_placeholder_date("")
        assert self.detector.is_placeholder_date(cast(str, None))

    def test_unknown_string(self) -> None:
        assert self.detector.is_placeholder_date("unknown")
        assert self.detector.is_placeholder_date("N/A")


class TestPlaceholderPhone:
    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_all_zeros(self) -> None:
        assert self.detector.is_placeholder_phone("0000000000")

    def test_all_same_digit(self) -> None:
        assert self.detector.is_placeholder_phone("1111111111")
        assert self.detector.is_placeholder_phone("5555555555")

    def test_sequential(self) -> None:
        assert self.detector.is_placeholder_phone("1234567890")

    def test_real_phone_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_phone("+15551234567")
        assert not self.detector.is_placeholder_phone("503-555-1234")


class TestPlaceholderAddress:
    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_unknown_address(self) -> None:
        assert self.detector.is_placeholder_address("Unknown")
        assert self.detector.is_placeholder_address("Homeless")
        assert self.detector.is_placeholder_address("No Fixed Address")
        assert self.detector.is_placeholder_address("General Delivery")

    def test_real_address_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_address("123 Main St")
        assert not self.detector.is_placeholder_address("456 Oak Ave Apt 2B")


class TestPlaceholderSSN:
    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_all_zeros(self) -> None:
        assert self.detector.is_placeholder_ssn("000-00-0000")

    def test_all_nines(self) -> None:
        assert self.detector.is_placeholder_ssn("999-99-9999")

    def test_starts_with_000(self) -> None:
        assert self.detector.is_placeholder_ssn("000-12-3456")

    def test_real_ssn_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_ssn("123-45-6789")
