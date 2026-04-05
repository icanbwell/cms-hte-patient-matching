"""Tests for FieldComparator."""

import pytest

from patient_matching.matching.field_comparator import (
    FieldComparator,
    MAX_DAMERAU_LEVENSHTEIN_DISTANCE,
    MIN_FUZZY_LENGTH,
)


@pytest.fixture
def comparator():
    return FieldComparator()


class TestExactMatch:
    def test_exact_match_overlap(self, comparator):
        assert comparator.exact_match({"john"}, {"john"}) is True

    def test_exact_match_no_overlap(self, comparator):
        assert comparator.exact_match({"john"}, {"jane"}) is False

    def test_exact_match_multiple_values(self, comparator):
        assert comparator.exact_match({"john", "johnny"}, {"johnny", "jon"}) is True

    def test_exact_match_empty_sets(self, comparator):
        assert comparator.exact_match(set(), set()) is False

    def test_exact_match_one_empty(self, comparator):
        assert comparator.exact_match({"john"}, set()) is False


class TestFuzzyMatch:
    def test_fuzzy_match_exact(self, comparator):
        """Fuzzy match includes exact matches."""
        assert comparator.fuzzy_match({"smith"}, {"smith"}) is True

    def test_fuzzy_match_substitution(self, comparator):
        """smith vs smtih — adjacent transposition."""
        assert comparator.fuzzy_match({"smith"}, {"smtih"}) is True

    def test_fuzzy_match_insertion(self, comparator):
        """smith vs smiths — 1 insertion."""
        assert comparator.fuzzy_match({"smith"}, {"smiths"}) is True

    def test_fuzzy_match_deletion(self, comparator):
        """smiths vs smith — 1 deletion."""
        assert comparator.fuzzy_match({"smiths"}, {"smith"}) is True

    def test_fuzzy_match_too_far(self, comparator):
        """Distance > 1 should not match."""
        assert comparator.fuzzy_match({"smith"}, {"snack"}) is False

    def test_fuzzy_match_short_string_rejected(self, comparator):
        """Strings < 5 chars should not fuzzy match (E.3)."""
        assert comparator.fuzzy_match({"jon"}, {"john"}) is False
        assert comparator.fuzzy_match({"ann"}, {"anne"}) is False

    def test_fuzzy_match_exactly_5_chars(self, comparator):
        """Strings of exactly 5 chars are eligible."""
        assert comparator.fuzzy_match({"james"}, {"janes"}) is True

    def test_fuzzy_match_empty_sets(self, comparator):
        assert comparator.fuzzy_match(set(), set()) is False

    def test_fuzzy_match_multiple_values(self, comparator):
        """Should match if any pair matches."""
        assert comparator.fuzzy_match(
            {"bob", "robert"}, {"robret", "alice"}
        ) is True


class TestIsFuzzyOnly:
    def test_is_fuzzy_only_exact_match(self, comparator):
        assert comparator.is_fuzzy_only({"smith"}, {"smith"}) is False

    def test_is_fuzzy_only_true(self, comparator):
        assert comparator.is_fuzzy_only({"smith"}, {"smtih"}) is True

    def test_is_fuzzy_only_no_match(self, comparator):
        assert comparator.is_fuzzy_only({"smith"}, {"jones"}) is False

    def test_is_fuzzy_only_short_string(self, comparator):
        assert comparator.is_fuzzy_only({"jon"}, {"joh"}) is False


class TestConstants:
    def test_min_fuzzy_length(self):
        assert MIN_FUZZY_LENGTH == 5

    def test_max_distance(self):
        assert MAX_DAMERAU_LEVENSHTEIN_DISTANCE == 1
