"""Data models for IAL2 token claims per CSP Payload Specification V7.1.

Handles field-name aliases across CSPs (e.g. name_first vs given_name)
and normalizes them into a single canonical representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class IAL2Address:
    """A physical address extracted from an IAL2 token.

    Attributes:
        address_line1: Primary street address.
        address_line2: Secondary address line (apt, suite, etc.).
        city: City or locality.
        state: State, province, or region.
        postal_code: ZIP or postal code.
        country: Country.
        full_address: Composite formatted address string.
    """

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    full_address: Optional[str] = None


@dataclass
class IAL2LegalId:
    """A government-issued legal identity document.

    Attributes:
        issuer: Issuing authority (e.g. state DMV, federal government).
        id_type: Type of document (e.g. drivers_license, passport).
        identifier: The document number/identifier.
    """

    issuer: Optional[str] = None
    id_type: Optional[str] = None
    identifier: Optional[str] = None


@dataclass
class IAL2Claims:
    """Normalized demographic claims from an IAL2 token.

    Fields follow the CSP Payload Specification V7.1 (Feb 2026).
    Alias resolution (e.g. given_name -> name_first) happens in from_token_claims().
    """

    # OIDC standard claims
    iss: str = ""
    sub: str = ""
    aud: str = ""
    exp: int = 0
    iat: int = 0
    jti: str = ""
    at_hash: Optional[str] = None
    auth_time: Optional[int] = None

    # Core person attributes
    name_first: str = ""
    name_middle: Optional[str] = None
    name_last: str = ""
    name_full: Optional[str] = None
    name_historical: Optional[List[str]] = None
    birth_date: str = ""
    sex_legal: Optional[str] = None

    # Address information
    address: Optional[IAL2Address] = None
    address_historical: Optional[List[IAL2Address]] = None

    # Contact information
    email: Optional[str] = None
    phone_number: Optional[str] = None
    phone_number_historical: Optional[List[str]] = None

    # Legal identifiers
    uuid: Optional[str] = None
    ssn: Optional[str] = None
    itin: Optional[str] = None
    legal_id: Optional[IAL2LegalId] = None
    suffix: Optional[str] = None

    @classmethod
    def from_token_claims(cls, claims: Dict[str, Any]) -> IAL2Claims:
        """Create an IAL2Claims instance from raw JWT claims.

        Resolves field-name aliases used by different CSPs:
          - given_name -> name_first
          - middle_name -> name_middle
          - last_name -> name_last
          - street_address -> address_line1
          - locality -> city
          - region -> state
          - postal_code / code_postal -> postal_code
          - formatted -> full_address
        """
        address = _extract_address(claims)
        historical_addresses = _extract_historical_addresses(
            claims.get("address_historical")
        )
        legal_id = _extract_legal_id(claims)

        return cls(
            # OIDC standard
            iss=claims.get("iss", ""),
            sub=claims.get("sub", ""),
            aud=claims.get("aud", ""),
            exp=claims.get("exp", 0),
            iat=claims.get("iat", 0),
            jti=claims.get("jti", ""),
            at_hash=claims.get("at_hash"),
            auth_time=claims.get("auth_time"),
            # Core person
            name_first=claims.get("name_first") or claims.get("given_name", ""),
            name_middle=claims.get("name_middle") or claims.get("middle_name"),
            name_last=claims.get("name_last") or claims.get("last_name", ""),
            name_full=claims.get("name_full"),
            name_historical=claims.get("name_historical"),
            birth_date=claims.get("birth_date") or claims.get("date_birth", ""),
            sex_legal=claims.get("sex_legal") or claims.get("gender"),
            suffix=claims.get("suffix"),
            # Address
            address=address,
            address_historical=historical_addresses,
            # Contact
            email=claims.get("email"),
            phone_number=claims.get("phone_number"),
            phone_number_historical=claims.get("phone_number_historical"),
            # Legal identifiers
            uuid=claims.get("UUID") or claims.get("uuid"),
            ssn=claims.get("ssn"),
            itin=claims.get("itin"),
            legal_id=legal_id,
        )


def _extract_address(claims: Dict[str, Any]) -> Optional[IAL2Address]:
    """Extract the primary address from claims, resolving aliases."""
    line1 = claims.get("address_line1") or claims.get("street_address")
    city = claims.get("city") or claims.get("locality")
    state = claims.get("state") or claims.get("region")
    postal = claims.get("postal_code") or claims.get("code_postal")

    if not any([line1, city, state, postal]):
        return None

    return IAL2Address(
        address_line1=line1,
        address_line2=claims.get("address_line2"),
        city=city,
        state=state,
        postal_code=postal,
        country=claims.get("country"),
        full_address=claims.get("full_address") or claims.get("formatted"),
    )


def _extract_historical_addresses(
    raw: Any,
) -> Optional[List[IAL2Address]]:
    """Parse historical addresses from the claims payload."""
    if not raw or not isinstance(raw, list):
        return None

    addresses: List[IAL2Address] = []
    for entry in raw:
        if isinstance(entry, dict):
            addresses.append(
                IAL2Address(
                    address_line1=entry.get("address_line1")
                    or entry.get("street_address"),
                    address_line2=entry.get("address_line2"),
                    city=entry.get("city") or entry.get("locality"),
                    state=entry.get("state") or entry.get("region"),
                    postal_code=entry.get("postal_code") or entry.get("code_postal"),
                    country=entry.get("country"),
                    full_address=entry.get("full_address") or entry.get("formatted"),
                )
            )
    return addresses if addresses else None


def _extract_legal_id(claims: Dict[str, Any]) -> Optional[IAL2LegalId]:
    """Extract legal identity document info from claims."""
    legal_id_raw = claims.get("legal_id") or claims.get("legal_id_issuer")
    if not legal_id_raw:
        return None

    if isinstance(legal_id_raw, dict):
        return IAL2LegalId(
            issuer=legal_id_raw.get("issuer"),
            id_type=legal_id_raw.get("type"),
            identifier=legal_id_raw.get("identifier"),
        )

    # If it's a string, treat it as the issuer identifier
    return IAL2LegalId(issuer=str(legal_id_raw))
