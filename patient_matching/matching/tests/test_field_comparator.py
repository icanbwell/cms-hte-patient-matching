"""Tests for FieldComparator."""

import pytest

from patient_matching.matching.field_comparator import (
    FieldComparator,
    MAX_DAMERAU_LEVENSHTEIN_DISTANCE,
    MIN_FUZZY_LENGTH,
)


@pytest.fixture
def comparator() -> FieldComparator:
    return FieldComparator()


class TestExactMatch:
    def test_exact_match_overlap(self, comparator: FieldComparator) -> None:
        assert comparator.exact_match({"john"}, {"john"}) is True

    def test_exact_match_no_overlap(self, comparator: FieldComparator) -> None:
        assert comparator.exact_match({"john"}, {"jane"}) is False

    def test_exact_match_multiple_values(self, comparator: FieldComparator) -> None:
        assert comparator.exact_match({"john", "johnny"}, {"johnny", "jon"}) is True

    def test_exact_match_empty_sets(self, comparator: FieldComparator) -> None:
        assert comparator.exact_match(set(), set()) is False

    def test_exact_match_one_empty(self, comparator: FieldComparator) -> None:
        assert comparator.exact_match({"john"}, set()) is False


class TestFuzzyMatch:
    def test_fuzzy_match_exact(self, comparator: FieldComparator) -> None:
        """Fuzzy match includes exact matches."""
        assert comparator.fuzzy_match({"smith"}, {"smith"}) is True

    def test_fuzzy_match_substitution(self, comparator: FieldComparator) -> None:
        """smith vs smtih — adjacent transposition."""
        assert comparator.fuzzy_match({"smith"}, {"smtih"}) is True

    def test_fuzzy_match_insertion(self, comparator: FieldComparator) -> None:
        """smith vs smiths — 1 insertion."""
        assert comparator.fuzzy_match({"smith"}, {"smiths"}) is True

    def test_fuzzy_match_deletion(self, comparator: FieldComparator) -> None:
        """smiths vs smith — 1 deletion."""
        assert comparator.fuzzy_match({"smiths"}, {"smith"}) is True

    def test_fuzzy_match_too_far(self, comparator: FieldComparator) -> None:
        """Distance > 1 should not match."""
        assert comparator.fuzzy_match({"smith"}, {"snack"}) is False

    def test_fuzzy_match_short_string_rejected(
        self, comparator: FieldComparator
    ) -> None:
        """Strings < 5 chars should not fuzzy match (E.3)."""
        assert comparator.fuzzy_match({"jon"}, {"john"}) is False
        assert comparator.fuzzy_match({"ann"}, {"anne"}) is False

    def test_fuzzy_match_exactly_5_chars(self, comparator: FieldComparator) -> None:
        """Strings of exactly 5 chars are eligible."""
        assert comparator.fuzzy_match({"james"}, {"janes"}) is True

    def test_fuzzy_match_empty_sets(self, comparator: FieldComparator) -> None:
        assert comparator.fuzzy_match(set(), set()) is False

    def test_fuzzy_match_multiple_values(self, comparator: FieldComparator) -> None:
        """Should match if any pair matches."""
        assert comparator.fuzzy_match({"bob", "robert"}, {"robret", "alice"}) is True


class TestIsFuzzyOnly:
    def test_is_fuzzy_only_exact_match(self, comparator: FieldComparator) -> None:
        assert comparator.is_fuzzy_only({"smith"}, {"smith"}) is False

    def test_is_fuzzy_only_true(self, comparator: FieldComparator) -> None:
        assert comparator.is_fuzzy_only({"smith"}, {"smtih"}) is True

    def test_is_fuzzy_only_no_match(self, comparator: FieldComparator) -> None:
        assert comparator.is_fuzzy_only({"smith"}, {"jones"}) is False

    def test_is_fuzzy_only_short_string(self, comparator: FieldComparator) -> None:
        assert comparator.is_fuzzy_only({"jon"}, {"joh"}) is False


class TestConstants:
    def test_min_fuzzy_length(self) -> None:
        assert MIN_FUZZY_LENGTH == 5

    def test_max_distance(self) -> None:
        assert MAX_DAMERAU_LEVENSHTEIN_DISTANCE == 1


class TestDobFuzzyMatch:
    """CMS v3.3 DOB tolerance: +/-1 day, exact calendar-date comparison."""

    def test_exact_same_date_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-01-15"}, {"1990-01-15"}) is True

    def test_one_day_before_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-01-15"}, {"1990-01-14"}) is True

    def test_one_day_after_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-01-15"}, {"1990-01-16"}) is True

    def test_two_days_does_not_match(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-01-15"}, {"1990-01-17"}) is False

    def test_month_boundary_one_day_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-02-01"}, {"1990-01-31"}) is True

    def test_year_boundary_one_day_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-01-01"}, {"1989-12-31"}) is True

    def test_malformed_date_never_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"not-a-date"}, {"1990-01-15"}) is False

    def test_partial_date_never_matches(self, comparator: FieldComparator) -> None:
        assert comparator.dob_fuzzy_match({"1990-01"}, {"1990-01-15"}) is False
