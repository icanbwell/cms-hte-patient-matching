"""Tests for PatientFields and FieldExtractor."""

import pytest

from patient_matching.matching.field_extractor import FieldExtractor, PatientFields


@pytest.fixture
def extractor():
    return FieldExtractor()


@pytest.fixture
def full_patient():
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
    def test_get_values_known_field(self):
        fields = PatientFields(first_names={"john", "johnny"})
        assert fields.get_values("first_name") == {"john", "johnny"}

    def test_get_values_unknown_field(self):
        fields = PatientFields()
        assert fields.get_values("nonexistent") == set()

    def test_has_field_true(self):
        fields = PatientFields(dob={"1990-01-15"})
        assert fields.has_field("dob") is True

    def test_has_field_false(self):
        fields = PatientFields()
        assert fields.has_field("dob") is False


class TestFieldExtractor:
    def test_extract_first_names(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "john" in fields.first_names
        assert "michael" in fields.first_names
        assert "johnny" in fields.first_names  # from _nicknames

    def test_extract_last_names(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "smith" in fields.last_names
        assert "doe" in fields.last_names

    def test_extract_suffixes(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "jr" in fields.suffixes

    def test_extract_dob(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert fields.dob == {"1990-01-15"}

    def test_extract_phones(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "+12125551234" in fields.phones
        assert "+12125559999" in fields.phones

    def test_extract_emails(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "john@gmail.com" in fields.emails

    def test_extract_street_lines(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "123 main st" in fields.street_lines
        assert "apt 4" in fields.street_lines
        assert "456 oak ave" in fields.street_lines

    def test_extract_ssn_last4(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "6789" in fields.ssn_last4

    def test_extract_itin_last4(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "1234" in fields.itin_last4

    def test_extract_mbi(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "1EG4TE5MK73" in fields.mbi

    def test_extract_legal_ids(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "CA-DMV|D12345678" in fields.legal_ids

    def test_extract_namespace_ids(self, extractor, full_patient):
        fields = extractor.extract(full_patient)
        assert "urn:hospital:abc|MRN001" in fields.namespace_ids

    def test_extract_empty_patient(self, extractor):
        fields = extractor.extract({})
        assert fields.first_names == set()
        assert fields.last_names == set()
        assert fields.dob == set()

    def test_extract_ignores_empty_values(self, extractor):
        patient = {
            "name": [{"family": "", "given": [""]}],
            "telecom": [{"system": "phone", "value": ""}],
        }
        fields = extractor.extract(patient)
        assert fields.first_names == set()
        assert fields.last_names == set()
        assert fields.phones == set()
