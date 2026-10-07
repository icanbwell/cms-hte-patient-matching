"""The institutional-address registry as FHIR R4 `Organization` resources.

One `Organization` per distinct (institution type, normalized street, ZIP5), stored as
NDJSON (one resource per line, the FHIR Bulk Data format), gzipped because the uncompressed
file is about 170 MB. `build_registry.py` writes it; `read_registry` reads it back.

Mapping (see docs/INSTITUTIONAL_ADDRESS_FEASIBILITY.md for the reasoning):

| Registry field              | FHIR element                                              |
|-----------------------------|-----------------------------------------------------------|
| name                        | `Organization.name`                                       |
| street, city, state, zip    | `Organization.address[0]` (`line`, `city`, `state`,       |
|                             | `postalCode`; `use=work`, `type=physical`)                |
| institution_type            | `Organization.type[1]` (our `institution-type` code       |
|                             | system) plus a coarse HL7 `organization-type` in `type[0]`|
| (source, source ID) pairs   | `Organization.identifier` (system per source)             |
| match_policy                | extension `institutional-address-match-policy` (code)     |
| data_collected              | extension `data-collected` (date, or a year)              |
| beds                        | extension `beds` (integer; omitted when not numeric)      |
| every source that lists it  | extension `source` (code), repeated                       |
| match_street, match_zip5    | extension `match-key` (complex: `street`, `zip5`)         |

The registry-specific fields have no standard FHIR home, so they are extensions under the
same base URL the engine already uses for its own (`field_extractor.py`). None of these
extension, code-system or naming-system URLs is published as a conformance resource yet.
`match-key` is derived from the address by `build_registry.address_key`; it is stored so a
reader can look an address up without re-implementing that normalization, and the resource
`id` is a hash of (institution type, match key) so it is stable across rebuilds.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

BASE_URL = "https://cms-hte-patient-matching.icanbwell.com/fhir"
ORGANIZATION_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/organization-type"
INSTITUTION_TYPE_SYSTEM = f"{BASE_URL}/CodeSystem/institution-type"
SOURCE_SYSTEM_PREFIX = f"{BASE_URL}/NamingSystem/institutional-address-source/"
MATCH_POLICY_URL = f"{BASE_URL}/StructureDefinition/institutional-address-match-policy"
DATA_COLLECTED_URL = f"{BASE_URL}/StructureDefinition/data-collected"
BEDS_URL = f"{BASE_URL}/StructureDefinition/beds"
SOURCE_URL = f"{BASE_URL}/StructureDefinition/source"
MATCH_KEY_URL = f"{BASE_URL}/StructureDefinition/match-key"

# Coarse HL7 organization-type per institution type; anything not listed is "other".
# A judgement call, not a spec requirement: licensed care facilities are providers,
# prisons are government, campuses are educational.
ORGANIZATION_TYPE = {
    "nursing_home": "prov",
    "hospice": "prov",
    "hospital": "prov",
    "psychiatric_hospital": "prov",
    "long_term_hospital": "prov",
    "assisted_living": "prov",
    "correctional": "govt",
    "federal_correctional": "govt",
    "higher_education_campus": "edu",
}
DEFAULT_ORGANIZATION_TYPE = "other"


@dataclass(frozen=True)
class RegistryEntry:
    """One registry row: a facility address of one institution type, with every source."""

    institution_type: str
    match_policy: str
    name: str
    street: str
    city: str
    state: str
    zip: str
    beds: Optional[int]
    data_collected: str  # ISO date, or a year
    match_street: str
    match_zip5: str
    sources: Tuple[Tuple[str, str], ...]  # (source, source_id); source_id may be ""


def organization_id(institution_type: str, match_street: str, match_zip5: str) -> str:
    """Stable resource id: a hash of the registry's own key (FHIR ids allow [A-Za-z0-9.-])."""
    key = f"{institution_type}|{match_street}|{match_zip5}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()  # nosec B324 - an id, not security


