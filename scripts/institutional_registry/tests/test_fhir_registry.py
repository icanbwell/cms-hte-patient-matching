"""Tests for the FHIR Organization representation of the institutional-address registry."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import pytest
from fhirschemapy.R4B.organization import Organization

from scripts.institutional_registry import fhir_registry as fr
from scripts.institutional_registry.build_registry import OUTPUT, _beds

ENTRY = fr.RegistryEntry(
    institution_type="nursing_home",
    match_policy="block_household_rules",
    name="Sunny Acres Care Center",
    street="12 Main St, Suite 4",
    city="Springfield",
    state="IL",
    zip="62701-1234",
    beds=60,
    data_collected="2026-10-06",
    match_street="12 main st",
    match_zip5="62701",
    sources=(("care_compare", "145001"), ("pos", "145001"), ("state_il", "")),
)


def _ext(resource: Dict[str, Any], url: str) -> list[Dict[str, Any]]:
    return [e for e in resource["extension"] if e["url"] == url]


def test_address_name_and_types_use_the_standard_elements() -> None:
    org = fr.to_organization(ENTRY)
    assert org["resourceType"] == "Organization"
    assert org["name"] == "Sunny Acres Care Center"
    assert org["address"] == [
        {
            "use": "work",
            "type": "physical",
            "line": ["12 Main St, Suite 4"],
            "city": "Springfield",
            "state": "IL",
            "postalCode": "62701-1234",
        }
    ]
    codings = [c for t in org["type"] for c in t["coding"]]
    assert {"system": fr.ORGANIZATION_TYPE_SYSTEM, "code": "prov"} in codings
    assert {"system": fr.INSTITUTION_TYPE_SYSTEM, "code": "nursing_home"} in codings


def test_identifiers_only_for_sources_that_have_an_id() -> None:
    org = fr.to_organization(ENTRY)
    assert org["identifier"] == [
        {"system": f"{fr.SOURCE_SYSTEM_PREFIX}care_compare", "value": "145001"},
        {"system": f"{fr.SOURCE_SYSTEM_PREFIX}pos", "value": "145001"},
    ]
    # state_il has no ID but is still listed as a source.
    assert {e["valueCode"] for e in _ext(org, fr.SOURCE_URL)} == {
        "care_compare",
        "pos",
        "state_il",
    }


def test_registry_specific_fields_are_extensions() -> None:
    org = fr.to_organization(ENTRY)
    assert _ext(org, fr.MATCH_POLICY_URL)[0]["valueCode"] == "block_household_rules"
    assert _ext(org, fr.DATA_COLLECTED_URL)[0]["valueDate"] == "2026-10-06"
    assert _ext(org, fr.BEDS_URL)[0]["valueInteger"] == 60
    key = _ext(org, fr.MATCH_KEY_URL)[0]["extension"]
    assert key == [
        {"url": "street", "valueString": "12 main st"},
        {"url": "zip5", "valueString": "62701"},
    ]


def test_beds_extension_is_omitted_when_unknown() -> None:
    org = fr.to_organization(
        fr.RegistryEntry(**{**ENTRY.__dict__, "beds": None})  # type: ignore[arg-type]
    )
    assert _ext(org, fr.BEDS_URL) == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("48.0", 48),
        ("60", 60),
        ("", None),
        ("Not Applicable", None),
        ("Not Available", None),
    ],
)
def test_beds_parsing_drops_non_numeric_values(raw: str, expected: object) -> None:
    assert _beds(raw) == expected


def test_unknown_institution_type_gets_the_other_organization_type() -> None:
    org = fr.to_organization(
        fr.RegistryEntry(**{**ENTRY.__dict__, "institution_type": "shelter_x"})  # type: ignore[arg-type]
    )
    assert org["type"][0]["coding"][0]["code"] == "other"
    assert org["type"][1]["coding"][0]["code"] == "shelter_x"


def test_resource_id_is_stable_and_a_valid_fhir_id() -> None:
    a = fr.organization_id("nursing_home", "12 main st", "62701")
    assert a == fr.organization_id("nursing_home", "12 main st", "62701")
    assert a != fr.organization_id("hospice", "12 main st", "62701")
    assert re.fullmatch(r"[A-Za-z0-9\-.]{1,64}", a)


def test_several_ids_from_one_source_survive_a_round_trip() -> None:
    entry = fr.RegistryEntry(
        **{
            **ENTRY.__dict__,  # type: ignore[arg-type]
            "sources": (("overture", "aaa"), ("overture", "bbb"), ("pos", "")),
        }
    )
    assert fr.from_organization(fr.to_organization(entry)) == entry


def test_round_trip_through_a_resource() -> None:
    assert fr.from_organization(fr.to_organization(ENTRY)) == ENTRY


@pytest.mark.parametrize(
    "resource",
    [
        {"resourceType": "Patient"},
        {"resourceType": "Organization", "type": [], "extension": []},
    ],
)
def test_from_organization_rejects_resources_that_are_not_ours(
    resource: Dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        fr.from_organization(resource)


def test_written_file_round_trips_and_is_byte_reproducible(tmp_path: Path) -> None:
    other = fr.RegistryEntry(
        **{**ENTRY.__dict__, "institution_type": "hospice", "beds": None}
    )  # type: ignore[arg-type]
    first, second = tmp_path / "a.ndjson.gz", tmp_path / "b.ndjson.gz"
    assert fr.write_registry([ENTRY, other], first) == 2
    fr.write_registry([ENTRY, other], second)
    assert first.read_bytes() == second.read_bytes()
    assert list(fr.read_registry(first)) == [ENTRY, other]


def test_resource_validates_against_the_fhir_r4_model() -> None:
    Organization.model_validate(fr.to_organization(ENTRY))


def test_the_fhir_validation_used_here_rejects_bad_data() -> None:
    bad = fr.to_organization(ENTRY)
    bad["address"] = "12 Main St"  # must be a list of Address objects
    with pytest.raises(Exception):
        Organization.model_validate(bad)


@pytest.mark.skipif(not OUTPUT.exists(), reason="registry not built")
def test_committed_registry_resources_validate_and_round_trip() -> None:
    n = 0
    for i, resource in enumerate(fr.read_resources(OUTPUT)):
        if i % 50:  # every 50th: keeps the test fast; the build was validated in full
            continue
        Organization.model_validate(resource)
        assert fr.to_organization(fr.from_organization(resource)) == resource
        n += 1
    assert n > 1000
