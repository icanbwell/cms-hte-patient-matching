# patient_matching

An open-source Python implementation of the [CMS Patient Matching Proposal v3.2.2](https://confluence.hl7.org/display/PA/Patient+Matching), providing deterministic patient matching using all 26 approved Table 2 field combination rules with support for IAL2 identity-proofed tokens, FHIR R4 Patient resources, and configurable fuzzy matching.

## Overview

The CMS Patient Matching Proposal defines a standardized approach to matching patients across healthcare systems. This library implements:

- **26 Table 2 matching rules** with exact and fuzzy field comparisons
- **IAL2 token extraction** — verify JWT tokens from Credential Service Providers (CSPs) and convert to FHIR Patient resources
- **Demographic normalization** — text normalization, nickname expansion, E.164 phone formatting, USPS address standardization, placeholder detection
- **FHIR R4 integration** — fetch patients from FHIR servers with OAuth2, paginate through Bundles
- **Patient cache** — pluggable backend (in-process DuckDB, or MongoDB Atlas Search for shared/multi-replica deployments) with field-level indexing and fuzzy search
- **HTTP API** — FastAPI application with FHIR `$match` endpoint
- **Confidence scoring** — based on P(collision) values from Table 2 rules

## Architecture

```
                          ┌─────────────────┐
                          │   FastAPI API    │
                          │  POST /$match   │
                          │  POST /match/ial2│
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │ PatientMatcher   │
                          │    Service       │
                          └──┬─────┬─────┬──┘
                             │     │     │
                ┌────────────┘     │     └────────────┐
                │                  │                   │
       ┌────────▼───────┐  ┌──────▼──────┐  ┌────────▼────────┐
       │ IAL2 Extractor  │  │ Normalizer  │  │ Matching Engine │
       │ (JWT → FHIR)   │  │ (A.1–D.6)  │  │ (26 Rules)      │
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

# FastAPI HTTP API
pip install cms-hte-patient-matching[api]     # fastapi, uvicorn

# Scheduled cache refresh
pip install cms-hte-patient-matching[scheduler]  # apscheduler

# All features
pip install cms-hte-patient-matching[all]
```

## Quick Start

### Match a FHIR Patient Against a Cache

```python
from patient_matching.cache import DuckDBCache, CacheMatchingBackend, CacheManager
from patient_matching.fhir_client import FhirClient, FhirClientConfig
from patient_matching.matching import MatchingEngine
from patient_matching.normalization import NormalizationManager

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
cache_manager.build_cache()

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
result = engine.match(normalized)

print(result.outcome)           # MatchOutcome.MATCH
print(result.matched_rule_id)   # e.g., "rule_02"
print(result.match_type)        # "exact" or "fuzzy"
```

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

response = service.match_patient(query_patient)

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
response = service.match_from_token(jwt_token_string)
```

### Run the HTTP API

```python
from patient_matching.api import create_app

app = create_app(service=service)

# Run with uvicorn
# uvicorn patient_matching.api:app --host 0.0.0.0 --port 8000
```

Or from the command line:

```bash
uvicorn patient_matching.api.app:app --host 0.0.0.0 --port 8000
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/Patient/$match` | FHIR `$match` operation — accepts a `Parameters` resource containing a `Patient`, returns a `Bundle` |
| `POST` | `/match/ial2` | Match from an IAL2 JWT token |
| `GET`  | `/health` | Health check |

#### FHIR $match Example

```bash
curl -X POST http://localhost:8000/Patient/\$match \
  -H "Content-Type: application/fhir+json" \
  -d '{
    "resourceType": "Parameters",
    "parameter": [{
      "name": "resource",
      "resource": {
        "resourceType": "Patient",
        "name": [{"family": "Smith", "given": ["John"]}],
        "birthDate": "1990-01-15"
      }
    }]
  }'
