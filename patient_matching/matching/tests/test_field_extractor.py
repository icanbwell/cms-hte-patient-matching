"""Tests for PatientFields and FieldExtractor."""

from typing import Any, Dict

import pytest

from patient_matching.matching.field_extractor import FieldExtractor, PatientFields


@pytest.fixture
def extractor() -> FieldExtractor:
    return FieldExtractor()


@pytest.fixture
def full_patient() -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "name": [
            {
                "use": "official",
                "family": "smith",
                "given": ["john", "michael"],
                "suffix": ["jr"],
                "_nicknames": ["johnny"],
            },
            {
                "use": "old",
                "family": "doe",
            },
        ],
        "birthDate": "1990-01-15",
        "telecom": [
            {"system": "phone", "value": "+12125551234"},
            {"system": "email", "value": "john@gmail.com"},
            {"system": "phone", "value": "+12125559999"},
        ],
        "address": [
            {"line": ["123 main st", "apt 4"]},
            {"line": ["456 oak ave"]},
        ],
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/us-ssn",
                "value": "123-45-6789",
            },
            {
                "system": "urn:oid:2.16.840.1.113883.4.4",
                "value": "900-70-1234",
            },
            {
                "system": "http://hl7.org/fhir/sid/us-mbi",
                "value": "1EG4TE5MK73",
            },
            {
                "type": {"coding": [{"code": "DL"}]},
                "value": "D12345678",
                "assigner": {"display": "CA-DMV"},
            },
            {
                "system": "urn:hospital:abc",
                "type": {"coding": [{"code": "MR"}]},
                "value": "MRN001",
            },
        ],
    }


class TestPatientFields:
    def test_get_values_known_field(self) -> None:
        fields = PatientFields(first_names={"john", "johnny"})
        assert fields.get_values("first_name") == {"john", "johnny"}

    def test_get_values_unknown_field(self) -> None:
        fields = PatientFields()
        assert fields.get_values("nonexistent") == set()

    def test_has_field_true(self) -> None:
        fields = PatientFields(dob={"1990-01-15"})
        assert fields.has_field("dob") is True

    def test_has_field_false(self) -> None:
        fields = PatientFields()
        assert fields.has_field("dob") is False


