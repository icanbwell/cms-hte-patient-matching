"""Field-level comparison logic per CMS Proposal v3.2.2 Section V.E.

Fuzzy matching constraints:
  E.1: Only on fields explicitly marked fuzzy-eligible in Table 2.
  E.2: Damerau-Levenshtein distance of 1 (1 insertion, deletion,
       substitution, or adjacent transposition).
  E.3: NOT applied to strings shorter than 5 characters.
  E.4: Soundex and phonetic matching are prohibited.
"""

from __future__ import annotations

from typing import Set

from rapidfuzz.distance import DamerauLevenshtein

MIN_FUZZY_LENGTH = 5
MAX_DAMERAU_LEVENSHTEIN_DISTANCE = 1


class FieldComparator:
    """Compares field values using exact and constrained fuzzy matching."""

    @staticmethod
    def exact_match(query_values: Set[str], candidate_values: Set[str]) -> bool:
        """Check if any query value exactly matches any candidate value.

        Per Core Principle 10, a match on ANY known value satisfies the field.
        """
        return bool(query_values & candidate_values)

    @staticmethod
    def fuzzy_match(query_values: Set[str], candidate_values: Set[str]) -> bool:
        """Check if any query value fuzzy-matches any candidate value.

        Fuzzy match = Damerau-Levenshtein distance <= 1, and both
        strings must be >= 5 characters after normalization.

        Returns True if exact match OR fuzzy match is found.
        """
        # Exact match always counts
        if query_values & candidate_values:
            return True

        for q_val in query_values:
            if len(q_val) < MIN_FUZZY_LENGTH:
                continue
            for c_val in candidate_values:
                if len(c_val) < MIN_FUZZY_LENGTH:
                    continue
                dist = DamerauLevenshtein.distance(
                    q_val, c_val
                )
                if dist <= MAX_DAMERAU_LEVENSHTEIN_DISTANCE:
                    return True

        return False

    @staticmethod
    def is_fuzzy_only(
        query_values: Set[str], candidate_values: Set[str]
    ) -> bool:
        """Check if the match is fuzzy-only (not exact).

        Returns True if fuzzy_match passes but exact_match does not.
        Used to count how many fields in a combination are fuzzy.
        """
        if query_values & candidate_values:
            return False  # It's an exact match, not fuzzy-only

        for q_val in query_values:
            if len(q_val) < MIN_FUZZY_LENGTH:
                continue
            for c_val in candidate_values:
                if len(c_val) < MIN_FUZZY_LENGTH:
                    continue
                dist = DamerauLevenshtein.distance(
                    q_val, c_val
                )
                if dist <= MAX_DAMERAU_LEVENSHTEIN_DISTANCE:
                    return True

        return False