def to_organization(entry: RegistryEntry) -> Dict[str, Any]:
    """Build the FHIR R4 Organization resource for `entry`."""
    extensions: List[Dict[str, Any]] = [
        {"url": MATCH_POLICY_URL, "valueCode": entry.match_policy},
        {"url": DATA_COLLECTED_URL, "valueDate": entry.data_collected},
    ]
    if entry.beds is not None:
        extensions.append({"url": BEDS_URL, "valueInteger": entry.beds})
    extensions.extend(
        {"url": SOURCE_URL, "valueCode": source}
        for source in sorted({source for source, _ in entry.sources})
    )
    extensions.append(
        {
            "url": MATCH_KEY_URL,
            "extension": [
                {"url": "street", "valueString": entry.match_street},
                {"url": "zip5", "valueString": entry.match_zip5},
            ],
        }
    )
    return {
        "resourceType": "Organization",
        "id": organization_id(
            entry.institution_type, entry.match_street, entry.match_zip5
        ),
        "extension": extensions,
        "identifier": [
            {"system": f"{SOURCE_SYSTEM_PREFIX}{source}", "value": source_id}
            for source, source_id in entry.sources
            if source_id
        ],
        "active": True,
        "type": [
            {
                "coding": [
                    {
                        "system": ORGANIZATION_TYPE_SYSTEM,
                        "code": ORGANIZATION_TYPE.get(
                            entry.institution_type, DEFAULT_ORGANIZATION_TYPE
                        ),
                    }
                ]
            },
            {
                "coding": [
                    {
                        "system": INSTITUTION_TYPE_SYSTEM,
                        "code": entry.institution_type,
                    }
                ]
            },
        ],
        "name": entry.name,
        "address": [
            {
                "use": "work",
                "type": "physical",
                "line": [entry.street],
                "city": entry.city,
                "state": entry.state,
                "postalCode": entry.zip,
            }
        ],
    }


def from_organization(resource: Dict[str, Any]) -> RegistryEntry:
    """Read a registry `Organization` back into a `RegistryEntry` (inverse of `to_organization`).

    Raises ValueError for a resource that is not one of ours (wrong type, missing the
    institution-type coding or the match-key extension).
    """
    if resource.get("resourceType") != "Organization":
        raise ValueError(f"not an Organization: {resource.get('resourceType')!r}")
    institution_type = next(
        (
            c["code"]
            for t in resource.get("type", [])
            for c in t.get("coding", [])
            if c.get("system") == INSTITUTION_TYPE_SYSTEM
        ),
        None,
    )
    if institution_type is None:
        raise ValueError("Organization has no institution-type coding")
    ext = resource.get("extension", [])

    def value(url: str, key: str) -> Optional[Any]:
        return next((e[key] for e in ext if e.get("url") == url and key in e), None)

    match_key = next((e for e in ext if e.get("url") == MATCH_KEY_URL), None)
    if match_key is None:
        raise ValueError("Organization has no match-key extension")
    key = {e["url"]: e["valueString"] for e in match_key.get("extension", [])}
    address = resource["address"][0]
    # Every identifier is one (source, ID) pair; a source can list several IDs at one
    # address. A source with an extension but no identifier had no ID of its own.
    pairs = {
        (i["system"][len(SOURCE_SYSTEM_PREFIX) :], i["value"])
        for i in resource.get("identifier", [])
        if i.get("system", "").startswith(SOURCE_SYSTEM_PREFIX)
    }
    with_id = {source for source, _ in pairs}
    pairs |= {
        (e["valueCode"], "")
        for e in ext
        if e.get("url") == SOURCE_URL and e["valueCode"] not in with_id
    }
    sources = tuple(sorted(pairs))
    return RegistryEntry(
        institution_type=institution_type,
        match_policy=value(MATCH_POLICY_URL, "valueCode") or "",
        name=resource.get("name", ""),
        street=address.get("line", [""])[0],
        city=address.get("city", ""),
        state=address.get("state", ""),
        zip=address.get("postalCode", ""),
        beds=value(BEDS_URL, "valueInteger"),
        data_collected=value(DATA_COLLECTED_URL, "valueDate") or "",
        match_street=key.get("street", ""),
        match_zip5=key.get("zip5", ""),
        sources=sources,
    )


def write_registry(entries: Iterable[RegistryEntry], path: Path) -> int:
    """Write `entries` as gzipped NDJSON, one Organization per line; return the count.

    The gzip header carries no filename or timestamp, so the same entries always produce
    byte-identical output.
    """
    count = 0
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="\n") as out:
                for entry in entries:
                    out.write(
                        json.dumps(
                            to_organization(entry),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
                    out.write("\n")
                    count += 1
    return count


def read_resources(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield each Organization in a registry file as a dict."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def read_registry(path: Path) -> Iterator[RegistryEntry]:
    """Yield each registry file line as a `RegistryEntry`."""
    for resource in read_resources(path):
        yield from_organization(resource)
