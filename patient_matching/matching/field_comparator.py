"""Field-level comparison logic per CMS Proposal v3.2.2 Section V.E.

Fuzzy matching constraints:
  E.1: Only on fields explicitly marked fuzzy-eligible in Table 2.
  E.2: Damerau-Levenshtein distance of 1 (1 insertion, deletion,
       substitution, or adjacent transposition).
  E.3: NOT applied to strings shorter than 5 characters.
  E.4: Soundex and phonetic matching are prohibited.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Set

from rapidfuzz.distance import DamerauLevenshtein

MIN_FUZZY_LENGTH = 5
MAX_DAMERAU_LEVENSHTEIN_DISTANCE = 1
DOB_FUZZY_TOLERANCE_DAYS = 1


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
                dist = DamerauLevenshtein.distance(q_val, c_val)
                if dist <= MAX_DAMERAU_LEVENSHTEIN_DISTANCE:
                    return True

        return False

    @staticmethod
    def dob_fuzzy_match(query_values: Set[str], candidate_values: Set[str]) -> bool:
        """CMS v3.3 DOB tolerance: +/-1 day, exact calendar-date comparison.

        Not a string edit-distance comparison - DOB is a date, not a name or
        street string, so Damerau-Levenshtein doesn't apply. Malformed/partial
        dates never fuzzy-match (fail closed, per the placeholder-date
        handling elsewhere in this codebase).
        """
        try:
            q_dates = {date.fromisoformat(v) for v in query_values}
            c_dates = {date.fromisoformat(v) for v in candidate_values}
        except ValueError:
            return False
        for q in q_dates:
            for c in c_dates:
                if abs((q - c).days) <= DOB_FUZZY_TOLERANCE_DAYS:
                    return True
        return False

    @staticmethod
    def fuzzy_distance(
        query_values: Set[str], candidate_values: Set[str]
    ) -> Optional[int]:
        """Minimum Damerau-Levenshtein distance among value pairs that
        qualify for fuzzy matching (both sides >= MIN_FUZZY_LENGTH chars,
        distance <= MAX_DAMERAU_LEVENSHTEIN_DISTANCE).

        For troubleshooting a "fuzzy" field_outcomes entry -- fuzzy_match()
        only says yes/no, not how close the pair actually was. Returns
        None if no qualifying pair exists (including an exact match,
        which has no meaningful "distance" to report).
        """
        best: Optional[int] = None
        for q_val in query_values:
            if len(q_val) < MIN_FUZZY_LENGTH:
                continue
            for c_val in candidate_values:
                if len(c_val) < MIN_FUZZY_LENGTH:
                    continue
                dist = DamerauLevenshtein.distance(q_val, c_val)
                if dist <= MAX_DAMERAU_LEVENSHTEIN_DISTANCE and (
                    best is None or dist < best
                ):
                    best = dist
        return best

    @staticmethod
    def dob_fuzzy_offset_days(
        query_values: Set[str], candidate_values: Set[str]
    ) -> Optional[int]:
        """Minimum day offset among DOB pairs within the +/-1 day tolerance.

        Companion to dob_fuzzy_match, for troubleshooting -- shows the
        actual offset (0 or 1 day) rather than just whether it passed.
        Returns None if unparseable or no pair is within tolerance.
        """
        try:
            q_dates = {date.fromisoformat(v) for v in query_values}
            c_dates = {date.fromisoformat(v) for v in candidate_values}
        except ValueError:
            return None
        best: Optional[int] = None
        for q in q_dates:
            for c in c_dates:
                offset = abs((q - c).days)
                if offset <= DOB_FUZZY_TOLERANCE_DAYS and (
                    best is None or offset < best
                ):
                    best = offset
        return best

    @staticmethod
    def is_fuzzy_only(query_values: Set[str], candidate_values: Set[str]) -> bool:
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
                dist = DamerauLevenshtein.distance(q_val, c_val)
                if dist <= MAX_DAMERAU_LEVENSHTEIN_DISTANCE:
                    return True

        return False
