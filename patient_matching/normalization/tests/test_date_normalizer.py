"""Tests for date of birth normalization."""

from patient_matching.normalization.date_normalizer import DateNormalizer


class TestDateNormalizer:
    def setup_method(self) -> None:
        self.normalizer = DateNormalizer()

    def test_full_date_preserved(self) -> None:
        assert self.normalizer.normalize_birth_date("1990-01-15") == "1990-01-15"

    def test_partial_year_month(self) -> None:
        assert self.normalizer.normalize_birth_date("1990-01") == "1990-01"

    def test_partial_year_only(self) -> None:
        assert self.normalizer.normalize_birth_date("1990") == "1990"

    def test_very_old_date_rejected(self) -> None:
        assert self.normalizer.normalize_birth_date("1800-01-01") is None

    def test_future_date_rejected(self) -> None:
        assert self.normalizer.normalize_birth_date("2099-06-15") is None

    def test_empty_returns_none(self) -> None:
        assert self.normalizer.normalize_birth_date("") is None

    def test_invalid_format_returns_none(self) -> None:
        assert self.normalizer.normalize_birth_date("01/15/1990") is None
        assert self.normalizer.normalize_birth_date("Jan 15, 1990") is None

    def test_whitespace_stripped(self) -> None:
        assert self.normalizer.normalize_birth_date("  1990-01-15  ") == "1990-01-15"

    def test_partial_year_out_of_range(self) -> None:
        assert self.normalizer.normalize_birth_date("1800") is None
        assert self.normalizer.normalize_birth_date("2099") is None

    def test_recent_date_valid(self) -> None:
        assert self.normalizer.normalize_birth_date("2024-01-01") == "2024-01-01"
