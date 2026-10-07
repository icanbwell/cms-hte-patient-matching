"""Edge cases from the adversarial review of the spec V.D placeholder change.

Covers: present-but-null FHIR values (docs/LEARNINGS.md, first entry), real names that
share a prefix or spelling with a placeholder, non-US phone numbers, phone extensions, what
counts as a unit for the "123 Main St" rule, placeholder spelling variants, and that every
new reason code reaches the normalization report.
"""

from typing import Any, Dict, List, Optional

import pytest

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.normalization.manager import NormalizationManager
from patient_matching.normalization.placeholder_detector import PlaceholderDetector

_SSN = "http://hl7.org/fhir/sid/us-ssn"
_ITIN = "urn:oid:2.16.840.1.113883.4.4"
_detector = PlaceholderDetector()


def _patient(**kw: Any) -> Dict[str, Any]:
    patient: Dict[str, Any] = {
        "resourceType": "Patient",
        "name": [{"family": "Alvarez", "given": ["Maria"]}],
        "birthDate": "1985-03-14",
    }
    patient.update(kw)
    return patient


def _normalized(**kw: Any) -> Dict[str, Any]:
    return NormalizationManager().normalize(_patient(**kw))


def _report_reasons(**kw: Any) -> Dict[str, str]:
    _, report = NormalizationManager().normalize_with_report(_patient(**kw))
    return {d.path: d.reason for d in report.dropped}


class TestNullValues:
    @pytest.mark.parametrize("system", [_SSN, _ITIN])
    def test_identifier_with_a_null_value_does_not_crash(self, system: str) -> None:
        normalized = _normalized(identifier=[{"system": system, "value": None}])
        fields = FieldExtractor().extract(normalized)
        assert fields.ssn_last4 == set() and fields.itin_last4 == set()

    def test_null_second_address_line_does_not_crash(self) -> None:
        normalized = _normalized(
            address=[{"line": ["42 Oak Rd", None], "postalCode": "94110"}]
        )
        assert normalized["address"][0]["line"] == ["42 oak rd"]

    def test_null_first_address_line_does_not_crash(self) -> None:
        normalized = _normalized(address=[{"line": [None, "Apt 4"], "city": "Reno"}])
        assert normalized["address"][0]["city"] == "reno"


class TestRealNamesAreNotPlaceholders:
    @pytest.mark.parametrize(
        "family",
        [
            "Infante",
            "Infantino",
            "Babyak",
            "Babylon",
            "Twine",
            "Zzaman",
            "Na",
            "Nil",
            "Sample",
            "Baby",
            "Demo",
        ],
    )
    def test_real_family_names_that_look_like_placeholders_are_kept(
        self, family: str
    ) -> None:
        names = _normalized(name=[{"family": family, "given": ["Maria"]}])["name"]
        assert names[0]["family"] == family.lower()

    @pytest.mark.parametrize("given", ["Nil", "Null"])
    def test_real_given_names_that_look_like_placeholders_are_kept(
        self, given: str
    ) -> None:
        names = _normalized(name=[{"family": "Shah", "given": [given]}])["name"]
        assert names[0]["given"][0] == given.lower()

    @pytest.mark.parametrize("family", ["Sample", "Baby", "Demo"])
    def test_test_and_newborn_words_are_real_family_names_through_the_extractor(
        self, family: str
    ) -> None:
        normalized = _normalized(name=[{"family": family, "given": ["Maria"]}])
        fields = FieldExtractor().extract(normalized)
        assert fields.last_names == {family.lower()}

    @pytest.mark.parametrize("given", ["Sample", "Baby", "Demo"])
    def test_test_and_newborn_words_still_drop_as_a_given_name(
        self, given: str
    ) -> None:
        names = _normalized(name=[{"family": "Shah", "given": [given]}])["name"]
        assert "given" not in names[0]
        assert names[0]["family"] == "shah"

    @pytest.mark.parametrize("family", ["Unknown", "Unidentified", "ZZZ", "TBD", "X"])
    def test_placeholder_family_is_dropped_and_the_given_name_kept(
        self, family: str
    ) -> None:
        names = _normalized(name=[{"family": family, "given": ["Maria"]}])["name"]
        assert "family" not in names[0]
        assert names[0]["given"] == ["maria"]

    @pytest.mark.parametrize("given", ["L", "L.", "A"])
    def test_a_given_initial_survives_a_placeholder_family_name(
        self, given: str
    ) -> None:
        names = _normalized(name=[{"family": "Unknown", "given": [given]}])["name"]
        assert names[0]["given"] == [given.lower().rstrip(".")]


