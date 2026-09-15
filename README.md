# patient_matching

An open-source Python implementation of the [CMS Patient Matching Proposal v3.2.2](https://confluence.hl7.org/display/PA/Patient+Matching), providing deterministic patient matching using 30 approved Category 1 (flat) Table 2 field combination rules plus 8 Category 2 (household/individual two-step) rules, with support for IAL2 identity-proofed tokens, FHIR R4 Patient resources, and configurable fuzzy matching.

## Overview

The CMS Patient Matching Proposal defines a standardized approach to matching patients across healthcare systems. This library implements:

- **38 Table 2 matching rules** (30 Category 1 flat + 8 Category 2 household/individual) with exact and fuzzy field comparisons
- **IAL2 token extraction** — verify JWT tokens from Credential Service Providers (CSPs) and convert to FHIR Patient resources
- **Demographic normalization** — text normalization, nickname expansion, E.164 phone formatting, USPS address standardization, placeholder detection
- **FHIR R4 integration** — fetch patients from FHIR servers with OAuth2, paginate through Bundles
- **Patient cache** — pluggable backend (in-process DuckDB, or MongoDB Atlas Search for shared/multi-replica deployments) with field-level indexing and fuzzy search
- **Confidence scoring** — based on P(collision) values from Table 2 rules

This is a pure Python library with no HTTP layer of its own — [`cms-hte-patient-matching-service`](https://github.com/icanbwell/cms-hte-patient-matching-service) wraps `PatientMatcherService`/`MatchingEngine` as a production HTTP microservice.

## Architecture

```
                          ┌─────────────────┐
                          │ PatientMatcher   │
                          │    Service       │
                          └──┬─────┬─────┬──┘
                             │     │     │
                ┌────────────┘     │     └────────────┐
                │                  │                   │
       ┌────────▼───────┐  ┌──────▼──────┐  ┌────────▼────────┐
       │ IAL2 Extractor  │  │ Normalizer  │  │ Matching Engine │
       │ (JWT → FHIR)   │  │ (A.1–D.6)  │  │ (38 Rules)      │
       └────────────────┘  └─────────────┘  └────────┬────────┘
                                                      │
                                             ┌────────▼────────┐
                                             │  Cache Backend   │
                                             │ (DuckDB or Mongo)│
                                             └────────┬────────┘
                                                      │
                                             ┌────────▼────────┐
                                             │  FHIR Client     │
                                             │  (fetch + OAuth) │
                                             └─────────────────┘
```

## Installation

```bash
pip install cms-hte-patient-matching
```

Or install from source:

```bash
git clone https://github.com/icanbwell/cms-hte-patient-matching.git
cd cms-hte-patient-matching
pip install -e .
```

### Optional Dependencies

The core package has minimal dependencies. Install extras for specific features:

```bash
# FHIR client with OAuth
pip install cms-hte-patient-matching[fhir]    # httpx, fhirschemapy

# DuckDB patient cache (single process/replica)
pip install cms-hte-patient-matching[cache]   # duckdb, rapidfuzz

# MongoDB Atlas Search patient cache (shared cache across replicas)
pip install cms-hte-patient-matching[mongo]   # pymongo

# Scheduled cache refresh
pip install cms-hte-patient-matching[scheduler]  # apscheduler

# All features
pip install cms-hte-patient-matching[all]
```

## Quick Start

### Match a FHIR Patient Against a Cache

```python
import asyncio

from patient_matching.cache import DuckDBCache, CacheMatchingBackend, CacheManager
from patient_matching.fhir_client import FhirClient, FhirClientConfig
from patient_matching.matching import MatchingEngine
from patient_matching.normalization import NormalizationManager


async def main() -> None:
    # 1. Set up the patient cache
    cache = DuckDBCache()  # in-memory DuckDB

    # 2. Connect to a FHIR server and build the cache
    fhir_client = FhirClient(FhirClientConfig(base_url="https://fhir.example.com/r4"))
    normalizer = NormalizationManager()
    cache_manager = CacheManager(
        fhir_client=fhir_client,
        cache=cache,
        normalizer=normalizer,
    )
    await cache_manager.build_cache()

    # 3. Set up the matching engine
    backend = CacheMatchingBackend(cache)
    engine = MatchingEngine(backend=backend)

    # 4. Match a patient
    query_patient = {
        "resourceType": "Patient",
        "name": [{"family": "Smith", "given": ["John"]}],
        "birthDate": "1990-01-15",
        "telecom": [{"system": "phone", "value": "+12125551234"}],
    }

    normalized = normalizer.normalize(query_patient)
    result = await engine.match(normalized)

    print(result.outcome)           # MatchOutcome.MATCH
    print(result.matched_rule_id)   # e.g., "rule_02"
    print(result.match_type)        # "exact" or "fuzzy"


asyncio.run(main())
```

All `CacheBackend`/`MatchingBackend`/`MatchingEngine`/`CacheManager`/
`PatientMatcherService` methods are `async def` (including `DuckDBCache`'s,
even though it has no real I/O to yield on) so that a network-backed
backend like `MongoAtlasCache` never blocks the event loop for the
duration of a round-trip -- see
[Choosing a Cache Backend](#choosing-a-cache-backend) below.

### Choosing a Cache Backend

Both backends implement the same `CacheBackend` interface (`upsert_patients`,
`search_by_field`, `get_patient`, `count`, `clear`), so `CacheMatchingBackend`
and `CacheManager` work identically regardless of which one you pick.

| | `DuckDBCache` | `MongoAtlasCache` |
|---|---|---|
| Install extra | `[cache]` (`duckdb`, `rapidfuzz`) | `[mongo]` (`pymongo`) |
| Storage | In-process, one cache per replica | Shared MongoDB database, one cache for all replicas |
| Fuzzy search | In-process Damerau-Levenshtein (`rapidfuzz`) | Network round-trip per call via Atlas `$search` |
| When to use it | Default choice — a single process/replica, or where per-request latency matters more than cache consistency across replicas | Multiple service replicas (e.g. behind a Kubernetes HPA) that need to share one candidate store instead of duplicating the upstream FHIR load N times |
| Index setup required | None — `CREATE INDEX IF NOT EXISTS` runs automatically in `DuckDBCache.__init__` | Two regular indexes are created automatically (`(field_name, value)` and `patient_id`); the **Atlas Search index is not** — see below |

**Use `DuckDBCache`** (no extra setup):

```python
from patient_matching.cache import DuckDBCache

cache = DuckDBCache()  # in-memory; pass database="/path/to/file.duckdb" to persist
```

**Use `MongoAtlasCache`** (requires a MongoDB Atlas cluster, or the
`mongodb-atlas-local` Docker image for local dev/testing):

```python
import os

from patient_matching.cache.mongo_atlas_cache import MongoAtlasCache

cache = MongoAtlasCache(
    connection_string=os.environ["MONGO_ATLAS_URI"],  # e.g. mongodb+srv://<host>/...
    database="patient_cache",
)
```

`MongoAtlasCache` additionally needs an **Atlas Search index** on the
`field_values` collection before fuzzy search will return results (exact
search works without it). This is a cluster-admin action, not something the
application creates for you:

- Definition: `patient_matching/cache/mongo_atlas_index.json` (loadable via
  `mongo_atlas_cache.search_index_definition()`).
- Create it once per environment via the Atlas UI ("Search" tab on the
  cluster), the Atlas Admin API, or `pymongo`'s
  `collection.create_search_index(SearchIndexModel(...))` using that same
  definition.
- Until the index exists (or while it's still building), fuzzy search
  degrades gracefully to an empty result — matching stays correct for the
  exact-match path, but silently misses fuzzy candidates, so confirm the
  index is `queryable` before relying on fuzzy matches in a new environment.

### Use the Service Layer (Simplest API)

```python
from patient_matching.api import PatientMatcherService

service = PatientMatcherService(
    engine=engine,
    normalizer=normalizer,
)

response = await service.match_patient(query_patient)

print(response.outcome)           # "match", "no_match", or "ambiguous"
print(response.confidence_score)  # 0.0 - 1.0
print(response.matched_patient_ids)
```

### Match from an IAL2 Token

```python
from patient_matching.ial2_extraction import IAL2Extractor, TokenVerifier

verifier = TokenVerifier(
    jwks_uri="https://idp.example.com/.well-known/jwks.json",
    audience="your-client-id",
)
extractor = IAL2Extractor(verifier=verifier)

service = PatientMatcherService(
    engine=engine,
    normalizer=normalizer,
    ial2_extractor=extractor,
)

# Full pipeline: verify JWT → extract demographics → normalize → match
response = await service.match_from_token(jwt_token_string)
```

No HTTP layer ships in this package — [`cms-hte-patient-matching-service`](https://github.com/icanbwell/cms-hte-patient-matching-service) is the FastAPI microservice that wraps `PatientMatcherService` and exposes it over `/Patient/$match` and `/match/ial2`.

## Table 2 Matching Rules

The Category 1 (flat) rule set defines 30 approved field combinations, numbered 01-30 with no
gaps (CMS v3.4.0's renumbering). Each rule specifies which fields must match, whether fuzzy
matching is allowed (marked with `*`), and the collision probability:

| Rule | Fields | P(collision) exact | P(collision) fuzzy |
|------|--------|-------------------:|-------------------:|
| 01 | First Name\* + Last Name\* + DOB\* + Street Line\* | 3.00e-13 | 9.00e-13 |
| 02 | First Name + Last Name\* + DOB\* + Phone | 1.00e-14 | 2.00e-14 |
| 03 | First Name\* + Last Name\* + DOB\* + Email | 1.00e-14 | 3.00e-14 |
| 04 | First Name\* + Last Name + DOB + SSN Last 4 | 1.00e-12 | 1.50e-12 |
| 05 | First Name + Last Name\* + DOB + SSN Last 4 | 1.00e-12 | 2.00e-12 |
| 06 | First Name\* + Last Name + DOB + ITIN Last 4 | 1.00e-12 | 1.50e-12 |
| 07 | First Name + Last Name\* + DOB + ITIN Last 4 | 1.00e-12 | 2.00e-12 |
| 08 | First Name + DOB + MBI | 2.00e-12 | — |
| 09 | First Name + DOB + Legal ID | 2.00e-12 | — |
| 10 | Last Name\* + DOB\* + Legal ID | 5.00e-13 | 1.00e-12 |
| 11 | First Name + DOB + Phone | 2.00e-12 | — |
| 12 | First Name + DOB + Email | 2.00e-12 | — |
| 13 | First Name + Phone + SSN Last 4 | 2.00e-12 | — |
| 14 | First Name + Phone + ITIN Last 4 | 2.00e-12 | — |
| 15 | First Name + Email + SSN Last 4 | 2.00e-12 | — |
| 16 | First Name + Email + ITIN Last 4 | 2.00e-12 | — |
| 17 | Phone + MBI | 1.00e-12 | — |
| 18 | Phone + Legal ID | 1.00e-12 | — |
| 19 | Email + MBI | 1.00e-12 | — |
| 20 | Email + Legal ID | 1.00e-12 | — |
| 21 | Legal ID + MBI | 1.00e-12 | — |
| 22 | Namespace ID (EMPI, FHIR ID, CSP UUID) | 1.00e-15 | — |
| 23 | First Name + DOB + Insurance Member ID | 2.00e-12 | — |
| 24 | Last Name\* + DOB\* + Insurance Member ID | 5.00e-13 | 1.00e-12 |
| 25 | Phone + Insurance Member ID | 1.00e-12 | — |
| 26 | Email + Insurance Member ID | 1.00e-12 | — |
| 27 | First Name\* + Last Name + DOB + Insurance Subscriber ID | 1.00e-12 | 1.50e-12 |
| 28 | First Name + Last Name\* + DOB + Insurance Subscriber ID | 1.00e-12 | 2.00e-12 |
| 29 | First Name\* + Last Name\* + Phone + ZIP Code | 3.00e-14 | 9.00e-14 |
| 30 | Last Name\* + DOB + Phone | 5.00e-13 | 1.00e-12 |

Fields marked with `*` are fuzzy-eligible. Fuzzy matching uses **Damerau-Levenshtein distance <= 1** for strings of **5 or more characters** (per CMS Appendix E.3), except DOB\*, which uses a **+/-1 calendar day** tolerance instead (CMS v3.3) — a date string's edit distance has no relationship to its calendar distance, so DOB is never compared via Damerau-Levenshtein.

Rules 13-16 above are new v3.4.0 flat content (First Name + Phone/Email + SSN/ITIN Last 4) - a
separate, unrelated set of Category 2 (household/individual two-step) rules also happens to use
IDs 13-16/34/35/37/38 and is disambiguated with a `C2-` prefix (`C2-13`, etc.) in the engine's
audit output; see `household_rules.py`.

## Normalization Pipeline

Before matching, patient demographics are normalized following the CMS proposal sections:

### Text (A.1-A.4)
- Lowercase all text
- Fold diacritics and accents to ASCII (e.g., `Müller` -> `muller`)
- Remove punctuation
- Collapse whitespace

### Names (B.1-B.6)
- Parse into components (given, family, suffix) using `nominally`
- Expand nicknames from reference table (e.g., `Bob` -> `{Bob, Robert, Bobby, ...}`)
- Normalize suffixes (e.g., `Jr.` -> `jr`, `III` -> `iii`)
- Preserve historical/maiden names
- Detect and remove placeholder names (e.g., `Baby Boy`, `Test Patient`)
- **Suffix conflict rule (B.5):** if both patients have suffixes and they differ, the match is negated

### Phone (C.3-C.4)
- Convert to E.164 format using `phonenumbers` (e.g., `(212) 555-1234` -> `+12125551234`)
- Detect and remove placeholder numbers (e.g., `000-000-0000`, `555-555-5555`)

### Address (C.1-C.2)
- Standardize to USPS format using `usaddress-scourgify`
- Detect and remove placeholder addresses

### Identifiers (D.1-D.5)
- Extract SSN last 4, ITIN last 4, MBI, Legal IDs from FHIR `identifier` entries
- Detect and remove placeholder values (e.g., `000-00-0000`, `999-99-9999`)

### Dates (A.5, D.6)
- Validate format (YYYY-MM-DD, YYYY-MM, or YYYY)
- No imputation or zero-padding of partial dates
- Reject dates outside valid range (today - 120 years to today)

## Modules

### `patient_matching.matching`

Core matching engine implementing the 26 Table 2 rules.

- **`MatchingEngine`** — evaluates all rules against a query patient, returns match/no_match/ambiguous
- **`FieldExtractor`** — extracts matching-relevant fields from FHIR Patient resources
- **`FieldComparator`** — exact and fuzzy field comparison (Damerau-Levenshtein)
- **`MatchingBackend`** — abstract interface for candidate retrieval

### `patient_matching.normalization`

Demographic normalization per CMS proposal sections A-D.

- **`NormalizationManager`** — high-level entry point
- **`PatientNormalizer`** — orchestrates all sub-normalizers
- **`NameNormalizer`** — name parsing, nicknames, suffix normalization
- **`PhoneNormalizer`** — E.164 conversion
- **`AddressNormalizer`** — USPS standardization
- **`DateNormalizer`** — date validation
- **`PlaceholderDetector`** — detects non-comparable placeholder values

### `patient_matching.cache`

Patient cache with field-level indexing for efficient blocking. See
[Choosing a Cache Backend](#choosing-a-cache-backend) above for how to pick
between the two implementations.

- **`DuckDBCache`** — in-memory (or on-disk) DuckDB with two-table schema (`patients` + `field_values`); one cache per process/replica
- **`MongoAtlasCache`** — MongoDB + Atlas Search-backed cache with the same two-collection schema, shared across replicas
- **`CacheMatchingBackend`** — adapts either cache to the `MatchingBackend` interface
- **`CacheManager`** — ETL pipeline: fetch from FHIR server -> normalize -> extract fields -> store

### `patient_matching.fhir_client`

FHIR R4 client with OAuth2 support.

- **`FhirClient`** — paginated patient fetching with Bundle `next` link traversal
- **`ClientCredentialsAuth`** — OAuth2 client credentials flow with token caching

### `patient_matching.ial2_extraction`

IAL2 JWT token processing per CSP Payload Specification V7.1.

- **`IAL2Extractor`** — verify token, extract claims, convert to FHIR Patient
- **`TokenVerifier`** — JWKS-based JWT signature verification
- **`IAL2Claims`** — structured claims model with alias resolution
- **`IAL2ToFhirConverter`** — converts IAL2 claims to FHIR R4 Patient resource

### `patient_matching.api`

End-to-end orchestration, no HTTP layer of its own.

- **`PatientMatcherService`** — chains IAL2 extraction, normalization, and matching against a cache into a single async entry point, with confidence scoring

### `patient_matching.fuzzy`

Multi-backend fuzzy string search (DuckDB, PostgreSQL, MongoDB, Redis, Elasticsearch).

- **`FuzzySearchManager`** — unified search interface
- **`FuzzySearchFactory`** — backend creation from configuration
- **`FuzzySearchBenchmark`** — compare performance across backends

## Development

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Docker, running locally (only for `MongoAtlasCache`'s testcontainer tests — the rest of the suite needs nothing beyond `uv`)

### Setup

Private packages are hosted on JFrog. Set `JFROG_READ_TOKEN` in your environment before building:

```bash
export JFROG_READ_TOKEN="<your-jfrog-token>"
```

Add it to `~/.zshrc` or `~/.bashrc` to persist across sessions.

```bash
make devsetup      # Install dependencies, set up pre-commit hooks, run tests
```

### Running Tests

```bash
make tests         # uv run pytest .
```

478 tests cover all modules including matching rules, normalization, caching, FHIR client, IAL2 extraction, and fuzzy backends.

### Code Quality

```bash
make run-pre-commit   # Run all pre-commit hooks
```

Pre-commit hooks include:

| Tool | Purpose |
|------|---------|
| **Ruff** | Linting and formatting |
| **mypy** | Strict type checking (Python 3.12) |
| **Bandit** | Security vulnerability scanning |
| **detect-secrets** | Secret detection |
| Standard hooks | Trailing whitespace, CRLF, valid Python AST, etc. |

### Building

```bash
make dist          # Build the sdist + wheel into dist/
make testpackage   # Upload to TestPyPI (token in TWINE_PASSWORD)
make package       # Upload to PyPI (token in TWINE_PASSWORD)
```

Real releases publish via GitHub Actions using [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(`.github/workflows/python-publish.yml`, triggered on a GitHub Release) rather than `make package` —
Trusted Publishing only authenticates from within that CI run, so `make package`/`make testpackage`
are for local TestPyPI dry runs only.

### Project Structure

```
patient_matching/
├── patient_matching/
│   ├── api/                    # End-to-end orchestration (no HTTP layer)
│   │   ├── service.py          # Orchestrator + confidence scoring
│   │   └── tests/
│   ├── cache/                  # Patient cache storage
│   │   ├── cache_backend.py    # Abstract cache interface
│   │   ├── duckdb_cache.py     # DuckDB implementation
│   │   ├── matching_adapter.py # Cache → MatchingBackend bridge
│   │   ├── cache_manager.py    # ETL pipeline + scheduled refresh
│   │   └── tests/
│   ├── fhir_client/            # FHIR R4 client
│   │   ├── auth.py             # OAuth2 client credentials
│   │   ├── client.py           # Patient fetcher with pagination
│   │   └── tests/
│   ├── ial2_extraction/        # IAL2 JWT processing
│   │   ├── token_verifier.py   # JWKS signature verification
│   │   ├── ial2_extractor.py   # Token → FHIR Patient
│   │   ├── claims_model.py     # CSP Payload V7.1 claims
│   │   ├── fhir_converter.py   # Claims → FHIR conversion
│   │   └── tests/
│   ├── matching/               # Core matching engine
│   │   ├── matching_engine.py  # Rule evaluation + deduplication
│   │   ├── table2_rules.py     # 26 CMS-approved rules
│   │   ├── field_extractor.py  # FHIR → matching fields
│   │   ├── field_comparator.py # Exact + fuzzy comparison
│   │   ├── backend.py          # Abstract candidate retrieval
│   │   ├── match_result.py     # Result types + outcomes
│   │   └── tests/
│   ├── normalization/          # Demographic normalization
│   │   ├── normalizer.py       # Orchestrator
│   │   ├── manager.py          # High-level manager
│   │   ├── name_normalizer.py  # Names, nicknames, suffixes
│   │   ├── phone_normalizer.py # E.164 phone formatting
│   │   ├── address_normalizer.py # USPS standardization
│   │   ├── date_normalizer.py  # Date validation
│   │   ├── placeholder_detector.py # Placeholder value detection
│   │   ├── text_utils.py       # Text normalization primitives
│   │   └── tests/
│   └── fuzzy/                  # Multi-backend fuzzy search
│       └── fuzzy_db/
│           ├── core.py         # Enums, config, base classes
│           ├── factory.py      # Backend factory
│           ├── manager.py      # Unified search interface
│           ├── config.py       # YAML/JSON/env config loading
│           ├── utils.py        # Benchmarking + recommendations
│           ├── backends/       # DuckDB, PostgreSQL, MongoDB,
│           │                   # Redis, Elasticsearch
│           └── tests/
├── pyproject.toml
├── uv.lock
├── Makefile
└── VERSION
```

## License

Apache License 2.0

**Repository:** [https://github.com/icanbwell/cms-hte-patient-matching](https://github.com/icanbwell/cms-hte-patient-matching)