class TestFieldExtractor:
    def test_extract_first_names(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "john" in fields.first_names
        assert "michael" in fields.first_names
        assert "johnny" in fields.first_names  # from _nicknames

    def test_extract_last_names(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "smith" in fields.last_names
        assert "doe" in fields.last_names

    def test_extract_suffixes(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "jr" in fields.suffixes

    def test_extract_dob(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert fields.dob == {"1990-01-15"}

    def test_extract_phones(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "+12125551234" in fields.phones
        assert "+12125559999" in fields.phones

    def test_extract_emails(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "john@gmail.com" in fields.emails

    def test_extract_street_lines(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "123 main st" in fields.street_lines
        assert "apt 4" in fields.street_lines
        assert "456 oak ave" in fields.street_lines

    def test_extract_ssn_last4(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "6789" in fields.ssn_last4

    def test_extract_itin_last4(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "1234" in fields.itin_last4

    def test_extract_mbi(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "1EG4TE5MK73" in fields.mbi

    def test_extract_legal_ids(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "CA-DMV|D12345678" in fields.legal_ids

    def test_extract_namespace_ids(
        self, extractor: FieldExtractor, full_patient: Dict[str, Any]
    ) -> None:
        fields = extractor.extract(full_patient)
        assert "urn:hospital:abc|MRN001" in fields.namespace_ids

    def test_extract_empty_patient(self, extractor: FieldExtractor) -> None:
        fields = extractor.extract({})
        assert fields.first_names == set()
        assert fields.last_names == set()
        assert fields.dob == set()

    def test_extract_ignores_empty_values(self, extractor: FieldExtractor) -> None:
        patient: Dict[str, Any] = {
            "name": [{"family": "", "given": [""]}],
            "telecom": [{"system": "phone", "value": ""}],
        }
        fields = extractor.extract(patient)
        assert fields.first_names == set()
        assert fields.last_names == set()
        assert fields.phones == set()

    def test_extract_ignores_null_subfields(self, extractor: FieldExtractor) -> None:
        """Real FHIR payloads can have any of these fields present but
        explicitly `null` rather than omitted or `[]`/`""`. Caught via a live
        run against `bronze.fhir_lake.patient_4_0_0`."""
        patient: Dict[str, Any] = {
            "name": [
                {
                    "family": None,
                    "given": None,
                    "suffix": None,
                    "_nicknames": None,
                }
            ],
            "telecom": [{"system": None, "value": None}],
            "address": [{"line": None}],
            "identifier": [
                {"system": None, "value": "123", "type": None, "assigner": None}
            ],
        }
        fields = extractor.extract(patient)
        assert fields.first_names == set()
        assert fields.last_names == set()
        assert fields.suffixes == set()
        assert fields.phones == set()
        assert fields.street_lines == set()

    def test_extract_null_top_level_lists(self, extractor: FieldExtractor) -> None:
        patient: Dict[str, Any] = {
            "name": None,
            "telecom": None,
            "address": None,
            "identifier": None,
        }
        fields = extractor.extract(patient)
        assert fields.first_names == set()
        assert fields.last_names == set()
        assert fields.dob == set()


class TestFieldExtractorCmsV33Fields:
    """zip_code, insurance_member_id, insurance_subscriber_id (session 6)."""

    def test_extract_zip_code(self, extractor: FieldExtractor) -> None:
        patient: Dict[str, Any] = {
            "address": [{"line": ["123 main st"], "postalCode": "10001"}]
        }
        fields = extractor.extract(patient)
        assert "10001" in fields.zip_codes

    def test_no_zip_code_when_absent(self, extractor: FieldExtractor) -> None:
        patient: Dict[str, Any] = {"address": [{"line": ["123 main st"]}]}
        fields = extractor.extract(patient)
        assert fields.zip_codes == set()

    def test_extract_insurance_member_id_namespace_scoped(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "https://payer.example/member-id",
                    "type": {"coding": [{"code": "MB"}]},
                    "value": "M123456",
                }
            ]
        }
        fields = extractor.extract(patient)
        assert "https://payer.example/member-id|M123456" in fields.insurance_member_ids

    def test_member_id_without_namespace_is_excluded(
        self, extractor: FieldExtractor
    ) -> None:
        """Per CMS v3.3: an unscoped ID has no payer namespace to bind to."""
        patient: Dict[str, Any] = {
            "identifier": [{"type": {"coding": [{"code": "MB"}]}, "value": "M123456"}]
        }
        fields = extractor.extract(patient)
        assert fields.insurance_member_ids == set()

    def test_extract_insurance_subscriber_id_namespace_scoped(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "https://payer.example/subscriber-id",
                    "type": {"coding": [{"code": "SN"}]},
                    "value": "S987654",
                }
            ]
        }
        fields = extractor.extract(patient)
        assert (
            "https://payer.example/subscriber-id|S987654"
            in fields.insurance_subscriber_ids
        )

    def test_member_and_subscriber_id_are_distinct_fields(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "https://payer.example/x",
                    "type": {"coding": [{"code": "MB"}]},
                    "value": "M1",
                },
                {
                    "system": "https://payer.example/x",
                    "type": {"coding": [{"code": "SN"}]},
                    "value": "S1",
                },
            ]
        }
        fields = extractor.extract(patient)
        assert fields.insurance_member_ids == {"https://payer.example/x|M1"}
        assert fields.insurance_subscriber_ids == {"https://payer.example/x|S1"}


class TestFieldExtractorCmsV340Fields:
    """guardian_identity, mother_identity, birth_encounter_id,
    relationship_linkage_clinical/_self_reported (session 17)."""

    _RELATIONSHIP_LINKAGE_URL = (
        "https://cms-hte-patient-matching.icanbwell.com/fhir/StructureDefinition/"
        "relationship-linkage"
    )

    def test_extract_guardian_identity_namespace_scoped(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "urn:cms-hte:guardian",
                    "type": {"coding": [{"code": "CMS-GRDN"}]},
                    "value": "GRD001",
                }
            ]
        }
        fields = extractor.extract(patient)
        assert "urn:cms-hte:guardian|GRD001" in fields.guardian_identities

    def test_guardian_identity_without_namespace_is_excluded(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [{"type": {"coding": [{"code": "CMS-GRDN"}]}, "value": "G1"}]
        }
        fields = extractor.extract(patient)
        assert fields.guardian_identities == set()

    def test_extract_mother_identity_namespace_scoped(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "urn:cms-hte:mother",
                    "type": {"coding": [{"code": "CMS-MTHR"}]},
                    "value": "MOM001",
                }
            ]
        }
        fields = extractor.extract(patient)
        assert "urn:cms-hte:mother|MOM001" in fields.mother_identities

    def test_extract_birth_encounter_id_namespace_scoped(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "urn:hospital:abc",
                    "type": {"coding": [{"code": "CMS-BEID"}]},
                    "value": "ENC12345",
                }
            ]
        }
        fields = extractor.extract(patient)
        assert "urn:hospital:abc|ENC12345" in fields.birth_encounter_ids

    def test_birth_encounter_id_without_namespace_is_excluded(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {"type": {"coding": [{"code": "CMS-BEID"}]}, "value": "ENC1"}
            ]
        }
        fields = extractor.extract(patient)
        assert fields.birth_encounter_ids == set()

    def test_guardian_mother_and_encounter_id_are_distinct_fields(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "identifier": [
                {
                    "system": "urn:x",
                    "type": {"coding": [{"code": "CMS-GRDN"}]},
                    "value": "G1",
                },
                {
                    "system": "urn:x",
                    "type": {"coding": [{"code": "CMS-MTHR"}]},
                    "value": "M1",
                },
                {
                    "system": "urn:x",
                    "type": {"coding": [{"code": "CMS-BEID"}]},
                    "value": "E1",
                },
            ]
        }
        fields = extractor.extract(patient)
        assert fields.guardian_identities == {"urn:x|G1"}
        assert fields.mother_identities == {"urn:x|M1"}
        assert fields.birth_encounter_ids == {"urn:x|E1"}

    def test_extract_relationship_linkage_clinical(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "extension": [
                {
                    "url": self._RELATIONSHIP_LINKAGE_URL,
                    "extension": [
                        {"url": "type", "valueCode": "child-of"},
                        {"url": "source", "valueCode": "clinical"},
                    ],
                }
            ]
        }
        fields = extractor.extract(patient)
        assert fields.relationship_linkage_clinical == {"child-of"}
        assert fields.relationship_linkage_self_reported == set()

    def test_extract_relationship_linkage_self_reported(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "extension": [
                {
                    "url": self._RELATIONSHIP_LINKAGE_URL,
                    "extension": [
                        {"url": "type", "valueCode": "newborn-of"},
                        {"url": "source", "valueCode": "self-reported"},
                    ],
                }
            ]
        }
        fields = extractor.extract(patient)
        assert fields.relationship_linkage_self_reported == {"newborn-of"}
        assert fields.relationship_linkage_clinical == set()

    def test_relationship_linkage_ignores_unrelated_extensions(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "extension": [{"url": "https://example.com/some-other-extension"}]
        }
        fields = extractor.extract(patient)
        assert fields.relationship_linkage_clinical == set()
        assert fields.relationship_linkage_self_reported == set()

    def test_relationship_linkage_missing_type_or_source_is_ignored(
        self, extractor: FieldExtractor
    ) -> None:
        patient: Dict[str, Any] = {
            "extension": [
                {
                    "url": self._RELATIONSHIP_LINKAGE_URL,
                    "extension": [{"url": "type", "valueCode": "child-of"}],
                }
            ]
        }
        fields = extractor.extract(patient)
        assert fields.relationship_linkage_clinical == set()
        assert fields.relationship_linkage_self_reported == set()
