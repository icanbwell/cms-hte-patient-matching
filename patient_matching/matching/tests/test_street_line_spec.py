"""CMS v3.4.0 Table 3: "Street line" is the standardized street line plus an exact ZIP.

Street Line is address line 1 standardized, and the ZIP must remain exact. A unit
(address line 2, or a line that is only a unit designator) is never a Street Line on
its own. These tests pin that contract at three levels: the extractor, the comparator,
and the end-to-end rule that uses it (rule 01, First* + Last* + DOB* + Street Line*).
"""

from typing import Any, Dict, List, Optional, Set

import pytest

from patient_matching.matching.field_comparator import FieldComparator
from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.matching.in_memory_backend import InMemoryBackend
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine


def _address(lines: List[str], postal: Optional[str]) -> Dict[str, Any]:
    address: Dict[str, Any] = {"line": lines}
    if postal is not None:
        address["postalCode"] = postal
    return address


def _street_lines(*addresses: Dict[str, Any]) -> Set[str]:
    return FieldExtractor().extract({"address": list(addresses)}).street_lines


class TestExtractorStreetLine:
    def test_street_line_is_line_one_with_zip5(self) -> None:
        assert _street_lines(_address(["123 main st"], "10001")) == {
            "123 main st|10001"
        }

    def test_unit_line_two_is_not_a_street_line(self) -> None:
        values = _street_lines(_address(["123 main st", "apt 4"], "10001"))
        assert values == {"123 main st|10001"}

    @pytest.mark.parametrize(
        "unit", ["apt 2", "unit 5b", "ste 100", "# 4", "rm 114", "fl 3", "bldg c"]
    )
    def test_line_that_is_only_a_unit_is_never_emitted(self, unit: str) -> None:
        assert _street_lines(_address([unit], "10001")) == set()

    @pytest.mark.parametrize(
        ("postal", "expected"),
        [
            ("10001", {"123 main st|10001"}),
            ("10001-1234", {"123 main st|10001"}),  # ZIP+4 reduces to ZIP5
            ("100011234", {"123 main st|10001"}),
            (None, set()),  # no ZIP: a Street Line needs its ZIP, so none is emitted
            ("", set()),
            ("1000", set()),  # not a ZIP
        ],
    )
    def test_zip_must_be_present_and_is_reduced_to_five_digits(
        self, postal: Optional[str], expected: Set[str]
    ) -> None:
        assert _street_lines(_address(["123 main st"], postal)) == expected

    def test_each_address_pairs_its_own_zip(self) -> None:
        values = _street_lines(
            _address(["123 main st"], "10001"), _address(["9 oak ave"], "94110")
        )
        assert values == {"123 main st|10001", "9 oak ave|94110"}

    def test_zip_code_field_is_zip5_so_zip_plus_4_matches_zip5(self) -> None:
        fields = FieldExtractor().extract(
            {"address": [_address(["1 a st"], "10001-1234")]}
        )
        assert fields.zip_codes == {"10001"}


class TestComparatorStreetLine:
    _cmp = FieldComparator()

    @pytest.mark.parametrize(
        ("query", "candidate", "expected"),
        [
            ("123 main street|10001", "123 main street|10001", True),
            ("123 main street|10001", "123 main streat|10001", True),  # DL 1
            ("123 main street|10001", "123 main streat|10002", False),  # ZIP differs
            ("123 main street|10001", "123 main street|10002", False),
            ("123 main street|10001", "123 maine strat|10001", False),  # DL 2
            ("1 el|10001", "1 ek|10001", False),  # under five characters
            ("123 main street|10001", "no zip here", False),
        ],
    )
    def test_fuzzy_requires_exact_zip_and_distance_one_on_the_line(
        self, query: str, candidate: str, expected: bool
    ) -> None:
        assert self._cmp.street_line_fuzzy_match({query}, {candidate}) is expected


# --- end to end: rule 01 = First* + Last* + DOB* + Street Line* ------------------
# The patients share no phone, email or ID, so no rule except one that uses Street Line
# can link them. (Phone + First Name + DOB is already rule 11, which is why C2-37 -
# Phone + Street Line, then First Name + DOB - rarely decides an outcome by itself.)


def _patient(
    *,
    street: str,
    unit: Optional[str] = None,
    zip_code: Optional[str] = "10001",
) -> Dict[str, Any]:
    lines = [street] + ([unit] if unit else [])
    return {
        "resourceType": "Patient",
        "name": [{"family": "smith", "given": ["john"]}],
        "birthDate": "1990-01-15",
        "telecom": [],
        "address": [_address(lines, zip_code)],
        "identifier": [],
    }


async def _outcome(query: Dict[str, Any], stored: Dict[str, Any]) -> MatchOutcome:
    engine = MatchingEngine(backend=InMemoryBackend([stored]))
    return (await engine.match(query)).outcome


@pytest.mark.asyncio
async def test_positive_control_same_street_and_zip_matches() -> None:
    query = _patient(street="123 main st")
    assert await _outcome(query, _patient(street="123 main st")) == MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_same_street_text_in_a_different_zip_does_not_match() -> None:
    query = _patient(street="123 main st", zip_code="10001")
    stored = _patient(street="123 main st", zip_code="94110")
    assert await _outcome(query, stored) != MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_shared_unit_in_different_buildings_does_not_match() -> None:
    query = _patient(street="123 main st", unit="apt 2")
    stored = _patient(street="987 oak ave", unit="apt 2")
    assert await _outcome(query, stored) != MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_unit_only_line_one_is_not_a_street_to_match_on() -> None:
    query = _patient(street="apt 2")
    stored = _patient(street="apt 2")
    assert await _outcome(query, stored) != MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_zip_plus_4_on_one_side_still_matches_zip5_on_the_other() -> None:
    query = _patient(street="123 main st", zip_code="10001-1234")
    stored = _patient(street="123 main st", zip_code="10001")
    assert await _outcome(query, stored) == MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_street_typo_in_the_same_zip_still_matches_as_fuzzy() -> None:
    query = _patient(street="123 main street")
    stored = _patient(street="123 main streat")
    assert await _outcome(query, stored) == MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_street_typo_with_a_different_zip_does_not_match() -> None:
    query = _patient(street="123 main street", zip_code="10001")
    stored = _patient(street="123 main streat", zip_code="10002")
    assert await _outcome(query, stored) != MatchOutcome.MATCH
