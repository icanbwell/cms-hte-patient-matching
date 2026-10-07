"""Tests for the registry builder's pure logic: the match key, helpers and the match policy."""

import pytest

from scripts.institutional_registry.build_registry import (
    _beds,
    HOSPITAL_TYPES,
    MATCH_POLICY,
    OVERTURE_TYPES,
    POS_TYPES,
    _iso_date,
    _pad_zip,
    address_key,
    strip_unit,
)


@pytest.mark.parametrize(
    ("street", "expected"),
    [
        ("7920 BELT LINE ROAD SUITE 760", "7920 BELT LINE ROAD"),
        ("1128 E WINONA AVENUE SUITE B1 -", "1128 E WINONA AVENUE"),
        ("42840 CHRISTY ST, SUITE 102 -", "42840 CHRISTY ST"),
        ("103 W ALAMEDA AVE #130", "103 W ALAMEDA AVE"),
        ("11010 ARROW ROUTE UNIT 102", "11010 ARROW ROUTE"),
        # A '#' that is part of the house number must survive.
        ("#16 WILSON FARM ROAD", "#16 WILSON FARM ROAD"),
        ("1 PINNACLE MEADOWS", "1 PINNACLE MEADOWS"),
        # Streets that merely contain a designator word are not truncated.
        ("1282 FL-78", "1282 FL-78"),
        ("100 Veterans Building Rd", "100 Veterans Building Rd"),
        ("77 Ste Marie St", "77 Ste Marie St"),
        ("12 Floor Ave", "12 Floor Ave"),
        ("3349 BLDG A WHITING AVENUE", "3349 BLDG A WHITING AVENUE"),
        ("500 MAIN ST BLDG 2", "500 MAIN ST"),
    ],
)
def test_strip_unit(street: str, expected: str) -> None:
    assert strip_unit(street) == expected


def test_address_key_ignores_unit_case_and_zip_plus_four() -> None:
    base = address_key("1 Pinnacle Meadows", "Richford", "VT", "05476")
    assert base == ("1 pinnacle mdws", "05476")
    assert address_key("1 PINNACLE MEADOWS, APT 4B", "Richford", "VT", "05476") == base
    assert address_key("1 pinnacle meadows", "Richford", "VT", "05476-1234") == base


def test_address_key_without_zip_or_street_is_not_usable() -> None:
    street, zip5 = address_key("1 Pinnacle Meadows", "Richford", "VT", "")
    assert len(zip5) != 5  # the builder drops rows whose ZIP5 isn't 5 characters
    assert address_key("", "Richford", "VT", "05476") == ("", "")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-08-19", "2024-08-19"),
        ("7/6/21", "2021-07-06"),
        ("6/30/2012", "2012-06-30"),
        ("2026-09-23.1", "2026-09-23"),  # an Overture release name
        ("not a date", ""),
        ("", ""),
    ],
)
def test_iso_date(raw: str, expected: str) -> None:
    assert _iso_date(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3431", "03431"), ("03431", "03431"), ("12345-6789", "12345-6789"), ("", "")],
)
def test_pad_zip_restores_dropped_leading_zeros(raw: str, expected: str) -> None:
    assert _pad_zip(raw) == expected


def test_every_institution_type_the_builder_emits_has_a_policy() -> None:
    emitted = (
        set(POS_TYPES.values())
        | set(HOSPITAL_TYPES.values())
        | set(OVERTURE_TYPES.values())
        | {
            "hospital",
            "higher_education_campus",
            "federal_correctional",
            "correctional",
            "assisted_living",
        }
    )
    assert emitted <= set(MATCH_POLICY), emitted - set(MATCH_POLICY)
    assert set(MATCH_POLICY.values()) == {"block_household_rules", "review"}


def test_all_hospitals_are_blocked() -> None:
    """Decided by the project owner: acute care hospitals are blocked like the rest."""
    for institution_type in ("hospital", *HOSPITAL_TYPES.values()):
        assert MATCH_POLICY[institution_type] == "block_household_rules"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("120", 120),
        ("12.0", 12),
        ("", None),
        ("Not Applicable", None),
        ("inf", None),
        ("-999", None),
    ],
)
def test_beds_rejects_non_numeric_non_finite_and_negative(
    raw: str, expected: object
) -> None:
    assert _beds(raw) == expected
