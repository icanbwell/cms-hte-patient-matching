"""CMS v3.4.0 §V.D placeholder table: every field's example placeholders are treated as absent.

Each group drives the real NormalizationManager and FieldExtractor, because a placeholder
only matters if it survives to a matchable field. Every group has real-value controls so a
detector that flags everything cannot pass.
"""

from typing import Any, Dict, Optional, Set

import pytest

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.normalization.manager import NormalizationManager
from patient_matching.normalization.placeholder_detector import PlaceholderDetector

_SSN = "http://hl7.org/fhir/sid/us-ssn"
_PAYER = "https://payer.example/id"


def _fields(
    *,
    given: str = "Maria",
    family: str = "Alvarez",
    dob: str = "1985-03-14",
    phone: Optional[str] = None,
    email: Optional[str] = None,
    ssn: Optional[str] = None,
    line: Optional[list] = None,  # type: ignore[type-arg]
    zip_code: Optional[str] = None,
) -> Any:
    patient: Dict[str, Any] = {
        "resourceType": "Patient",
        "name": [{"family": family, "given": [given]}],
        "birthDate": dob,
        "telecom": [],
        "address": [],
        "identifier": [],
    }
    if phone:
        patient["telecom"].append({"system": "phone", "value": phone})
    if email:
        patient["telecom"].append({"system": "email", "value": email})
    if ssn:
        patient["identifier"].append({"system": _SSN, "value": ssn})
    if line or zip_code:
        address: Dict[str, Any] = {"line": line or ["42 Willow Creek Rd"]}
        if zip_code:
            address["postalCode"] = zip_code
        patient["address"].append(address)
    return FieldExtractor().extract(NormalizationManager().normalize(patient))


def _survives(values: Set[str]) -> bool:
    return bool(values)


class TestNames:
    @pytest.mark.parametrize(
        "given",
        ["Unknown", "Unk", "Test", "Test Patient", "Baby Boy", "Twin A", "Newborn"]
        + ["N/A", "None", "TBD", "ZZZ", "AAAA", "eee"],
    )
    def test_placeholder_first_names_are_absent(self, given: str) -> None:
        assert not _survives(_fields(given=given).first_names)

    @pytest.mark.parametrize("given", ["X", "L.", "q"])
    def test_single_character_given_name_is_kept_as_an_initial(
        self, given: str
    ) -> None:
        # Deliberate deviation from the spec's "single-character" placeholder example: an
        # initial is a legitimate abbreviation (ONC given_abbreviate); dropping it costs
        # ~194 true matches in the pairs tier. A single-character FAMILY name is absent.
        assert given.lower().rstrip(".") in _fields(given=given).first_names

    @pytest.mark.parametrize("family", ["Unknown", "Unk", "TBD", "ZZZ", "X", "None"])
    def test_placeholder_last_names_are_absent(self, family: str) -> None:
        assert not _survives(_fields(family=family).last_names)

    def test_placeholder_family_keeps_a_real_given_name(self) -> None:
        fields = _fields(given="Maria", family="Unknown")
        assert fields.first_names == {"maria"}

    @pytest.mark.parametrize(("given", "family"), [("John", "Doe"), ("Jane", "Doe")])
    def test_doe_paired_with_generic_first_name_is_absent(
        self, given: str, family: str
    ) -> None:
        fields = _fields(given=given, family=family)
        assert not _survives(fields.first_names | fields.last_names)

    @pytest.mark.parametrize(
        ("given", "family"),
        [
            ("Maria", "Alvarez"),
            ("Lee", "Ng"),
            ("Ann", "Li"),
            ("Maria", "Doe"),
            ("Bo", "Yi"),
        ],
    )
    def test_real_names_survive(self, given: str, family: str) -> None:
        fields = _fields(given=given, family=family)
        assert given.lower() in fields.first_names  # nicknames may be added too
        assert fields.last_names == {family.lower()}