class TestPhone:
    @pytest.mark.parametrize(
        "phone",
        ["+46 8 555 1234", "+65 6555 1234", "+354 555 1234", "+359 555 1234"],
    )
    def test_non_us_numbers_with_555_inside_are_not_placeholders(
        self, phone: str
    ) -> None:
        assert not _detector.is_placeholder_phone(phone)

    @pytest.mark.parametrize(
        "phone",
        [
            "212-555-1212 ext 3",
            "(212) 555-0100 x12",
            "+1 212 555 1212;ext=4",
            "1-212-555-1212",
            "+12125551212",
        ],
    )
    def test_555_exchange_is_a_placeholder_with_an_extension_or_country_code(
        self, phone: str
    ) -> None:
        assert _detector.is_placeholder_phone(phone)

    def test_real_number_with_an_extension_is_kept(self) -> None:
        assert not _detector.is_placeholder_phone("415-867-5309 ext 3")


class TestStreetPlaceholders:
    @pytest.mark.parametrize(
        "line",
        [
            "PO Box 0",
            "P.O. Box 0",
            "PO BOX 00",
            "PO Box #0",
            "PO Box 0.",
            "Post Office Box 0",
            "123 Main St,",
            "123 Main St.",
            "123 MAIN STREET",
        ],
    )
    def test_spelling_variants_are_placeholders(self, line: str) -> None:
        assert _detector.is_placeholder_address(line)

    @pytest.mark.parametrize("line", ["PO Box 17", "PO Box 10", "123 Main St Apt 4"])
    def test_real_variants_are_not_placeholders(self, line: str) -> None:
        assert not _detector.is_placeholder_address(line)

    @pytest.mark.parametrize(
        "line2", ["Apt 4", "Unit 12", "#3B", "Suite 200", "4B", "Rear"]
    )
    def test_a_real_unit_makes_123_main_st_real(self, line2: str) -> None:
        normalized = _normalized(address=[{"line": ["123 Main St", line2]}])
        assert "address" in normalized

    @pytest.mark.parametrize(
        "line2", [None, "", "  ", "N/A", "Unknown", "-", "Springfield, IL"]
    )
    def test_a_non_unit_second_line_does_not_rescue_123_main_st(
        self, line2: Optional[str]
    ) -> None:
        assert "address" not in _normalized(address=[{"line": ["123 Main St", line2]}])

    @pytest.mark.parametrize("zip_code", ["00000", "99999", "00000-0000", "99999-1234"])
    def test_placeholder_zip_plus_4_forms_are_dropped(self, zip_code: str) -> None:
        address = _normalized(
            address=[{"line": ["42 Oak Rd"], "postalCode": zip_code}]
        )["address"][0]
        assert "postalCode" not in address

    def test_fullwidth_digit_zip_is_not_mistaken_for_ascii(self) -> None:
        assert _detector.reason_for_postal_code("００００００") is None


class TestSsnLast4:
    @pytest.mark.parametrize("last4", ["0000", "9999", "1234", "1111", "5555"])
    def test_itin_last4_placeholders_are_dropped(self, last4: str) -> None:
        normalized = _normalized(
            identifier=[{"system": _ITIN, "value": f"900-70-{last4}"}]
        )
        assert "identifier" not in normalized

    def test_real_itin_last4_survives(self) -> None:
        fields = FieldExtractor().extract(
            _normalized(identifier=[{"system": _ITIN, "value": "900-70-4321"}])
        )
        assert fields.itin_last4 == {"4321"}

    def test_value_shorter_than_four_digits_is_left_alone(self) -> None:
        assert "identifier" in _normalized(
            identifier=[{"system": _SSN, "value": "123"}]
        )


class TestReportReasons:
    @pytest.mark.parametrize(
        ("kwargs", "path", "reason"),
        [
            (
                {"identifier": [{"system": _SSN, "value": "123-45-1234"}]},
                "identifier[0].value",
                "placeholder_last4",
            ),
            (
                {"telecom": [{"system": "phone", "value": "415-555-0134"}]},
                "telecom[0].value",
                "placeholder_555_exchange",
            ),
            ({"birthDate": "2000-01-01"}, "birthDate", "placeholder_date"),
            (
                {"address": [{"line": ["42 Oak Rd"], "postalCode": "00000"}]},
                "address[0].postalCode",
                "placeholder_zip",
            ),
            (
                {"address": [{"line": ["123 Main St"]}]},
                "address[0].line[0]",
                "generic_street",
            ),
            (
                {"name": [{"family": "Unknown", "given": ["Maria"]}]},
                "name[0].family",
                "unidentified_name",
            ),
            (
                {"name": [{"family": "Alvarez", "given": ["TBD"]}]},
                "name[0].given",
                "unknown_placeholder",
            ),
            (
                {"name": [{"family": "Alvarez", "given": ["ZZZ"]}]},
                "name[0].given",
                "single_or_repeated_character",
            ),
        ],
    )
    def test_reason_reaches_the_normalization_report(
        self, kwargs: Dict[str, Any], path: str, reason: str
    ) -> None:
        assert _report_reasons(**kwargs).get(path) == reason

    def test_a_zip_only_address_is_reported_once(self) -> None:
        reasons: List[str] = [
            d.reason
            for d in NormalizationManager()
            .normalize_with_report(_patient(address=[{"postalCode": "00000"}]))[1]
            .dropped
        ]
        assert reasons == ["placeholder_zip"]
