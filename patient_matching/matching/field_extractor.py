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
        zip_codes: 5-digit ZIP codes from all addresses (CMS v3.3).
        insurance_member_ids: Payer-namespace-scoped, individual-level
            insurance Member IDs (CMS v3.3).
        insurance_subscriber_ids: Payer-namespace-scoped, policyholder-level
            insurance Subscriber IDs (CMS v3.3).
        relationship_linkage_clinical: Relationship-type claims (e.g.
            "child-of", "newborn-of") sourced from a clinical record (CMS
            v3.4.0, session 17).
        relationship_linkage_self_reported: Same shape, self-reported/intake
            source (CMS v3.4.0) - defined for completeness; no rule in this
            repo currently uses it (see collision.py's FIELD_U_PROBS comment).
        guardian_identities: Namespace-scoped references to a guardian's own,
            separately-matched identity (CMS v3.4.0 Rule C2-39).
        mother_identities: Namespace-scoped references to a mother's own,
            separately-matched identity (CMS v3.4.0 Rule C2-40).
        birth_encounter_ids: Namespace-scoped, per-encounter birth identifiers
            (CMS v3.4.0 Rule C2-40).
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
    zip_codes: Set[str] = field(default_factory=set)
    insurance_member_ids: Set[str] = field(default_factory=set)
    insurance_subscriber_ids: Set[str] = field(default_factory=set)
    relationship_linkage_clinical: Set[str] = field(default_factory=set)
    relationship_linkage_self_reported: Set[str] = field(default_factory=set)
    guardian_identities: Set[str] = field(default_factory=set)
    mother_identities: Set[str] = field(default_factory=set)
    birth_encounter_ids: Set[str] = field(default_factory=set)

    @property
    def relationship_linkage_child_of_clinical(self) -> Set[str]:
        """Clinical relationship claims narrowed to specifically "child-of".

        Rule C2-39 requires this exact relationship type, not merely "some
        clinical relationship claim was made" (adversarial-review finding:
        the un-narrowed `relationship_linkage_clinical` field matches on
        ANY code via ordinary set-overlap semantics, so an arbitrary or
        wrong-typed claim, e.g. "spouse-of", would satisfy the rule)."""
        return {v for v in self.relationship_linkage_clinical if v == "child-of"}

    @property
    def relationship_linkage_newborn_of_clinical(self) -> Set[str]:
        """Clinical relationship claims narrowed to specifically "newborn-of".

        Rule C2-40's equivalent of relationship_linkage_child_of_clinical -
        see that property's docstring."""
        return {v for v in self.relationship_linkage_clinical if v == "newborn-of"}

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
            "zip_code": self.zip_codes,
            "insurance_member_id": self.insurance_member_ids,
            "insurance_subscriber_id": self.insurance_subscriber_ids,
            "relationship_linkage_clinical": self.relationship_linkage_clinical,
            "relationship_linkage_self_reported": self.relationship_linkage_self_reported,
            "relationship_linkage_child_of_clinical": self.relationship_linkage_child_of_clinical,
            "relationship_linkage_newborn_of_clinical": self.relationship_linkage_newborn_of_clinical,
            "guardian_identity": self.guardian_identities,
            "mother_identity": self.mother_identities,
            "birth_encounter_id": self.birth_encounter_ids,
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
# HL7 v2-0203 Identifier Type codes for insurance identifiers (CMS v3.3).
_MEMBER_ID_CODE = "MB"
_SUBSCRIBER_ID_CODE = "SN"
# CMS v3.4.0 (session 17): no standard HL7 v2-0203 code exists for "a
# reference to a different person's already-matched identity" (unlike MB/SN
# above, which are real codes) - these are repo-defined codes, documented
# here rather than silently invented.
_GUARDIAN_IDENTITY_CODE = "CMS-GRDN"
_MOTHER_IDENTITY_CODE = "CMS-MTHR"
_BIRTH_ENCOUNTER_ID_CODE = "CMS-BEID"
# Not a published/registered FHIR extension - a repo-internal convention
# (session 17) for a relationship claim, since Patient.link's type enum
# (replaced-by/replaces/refer/seealso) has no family-relationship semantics
# and Patient.contact isn't a Reference to another Patient resource.
_RELATIONSHIP_LINKAGE_EXTENSION_URL = (
    "https://cms-hte-patient-matching.icanbwell.com/fhir/StructureDefinition/"
    "relationship-linkage"
)


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
        self._extract_relationship_linkage(patient, fields)

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
        """Extract street lines and ZIP codes from all addresses."""
        for addr in patient.get("address") or []:
            for line in addr.get("line") or []:
                if line:
                    fields.street_lines.add(line)
            postal_code = addr.get("postalCode", "")
            if postal_code:
                fields.zip_codes.add(postal_code)

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
            elif _MEMBER_ID_CODE in codes:
                # Payer-namespace-scoped per CMS v3.3: system (the payer's
                # namespace) + value. A bare value with no namespace is
                # excluded, per "the bare subscriber base value without
                # dependent suffix SHALL NOT be treated as a Member ID" -
                # the same principle applies to an unscoped Member ID.
                if system:
                    fields.insurance_member_ids.add(f"{system}|{value}")
            elif _SUBSCRIBER_ID_CODE in codes:
                if system:
                    fields.insurance_subscriber_ids.add(f"{system}|{value}")
            elif _GUARDIAN_IDENTITY_CODE in codes:
                # CMS v3.4.0 Rule C2-39: a reference to the guardian's own,
                # separately-matched identity. Namespace-scoped like the
                # identifiers above - an unscoped reference is excluded, same
                # principle as Member/Subscriber ID above (an unscoped value
                # can't be trusted to mean the same guardian across systems).
                if system:
                    fields.guardian_identities.add(f"{system}|{value}")
            elif _MOTHER_IDENTITY_CODE in codes:
                # CMS v3.4.0 Rule C2-40: same pattern, for the mother's
                # separately-matched identity.
                if system:
                    fields.mother_identities.add(f"{system}|{value}")
            elif _BIRTH_ENCOUNTER_ID_CODE in codes:
                # CMS v3.4.0 Rule C2-40: must be namespace-scoped to be usable
                # at all - this makes a shared facility-wide ID structurally
                # distinguishable from a genuine per-encounter one *if* the
                # source data tags them differently, but doesn't itself
                # verify per-encounter uniqueness (a data-quality property of
                # whatever feeds this field).
                if system:
                    fields.birth_encounter_ids.add(f"{system}|{value}")
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

    @staticmethod
    def _extract_relationship_linkage(
        patient: Dict[str, Any], fields: PatientFields
    ) -> None:
        """Extract Relationship Linkage claims (CMS v3.4.0, session 17).

        Represented as a Patient extension, not an identifier - this
        describes a relationship *claim* (e.g. "child-of", "newborn-of"),
        not an identity. Not a published/registered FHIR extension; see
        _RELATIONSHIP_LINKAGE_EXTENSION_URL's definition for why no standard
        element fits.
        """
        for ext in patient.get("extension") or []:
            if ext.get("url") != _RELATIONSHIP_LINKAGE_EXTENSION_URL:
                continue

            sub_extensions = ext.get("extension") or []
            relationship_type = ""
            source = ""
            for sub in sub_extensions:
                sub_url = sub.get("url") or ""
                if sub_url == "type":
                    relationship_type = sub.get("valueCode") or ""
                elif sub_url == "source":
                    source = sub.get("valueCode") or ""

            if not relationship_type or not source:
                continue

            if source == "clinical":
                fields.relationship_linkage_clinical.add(relationship_type)
            elif source == "self-reported":
                fields.relationship_linkage_self_reported.add(relationship_type)
