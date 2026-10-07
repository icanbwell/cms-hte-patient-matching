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
from patient_matching.normalization.manager import NormalizationManager


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
        "unit",
        [
            "apt 2",
            "unit 5b",
            "ste 100",
            "rm 114",
            "fl 3",
            "bldg c",
            # forms the normalizer produces (it strips "#"): bare ids, split ids, rarer USPS designators
            "4b",
            "unit 5 b",
            "apt 4 b",
            "ph 3",
            "bsmt a",
        ],
    )
    def test_line_that_is_only_a_unit_is_never_emitted(self, unit: str) -> None:
        assert _street_lines(_address([unit], "10001")) == set()

    @pytest.mark.parametrize(
        "street", ["floor rd", "unit dr", "lot ln", "unity", "building", "suites"]
    )
    def test_street_that_merely_starts_with_a_designator_word_is_kept(
        self, street: str
    ) -> None:
        assert _street_lines(_address([street], "10001")) == {f"{street}|10001"}

    @pytest.mark.parametrize(
        "lines",
        [
            ["co jane doe", "123 main st"],
            ["attn billing", "123 main st"],
            ["riverside apartments", "123 main st"],
            ["123 main st"],
            ["apt 2", "123 main st"],
        ],
    )
    def test_street_is_the_line_with_the_house_number_not_a_care_of_or_name_line(
        self, lines: List[str]
    ) -> None:
        assert _street_lines(_address(lines, "10001")) == {"123 main st|10001"}

    def test_no_house_number_anywhere_falls_back_to_line_one(self) -> None:
        values = _street_lines(_address(["main st", "rear"], "10001"))
        assert values == {"main st|10001"}

    @pytest.mark.parametrize(
        ("lines", "street"),
        [
            (["2b", "123 main st"], "123 main st"),  # bare unit first, digit-leading
            (["main st", "12"], "main st"),
            (["oak street", "2b"], "oak street"),
            (["apt 2", "main st"], "main st"),
            (["main plaza", "3rd floor"], "main plaza"),  # floor is not a house number
            (["1st floor", "123 main st"], "123 main st"),
            (
                ["c/o jane doe", "3rd ave"],
                "3rd ave",
            ),  # ordinal street is still a street
        ],
    )
    def test_unit_lines_are_skipped_before_the_street_is_chosen(
        self, lines: List[str], street: str
    ) -> None:
        assert _street_lines(_address(lines, "10001")) == {f"{street}|10001"}

    def test_malformed_line_values_do_not_crash(self) -> None:
        assert _street_lines(_address([123], "10001")) == set()  # type: ignore[list-item]
        assert _street_lines({"line": "123 main st", "postalCode": "10001"}) == {
            "123 main st|10001"
        }

    @pytest.mark.parametrize(
        ("postal", "expected"),
        [
            ("10001", {"123 main st|10001"}),
            ("10001-1234", {"123 main st|10001"}),  # ZIP+4 reduces to ZIP5
            ("100011234", {"123 main st|10001"}),
            (None, set()),  # no ZIP: a Street Line needs its ZIP, so none is emitted
            ("", set()),
            ("1000", set()),  # not a ZIP
            ("123456", set()),  # six digits is not a US ZIP: don't truncate it
            ("ab10001", set()),  # stray characters are not stripped into a ZIP
            ("1000 1", set()),
            ("10001 1234", {"123 main st|10001"}),  # ZIP+4 written with a space
            ("10001-12", set()),  # truncated ZIP+4
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


@pytest.mark.asyncio
async def test_identical_line_with_zips_one_digit_apart_does_not_match() -> None:
    # The composites differ by one character, so a generic fuzzy comparison would accept
    # them and in-memory blocking passes them through; only the Street Line comparator,
    # which holds the ZIP exact, rejects this pair.
    query = _patient(street="123 main street", zip_code="10001")
    stored = _patient(street="123 main street", zip_code="10002")
    assert await _outcome(query, stored) != MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_fuzzy_street_is_reported_with_its_distance() -> None:
    engine = MatchingEngine(
        backend=InMemoryBackend([_patient(street="123 main streat")])
    )
    result = await engine.match(_patient(street="123 main street"))
    rule_01 = next(e for e in result.rule_evaluations if e.rule_id == "01")
    assert rule_01.field_outcomes["street_line"] == "fuzzy"
    assert rule_01.field_fuzzy_detail["street_line"] == {"distance": 1}


@pytest.mark.asyncio
async def test_care_of_line_before_the_street_still_matches_through_normalization() -> (
    None
):
    # Goes through the real NormalizationManager, which keeps the original line order
    # when it cannot parse a care-of line. The street is "456 Oak St", not "123 Main St":
    # CMS v3.4.0 §V.D lists "123 Main St" as a placeholder street, which normalization
    # drops, so a test through the normalizer must not use it as a real address.
    normalizer = NormalizationManager()
    stored = normalizer.normalize(
        _patient(street="C/O Jane Doe", zip_code="10001")
        | {"address": [_address(["C/O Jane Doe", "456 Oak St"], "10001")]}
    )
    query = normalizer.normalize(_patient(street="456 Oak St", zip_code="10001"))
    assert await _outcome(query, stored) == MatchOutcome.MATCH


@pytest.mark.asyncio
async def test_different_buildings_with_the_same_normalized_unit_do_not_match() -> None:
    normalizer = NormalizationManager()
    query = normalizer.normalize(_patient(street="456 Oak St", unit="#4B"))
    stored = normalizer.normalize(_patient(street="987 Oak Ave", unit="#4B"))
    assert await _outcome(query, stored) != MatchOutcome.MATCH