```

## Table 2 Matching Rules

The CMS proposal defines 26 approved field combinations. Each rule specifies which fields must match, whether fuzzy matching is allowed (marked with `*`), and the collision probability:

| Rule | Fields | P(collision) exact | P(collision) fuzzy |
|------|--------|-------------------:|-------------------:|
| 01 | First Name\* + Last Name\* + DOB + Street Line\* | 2.86e-14 | 2.73e-11 |
| 02 | First Name + Last Name\* + DOB + Phone | 2.86e-14 | 3.96e-12 |
| 03 | First Name\* + Last Name\* + DOB + Email | 1.72e-14 | 1.64e-11 |
| 04 | First Name\* + Last Name + DOB + SSN Last 4 | 1.00e-11 | 1.00e-09 |
| 05 | First Name + Last Name\* + DOB + SSN Last 4 | 1.00e-11 | 1.39e-09 |
| 06 | First Name\* + Last Name + DOB + ITIN Last 4 | 1.00e-11 | 1.00e-09 |
| 07 | First Name + Last Name\* + DOB + ITIN Last 4 | 1.00e-11 | 1.39e-09 |
| 08 | First Name + DOB + MBI | 3.60e-13 | — |
| 09 | First Name + DOB + Legal ID | 3.60e-13 | — |
| 10 | Last Name\* + DOB + Legal ID | 3.60e-13 | 4.99e-11 |
| 11 | First Name + DOB + Phone | 3.60e-10 | — |
| 12 | First Name + DOB + Email | 2.16e-10 | — |
| 13 | Last Name + Phone + SSN Last 4 | 1.00e-11 | — |
| 14 | Last Name + Phone + ITIN Last 4 | 1.00e-11 | — |
| 15 | Last Name\* + Email + SSN Last 4 | 6.00e-12 | 8.31e-10 |
| 16 | Last Name\* + Email + ITIN Last 4 | 6.00e-12 | 8.31e-10 |
| 17 | First Name + Phone + SSN Last 4 | 1.00e-11 | — |
| 18 | First Name + Phone + ITIN Last 4 | 1.00e-11 | — |
| 19 | First Name + Email + SSN Last 4 | 6.00e-12 | — |
| 20 | First Name + Email + ITIN Last 4 | 6.00e-12 | — |
| 21 | Phone + MBI | 1.00e-12 | — |
| 22 | Phone + Legal ID | 1.00e-12 | — |
| 23 | Email + MBI | 6.00e-13 | — |
| 24 | Email + Legal ID | 6.00e-13 | — |
| 25 | Legal ID + MBI | 1.00e-14 | — |
| 26 | Namespace-bound unique IDs (EMPI, FHIR ID, CSP UUID) | 0.0 | — |

Fields marked with `*` are fuzzy-eligible. Fuzzy matching uses **Damerau-Levenshtein distance <= 1** for strings of **5 or more characters** (per CMS Appendix E.3).

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

FastAPI HTTP API with FHIR-compliant endpoints.

- **`PatientMatcherService`** — end-to-end orchestrator with confidence scoring
- **`create_app()`** — FastAPI application factory

### `patient_matching.fuzzy`

Multi-backend fuzzy string search (DuckDB, PostgreSQL, MongoDB, Redis, Elasticsearch).

- **`FuzzySearchManager`** — unified search interface
- **`FuzzySearchFactory`** — backend creation from configuration
- **`FuzzySearchBenchmark`** — compare performance across backends

## Development

### Prerequisites

- Python 3.12+
- Docker (for containerized development)
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Setup

Private packages are hosted on JFrog. Set `JFROG_READ_TOKEN` in your environment before building:

```bash
export JFROG_READ_TOKEN="<your-jfrog-token>"
```

Add it to `~/.zshrc` or `~/.bashrc` to persist across sessions.

```bash
make init          # Install dependencies and set up pre-commit hooks
make up            # Start Docker dev stack
```

### Running Tests

```bash
make tests         # Run tests in Docker container

# Or locally:
uv run pytest -v
```

295 tests cover all modules including matching rules, normalization, caching, FHIR client, API endpoints, and fuzzy backends.

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
make dist          # Build distribution packages into dist/ (named `dist`, not `build`,
                    # since `make build` already means "build the dev Docker image")
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
│   ├── api/                    # FastAPI HTTP endpoints
│   │   ├── app.py              # Application factory + routes
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
├── VERSION
└── docker-compose.yml
```

## License

Apache License 2.0

**Repository:** [https://github.com/icanbwell/cms-hte-patient-matching](https://github.com/icanbwell/cms-hte-patient-matching)