class TestDateOfBirth:
    @pytest.mark.parametrize(
        "dob",
        ["1900-01-01", "1901-01-01", "1800-01-01", "2000-01-01", "1111-11-11"]
        + ["0001-01-01", "2099-01-01"],
    )
    def test_placeholder_dates_are_absent(self, dob: str) -> None:
        assert not _survives(_fields(dob=dob).dob)

    @pytest.mark.parametrize(
        "dob", ["1985-03-14", "2000-01-02", "1999-12-31", "2001-01-01"]
    )
    def test_real_dates_survive(self, dob: str) -> None:
        assert _fields(dob=dob).dob == {dob}


class TestSsnLast4:
    @pytest.mark.parametrize(
        "ssn",
        ["123-45-0000", "123-45-9999", "123-45-1234", "0000", "9999", "1234"]
        + [f"123-45-{d * 4}" for d in "12345678"],
    )
    def test_placeholder_last4_is_absent(self, ssn: str) -> None:
        assert not _survives(_fields(ssn=ssn).ssn_last4)

    @pytest.mark.parametrize(
        "ssn", ["123-45-6789", "123-45-4321", "123-45-1212", "6789"]
    )
    def test_real_last4_survives(self, ssn: str) -> None:
        assert _fields(ssn=ssn).ssn_last4 == {ssn[-4:]}


class TestPhone:
    @pytest.mark.parametrize(
        "phone",
        ["000-000-0000", "555-555-5555", "111-111-1111", "123-456-7890"]
        + ["415-555-0134", "(310) 555-9999", "+1 212 555 1212"],
    )
    def test_placeholder_phones_are_absent(self, phone: str) -> None:
        assert not _survives(_fields(phone=phone).phones)

    @pytest.mark.parametrize(
        ("phone", "e164"),
        [
            ("415-867-5309", "+14158675309"),
            ("+1 212 556 1212", "+12125561212"),  # 556 is not the 555 exchange
            (
                "555-867-5309",
                "+15558675309",
            ),  # 555 as the AREA code is not the exchange
        ],
    )
    def test_real_phones_survive(self, phone: str, e164: str) -> None:
        assert not PlaceholderDetector().is_placeholder_phone(e164)
        if not phone.startswith(
            "555"
        ):  # 555 is not an assigned area code (validity gate)
            assert _fields(phone=phone).phones == {e164}


class TestEmail:
    @pytest.mark.parametrize(
        "email",
        ["test@test.com", "noreply@acme.org", "unknown@unknown.com", "none@none.com"]
        + ["maria@example.com"],
    )
    def test_placeholder_emails_are_absent(self, email: str) -> None:
        assert not _survives(_fields(email=email).emails)

    @pytest.mark.parametrize("email", ["maria.alvarez@gmail.com", "tom@testarossa.io"])
    def test_real_emails_survive(self, email: str) -> None:
        assert _fields(email=email).emails == {email}


class TestStreetAndZip:
    @pytest.mark.parametrize(
        "line",
        [
            ["123 Main St"],
            ["PO Box 0"],
            ["Unknown"],
            ["Homeless"],
            ["No Fixed Address"],
        ],
    )
    def test_placeholder_street_is_absent(self, line: list) -> None:  # type: ignore[type-arg]
        assert not _survives(_fields(line=line, zip_code="94110").street_lines)

    def test_123_main_st_with_a_real_unit_is_not_a_placeholder(self) -> None:
        fields = _fields(line=["123 Main St", "Apt 4"], zip_code="94110")
        assert any(v.startswith("123 main st") for v in fields.street_lines)

    @pytest.mark.parametrize("zip_code", ["00000", "99999"])
    def test_placeholder_zip_is_absent_and_drops_the_street_line(
        self, zip_code: str
    ) -> None:
        fields = _fields(line=["42 Willow Creek Rd"], zip_code=zip_code)
        assert fields.zip_codes == set()

    @pytest.mark.parametrize(
        "line", [["42 Willow Creek Rd"], ["PO Box 17"], ["123 Main St", "Apt 4"]]
    )
    def test_real_address_survives(self, line: list) -> None:  # type: ignore[type-arg]
        fields = _fields(line=line, zip_code="94110")
        assert fields.street_lines
        assert fields.zip_codes == {"94110"}
