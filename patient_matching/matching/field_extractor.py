"""Extract canonical field values from a normalized FHIR Patient resource.

Per Core Principle 10: each field represents a set of ALL known values
(current and historical). A match on any known value satisfies the field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class PatientFields:
    """Canonical field values extracted from a FHIR Patient.

    Each field is a set because matching evaluates against ALL known
    values (current and historical) per Core Principle 10.

    Attributes:
        first_names: All given names (including nicknames).
        last_names: All family names (including maiden/previous).
        suffixes: All generational suffixes.
        dob: Date of birth (single value, set for consistency).
        street_lines: All street address lines.
        phones: All phone numbers (E.164).
        emails: All email addresses.
        ssn_last4: Last 4 digits of SSN.
        itin_last4: Last 4 digits of ITIN.
        mbi: Medicare Beneficiary Identifier.
        legal_ids: Legal ID values (DL, passport) with namespace.
        namespace_ids: Namespace-bound unique identifiers.
    """

    first_names: Set[str] = field(default_factory=set)
    last_names: Set[str] = field(default_factory=set)
    suffixes: Set[str] = field(default_factory=set)
    dob: Set[str] = field(default_factory=set)
    street_lines: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    emails: Set[str] = field(default_factory=set)
    ssn_last4: Set[str] = field(default_factory=set)
    itin_last4: Set[str] = field(default_factory=set)
    mbi: Set[str] = field(default_factory=set)
    legal_ids: Set[str] = field(default_factory=set)
    namespace_ids: Set[str] = field(default_factory=set)

    def get_values(self, field_name: str) -> Set[str]:
        """Get the set of values for a canonical field name."""
        mapping = {
            "first_name": self.first_names,
            "last_name": self.last_names,
            "dob": self.dob,
            "street_line": self.street_lines,
            "phone": self.phones,
            "email": self.emails,
            "ssn_last4": self.ssn_last4,
            "itin_last4": self.itin_last4,
            "mbi": self.mbi,
            "legal_id": self.legal_ids,
            "namespace_id": self.namespace_ids,
        }
        return mapping.get(field_name, set())

    def has_field(self, field_name: str) -> bool:
        """Check if any values exist for a canonical field."""
        return len(self.get_values(field_name)) > 0


# FHIR identifier system URIs for categorization
_SSN_SYSTEM = "http://hl7.org/fhir/sid/us-ssn"
_ITIN_SYSTEM = "urn:oid:2.16.840.1.113883.4.4"
_MBI_SYSTEM = "http://hl7.org/fhir/sid/us-mbi"
_DL_CODE = "DL"
_NAMESPACE_CODES = {"RI", "MR", "AN", "PI"}


class FieldExtractor:
    """Extracts canonical field values from a normalized FHIR Patient."""

    def extract(self, patient: Dict[str, Any]) -> PatientFields:
        """Extract all matching-relevant fields from a FHIR Patient.

        Assumes the patient has already been normalized (lowercase,
        diacritics folded, punctuation removed, etc.).

        Args:
            patient: A normalized FHIR R4 Patient resource dict.

        Returns:
            A PatientFields with sets of all known values per field.
        """
        fields = PatientFields()

        self._extract_names(patient, fields)
        self._extract_birth_date(patient, fields)
        self._extract_telecoms(patient, fields)
        self._extract_addresses(patient, fields)
        self._extract_identifiers(patient, fields)

        return fields

    @staticmethod
    def _extract_names(patient: Dict[str, Any], fields: PatientFields) -> None:
        """Extract name components from all HumanName entries."""
        for name_entry in patient.get("name") or []:
            # Family names
            family = name_entry.get("family") or ""
            if family:
                fields.last_names.add(family)

            # Given names — first given is the "first name"
            given_list: List[str] = name_entry.get("given") or []
            for g in given_list:
                if g:
                    fields.first_names.add(g)

            # Nicknames (attached by normalization as _nicknames)
            for nick in name_entry.get("_nicknames") or []:
                if nick:
                    fields.first_names.add(nick)

            # Suffixes
            for s in name_entry.get("suffix") or []:
                if s:
                    fields.suffixes.add(s)

    @staticmethod
    def _extract_birth_date(patient: Dict[str, Any], fields: PatientFields) -> None:
        """Extract date of birth."""
        dob = patient.get("birthDate") or ""
        if dob:
            fields.dob.add(dob)

    @staticmethod
    def _extract_telecoms(patient: Dict[str, Any], fields: PatientFields) -> None:
        """Extract phone numbers and email addresses."""
        for telecom in patient.get("telecom") or []:
            system = telecom.get("system") or ""
            value = telecom.get("value") or ""
            if not value:
                continue

            if system == "phone":
                fields.phones.add(value)
            elif system == "email":
                fields.emails.add(value)

    @staticmethod
    def _extract_addresses(patient: Dict[str, Any], fields: PatientFields) -> None:
        """Extract street lines from all addresses."""
        for addr in patient.get("address") or []:
            for line in addr.get("line") or []:
                if line:
                    fields.street_lines.add(line)

    @staticmethod
    def _extract_identifiers(patient: Dict[str, Any], fields: PatientFields) -> None:
        """Extract structured identifiers (SSN last 4, ITIN, MBI, etc.)."""
        for ident in patient.get("identifier") or []:
            system = ident.get("system") or ""
            value = ident.get("value") or ""
            if not value:
                continue

            type_codings = (ident.get("type") or {}).get("coding") or []
            codes = {c.get("code") or "" for c in type_codings}

            if system == _SSN_SYSTEM:
                # Only last 4 digits
                last4 = value.replace("-", "").replace(" ", "")[-4:]
                if len(last4) == 4:
                    fields.ssn_last4.add(last4)
            elif system == _ITIN_SYSTEM:
                last4 = value.replace("-", "").replace(" ", "")[-4:]
                if len(last4) == 4:
                    fields.itin_last4.add(last4)
            elif system == _MBI_SYSTEM:
                fields.mbi.add(value)
            elif _DL_CODE in codes:
                # Legal ID: combine assigner namespace + value
                assigner = (ident.get("assigner") or {}).get("display") or ""
                if assigner:
                    fields.legal_ids.add(f"{assigner}|{value}")
                else:
                    fields.legal_ids.add(value)
            elif codes & _NAMESPACE_CODES:
                # Namespace-bound identifiers: system + value
                if system:
                    fields.namespace_ids.add(f"{system}|{value}")
                else:
                    fields.namespace_ids.add(value)
            else:
                # Unknown identifier type with a system = namespace ID
                if system:
                    fields.namespace_ids.add(f"{system}|{value}")
