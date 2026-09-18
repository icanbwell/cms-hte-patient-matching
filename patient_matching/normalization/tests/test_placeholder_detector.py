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

    def test_reason_for_name_codes(self) -> None:
        """is_placeholder_name()'s bool now delegates to reason_for_name() --
        assert the actual reason string per category, not just the bool,
        so a miscategorization (e.g. a newborn pattern mislabeled
        "unidentified_name") would be caught."""
        assert self.detector.reason_for_name("") == "empty"
        assert self.detector.reason_for_name("Baby Boy") == "newborn_temp_name"
        assert self.detector.reason_for_name("Jane Doe") == "unidentified_name"
        assert self.detector.reason_for_name("TestPatient") == "test_name"
        assert self.detector.reason_for_name("zzztestrecord") == "placeholder_pattern"
        assert self.detector.reason_for_name("James") is None


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

    def test_reason_for_date_codes(self) -> None:
        assert self.detector.reason_for_date("") == "empty"
        assert self.detector.reason_for_date("unknown") == "unknown_placeholder"
        assert self.detector.reason_for_date("not-a-date") == "unparseable"
        assert self.detector.reason_for_date("1800-01-01") == "out_of_range"
        assert self.detector.reason_for_date("2099-01-01") == "out_of_range"
        assert self.detector.reason_for_date("1990-01-15") is None


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

    def test_reason_for_phone_codes(self) -> None:
        """Detector-level reasons only -- format/validity rejections
        (unparseable, invalid_number) are PhoneNormalizer's, not this
        detector's, since they depend on the `phonenumbers` library."""
        assert self.detector.reason_for_phone("") == "empty"
        assert self.detector.reason_for_phone("abc") == "no_digits"
        assert self.detector.reason_for_phone("0000000000") == "placeholder_pattern"
        assert self.detector.reason_for_phone("+15037654321") is None


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

    def test_reason_for_address_codes(self) -> None:
        assert self.detector.reason_for_address("") == "empty"
        assert self.detector.reason_for_address("Unknown") == "unknown_placeholder"
        assert self.detector.reason_for_address("Homeless") == "placeholder_pattern"
        assert self.detector.reason_for_address("123 Main St") is None


class TestPlaceholderEmail:
    """Email placeholder detection had no dedicated test class at all
    before this -- is_placeholder_email()/reason_for_email() were only
    exercised transitively via PhoneNormalizer's telecom tests."""

    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_placeholder_emails(self) -> None:
        assert self.detector.is_placeholder_email("test@example.com")
        assert self.detector.is_placeholder_email("noreply@gmail.com")

    def test_real_email_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_email("maria@gmail.com")

    def test_reason_for_email_codes(self) -> None:
        assert self.detector.reason_for_email("") == "empty"
        assert self.detector.reason_for_email("test@example.com") == "placeholder_pattern"
        assert self.detector.reason_for_email("maria@gmail.com") is None


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

    def test_reason_for_ssn_codes(self) -> None:
        assert self.detector.reason_for_ssn("") == "empty"
        assert self.detector.reason_for_ssn("000-00-0000") == "placeholder_pattern"
        assert self.detector.reason_for_ssn("123-45-6789") is None


class TestPlaceholderSubscriberId:
    """v3.3.4: Subscriber/Member ID placeholder detection (session 6)."""

    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_all_zeros(self) -> None:
        assert self.detector.is_placeholder_subscriber_id("0000000")

    def test_all_nines(self) -> None:
        assert self.detector.is_placeholder_subscriber_id("999999")

    def test_pending(self) -> None:
        assert self.detector.is_placeholder_subscriber_id("PENDING")
        assert self.detector.is_placeholder_subscriber_id("pending")

    def test_tbd(self) -> None:
        assert self.detector.is_placeholder_subscriber_id("TBD")

    def test_none_literal(self) -> None:
        assert self.detector.is_placeholder_subscriber_id("NONE")

    def test_empty_string(self) -> None:
        assert self.detector.is_placeholder_subscriber_id("")

    def test_real_looking_id_not_placeholder(self) -> None:
        assert not self.detector.is_placeholder_subscriber_id("M123456789")
        assert not self.detector.is_placeholder_subscriber_id("W900123456")

    def test_reason_for_subscriber_id_codes(self) -> None:
        assert self.detector.reason_for_subscriber_id("") == "empty"
        assert self.detector.reason_for_subscriber_id("PENDING") == "placeholder_pattern"
        assert self.detector.reason_for_subscriber_id("W900123456") is None


class TestPlaceholderGeneral:
    def setup_method(self) -> None:
        self.detector = PlaceholderDetector()

    def test_reason_for_general_codes(self) -> None:
        assert self.detector.reason_for_general("") == "empty"
        assert self.detector.reason_for_general("n/a") == "unknown_placeholder"
        assert self.detector.reason_for_general("W900123456") is None
