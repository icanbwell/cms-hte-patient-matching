"""Converts IAL2 demographic claims into a FHIR R4 Patient resource.

Produces a dict conforming to the FHIR R4 Patient resource structure
(https://hl7.org/fhir/R4/patient.html).
"""

from __future__ import annotations

from typing import Any, Dict, List

from fhirschemapy.R4B.patient import Patient

from .claims_model import IAL2Address, IAL2Claims

# Mapping from CSP sex_legal values to FHIR administrative gender codes
_SEX_TO_FHIR_GENDER: Dict[str, str] = {
    "male": "male",
    "m": "male",
    "female": "female",
    "f": "female",
    "other": "other",
    "unknown": "unknown",
}


class IAL2ToFhirConverter:
    """Converts IAL2Claims into a FHIR R4 Patient resource dictionary."""

    def convert(self, claims: IAL2Claims) -> Dict[str, Any]:
        """Convert IAL2 claims to a FHIR Patient resource.

        Args:
            claims: The normalized IAL2 demographic claims.

        Returns:
            A dictionary representing a FHIR R4 Patient resource, validated
            through fhirschemapy.

        Raises:
            pydantic.ValidationError: If the built resource doesn't conform
                to the FHIR R4 Patient schema.
        """
        patient: Dict[str, Any] = {
            "resourceType": "Patient",
        }

        # Identifiers
        identifiers = self._build_identifiers(claims)
        if identifiers:
            patient["identifier"] = identifiers

        # Name
        names = self._build_names(claims)
        if names:
            patient["name"] = names

        # Birth date
        if claims.birth_date:
            patient["birthDate"] = claims.birth_date

        # Gender
        if claims.sex_legal:
            gender = _SEX_TO_FHIR_GENDER.get(claims.sex_legal.lower(), "unknown")
            patient["gender"] = gender

        # Telecom (email, phone)
        telecoms = self._build_telecoms(claims)
        if telecoms:
            patient["telecom"] = telecoms

        # Address
        addresses = self._build_addresses(claims)
        if addresses:
            patient["address"] = addresses

        validated = Patient.model_validate(patient)
        result: Dict[str, Any] = validated.model_dump(
            exclude_none=True, by_alias=True
        )
        return result

    @staticmethod
    def _build_identifiers(claims: IAL2Claims) -> List[Dict[str, Any]]:
        """Build FHIR Identifier entries from claims."""
        identifiers: List[Dict[str, Any]] = []

        if claims.uuid:
            identifiers.append(
                {
                    "system": claims.iss,
                    "value": claims.uuid,
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                "code": "RI",
                                "display": "Resource identifier",
                            }
                        ]
                    },
                }
            )

        if claims.ssn_itin:
            identifiers.append(
                {
                    "system": "http://hl7.org/fhir/sid/us-ssn",
                    "value": claims.ssn_itin,
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                "code": "SS",
                                "display": "Social Security number",
                            }
                        ]
                    },
                }
            )

        if claims.legal_id:
            lid = claims.legal_id
            identifier_entry: Dict[str, Any] = {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "DL",
                            "display": "Driver's license number",
                        }
                    ]
                },
            }
            if lid.identifier:
                identifier_entry["value"] = lid.identifier
            if lid.issuer:
                identifier_entry["assigner"] = {"display": lid.issuer}
            identifiers.append(identifier_entry)

        return identifiers

    @staticmethod
    def _build_names(claims: IAL2Claims) -> List[Dict[str, Any]]:
        """Build FHIR HumanName entries from claims."""
        names: List[Dict[str, Any]] = []

        # Official / current name
        official: Dict[str, Any] = {"use": "official"}
        if claims.name_last:
            official["family"] = claims.name_last
        given: List[str] = []
        if claims.name_first:
            given.append(claims.name_first)
        if claims.name_middle:
            given.append(claims.name_middle)
        if given:
            official["given"] = given
        if claims.suffix:
            official["suffix"] = [claims.suffix]
        if claims.name_full:
            official["text"] = claims.name_full
        if official.get("family") or official.get("given"):
            names.append(official)

        # Historical names
        if claims.name_historical:
            for hist_name in claims.name_historical:
                names.append(
                    {
                        "use": "old",
                        "text": hist_name,
                    }
                )

        return names

    @staticmethod
    def _build_telecoms(claims: IAL2Claims) -> List[Dict[str, Any]]:
        """Build FHIR ContactPoint entries from claims."""
        telecoms: List[Dict[str, Any]] = []

        if claims.email:
            telecoms.append(
                {
                    "system": "email",
                    "value": claims.email,
                    "use": "home",
                }
            )

        if claims.phone_number:
            telecoms.append(
                {
                    "system": "phone",
                    "value": claims.phone_number,
                    "use": "mobile",
                }
            )

        if claims.phone_number_historical:
            for phone in claims.phone_number_historical:
                telecoms.append(
                    {
                        "system": "phone",
                        "value": phone,
                        "use": "old",
                    }
                )

        return telecoms

    @staticmethod
    def _build_addresses(claims: IAL2Claims) -> List[Dict[str, Any]]:
        """Build FHIR Address entries from claims."""
        addresses: List[Dict[str, Any]] = []

        if claims.address:
            addresses.append(_address_to_fhir(claims.address, use="home"))

        if claims.address_historical:
            for hist_addr in claims.address_historical:
                addresses.append(_address_to_fhir(hist_addr, use="old"))

        return addresses


def _address_to_fhir(addr: IAL2Address, *, use: str) -> Dict[str, Any]:
    """Convert an IAL2Address to a FHIR Address dict."""
    fhir_addr: Dict[str, Any] = {"use": use}

    lines: List[str] = []
    if addr.address_line1:
        lines.append(addr.address_line1)
    if addr.address_line2:
        lines.append(addr.address_line2)
    if lines:
        fhir_addr["line"] = lines

    if addr.city:
        fhir_addr["city"] = addr.city
    if addr.state:
        fhir_addr["state"] = addr.state
    if addr.postal_code:
        fhir_addr["postalCode"] = addr.postal_code
    if addr.country:
        fhir_addr["country"] = addr.country
    if addr.full_address:
        fhir_addr["text"] = addr.full_address

    return fhir_addr
