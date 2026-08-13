# b.well Connected Health — Master Business Logic & Invariants

**Purpose:** Authoritative reference for AI-driven test generation and bug detection. Every rule in this document defines CORRECT behavior — code that violates any rule is buggy regardless of what any PR description claims.

**Usage:** Feed this document to the `unit-test-master` or `bug-sweep` skill as context. The skill should test code against these rules WITHOUT relying on developer-written stories, PR descriptions, or inline comments as truth.

**Date compiled:** 2026-08-09
**Sources:** All Confluence spaces, GitHub repositories (60+ repos), ADRs, README files, Helm values, AGENTS.md, and source code analysis.

---

## HOW TO USE THIS DOCUMENT FOR TEST GENERATION

1. **Each rule is a test assertion.** If code violates a rule, the code is wrong.
2. **Rules are grouped by domain.** When testing a file, find its domain and test against ALL applicable rules.
3. **Rules override developer intent.** A PR that claims "feature X works like Y" is irrelevant if these rules say otherwise.
4. **Absence of a rule does not mean absence of a constraint.** Standard FHIR R4 spec applies for anything not explicitly overridden here.

---

## Table of Contents

### Part I: Platform Identity & Architecture
- [1. System Overview](#1-system-overview)
- [2. Multi-Tenancy Model](#2-multi-tenancy-model)
- [3. Security Tag System](#3-security-tag-system)
- [4. Identity Hierarchy](#4-identity-hierarchy)

### Part II: Access Control Invariants
- [5. Scope System](#5-scope-system)
- [6. Resource Authorization Decision Tree](#6-resource-authorization-decision-tree)
- [7. Patient Scope & Identity Graph](#7-patient-scope--identity-graph)
- [8. Delegated Access](#8-delegated-access)
- [9. CMS Partner Access](#9-cms-partner-access)
- [10. Consent System](#10-consent-system)

### Part III: Data Integrity Invariants
- [11. Resource Lifecycle (Create/Update/Merge/Delete)](#11-resource-lifecycle)
- [12. Merge Operation Rules](#12-merge-operation-rules)
- [13. Pre-Save Handler Chain](#13-pre-save-handler-chain)
- [14. Immutable Fields](#14-immutable-fields)
- [15. Validation Rules](#15-validation-rules)
- [16. Reference Format Rules](#16-reference-format-rules)

### Part IV: Operations & API Contract
- [17. $everything Operation](#17-everything-operation)
- [18. Bulk Export ($export)](#18-bulk-export)
- [19. Bulk Import ($import)](#19-bulk-import)
- [20. Search & Pagination](#20-search--pagination)
- [21. Streaming Response Behavior](#21-streaming-response-behavior)
- [22. Error Response Codes](#22-error-response-codes)
- [23. Caching Rules](#23-caching-rules)

### Part V: Audit & Observability
- [24. Audit Event Requirements](#24-audit-event-requirements)
- [25. Kafka Event System](#25-kafka-event-system)
- [26. Access Logging](#26-access-logging)

### Part VI: Identity & Person Matching
- [27. Person-Patient Data Model](#27-person-patient-data-model)
- [28. Person Matching Algorithm](#28-person-matching-algorithm)
- [29. Proxy Patient Resolution](#29-proxy-patient-resolution)

### Part VII: Data Pipeline & Ingestion
- [30. PROA Pipeline Rules](#30-proa-pipeline-rules)
- [31. Data Connection Lifecycle](#31-data-connection-lifecycle)
- [32. Data Deletion Pipeline](#32-data-deletion-pipeline)

### Part VIII: Clinical Services
- [33. CQL Engine & Care Gaps](#33-cql-engine--care-gaps)
- [34. Composition Service](#34-composition-service)
- [35. Subscription System](#35-subscription-system)

### Part IX: Cross-Service Architecture
- [36. Event-Driven Patterns](#36-event-driven-patterns)
- [37. Authentication & Token Management](#37-authentication--token-management)
- [38. SDK & API Gateway Contract](#38-sdk--api-gateway-contract)
- [39. Configuration Constants](#39-configuration-constants)

### Part X: FHIR Subscription & SSE Service
- [40. SSE Connection Lifecycle](#40-sse-connection-lifecycle)
- [41. Kafka Partition & Consumer Rules](#41-kafka-partition--consumer-rules)
- [42. SSE Token Expiry Handling](#42-sse-token-expiry-handling)

### Part XI: Health Link Service (SMART Health Links)
- [43. Health Link Creation](#43-health-link-creation)
- [44. Health Data Strategy Resolution](#44-health-data-strategy-resolution)
- [45. Response Build & Caching](#45-response-build--caching)
- [46. Manifest & File Access Control](#46-manifest--file-access-control)
- [47. Health Link Audit Events](#47-health-link-audit-events)

### Part XII: Workflow & Data Integration Services
- [48. Data Connection Events](#48-data-connection-events)
- [49. CAN Integration Rules](#49-can-integration-rules)
- [50. Intelligence Layer Integration](#50-intelligence-layer-integration)

### Part XIII: MongoDB & Database Invariants
- [51. Collection Naming & Architecture](#51-collection-naming--architecture)
- [52. Index Requirements](#52-index-requirements)
- [53. Concurrency Control & Optimistic Locking](#53-concurrency-control--optimistic-locking)
- [54. History Collection Rules](#54-history-collection-rules)
- [55. Two-Timeout Streaming Pattern](#55-two-timeout-streaming-pattern)
- [56. Write Concern & Connection Pool](#56-write-concern--connection-pool)

### Part XIV: Consent System Deep Dive
- [57. PROA Consent (Expands Visibility)](#57-proa-consent-expands-visibility)
- [58. CMS Consent (Restricts to Consented)](#58-cms-consent-restricts-to-consented)
- [59. Delegated Access Consent](#59-delegated-access-consent)
- [60. DataViewControl Consent](#60-dataviewcontrol-consent)
- [61. Consent State Machine](#61-consent-state-machine)
- [62. Consent Cache Invalidation](#62-consent-cache-invalidation)
- [63. SHL Consent Rules](#63-shl-consent-rules)

### Part XV: Error Handling & Failure Modes
- [64. OperationOutcome Format](#64-operationoutcome-format)
- [65. HTTP Status Code Mapping](#65-http-status-code-mapping)
- [66. Retry & Circuit Breaker Patterns](#66-retry--circuit-breaker-patterns)
- [67. Fail-Open vs Fail-Closed Classification](#67-fail-open-vs-fail-closed-classification)
- [68. Streaming Mid-Response Errors](#68-streaming-mid-response-errors)
- [69. Dead Letter Topic (DLT) Rules](#69-dead-letter-topic-dlt-rules)

### Part XVI: Identity Gateway & Authentication
- [70. Guest User Lifecycle](#70-guest-user-lifecycle)
- [71. OAuth Grant Types & Token Exchange](#71-oauth-grant-types--token-exchange)
- [72. Scope Enforcement Deep Rules](#72-scope-enforcement-deep-rules)
- [73. Account Deletion Sequence](#73-account-deletion-sequence)
- [74. Cognito/Descope Dual-IdP](#74-cognitodescope-dual-idp)
- [75. MFA & Phone Verification](#75-mfa--phone-verification)

### Part XVII: GraphQL & API Gateway
- [76. GraphQL Schema & Federation](#76-graphql-schema--federation)
- [77. API Gateway Routing](#77-api-gateway-routing)
- [78. Batch Bundle Processing](#78-batch-bundle-processing)
- [79. Content Negotiation & CORS](#79-content-negotiation--cors)
- [80. Webhook Delivery Contracts](#80-webhook-delivery-contracts)

### Part XVIII: Bulk Export & Import Deep Dive
- [81. Export Lifecycle & File Format](#81-export-lifecycle--file-format)
- [82. Import Byte-Range Parallelism](#82-import-byte-range-parallelism)
- [83. Import Validation & SSRF Prevention](#83-import-validation--ssrf-prevention)
- [84. Job Timeout & Concurrency](#84-job-timeout--concurrency)

### Part XIX: Clinical Pipeline & PROA Deep Dive
- [85. GraphDefinition Traversal](#85-graphdefinition-traversal)
- [86. Document Processing Pipeline](#86-document-processing-pipeline)
- [87. Source Patient Classification](#87-source-patient-classification)
- [88. Data Freshness & Refresh Tiers](#88-data-freshness--refresh-tiers)
- [89. Clinical Data Normalization](#89-clinical-data-normalization)

### Part XX: SDK & Mobile Contracts
- [90. SDK Result Types & Lifecycle](#90-sdk-result-types--lifecycle)
- [91. Token Refresh & Storage](#91-token-refresh--storage)
- [92. Pagination & Feature Flags](#92-pagination--feature-flags)
- [93. Push Notifications & Deep Linking](#93-push-notifications--deep-linking)

### Part XXI: Hidden Invariants (Test-Revealed)
- [94. Security Tag Race Conditions](#94-security-tag-race-conditions)
- [95. Cross-Tenant Identity Grafting Prevention](#95-cross-tenant-identity-grafting-prevention)
- [96. SHL Passcode & Access Limit Mechanics](#96-shl-passcode--access-limit-mechanics)
- [97. SSE Event Security Filtering](#97-sse-event-security-filtering)

### Part XXII: Deployment & Runtime Configuration
- [98. Memory & Worker Scaling](#98-memory--worker-scaling)
- [99. Health Probes & Graceful Shutdown](#99-health-probes--graceful-shutdown)
- [100. Feature Flags & Thresholds](#100-feature-flags--thresholds)

### Part XXIII: Resource-Specific Behavioral Rules
- [101. Person Resource Rules](#101-person-resource-rules)
- [102. Patient Resource Rules](#102-patient-resource-rules)
- [103. Consent Resource Rules](#103-consent-resource-rules)
- [104. Group Resource Rules](#104-group-resource-rules)
- [105. AuditEvent Resource Rules](#105-auditevent-resource-rules)
- [106. DocumentReference & Binary Rules](#106-documentreference--binary-rules)
- [107. Subscription Family Rules](#107-subscription-family-rules)
- [108. Cross-Resource Behavioral Tags](#108-cross-resource-behavioral-tags)
- [109. Merge Array Semantics](#109-merge-array-semantics)
- [110. Pre-Save Handler Chain (All Resources)](#110-pre-save-handler-chain-all-resources)

---

## 1. System Overview

b.well Connected Health is a FHIR-native, multi-tenant, event-driven healthcare data platform. The FHIR server is the platform system-of-record. All services access it via approved APIs (FHIR REST, federated GraphQL, Kafka events) — never via direct MongoDB access.

**Core Architectural Constraints:**
- Event-driven first (Kafka + CloudEvents). Sync calls require documented justification.
- Services own their private datastores. No shared databases.
- Choreography over orchestration for cross-service workflows.
- Eventually consistent across service boundaries.
- Tenant isolation on every persistence model and every query path.
- No PHI/PII in logs, test fixtures, comments, commit messages, or PR descriptions.

---

## 2. Multi-Tenancy Model

**INVARIANT:** Every FHIR resource MUST have exactly one `owner` tag and at least one `access` tag in `meta.security`.

**INVARIANT:** Tenant isolation is enforced by security tags on EVERY query path. There is no query that bypasses tenant filtering except the `access/*` wildcard scope.

**INVARIANT:** A resource is visible to a caller if the caller is authorized for at least one of the resource's access tags (OR semantics on read).

**INVARIANT:** Data from one client is NEVER shared with another client unless an explicit data-sharing Consent exists.

---

## 3. Security Tag System

### Tag Systems & URIs

| Tag Type | System URI | Mutable? | Purpose |
|----------|-----------|----------|---------|
| Owner | `https://www.icanbwell.com/owner` | IMMUTABLE | Authoritative tenant. Exactly one per resource. |
| Access | `https://www.icanbwell.com/access` | Mutable (with scope validation) | Tenant visibility list. OR semantics. |
| SourceAssigningAuthority | `https://www.icanbwell.com/sourceAssigningAuthority` | IMMUTABLE | Identity system origin. |
| Vendor | `https://www.icanbwell.com/vendor` | Mutable | System of origin. |
| ConnectionType | `https://www.icanbwell.com/connectionType` | Mutable | Data connection type (proa, ias). |
| Hidden | `https://fhir.icanbwell.com/4_0_0/CodeSystem/server-behavior` (code: `hidden`) | Mutable | Soft-delete/exclusion from search. |
| Confidentiality-R | `http://terminology.hl7.org/CodeSystem/v3-Confidentiality` (code: `R`) | Mutable | Restricted — excluded for ALL patient-scoped callers. |
| Unclassified | `https://www.icanbwell.com/sensitivity-category` (code: `unclassified`) | Auto-added on write | ALWAYS excluded for delegated actors. |

### Tag Invariants

**INVARIANT:** Owner tag is IMMUTABLE. Once created, it CANNOT be changed. Resource must be deleted and recreated to change ownership.

**INVARIANT:** SourceAssigningAuthority is IMMUTABLE. Once created, it CANNOT be changed.

**INVARIANT:** During $merge, `resourceMerger.overWriteNonWritableFields()` ALWAYS replaces incoming owner and sourceAssigningAuthority tags with the database version. Only access tags are user-controllable.
- Source: `src/operations/common/resourceMerger.js` lines 144-154

**INVARIANT:** If a resource has an access tag but NO owner tag, the owner tag MUST be set to the first access tag's code during preSave.
- Source: `src/preSaveHandlers/handlers/ownerColumnHandler.js` lines 36-66

**INVARIANT:** If sourceAssigningAuthority is absent, it MUST be derived from the first owner tag's code.
- Source: `src/preSaveHandlers/handlers/sourceAssigningAuthorityColumnHandler.js` lines 37-75

**INVARIANT:** The internal `_access` field MUST be exactly synchronized with meta.security access tags. For each access code, `_access[code]` = 1. Stale codes MUST be deleted.
- Source: `src/preSaveHandlers/handlers/accessColumnHandler.js` lines 16-39

**INVARIANT:** No tag in meta.security MAY have a system or code value of literal string "null" or empty string.

**INVARIANT:** After any merge, meta.security MUST contain no duplicate tags by system+code combination.
- Source: `src/operations/common/resourceMerger.js` lines 156-165

---

## 4. Identity Hierarchy

```
Master Person (owner=bwell, exactly 1 per human)
  └── Client Person (owner=<client>, 1 per client per human)
       └── Patient (owner=<source>, 1+ per data source)
            └── Clinical Resources (linked via patient/subject reference)
```

**INVARIANT:** Each registered b.well user has exactly 1 master Person resource with owner=bwell.

**INVARIANT:** There MUST be exactly 1 Client Person per (human, client) pair.

**INVARIANT:** A Patient is always associated with a data source (reflected in owner tag), NOT a client.

**INVARIANT:** Same owner tag on two Person resources does NOT mean same identity. `client_person_id` is the intra-tenant person discriminator.

**INVARIANT:** The relationship of Person to Patient is 1-to-many (via Person.link).

**INVARIANT:** Data from each source is kept separately. The FHIR server creates combined views on-the-fly (schema-on-read, not schema-on-write).

**INVARIANT:** The Intelligence Layer may extend FHIR resources but NEVER modifies existing fields.

---

## 5. Scope System

### Scope Types

| Scope Pattern | Purpose | Example |
|---------------|---------|---------|
| `patient/{ResourceType}.{action}` | Patient-facing access via identity graph | `patient/Patient.read` |
| `user/{ResourceType}.{action}` | Service/admin resource type access | `user/Observation.write` |
| `access/{tag}.{action}` | Tenant visibility control | `access/clientA.*` |
| `admin/*.{action}` | Admin routes and debug features | `admin/*.*` |

**INVARIANT:** Scopes are space-separated (not comma), per OAuth spec.

**INVARIANT:** If `patient/` scope is present in JWT, access is determined by patient scope ONLY — all other scope types are skipped for data filtering.

**INVARIANT:** `admin/*.*` does NOT bypass tenant filtering. Only `access/*` wildcard bypasses security tag filtering.

**INVARIANT:** Patient-scoped access and access-tag filtering are MUTUALLY EXCLUSIVE code branches. A patient-scoped caller on a patient-filterable resource gets identity-graph filtering, not access-tag filtering.

**INVARIANT:** Access codes are extracted from scopes matching `access/{tag}.{action}`. If action is `*` or matches requested action, the tag is an allowed access code.
- Source: `src/operations/security/scopesManager.js` lines 49-77

**INVARIANT:** For a user to access a resource via access/owner scopes, BOTH conditions MUST be true: (1) at least one access code matches an access tag on the resource, AND (2) at least one access code matches the owner tag. Exception: `*` access code bypasses both.
- Source: `src/operations/security/scopesManager.js` lines 85-122

---

## 6. Resource Authorization Decision Tree

A resource IS returned ONLY if ALL of the following apply:

1. **Scope validation passes** — caller has `user/` or `patient/` scope for the resource type and action
2. **Tenant visibility passes** — one of:
   - Caller holds `access/*` (wildcard), OR
   - Resource has an access tag matching caller's access codes, OR
   - Caller is patient-scoped AND resource is reachable through identity graph
3. **Hidden tag check** — resource does NOT have `hidden` tag (unless `_includeHidden=true`)
4. **Confidentiality-R check** — if caller is patient-scoped, resource does NOT have Confidentiality-R tag
5. **Unclassified check** — if caller is delegated actor, resource does NOT have `unclassified` tag
6. **Consent filtering** — if applicable (PROA/CMS/delegated), consent permits access

**INVARIANT:** Resources with hidden tag are excluded from ALL searches by default. Exception: by-ID lookups, history, DELETE, AuditEvent.

**INVARIANT:** Confidentiality-R tagged resources are excluded UNCONDITIONALLY for every patient-scoped caller, regardless of identity-graph reachability. Also cannot be written by patient-scoped callers.

**INVARIANT:** `_includeHidden=true` — only accessible to callers with appropriate scope (not all users).

---

## 7. Patient Scope & Identity Graph

**INVARIANT:** When a caller holds `patient/` scope AND the resource type is patient-filterable, access is decided by reachability through the caller's Person/Patient identity graph — NOT by access tags.

**INVARIANT:** Person-to-Patient link traversal is capped at recursion depth 4. Hitting the cap logs a warning and returns whatever was resolved.
- Source: `src/operations/security/patientScopeManager.js` lines 67-100

**INVARIANT:** Cross-tenant Person.link traversal — a hop where source and target have different owner tags IS a legitimate traversal step and MUST be followed (enables cross-tenant aggregation).

**INVARIANT:** When traversing Person.link, access tags are checked at EACH hop (not just top-level Person). Callers with only patient scopes cannot traverse links across tenant boundaries where they lack access.
- Source: `src/utils/personToPatientIdsExpander.js` lines 67-98

**INVARIANT:** With patient scopes, users CANNOT write non-patient-filterable resources. Adding `user/*.write` + `access/*.write` provides NO write access for a patient-scoped caller.

**INVARIANT:** A Person resource CANNOT be created using patient scope. The corresponding clientPerson in the JWT CAN still be updated.

**INVARIANT:** `$everything` and `$graph` re-invoke `constructQueryAsync` at every traversal hop — a resource reached via link-following gets the same security filter as a direct search.

### Patient-Filterable Resources (97 types)

Account, AdverseEvent, AllergyIntolerance, Appointment, AppointmentResponse, AuditEvent, Basic, BiologicallyDerivedProduct, BodyStructure, CarePlan, CareTeam, ChargeItem, Claim, ClaimResponse, ClinicalImpression, Communication, CommunicationRequest, Composition, Condition, Consent, Contract, Coverage, CoverageEligibilityRequest, CoverageEligibilityResponse, DetectedIssue, Device, DeviceRequest, DeviceUseStatement, DiagnosticReport, DocumentManifest, DocumentReference, Encounter, EnrollmentRequest, EpisodeOfCare, ExplanationOfBenefit, FamilyMemberHistory, Flag, Goal, GuidanceResponse, ImagingStudy, Immunization, ImmunizationEvaluation, ImmunizationRecommendation, Invoice, Linkage, List, MeasureReport, Media, MedicationAdministration, MedicationDispense, MedicationRequest, MedicationStatement, MolecularSequence, NutritionOrder, Observation, Patient, PaymentNotice, Procedure, Provenance, QuestionnaireResponse, RelatedPerson, RequestGroup, ResearchSubject, RiskAssessment, Schedule, ServiceRequest, Specimen, SupplyDelivery, SupplyRequest, Task, VisionPrescription

Source: `src/fhir/patientFilterManager.js` lines 7-79

### Non-Patient-Filterable Resources (examples)

All foundation resources (CodeSystem, ValueSet, ConceptMap, StructureDefinition), conformance resources (CapabilityStatement, OperationDefinition), infrastructure resources (Bundle, OperationOutcome), knowledge resources (Measure, PlanDefinition, Library), Organization, Practitioner, Location, Endpoint, HealthcareService.

**Key restriction:** Patient-scoped tokens CANNOT write to any non-patient-filterable resource type.

---

## 8. Delegated Access

**INVARIANT:** A delegated user is detected via JWT `act` claim containing a `RelatedPerson/<id>` reference. Detection gated by `ENABLE_DELEGATED_ACCESS_DETECTION` config flag.
- Source: `src/strategies/authService.js` line ~340

**INVARIANT:** A delegated user MUST NOT perform ANY write operation. Only `search`, `searchById`, `everything`, `graph` are allowed. All writes return 403.
- Source: `src/utils/delegatedAccessManager.js` lines 36-46
- Source: `src/constants.js` lines 327-342

**INVARIANT:** A delegated user MUST have exactly one valid active Consent resource tying grantor to actor. Zero = forbidden (403). Multiple = ambiguous = forbidden (403).
- Source: `src/utils/delegatedAccessRulesManager.js` lines 118-121

**INVARIANT:** Consent requirements for delegated access:
- `status: 'active'`
- `provision.type: 'permit'`
- `category.coding` matching `configManager.dataSharingAccessCodes`
- `provision.actor.reference` matching the actor's reference
- `patient` matching the person ID
- Active time period: `provision.period.start` ≤ now AND (`end` absent OR `end` ≥ now)
- Source: `src/utils/delegatedAccessRulesManager.js` lines 200-285

**INVARIANT:** Resources tagged `unclassified` are ALWAYS hidden from delegated users regardless of Consent provisions. This is hardcoded and cannot be overridden by any Consent.
- Source: `src/operations/search/dataSharingManager.js` lines 705-749

**INVARIANT:** A delegated user's query routes through the patient-scope/identity-graph branch (not access-tag branch).

**INVARIANT:** Redis response caching is disabled for delegated users.

**INVARIANT:** Composition section filtering: sections tagged with Consent-denied sensitivity codes are removed. BUT `unclassified`-only sections are NOT stripped at enrichment time (known gap — query-level exclusion is the primary defense).

---

## 9. CMS Partner Access

**INVARIANT:** CMS partner user type = `cms-partner`. Allowed resource types = `['Patient']` only. Allowed operations = `['search', 'everything']` only. Allowed HTTP methods = `['GET']` only.
- Source: `src/constants.js` lines 322-326

**INVARIANT:** CMS partner search for Patient MUST restrict to consented patient UUIDs. Fails closed: no valid Consent = impossible query `{ _uuid: '__invalid__' }` = zero results.
- Source: `src/operations/search/dataSharingManager.js` lines 258-301

**INVARIANT:** CMS consent category: system `http://www.icanbwell.com/consent-category`, code `cms:share:records`.

---

## 10. Consent System

### Consent Categories

| Category Code | System | Purpose |
|---------------|--------|---------|
| `dataSharingAccess` | `http://www.icanbwell.com/consent-category` | Delegated actor access |
| `dataConnectionViewControl` | `http://www.icanbwell.com/consent-category` | Patient hiding resources from own $everything |
| `cms:share:records` | `http://www.icanbwell.com/consent-category` | CMS partner data sharing |

### PROA/IAS Data-Sharing Consent

**INVARIANT:** When `enableConsentedProaDataAccess` is true, active `permit`-type Consents are OR'd onto the query to unlock source data not owned by the caller's tenant.
- Source: `src/operations/search/dataSharingManager.js` lines 135-243

**INVARIANT:** A Consent is valid for data sharing ONLY if: status=active, provision.type=permit, period.start ≤ now, (period.end absent OR ≥ now).
- Source: `src/operations/search/proaConsentManager.js` lines 35-82

**INVARIANT:** When consent is revoked, ALL consented-path data disappears together. The consent is the single switch.

**INVARIANT:** $everything cache invalidates automatically on Consent writes (generation counter increment).

### Consent State Machine

**INVARIANT:** Consent status lifecycle: draft → active → rejected → inactive.

**INVARIANT:** When consent status changes, set existing consent status to "inactive" and create a NEW consent resource (do not update in place).

**INVARIANT:** Multiple Consents in a single QuestionnaireResponse: create a SEPARATE Consent resource for each item.

### Patient Data View Control

**INVARIANT:** A patient can exclude specific resources from their own $everything via a `dataConnectionViewControl`-category Consent referencing the resources to hide. Applies only to patient-scoped requests.

---

## 11. Resource Lifecycle

### Write Authorization Rules

**INVARIANT:** Every write operation MUST verify `accessRequested: 'write'` scopes BEFORE any query is built.
- Source: `src/operations/create/create.js` lines 137-146

**INVARIANT:** A write MUST NOT allow a caller to add or remove access tags it isn't authorized for. Caller can only add/remove tags matching its own access scopes (or holds wildcard).
- Source: `src/operations/security/scopesManager.js` lines 174-212
- Exception: CREATEs with patient scope skip this check.
- Exception: Smart merge mode with `ignoreRemovals=true` (missing tags ≠ intentional removal).

**INVARIANT:** On UPDATE: the resource's patient reference(s) MUST match the patient reference(s) in the existing database record. Changing patient assignment via update is forbidden.

**INVARIANT:** PUT/$merge returns 403 (not 404) when a resource exists but is inaccessible to the caller.

---

## 12. Merge Operation Rules

**INVARIANT:** `$merge` always returns HTTP 200 OK. Validation errors and forbidden actions are in the response body as OperationOutcome entries, not as HTTP error codes.

**INVARIANT:** `resource.id` is REQUIRED on every resource in a merge payload.

**INVARIANT:** `resource.id` MUST NOT contain a pipe character (`|`).

**INVARIANT:** Non-UUID ids require either an owner security tag or a sourceAssigningAuthority tag.

**INVARIANT:** `meta.source` is REQUIRED on every resource (when `requireMetaSourceTags=true`, production default).

**INVARIANT:** Exactly one owner tag MUST be present on new resources.

**INVARIANT:** AuditEvent resources via $merge ALWAYS create new records regardless of whether one with that id exists.

**INVARIANT:** Resources without changes are skipped (no-op detection via hash comparison). Hash generated after removing lastUpdated and versionId.

**INVARIANT:** Optimal $merge payload size is 100 resources.

### Array Merge Semantics

**INVARIANT:** Primitive arrays are FULLY REPLACED (not merged element-by-element).

**INVARIANT:** Object arrays match on `id` field first, then `sequence`. No match = append.

**INVARIANT:** Items ending in `-delete` suffix are removed from the array.

### Smart Merge

**INVARIANT:** `smartMerge=true` suppresses required-field and oneOf schema errors (allows partial payloads). All other schema errors still fail.

**INVARIANT:** In smart merge mode, incoming resource is deeply merged with current using recursive object merge (not replacement).

### Concurrency

**INVARIANT:** Optimistic concurrency with version checks — updates only succeed if database version equals (new version - 1). Conflict triggers one-by-one retry (max 5 retries per resource).

### Non-Writable Fields

**INVARIANT:** The following fields are ALWAYS overwritten from current resource during merge (NEVER updated from incoming):
- `id`
- `meta.versionId`
- `meta.lastUpdated`
- `meta.source`
- `meta.security` owner tag
- `meta.security` sourceAssigningAuthority tag
- Source: `src/operations/common/resourceMerger.js` lines 134-230

---

## 13. Pre-Save Handler Chain

All writes pass through handlers in this exact sequence:

1. **UuidColumnHandler** — generates `_uuid`
   - If `id` is valid UUID: `_uuid = id`
   - If `id` missing: `_uuid = generateUUID()` (random)
   - Else: `_uuid = generateUUIDv5(id | sourceAssigningAuthority)` (deterministic)
   - Also removes `https://www.icanbwell.com/uuid` identifier from array
   - Source: `src/preSaveHandlers/handlers/uuidColumnHandler.js` lines 19-38

2. **SourceIdColumnHandler** — maintains `_sourceId = resource.id`
   - Also removes `https://www.icanbwell.com/sourceId` identifier from array
   - Source: `src/preSaveHandlers/handlers/sourceIdColumnHandler.js` lines 18-27

3. **OwnerColumnHandler** — adds owner tag if missing (derives from first access tag)
   - Source: `src/preSaveHandlers/handlers/ownerColumnHandler.js` lines 36-66

4. **SourceAssigningAuthorityColumnHandler** — adds sourceAssigningAuthority (derives from owner)
   - Source: `src/preSaveHandlers/handlers/sourceAssigningAuthorityColumnHandler.js` lines 37-75

5. **AccessColumnHandler** — maintains `_access.<code>` denormalization
   - Source: `src/preSaveHandlers/handlers/accessColumnHandler.js` lines 16-39

6. **DateColumnHandler** — timestamps (meta.lastUpdated)

7. **UnclassifiedSensitivityTagHandler** — auto-adds `unclassified` tag for configured resource types
   - Suppressed by `X-Suppress-Unclassified-Tag: true` header
   - Tag's `id` field is ALWAYS overwritten to a fixed deterministic UUID

---

## 14. Immutable Fields

| Field | Immutability Rule |
|-------|-------------------|
| Owner tag (meta.security) | Set at creation, NEVER changeable |
| SourceAssigningAuthority tag | Set at creation, NEVER changeable |
| meta.source | Set at creation, NEVER changeable |
| resource.id | Assigned by server, NEVER changeable |
| _uuid | Deterministic from id+sourceAssigningAuthority, NEVER changeable |
| Patient reference on update | MUST match existing record's patient reference |

---

## 15. Validation Rules

**INVARIANT:** `resource.resourceType` MUST match the resource type in the request URL (400 error).

**INVARIANT:** Resource MUST pass `fhirSchemaValidator.validate()` against FHIR R4 JSON schema (422 error).

**INVARIANT:** All FHIR references MUST follow one of three formats:
- Contained: `#<localId>`
- Absolute URL: matches `^(?:[a-z+]+:)?\/\/`
- Relative: `ResourceType/id` (exactly one forward slash)
- Source: `src/utils/referenceValidator.js` lines 13-24

**INVARIANT:** Valid ID format: `/^[A-Za-z0-9\-.]+$/` (alphanumerics, hyphens, dots only).

**INVARIANT:** No security tag MAY have a null or empty `system` or `code`.

**INVARIANT:** Group with `actual=false` MUST NOT have any members (FHIR invariant grp-1, returns 400).
- Source: `src/preSaveHandlers/handlers/groupInvariantHandler.js` lines 40-57

**INVARIANT:** FHIR date type: no timezone. FHIR dateTime type: if hours/minutes specified, timezone SHALL be populated. "24:00" is NOT allowed.

**INVARIANT:** Dates are stored as UTC. Timezone offsets received are converted to UTC for storage.

**INVARIANT:** Do NOT add timestamps to plain dates during ingestion. "2022-01-07" stays "2022-01-07".

---

## 16. Reference Format Rules

| Prefix | Meaning |
|--------|---------|
| `Patient/` | Direct patient reference |
| `Person/` | Direct person reference |
| `person.` | Proxy patient prefix (virtual, rewritten at query time) |
| `Practitioner/<id>\|nppes` | NPI-based practitioner (pipe-delimited sourceAssigningAuthority) |

**INVARIANT:** `_uuid`/`id` are NOT secrets — they are deterministic UUIDv5 hashes derivable from `<sourceId>|<sourceAssigningAuthority>`. Never use them as sole authorization factors.

**INVARIANT:** Any externally-provided ID is moved to the identifier field at ingestion. b.well generates a UUID for the id field.

**INVARIANT:** FHIR Server v3+ uses UUIDv5 as preferred ID format. Existing UUIDv4 IDs continue to work.

---

## 17. $everything Operation

**INVARIANT:** `$everything` requires an `id` parameter (path or query).

**INVARIANT:** Person `$everything` scopes results to only the requested Person id(s) — sibling Persons sharing the same Patient are resolved internally but excluded from the response.

**INVARIANT:** Subscription/SubscriptionStatus/SubscriptionTopic are scoped by `client_person_id` in Person $everything.

**INVARIANT:** Proxy patient ids and regular patient ids CANNOT be mixed in the same $everything request (returns 400).

**INVARIANT:** Non-clinical resource references are fetched up to recursive depth 3.
- Source: `src/constants.js` line 154 (`EVERYTHING_OP_NON_CLINICAL_RESOURCE_DEPTH = 3`)

**INVARIANT:** Hidden-tagged resources are excluded by default (unless `_includeHidden=true`).

**INVARIANT:** $everything returns ALL clinical resources for a patient. Non-clinical resources (Practitioner, Organization, Location, Endpoint) are included by default up to 3 levels of depth from clinical resources.

**INVARIANT:** `_includePatientLinkedOnly=true` restricts to patient-linked resources only (no non-clinical expansion).

**INVARIANT:** Querying by Client Person returns data from all Patients linked to that Client Person. Querying by Main Person returns data across ALL tenants for that human. Querying by Patient returns only that specific Patient's data.

---

## 18. Bulk Export ($export)

**INVARIANT:** Bulk export is restricted to non-patient REST requests ONLY (service/admin scopes). Patient-scoped JWT returns 403.

**INVARIANT:** Export is asynchronous — POST returns 202 with `Content-Location` URL for polling.

**INVARIANT:** Only resources allowed by the scopes in the request are exported.

**INVARIANT:** Export status progression: accepted → in-progress → completed | entered-in-error.

**INVARIANT:** Exported files kept on S3 for 7 days, then automatically deleted.

**INVARIANT:** S3 directory structure: `exports/{owner-tag}/{ExportStatus-id}/`.

**INVARIANT:** ExportStatus resources always have owner tag = "bwell".

---

## 19. Bulk Import ($import)

**INVARIANT:** $import rejects patient-scoped tokens (403).

**INVARIANT:** `inputFormat` MUST be `application/fhir+ndjson`. `resourceType` MUST be `Parameters`.

**INVARIANT:** Requires 1-100 input files. Each file must be 50 MB to 5 GB. Each NDJSON line must be under 16 MB.

**INVARIANT:** Input URLs must be valid S3 URIs (`s3://bucket/key`) with bucket in configured allow-list.

**INVARIANT:** One range failing does NOT fail entire Task (unless all fail).

**INVARIANT:** Duplicate resources within a single ~100MB batch are rejected. Across batches, processed via merge (idempotent).

**INVARIANT:** Task status progression: requested → in-progress → completed | failed. Stalled task timeout: 30 minutes.

**INVARIANT:** Consumers align to NDJSON line boundaries: skip first partial line if byteRangeStart > 0; read one extra line past byteRangeEnd.

---

## 20. Search & Pagination

**INVARIANT:** Default page size = 100 (when `_count` not specified).

**INVARIANT:** Max page size = 10,000 (hard limit).

**INVARIANT:** Default sort = `_uuid` when no `_sort` parameter provided.

**INVARIANT:** Pagination uses `_getpagesoffset` parameter (offset-based).

**INVARIANT:** Binary resource search is NOT supported (returns 404). Direct read by ID returns 200.

**INVARIANT:** `LENIENT_SEARCH_HANDLING` = permit unknown search parameters. `STRICT_SEARCH_HANDLING` = reject with error.

**INVARIANT:** AuditEvent queries MUST supply required date range filter. Date range bounded by `configManager.auditEventMaxRangePeriod`.

---

## 21. Streaming Response Behavior

**INVARIANT:** Responses are streamed — resources sent directly without loading entire result set in memory.

**INVARIANT:** Two MongoDB timeouts: `MONGO_TIMEOUT` (60s default) for initial query; `MONGO_STREAMING_TIMEOUT` for ongoing streaming.

**INVARIANT:** If initial query takes > 60 seconds, returns 500 with OperationOutcome.

**INVARIANT:** If first batch sent within 60s but total > 60 minutes: status is 200 (already sent), OperationOutcome appended at end.

**INVARIANT:** Clients MUST: (1) check status code = 200, (2) verify valid JSON/NDJSON, (3) check for OperationOutcome resources in response, (4) if found, retry with `id:above=<last_valid_id>`.

**INVARIANT:** Response batch size = 50 documents per chunk (configurable via `STREAM_RESPONSE_BATCH_COUNT`).

---

## 22. Error Response Codes

| Code | Condition | Issue Code |
|------|-----------|------------|
| 400 | Invalid/missing parameter, bad reference format, schema validation failure | INVALID |
| 401 | Missing/invalid token | FORBIDDEN |
| 403 | Valid token but insufficient permissions | FORBIDDEN |
| 404 | Resource does not exist | NOT_FOUND |
| 405 | HTTP method not supported | NOT_SUPPORTED |
| 409 | Resource version/state conflict | CONFLICT |
| 410 | Resource has been deleted | NOT_FOUND |
| 422 | FHIR schema validation failure (structural) | - |
| 500 | Unhandled server error | EXCEPTION |

**INVARIANT:** PUT/$merge returns 403 (not 404) when a resource EXISTS but is inaccessible to the caller.

---

## 23. Caching Rules

**INVARIANT:** $everything cache TTL = 300 seconds (configurable via `everythingCacheTtlSeconds`). Bypassed with `cache-control: no-cache` header.

**INVARIANT:** Cache stored ONLY when ALL conditions met: (1) accepts JSON or NDJSON, (2) no query parameters present, (3) patient account request.

**INVARIANT:** Cache key format: `{ResourceType}:{id}:Everything:Generation:{gen}:Scopes:{hash}:Param:{hash}`

**INVARIANT:** Cache invalidates on Consent writes (generation counter incremented for Patient AND linked Person UUIDs).

**INVARIANT:** Cache-invalidating parameters (skip cache entirely): `_since`, `_includePatientLinkedOnly`, `_rewritePatientReference`, `_includeNonClinicalResources`, `_debug`, `_explain`, `_includeHidden`, `_includeProxyPatientLinkedOnly`, `_excludeProxyPatientLinked`, `_includePatientLinkedUuidOnly`, `_includeUuidOnly`, `contained`

**INVARIANT:** Proxy Patient by Source ID: NO caching. Patient by Source ID: cached only when exactly one match.

**INVARIANT:** X-CACHE response header: `Hit` or `Miss`.

---

## 24. Audit Event Requirements

**INVARIANT:** AuditEvents MUST be created for ALL CRUD operations (action codes: C, R, U, D).

**INVARIANT:** Successful operations produce AuditEvent with `entity.what` referencing the resource.

**INVARIANT:** Failed operations (4xx/5xx) produce AuditEvent with action=E, NO `entity.what` reference, only `entity.detail` with requestUrl.

**INVARIANT:** AuditEvents for error requests include `outcomeDesc` matching the HTTP status text ("Bad Request", "Not Found").

**INVARIANT:** All AuditEvents have owner=bwell, access=bwell (platform-owned, not tenant-specific).

**INVARIANT:** AuditEvents MUST NOT trigger audit logging themselves (prevents infinite recursion).

**INVARIANT:** Large entity lists split into multiple AuditEvents (prevents exceeding 16MB BSON limit).

**INVARIANT:** For delegated users, AuditEvent records TWO agents: end-user (requestor=false) and actor/service (requestor=true with consent policy reference).

**INVARIANT:** Audit events are queryable within 60 seconds of the operation (SLA).

**INVARIANT:** AuditEvent searches MUST include explicit date range boundaries (both lower and upper).

**INVARIANT:** AuditEvents stored in time-partitioned collections: `AuditEvent_4_0_0_<YYYY>_<MM>`.

**INVARIANT:** Post-request processing (audit, events) executes AFTER response sent to client (eventually consistent).

---

## 25. Kafka Event System

**INVARIANT:** Change events follow FHIR AuditEvent schema, fired AFTER response returned (via PostRequestProcessor).

**INVARIANT:** Change events are NOT fired for AuditEvent resources or history collection writes.

**INVARIANT:** Patient/Person Data Change Events emitted whenever any clinical resource linked to a Patient/Person is updated.

**INVARIANT:** Default Kafka-enabled resources: `Consent, ExportStatus`. Others require explicit config via `KAFKA_ENABLED_RESOURCES`.

**INVARIANT:** CloudEvents envelope format mandatory. Partition keys must ensure entity ordering (typically entity ID or tenant + entity ID). For subscription events specifically: Patient ID + Resource Type format (`{patientId}|{resourceType}`).

**INVARIANT:** All consumers MUST be idempotent (at-least-once delivery assumed). Duplicate processing MUST produce the same result.

**INVARIANT:** The FHIR server API MUST throw an error if Kafka event publishing fails — silent failure with 200 OK response causes data loss and is a critical bug.

**INVARIANT:** Cloud event source = `https://www.icanbwell.com/fhir-server`.

**INVARIANT:** Kafka events from resource changes generated in `DatabaseBulkInserter.postSaveAsync()`. An Update event is ALSO added at end of Create, Patch, and Update operations.

---

## 26. Access Logging

**INVARIANT:** Access logs created for all write operations and read operations with payloads.

**INVARIANT:** Retrieving access logs requires admin scope (`admin/*.*`).

**INVARIANT:** Access logs expire after 7 days (604,800 seconds).

**INVARIANT:** Access log stream response body limit = 100 bytes.

---

## 27. Person-Patient Data Model

**INVARIANT:** Guest users identified by meta.tag: system `https://www.icanbwell.com/userType`, code `guest` (active) or `converted-from-guest` (registered).

**INVARIANT:** Identity verification levels (codes from `https://fhir.icanbwell.com/4_0_0/CodeSystem/document-reference-category`): IAL1, IAL1.2, IAL1.4, IAL2, IAL3, PhoneVerified, EmailVerified.

**INVARIANT:** A single Verified Patient DocumentReference per person. New verification data is merged into existing (not duplicated).

**INVARIANT:** There is a SINGLE Practitioner record per NPI. sourceAssigningAuthority must be "nppes". References use format: `Practitioner/<id>|nppes`.

**INVARIANT:** NPI detection: `/^\d{10}$/` (or Luhn algorithm with "80840" prefix).

---

## 28. Person Matching Algorithm

**INVARIANT:** MATCH_THRESHOLD = 0.955. Scores ≥ 0.955 trigger automatic link creation.

**INVARIANT:** When match succeeds, Client Person ID is added to bWell Master Person.link with `assurance=level4`.

**INVARIANT:** Candidate selection: two-stage fallback — (1) MongoDB Atlas $search with MAX_BLOCKING_CANDIDATES limit (default 100), then (2) basic attribute search. Both empty = no match.

**INVARIANT:** User-provided candidates bypass threshold filtering (return all scored results). Blocking-search candidates apply threshold.

**INVARIANT:** Fuzzy matching uses Levenshtein distance (insertion:1, deletion:1, substitution:1), cutoff at 0.7 ratio (rapidfuzz).

**INVARIANT:** Postal codes use only first 5 digits (ZIP, not ZIP+4).

**INVARIANT:** PROA connection gives +0.05 boost to matching score.

**INVARIANT:** Design principle: false positive (wrong match) is WORSE than false negative (missed match). Threshold set high to minimize false positives.

---

## 29. Proxy Patient Resolution

**INVARIANT:** Proxy patient (`Patient/person.<uuid>`) is a virtual resource that does NOT exist in storage. Queries are rewritten to search all linked Patients.

**INVARIANT:** Person id for proxy patient must always be a global uuid.

**INVARIANT:** Proxy patient lookup: UUID-format → lookup by `_uuid`; non-UUID → lookup by `_sourceId` (with access tag filtering).

**INVARIANT:** After resource fetch, `proxyPatientReferenceEnrichmentProvider` rewrites Patient IDs back to `person.<uuid>` format.

---

## 30. PROA Pipeline Rules

**INVARIANT:** PROA pipeline creates a MedicationStatement for each MedicationRequest.

**INVARIANT:** PROA pipeline creates Communication resources for "New" icon notifications.

**INVARIANT:** PROA pipeline updates IDs by prefixing with service_slug.

**INVARIANT:** PROA pipeline uses GraphDefinition to determine FHIR API calls per token.

**INVARIANT:** Person matching in pipeline: (1) check if Person already includes Patient, (2) load Client Person by client_fhir_person_id, (3) check if it links to patient, (4) match demographics and add link if match. Running twice does NOT create duplicate links.

**INVARIANT:** Data connection status priority (highest to lowest): User Matching Error > Connection Error > Mapping Error > Sending to FHIR Error > Intelligence Layer Error.

---

## 31. Data Connection Lifecycle

**INVARIANT:** ATS must restrict status updates FROM Disconnected and Deleted status from all internal sources. Only user can update from frontend.

**INVARIANT:** Token status: NEW → RETRIEVING_DATA → DATA_RETRIEVED → (user action) → DISCONNECTED | DELETED. Only tokens in [NEW, RETRIEVING_DATA, DATA_RETRIEVED] are active.

**INVARIANT:** API token expiration = 10 minutes.

**INVARIANT:** Race condition protection: ATS receiving update for Deleted token triggers re-deletion event.

**INVARIANT:** Delete token permanently ONLY if status is still Deleted (prevents deleting reconnected token).

**INVARIANT:** Walgreens auto-connect on account creation. Users CANNOT remove Walgreens connection from Walgreens app.

**INVARIANT:** Walgreens deletion: remove connectionType (Proa) from meta.security rather than deleting resource. Person-Patient link NOT removed.

---

## 32. Data Deletion Pipeline

**INVARIANT:** Deletion severs connection between Client Person and Patient (does NOT delete Person).

**INVARIANT:** Request $everything with `_since` = token created_date. Delete resource IF it references the patient AND references the slug from the token.

**INVARIANT:** Resources with NO patient linkage (Location, PractitionerRole) PERSIST after deletion (congressional mandate for plan-net IG).

**INVARIANT:** Deletion pipeline runs every 10 minutes.

---

## 33. CQL Engine & Care Gaps

**INVARIANT:** CQL Engine operates at the scope of the Client Person (not proxy Patient or master Person).

**INVARIANT:** Care gap Task creation criteria: initial_population=1, denominator=1, denominator_exclusion=0, numerator=0 → Task status "ready".

**INVARIANT:** Care gap Task completion: numerator=1 → Task status "completed".

**INVARIANT:** Care gap Task cancellation: denominator_exclusion=1 → Task status "canceled". Only applies to Tasks in "ready" state (NOT in-progress).

**INVARIANT:** If Observation value equals previous value: DO NOTHING (no event, processing stops).

**INVARIANT:** Cohort membership determined by CQL output variables: InCohort_Out_Bool, Eligibility_Output_Obs, Completed_Out_Date, Completed_Output_Obs.

---

## 34. Composition Service

**INVARIANT:** Pipeline status transitions: PENDING → FETCHING → GENERATING → WRITING → COMPLETED (or FAILED).

**INVARIANT:** Three trigger modes: synchronous HTTP (:generate), asynchronous HTTP (:generate-async), Kafka CloudEvents.

**INVARIANT:** Debounce applies to HTTP triggers only. Kafka events MUST NEVER be debounced.

**INVARIANT:** Kafka failures retry with exponential backoff (backoff_seconds × 2^attempt). After max retries, failed result event published.

**INVARIANT:** Async job records expire after 24h TTL in MongoDB.

**INVARIANT:** FHIR writer uses $merge endpoint. Must be enabled via `FHIR_WRITER_ENABLED=true`.

---

## 35. Subscription System

**INVARIANT:** Subscription patient reference system = `https://icanbwell.com/codes/source_patient_id`.

**INVARIANT:** Subscription person reference system = `https://icanbwell.com/codes/client_person_id`.

**INVARIANT:** Subscription/SubscriptionStatus/SubscriptionTopic are person-scoped (filtered by `client_person_id`).

**INVARIANT:** Subscription ID for PROA = UUID v5 of `{client_person_id}_{source_patient_id}_{service_slug}`.

---

## 36. Event-Driven Patterns

**INVARIANT:** Sagas for multi-service workflows. Each step independently completable and compensatable. Compensating actions idempotent.

**INVARIANT:** Choreography over orchestration for cross-service workflows.

**INVARIANT:** Dead letter topics for messages failing after retries.

**INVARIANT:** Kafka NOT used as request-reply mechanism.

**INVARIANT:** Schema evolution: additive changes only. No field removal, rename, or type change without EA-approved migration plan.

---

## 37. Authentication & Token Management

**INVARIANT:** Three token types: service-to-service (client credentials), admin user (username/password), Person/Patient (SMART on FHIR authorization code flow).

**INVARIANT:** Patient-scoped tokens carry `clientFhirPersonId` in JWT payload.

**INVARIANT:** Token verification uses JWKS public keys from OAuth provider.

**INVARIANT:** JWT expiry clock tolerance = 30 seconds.

**INVARIANT:** JWKS requests per minute = 60.

**INVARIANT:** Refresh token rotation: old token has 60-second grace period. After grace, treated as replayed and rejected.

**INVARIANT:** Refresh token metadata persists 30 days in Redis.

**INVARIANT:** Token validity ALWAYS validated against IdP (Cognito/Descope). Redis is NEVER sole authority.

**INVARIANT:** Guest tokens limited to 4 concurrent per IP. 5th rotates oldest.

**INVARIANT:** S2S authentication: AES-256-CBC. Shared secret + UTC timestamp (YYYY-MM-DDTHH:mm:ssZ) separated by "@". Timestamp must NOT be older than 30 seconds.

**INVARIANT:** HMAC signature: HMAC-SHA256(key=API_SECRET, message=METHOD + PATH + BODY_SHA256 + TIMESTAMP + CLIENT_KEY, newline-separated), Base64 encoded. Timestamp within ±5 minutes.

**INVARIANT:** OAuth issuer = `https://icanbwell.okta.com`. Custom claims mapped from Cognito fields.

---

## 38. SDK & API Gateway Contract

**INVARIANT:** SDK errors MUST NOT be thrown — all returned as typed Result values (BWellTransactionResult or BWellQueryResult).

**INVARIANT:** SDK runtime dependencies strictly limited: graphql-request and @opentelemetry/* only. New deps require explicit approval.

**INVARIANT:** SDK tests MUST NOT use jest.mock() — plain mock classes implementing interfaces only.

**INVARIANT:** Public API field names use domain language, not FHIR resource names or internal identifiers.

**INVARIANT:** Client-facing capabilities go through federated GraphQL gateway. No point-to-point bypass.

**INVARIANT:** HTTP retries: automatic only for idempotent methods (GET, HEAD, OPTIONS). POST/PUT/PATCH require explicit `is_idempotent=true`.

**INVARIANT:** HTTP timeout = 30 seconds. Retry attempts = 3 (initial + 2). Exponential backoff (base 100ms).

**INVARIANT:** Retryable status codes: 429, 502, 503, 504.

---

## 39. Configuration Constants

### Database

| Constant | Value | Source |
|----------|-------|--------|
| MongoDB min pool size | 3 (production Helm) / 10 (code default) | common.values.yaml / config.js |
| MongoDB max pool size | 5 (production Helm) / 100 (code default) | common.values.yaml / config.js |
| MongoDB operation timeout | 60,000 ms | common.values.yaml |
| MongoDB batch size | 100 documents | common.values.yaml |
| MongoDB BSON limit | 16,777,216 bytes (16 MB) | constants.js |
| History write concern | majority | config.js |

### Search & Pagination

| Constant | Value | Source |
|----------|-------|--------|
| DB_SEARCH_LIMIT | 100 | constants.js |
| DB_SEARCH_LIMIT_FOR_IDS | 1,000 | constants.js |
| ClickHouse max page size | 10,000 | clickHouseConstants.js |
| ClickHouse max batch size | 50,000 | clickHouseConstants.js |
| Max PATCH operations | 10,000 | clickHouseConstants.js |

### Request Handling

| Constant | Value | Source |
|----------|-------|--------|
| Max request payload | 25 MB | common.values.yaml |
| Stream response batch count | 50 | common.values.yaml |
| Graceful shutdown timeout | 59,000 ms | common.values.yaml |
| CORS max age | 86,400 seconds (24h) | config.js |
| Server port | 3000 | common.values.yaml |

### Caching & Expiry

| Constant | Value | Source |
|----------|-------|--------|
| Default cache max count | 25 | constants.js |
| Default cache expiry | 24 hours | constants.js |
| User info cache expiry | 5 minutes | constants.js |
| Access logs expiry | 7 days (604,800s) | common.values.yaml |
| Audit event max size | 1,048,576 bytes (1 MB) | common.values.yaml |
| $everything cache TTL | 300-600 seconds | configurable |
| $access-history window | 90 days | clickHouseConstants.js |
| Export file retention | 7 days | documentation |
| Async job TTL | 24 hours | fhir-composition-service |

### Feature Flags (Production Defaults)

| Flag | Value | Effect |
|------|-------|--------|
| VALIDATE_SCHEMA | 1 | Schema validation enabled |
| ENABLE_PATIENT_FILTERING | 1 | Multi-tenant isolation active |
| ENABLE_EVENTS_KAFKA | 1 | Kafka events active |
| ENABLE_BULK_EXPORT | 1 | Bulk export enabled |
| ENABLE_GRAPHQL | 0 | GraphQL disabled by default |
| ENABLE_PATIENT_DATA_CHANGE_EVENTS | 0 | Opt-in |
| ENABLE_PERSON_DATA_CHANGE_EVENTS | 0 | Opt-in |
| RETURN_BUNDLE | 1 | Results wrapped in Bundle |
| STREAM_RESPONSE | 1 | Streaming enabled |

---

## 40. SSE Connection Lifecycle

**INVARIANT:** All SSE service pods MUST use the same Kafka consumer group ID (`fhir-sse-consumer` by default). Using unique IDs per pod causes N× message duplication (10 pods = 10× duplication).

**INVARIANT:** SSE connections MUST emit a `token-expiring` event within the warning threshold (default 5 minutes) before JWT expiry, and a `token-expired` event immediately before closing the connection.

**INVARIANT:** SSE clients that reconnect with `Last-Event-ID` header MUST receive replayed events from the ClickHouse event store (up to the replay limit, default 1000 events).

**INVARIANT:** The `tokenExpiryWarningSent` flag on SSE connections MUST ensure the warning is emitted exactly once per connection — never zero, never more than once.

**INVARIANT:** SSE heartbeat checks MUST occur on each tick with `concatMap` to ensure expiry is detected with ±30s precision.

---

## 41. Kafka Partition & Consumer Rules

**INVARIANT:** Partition keys MUST use Patient ID + Resource Type (format: `{patientId}|{resourceType}`) to ensure all events for a patient's resources go to the same partition for ordering.

**INVARIANT:** The FHIR server API MUST throw an error if Kafka event publishing fails — it CANNOT silently fail and return 200 OK. Silent failure causes data loss.

**INVARIANT:** The MongoDB Kafka Connector MUST be configured with `change.stream.full.document=updateLookup` so update events include the full document for resource type extraction and patient reference resolution.

**INVARIANT:** Every external call MUST have an explicit timeout. Retries MUST use exponential backoff with jitter. Unbounded retries are forbidden.

**INVARIANT:** Partition key strategy MUST ensure ordering for the same entity (typically entity ID or tenant + entity ID).

**INVARIANT:** Consumers MUST assume at-least-once delivery and be idempotent — duplicate processing MUST produce the same result.

**INVARIANT:** Event schemas are real contracts. All changes MUST be documented in AsyncAPI specifications.

---

## 42. SSE Token Expiry Handling

**INVARIANT:** Token expiry timeline: warning event → grace period → expired event → connection close. The three events are distinct and ordered.

**INVARIANT:** `token-expiring` fires at `expiryTime - warningThreshold` (default 5 min before). The client has this window to refresh and reconnect.

**INVARIANT:** `token-expired` fires at exactly `expiryTime`. The server closes the connection immediately after emitting this event.

**INVARIANT:** On reconnect with a valid refreshed token and `Last-Event-ID`, the server replays missed events from ClickHouse in order (not re-fetched from Kafka).

---

## 43. Health Link Creation

**INVARIANT:** Health link creation MUST generate a unique `shlId` and encryption key, fetch the Person resource, create DocumentReference and CareTeam resources, and persist the client slug as a DocumentReference extension.

**INVARIANT:** The passcode flag MUST be set to `P` (POST /manifests endpoint) when a passcode is provided, and `U` (GET /shl-files endpoint) when no passcode is provided.

**INVARIANT:** Health link creation MUST emit a `HEALTH_LINK_CREATED` event to the `health_link.lifecycle.events` Kafka topic containing documentReference, encryptionKey, passcode, and permissions.

**INVARIANT:** Client Hub outage or unknown organization resolution MUST NOT throw — degrades to null clientSlug and uses IPS strategy instead of failing creation. Health link creation must succeed even when client metadata is unavailable.

**INVARIANT:** ClientSlug MUST be persisted as a DocumentReference extension so manifest/file retrieval (which has no JWT) can re-resolve the health data strategy later.

---

## 44. Health Data Strategy Resolution

**INVARIANT:** Strategy resolution MUST check the client slug extension on DocumentReference and query CCS for `isEverythingEnabled` (with Redis caching at `FEATURE_FLAGS_REFRESH_FREQUENCY` TTL).

**INVARIANT:** Everything strategy MUST fetch `$everything?_type=<USCDI v3 types>` in parallel with `$summary` (for PDF only).

**INVARIANT:** IPS strategy MUST fetch `$summary` + active Coverage and merge them.

**INVARIANT:** Health data bundles MUST be filtered by Consent class before encryption. Only consented data enters the encrypted payload.

**INVARIANT:** PDF generation MUST use Puppeteer/headless Chromium and is gated by `PDF_GENERATION_ENABLED` feature flag. PDF failure degrades to "no PDF in response" — NOT a failed response.

**INVARIANT:** The final bundle (with PDF if generated) MUST be encrypted as JWE, compressed with gzip, and cached in Redis with a TTL matching SHL expiration.

---

## 45. Response Build & Caching

**INVARIANT:** Response payload builds MUST deduplicate work using both in-pod `inFlightBuilds` maps AND cross-pod Redis `SET NX` locks with ownership tokens.

**INVARIANT:** The response builder MUST check for an already-in-progress build before doing work. If another pod holds the lock, return immediately without building.

**INVARIANT:** Redis build locks MUST have a random per-acquisition token and a 120-second TTL, with ownership-guarded release (only delete if token matches).

**INVARIANT:** Cache miss sync fallbacks (3a/3b) MUST NOT register in `inFlightBuilds`, take the build lock, or write to the response cache. They are one-shot responses only.

**INVARIANT:** Manifest/file access MUST attempt to join an in-progress build before falling back to synchronous construction, with polling capped at 15 seconds.

---

## 46. Manifest & File Access Control

**INVARIANT:** Access limit validation MUST read from the Consent `shl-config` extension (default 2) and count from `shl-access-count:{documentReferenceId}` in Redis, throwing 403 (throttled) when count is reached.

**INVARIANT:** Passcode-less (U flag) links MUST reject passcode-protected (P flag) links with 403 Forbidden. The flag is a gate — you cannot bypass a passcode by using the passcode-less endpoint.

**INVARIANT:** Every successful or failed access MUST emit a `HEALTH_LINK_AUDIT` event to `health_link.audit.events` Kafka topic.

---

## 47. Health Link Audit Events

**INVARIANT:** Audit event processing MUST create a CommunicationRequest for ALL accesses (success and failure).

**INVARIANT:** CareTeam update occurs ONLY on successful access — failed access does NOT modify the CareTeam.

**INVARIANT:** Audit event processing MUST emit a `HEALTH_LINK_VIEWED` event (success) or `HEALTH_LINK_FAILED_ACCESS_ATTEMPT` event (failure) to analytics after creating audit artifacts.

---

## 48. Data Connection Events

**INVARIANT:** The `/v1/data-connection` POST endpoint MUST retrieve the user's FHIR details and publish a `ConnectionDataSourceStatusChanged` CloudEvent to Kafka.

**INVARIANT:** Data connection requests MUST include required fields: `dataSourceId`, `dataSourceName`, `clientPersonId`, and `managingOrganization`. Missing any field is a validation failure.

---

## 49. CAN Integration Rules

**INVARIANT:** CAN (CMS Aligned Network) integration MUST handle patient consent approvals/denials and process IAL2 tokens for authenticated data access from the `can-integration.consent.events` topic.

**INVARIANT:** Sagas MUST be resilient to out-of-order delivery and duplicate events. Each step must be independently completable and compensatable.

**INVARIANT:** Dead letter topics MUST be used for messages that fail processing after retries. Failed messages cannot be silently dropped.

---

## 50. Intelligence Layer Integration

**INVARIANT:** Intelligence Layer integration MUST trigger Prefect pipeline workflows for client person data events from the `can-integration.intelligence_layer.events` topic.

**INVARIANT:** Tenant isolation is mandatory on every persistence model and every query path. Every read and write MUST enforce tenant ownership boundaries — no cross-tenant data leakage is acceptable under any circumstance.

---

## 51. Collection Naming & Architecture

**INVARIANT:** Collection names follow pattern `{ResourceType}_4_0_0`. History collections: `{ResourceType}_4_0_0_History`. Access logs: fixed name `access-logs`.

**INVARIANT:** Five separate logical databases (potentially separate clusters): main FHIR, audit events, audit read-only (online archive), access logs, and resource history.

**INVARIANT:** AuditEvent lives in a dedicated database (`AUDIT_EVENT_MONGO_DB_NAME: audit-events`). AuditEvent reads can go to a separate read-only archive cluster when `enableAuditEventArchiveRead` is enabled.

**INVARIANT:** `ExportStatus_4_0_0` is a custom (non-standard FHIR) collection created alongside standard resources.

**INVARIANT:** System collections (`system.*`, `fs.files`, `fs.chunks`) are filtered out from index and collection operations.

**INVARIANT:** Resources are stored WITHOUT MongoDB `_id` in the application layer. `_id` is auto-generated by MongoDB but ignored by the application. The application primary key is `_uuid`.

---

## 52. Index Requirements

**INVARIANT:** `_uuid` MUST have a unique index on every collection EXCEPT AuditEvent and access-logs.

**INVARIANT:** `_sourceId + _uuid` compound index MUST exist on every collection except AuditEvent and access-logs.

**INVARIANT:** `meta.source + _uuid` compound index MUST exist on all collections except AuditEvent and access-logs.

**INVARIANT:** Per-tenant `_access.{client}` indexes are created dynamically based on `ACCESS_TAGS_INDEXED` env var. Each generates compound index `{_access.{client}: 1, _uuid: 1}`.

**INVARIANT:** History collections MUST have indexes on: `{id: 1}`, `{resource._uuid: 1}` (or hashed variant for high-volume types), and `{resource.meta.lastUpdated: 1}`.

**INVARIANT:** Production uses external `mongoIndexes.json` file (via `CUSTOM_INDEXES_FILE_PATH`) that overrides in-code indexes. External file CANNOT contain wildcard `*` key.

**INVARIANT:** Production uses hashed `resource._uuid` indexes on history collections for high-volume resource types instead of standard ascending.

**INVARIANT:** TTL index exists ONLY on `access-logs` collection (`timestamp` field). Default 30 days, production 7 days (604,800s). No other collections have TTL indexes.

---

## 53. Concurrency Control & Optimistic Locking

**INVARIANT:** `_uuid` is UUIDv5 deterministically generated from `{id}|{sourceAssigningAuthority}`. If resource `id` is already a UUID, it IS the `_uuid`.

**INVARIANT:** Optimistic locking filter: `{ $and: [{ _uuid: doc._uuid }, { 'meta.versionId': previousVersionId }] }`. If matchedCount=0, resource was updated concurrently — re-read and re-merge.

**INVARIANT:** Concurrent retry limit is 10 attempts (`REPLACE_RETRIES`). After 10 failures, the operation throws.

**INVARIANT:** For initial inserts, uses `updateOne` with `$setOnInsert` and `upsert: true` (not `insertOne`) to handle concurrent inserts of same resource.

**INVARIANT:** AuditEvent is the exception: uses plain `insertOne` (no upsert) because AuditEvents are never updated or deduplicated.

**INVARIANT:** `meta.versionId` starts at `'1'` for new resources and increments by 1 on each successful update. String type (not integer).

**INVARIANT:** During optimistic-concurrency retry, reads MUST use `ReadPreference.PRIMARY` to avoid stale reads causing infinite retry loops.

---

## 54. History Collection Rules

**INVARIANT:** Every write to a non-AuditEvent resource MUST also write a history entry to the corresponding `_History` collection.

**INVARIANT:** AuditEvent NEVER gets a history entry. Attempting to get a history collection for AuditEvent throws.

**INVARIANT:** History entries are `BundleEntry` documents containing: `id` (resource's _uuid), `resource` (full snapshot), `request` (method + requestId + URL).

**INVARIANT:** History entries are insert-only (blind inserts with `operationType: 'insert'`). Never check for existing history entries.

**INVARIANT:** History collections live in a dedicated database/cluster, configurable via `RESOURCE_HISTORY_MONGO_URL`.

**INVARIANT:** Production history cluster uses `w=1` (single node acknowledgment) for performance since history is append-only.

---

## 55. Two-Timeout Streaming Pattern

**INVARIANT:** Standard queries use `mongoTimeout` (default 2 min, production 60s). Streaming queries that timeout retry with `mongoStreamingTimeout` (default 60 min).

**INVARIANT:** On MongoDB error code 50 (ExceededTimeLimit) mid-stream and NO retry attempted: retry ONCE with new cursor starting after last processed `_uuid` (`{ _uuid: { $gt: lastUUID } }`), switch to longer timeout.

**INVARIANT:** After streaming retry, if second code 50 occurs, does NOT retry further (hasRetried flag). Emits OperationOutcome into stream and closes with HTTP 500.

**INVARIANT:** Every query MUST have `maxTimeMS` set. No query runs without a timeout.

---

## 56. Write Concern & Connection Pool

**INVARIANT:** Default write concern: `majority` for main FHIR database. History: `w=1`. Access logs: `w=1`.

**INVARIANT:** Production uses `readPreference=secondaryPreferred` for read load distribution across replicas.

**INVARIANT:** Connection pool: production uses minPoolSize=3, maxPoolSize=5 per pod (with horizontal scaling to 100 pods). Access logs pool: maxPoolSize=10, minPoolSize=1.

**INVARIANT:** Network compression uses `zstd`. `retryReads: true` always enabled. `retryWrites=true` in production.

**INVARIANT:** BSON document size limit is 16 MiB. Oversized documents (error codes 10334, 17419) get graceful per-resource error reporting rather than failing entire batch.

---

## 57. PROA Consent (Expands Visibility)

**INVARIANT:** PROA consent is opt-in. Without active, permit-type Consent with category `dataSharing`, upstream PROA/IAS data is invisible.

**INVARIANT:** PROA consent EXPANDS visibility. Server ORs a connection-type-filtered query branch onto original: `{ $or: [originalQuery, queryWithConsentedData] }`. Never restricts what caller could already see.

**INVARIANT:** PROA consent gated by BOTH `ENABLE_CONSENTED_PROA_DATA_ACCESS` env var AND caller-supplied `allowConsentedProaDataAccess` flag. Both must be true.

**INVARIANT:** PROA consent unlocked data filtered by `connectionType` meta.security tag. Only resources matching `CONSENT_CONNECTION_TYPES_LIST` (default: `['proa']`) are included.

**INVARIANT:** IAS data rides same consent path. Requires explicit configuration widening `CONSENT_CONNECTION_TYPES_LIST` to include `'ias'`.

**INVARIANT:** PROA consent does NOT make upstream resources individually readable by direct ID. Only widens aggregate $everything/search view.

**INVARIANT:** PROA consent evaluated at Person level, not individual Patient level. Single consent referencing one patient linked to a Person grants visibility to ALL patients linked to that Person with matching connectionType.

---

## 58. CMS Consent (Restricts to Consented)

**INVARIANT:** CMS consent gates Patient resource access for `userType: 'cms-partner'` callers ONLY. Only applies when `resourceType === 'Patient' && userType === 'cms-partner'`.

**INVARIANT:** CMS consent RESTRICTS (not expands). Narrows Patient search to consented patient UUIDs: `{ $and: [originalQuery, { _uuid: { $in: consentedPatientIds } }] }`.

**INVARIANT:** CMS consent FAILS CLOSED. No consent found = impossible filter `{ _uuid: '__invalid__' }` matching zero records. Never falls back to unrestricted access.

**INVARIANT:** CMS consent uses category `cms:share:records` under system `http://www.icanbwell.com/consent-category`.

---

## 59. Delegated Access Consent

**INVARIANT:** Exactly ONE active Consent per grantor-actor pair. Zero = 403 "not enough permissions". Multiple = 403 "ambiguous permissions". Not configurable.

**INVARIANT:** Delegated actors are READ-ONLY. Allowed operations: `search`, `searchById`, `everything`, `graph`. All writes return 403.

**INVARIANT:** `unclassified` sensitivity category is ALWAYS excluded for delegated users regardless of Consent content. Hardcoded, not configurable.

**INVARIANT:** Null/undefined actor or personIdFromJwtToken fails closed (returns false) WITHOUT calling rules manager.

**INVARIANT:** Delegated consent filtering rules cached on request-scoped `actor._filteringRules`. Same actor in same request doesn't re-fetch.

**INVARIANT:** Redis caching DISABLED for delegated users. $everything and $summary skip both cache reads and writes for delegated actors.

**INVARIANT:** Consent can deny specific sensitivity categories via nested provisions with `type: 'deny'` and `securityLabel` codes.

---

## 60. DataViewControl Consent

**INVARIANT:** DataViewControl lets patient exclude specific resources from $everything and GraphQLv2 results. Does NOT apply to REST search or GraphQL v1.

**INVARIANT:** Only triggered for clients in `CLIENTS_WITH_DATA_CONNECTION_VIEW_CONTROL` list. Only for patient-scoped requests (isUser=true).

**INVARIANT:** Absence of DataViewControl consent = no exclusions. All resources visible. This is correct because this mechanism REMOVES things patient requested hidden.

---

## 61. Consent State Machine

**INVARIANT:** Only `status: 'active'` consents are evaluated. All other statuses treated as non-existent.

**INVARIANT:** Revocation is immediate. Setting consent to `inactive` takes effect on very next request — no grace period.

**INVARIANT:** Deleting a consent removes access immediately.

**INVARIANT:** `provision.type: 'deny'` never unlocks data even if consent is active with current period.

**INVARIANT:** Consent validity requires ALL of: `status: 'active'`, `provision.type: 'permit'`, `provision.period.start <= now OR absent`, `provision.period.end >= now OR absent`.

---

## 62. Consent Cache Invalidation

**INVARIANT:** Consent writes trigger `ConsentCacheInvalidationHandler` which bumps Redis generation counter (`Patient:<uuid>:Everything:Generation` or `ClientPerson:<uuid>:Everything:Generation`). Changes $everything cache key causing miss on next read.

**INVARIANT:** Cache invalidation is best-effort. Failure does NOT fail the Consent write. Worst case: stale data served until TTL expires.

**INVARIANT:** Handler walks up Person link graph (immediate Person + bwell master Person) to bump generation counters for both.

**INVARIANT:** In $everything, consent set MUST be scoped per batch (INC-331 regression). Cached consent decision from chunk 1 MUST NOT bleed into chunk 2 when processing more patients than `everythingBatchSize`.

---

## 63. SHL Consent Rules

**INVARIANT:** Each SHL has associated Consent resource fetched via `Consent?patient=<patientRef>&source-reference=DocumentReference/<docRefId>`.

**INVARIANT:** SHL passcode hash stored in `provision.extension` under URL `https://www.icanbwell.com/smart-health-links/StructureDefinition/passcode-hash`.

**INVARIANT:** SHL access limit stored on Consent in `provision.extension` path: `shl-config` → `access-limit` → `valueInteger`. Default 2, max 3.

**INVARIANT:** SHL filtering uses `Consent.provision.class` to define allowed FHIR resource types in shared bundle. Non-listed resources filtered out post-fetch.

**INVARIANT:** SHL property-level filtering uses nested `provision.provision` with extensions defining filter property and values.

---

## 64. OperationOutcome Format

**INVARIANT:** All FHIR REST errors returned as OperationOutcome with `issue[]` containing `severity`, `code`, `details.text`.

**INVARIANT:** 5xx errors MUST redact message to "Internal Server Error" to prevent leaking implementation details. Only 4xx retain descriptive messages.

**INVARIANT:** Batch/merge operations return per-resource `MergeResultEntry` objects with individual `operationOutcome`. Individual failures do NOT fail entire batch.

---

## 65. HTTP Status Code Mapping

**INVARIANT:** 400=invalid input, 401=authentication failure (missing/expired/malformed token), 403=authorization failure (insufficient scope), 404=not found, 405=method not allowed, 409=delete conflict, 412=If-Match version mismatch, 413=payload too large, 500=internal (always redacted), 503=transient infrastructure failure, 504=external timeout.

**INVARIANT:** Transient auth failures (JWKS unreachable) MUST return 503, NEVER 401. A 401 signals permanent credential invalidity and can trigger downstream grant revocation. (INC-322)

**INVARIANT:** Export status polling returns 404 (not 403) for unauthorized access to avoid leaking existence.

---

## 66. Retry & Circuit Breaker Patterns

**INVARIANT:** External HTTP requests: 3 retries default (`EXTERNAL_REQUEST_RETRY_COUNT`). Kafka producer: 3 retries with 500ms initial. Kafka consumer: 3 retries with exponential backoff (200ms initial). S3 writes: 3 retries with linear backoff (200ms * attempt).

**INVARIANT:** Webhook circuit breaker (fhir-subscription-service): 50% failure rate in 5-call window opens circuit, 60s wait, 2 calls in half-open. Per-subscription isolation. Circuit open = immediate DLT routing.

**INVARIANT:** ClickHouse event store circuit breaker: 50% failure rate in 5-call window, 30s open wait, 2 calls in half-open.

**INVARIANT:** Webhook 429 (Too Many Requests) is RETRYABLE (same as 5xx). Other 4xx are NON-RETRYABLE and immediately DLT'd. 4xx (except 429) counts as circuit breaker SUCCESS (server is healthy, rejecting payload).

**INVARIANT:** Webhook delivery: exponential backoff with jitter (initial 1s, max 8s, jitter 0.25, max 3 attempts, 10s timeout per call).

---

## 67. Fail-Open vs Fail-Closed Classification

**INVARIANT:** FAIL CLOSED: Authentication with missing strategy denies with 401. Resources with no access tag visible to nobody. Empty S3 bucket allow-list rejects all imports. ClickHouse Group member roster denies callers with no tenant scope.

**INVARIANT:** FAIL OPEN: Access log ClickHouse writes (lost log doesn't break request). ClickHouse schema init failure (events not persisted for replay, service continues). ClickHouse replay query failure returns empty list. JWKS cache warming during health check (failure doesn't fail endpoint). Redis connection failure (logged, not crash).

---

## 68. Streaming Mid-Response Errors

**INVARIANT:** When unretryable error occurs mid-stream: statusCode set to 500, final OperationOutcome pushed into stream body, then stream closed. Client receives error as part of Bundle.

**INVARIANT:** HttpResponseWriter only writes if `response.writable` is true. If not writable, chunk silently dropped.

**INVARIANT:** GraphQL: if `response.headersSent` is true when error occurs, passes to `next(err)` rather than attempting new response.

---

## 69. Dead Letter Topic (DLT) Rules

**INVARIANT:** Messages failing after `maxRetries` published to `{original-topic}.dlt` with original value, headers, error details, and `failedAt` timestamp. Original offset then commits normally.

**INVARIANT:** If DLT publish itself fails, error propagates (NOT swallowed) so offset does NOT commit. Losing message's only record is worse than redelivering.

**INVARIANT:** Non-retriable Kafka crashes (`payload.restart === false`) trigger `process.exit(1)` for k8s restart. Retriable crashes (`payload.restart === true`) self-heal in-process.

**INVARIANT:** Webhook DLT uses CloudEvents envelope with `type: "com.icanbwell.webhook.delivery.failed"` containing subscriptionId, endpoint, attemptCount, failureReason.

---

## 70. Guest User Lifecycle

**INVARIANT:** Guest tokens have `sub: 'guest'` and issuer ending `bwell.zone`. Validated by checking BOTH.

**INVARIANT:** Guest scope: `patient/*.* user/*.* access/*.*`. Registered user default: `patient/*.read user/*.* access/*.*`.

**INVARIANT:** Guest-to-registered conversion: create IdP account, strip guest meta tag from all 4 EMPI resources via fire-and-forget `removeGuestTag`. Tag removal is non-blocking; failure doesn't prevent token issuance.

**INVARIANT:** Guest optionally creates FHIR Person/Patient resources (with `guest` userType meta tag) if CCS `guest_access.createEmpiWithLogin` flag is true.

---

## 71. OAuth Grant Types & Token Exchange

**INVARIANT:** Supported OAuth grants at `/oauth/token`: `urn:ietf:params:oauth:grant-type:jwt-bearer` (Google Streamlined Linking), `refresh_token`, `urn:ietf:params:oauth:grant-type:token-exchange` (RFC 8693). Authorization code and client_credentials NOT supported.

**INVARIANT:** Token exchange validates BOTH `actor_token` (partner access token via partner JWKS) and `subject_token` (IAL2 patient identity token via IAL2 provider JWKS) independently.

**INVARIANT:** Currently only `cms-partner` user type supported for token exchange. Other user types throw.

**INVARIANT:** Refresh token rotation uses 60-second grace period. Replay within grace is recoverable. After grace, treated as replayed and rejected.

**INVARIANT:** Refresh token metadata cached 30 days (maps refresh token hash to clientRecord).

---

## 72. Scope Enforcement Deep Rules

**INVARIANT:** Token identified as user/patient token when ANY scope starts with `patient/` (case-insensitive). This determines whether JWT must contain FHIR identity fields.

**INVARIANT:** If patient scopes present, user scopes restricted to READ only. Write via user scopes blocked when patient scope exists.

**INVARIANT:** `access/*.*` is wildcard bypassing all tenant/access-tag filtering. Literal string `*` as access code.

**INVARIANT:** Resource access requires BOTH owner tag match AND access tag match. Multi-access-tagged resources visible to ANY tenant matching at least one tag (OR/membership/$in check, not AND/$all).

**INVARIANT:** Caller cannot add/remove access tags on resource it's not authorized for (unless `access/*.*`). Prevents silently sharing/revoking another tenant's access.

**INVARIANT:** Token with zero scopes rejected at authentication (401), not authorization (403). "No scope" = auth failure.

**INVARIANT:** Service accounts do NOT have `patient/` scopes. Presence of any `patient/` scope distinguishes user from service account.

**INVARIANT:** User tokens MUST contain: `clientFhirPersonId`, `clientFhirPatientId`, `bwellFhirPersonId`, `bwellFhirPatientId`. Missing any = auth rejected.

---

## 73. Account Deletion Sequence

**INVARIANT:** Deletion grace period configurable per-client (`account_deletion_days` in CCS). Default 30 days. Zero = immediate.

**INVARIANT:** Deletion sequence: (1) mark Person/Patient `active: false`, (2) delete from IdP, (3) remove from cache (critical — if skipped, FHIR IDs get reused making user think account still active), (4) publish `DELETION_IN_PROGRESS` event.

**INVARIANT:** Deletion uses distributed lock (60s TTL) to prevent concurrent deletion of same user.

**INVARIANT:** User undergoing deletion who tries to authenticate: system detects `isUserDeletionInProgress` and waits for completion.

---

## 74. Cognito/Descope Dual-IdP

**INVARIANT:** Dual IdP support: Cognito and Descope. Provider selection per-client via CCS `auth.idpProvider`. Default: Cognito.

**INVARIANT:** Descope userId = SHA-256 hash of `organizationId:userIdentifier`. Prevents collisions across orgs.

**INVARIANT:** Descope uses same JWT for both access and ID token (`sessionJwt` serves as both).

**INVARIANT:** Cognito username = `clientPersonId`. Same email + different client = different Cognito user.

**INVARIANT:** User migration only allowed within SAME Cognito user pool. Cross-pool migrations explicitly rejected.

**INVARIANT:** Same email + same client already existing = 409 Conflict. System does NOT merge on signup; rejects duplicate.

---

## 75. MFA & Phone Verification

**INVARIANT:** Only SMS_MFA supported. Cannot enable MFA without verified phone number.

**INVARIANT:** Updating phone number automatically disables MFA. User must re-verify and re-enable.

**INVARIANT:** Password reset requires BOTH current password + new password (not just new).

**INVARIANT:** Email domain validation per-client via CCS `auth.whitelistedEmailDomain`. Non-whitelisted domains rejected at signup.

---

## 76. GraphQL Schema & Federation

**INVARIANT:** FHIR server exposes GraphQL as federated subgraph via `@apollo/subgraph`. Root Query type annotated `@authenticated` — all operations require authentication at schema level.

**INVARIANT:** GraphQL v1 at `/$graphql`, v2 at `/4_0_0/$graphqlv2`. Both require JWT via passport.

**INVARIANT:** Schemas auto-generated from FHIR resource definitions. Manual edits forbidden.

**INVARIANT:** Each FHIR resource gets typed Bundle wrapper (e.g., `PatientBundle`). Generic FHIR Bundle not used for search.

**INVARIANT:** FHIR search parameter hyphens become underscores in GraphQL (e.g., `address-city` → `address_city`).

**INVARIANT:** CMS partner users explicitly forbidden from accessing GraphQL endpoints.

**INVARIANT:** Introspection gated by `enableGraphQLPlayground` config (disabled in production).

---

## 77. API Gateway Routing

**INVARIANT:** Gateway is reverse proxy routing by URL prefix. Longest-prefix-first matching.

**INVARIANT:** Gateway injects `x-forwarded-path` header with `req.originalUrl` and `origin-service: api-gateway` on FHIR requests.

**INVARIANT:** Gateway enriches requests with identity headers from JWT: `bwell-fhir-patient-id`, `bwell-fhir-person-id`, `bwell-client-fhir-person-id`, `bwell-client-fhir-patient-id`, `bwell-client-key`, `bwell-managing-organization`.

**INVARIANT:** $everything operations route to separate `BASE_FHIR_EVERYTHING_ENDPOINT` (not main FHIR server).

**INVARIANT:** OPTIONS requests bypass authentication entirely.

**INVARIANT:** Health check endpoints (`/health`, `/healthcheck`, `/actuator/health`) exempt from auth.

**INVARIANT:** Five auth types: `None`, `Jwt`, `JwtExternal`, `JwtOrExternal`, `JwtNetworkPartner`.

---

## 78. Batch Bundle Processing

**INVARIANT:** Batch entries processed in PARALLEL via `Promise.all` (not sequentially). Response is Bundle with per-entry status.

**INVARIANT:** Transaction processing uses SAME code path as batch. There is NO true atomicity guarantee — both execute entries independently. No all-or-nothing semantics.

**INVARIANT:** Bundle entry URLs must pass strict regex and must not contain `..`. Only GET, POST, PUT, DELETE, PATCH allowed.

**INVARIANT:** Batch re-dispatches each entry as loopback HTTP request to `127.0.0.1:{port}` (never to external hosts).

**INVARIANT:** `conditionalDelete` is `not-supported` per CapabilityStatement.

---

## 79. Content Negotiation & CORS

**INVARIANT:** FHIR R4 content type: `application/fhir+json`. No XML support. CapabilityStatement declares only `application/fhir+json`.

**INVARIANT:** Accepted types: `application/fhir+ndjson`, `application/ndjson`, `application/fhir+json`, `application/json`, `application/json-patch+json`, `text/csv`, `text/tab-separated-values`, `application/zip`.

**INVARIANT:** CORS origin via `WHITELIST` env var (comma-separated). If unset, CORS disabled. `maxAge` = 86400 seconds (24h).

**INVARIANT:** FHIR version embedded in URL path: `/:base_version/`. Effectively runs R4 (`4_0_0`). Unknown versions: 404.

---

## 80. Webhook Delivery Contracts

**INVARIANT:** (Go webhook-service) Payload is HTTP POST with `Content-Type: application/json`. Auth: HMAC (sha1/sha256/sha512/md5) or API Key (Basic auth). Uses CloudEvents envelope.

**INVARIANT:** (Go webhook-service) Retries: exponential backoff (`2^n` seconds, max 64s). Default max retries: 1.

**INVARIANT:** (Java fhir-subscription-service) Notification bundles follow FHIR R5 Backport IG: Bundle type `history`, first entry is SubscriptionStatus as Parameters resource. Payload levels: `empty`, `id-only`, `full-resource`.

**INVARIANT:** Webhook config is per-organization via CCS. Each org configures endpoint, version, auth, and subscriptions.

---

## 81. Export Lifecycle & File Format

**INVARIANT:** Export kickoff returns HTTP 202 + `Content-Location` header pointing to status endpoint.

**INVARIANT:** Export status values: `accepted` → `in-progress` → `completed` or `entered-in-error`. Runner only starts if status is `accepted`.

**INVARIANT:** Export polling: 202 with `X-Progress` header when not complete. 200 with JSON body when complete.

**INVARIANT:** Export forbidden for patient-scoped tokens. Only `user/*` scopes permitted.

**INVARIANT:** Output format: NDJSON files at `exports/{accessTags}/{exportStatusId}/{ResourceType}.ndjson`. S3 multipart upload with 100MB part size.

**INVARIANT:** AuditEvent always excluded from export regardless of scope or `_type`.

**INVARIANT:** Export status polling restricted to initiating user. Mismatch returns 404 (not 403).

**INVARIANT:** No explicit cancel endpoint. Stale `in-progress` exports marked `entered-in-error` after 24h by cron.

---

## 82. Import Byte-Range Parallelism

**INVARIANT:** Files split into byte ranges (default 100MB). Each range processed as independent Kafka message.

**INVARIANT:** First partial line in non-first range is SKIPPED (previous range owns it). One extra line past boundary is READ to complete last line.

**INVARIANT:** Task completion determined by counting completion markers in `Task.extension`. Fully complete when every range of every file has marker.

**INVARIANT:** Import Kafka redelivery is safe (idempotent): MongoDB writes are merge operations, duplicate completion markers harmless.

---

## 83. Import Validation & SSRF Prevention

**INVARIANT:** All S3 URIs must match `s3://bucket/key`. Non-matching rejected.

**INVARIANT:** S3 bucket must be in configured allow-list (`BULK_IMPORT_ALLOWED_S3_BUCKETS`). Empty allow-list rejects ALL requests (fail-closed).

**INVARIANT:** Max files per request: 100. Min file size: 50MB. Max file size: 5GB. Max line size: 16MB (aligns with MongoDB 16MB doc limit). Empty files rejected.

**INVARIANT:** NDJSON lines without `meta.security` get default ownership (owner=bwell, SAA=bwell). Lines with existing tags keep them.

**INVARIANT:** Import uses $merge semantics. Existing resources are merged (updated), new resources created. No transaction atomicity — partial success is normal.

---

## 84. Job Timeout & Concurrency

**INVARIANT:** Export K8s jobs: `activeDeadlineSeconds=86400` (24h), `restartPolicy=Never`, `backoffLimit=0`. `ttlSecondsAfterFinished` default 60s.

**INVARIANT:** Export concurrency limited by k8s namespace resource quotas. Quota exceeded = `createJob` returns false, cron stops creating new jobs.

**INVARIANT:** Import uses Kafka consumers (orchestrator + worker topology). No application-level rate limiting — bounded by consumer group parallelism.

**INVARIANT:** Kafka message processing: 3 retries with exponential backoff (200ms initial). After exhaustion → DLT with `.dlt` suffix.

---

## 85. GraphDefinition Traversal

**INVARIANT:** Vendor connection graph starts at Patient, traverses to: AllergyIntolerance, CarePlan, CareTeam, Condition, Coverage, DiagnosticReport, DocumentReference, Encounter, ExplanationOfBenefit, Goal, Immunization, MedicationRequest, Observation, Procedure. Each by `patient={ref}` with optional `date=ge{ifModifiedSince}`.

**INVARIANT:** Nested resources resolved via `link[].path` (forward references). DiagnosticReport→Encounter+Observation, MedicationRequest→Medication+Coverage+Encounter, DocumentReference→Binary+Encounter.

**INVARIANT:** $graph filter properties validated by regex `/^[A-Za-z][A-Za-z0-9_.]*$/` to prevent MongoDB injection.

**INVARIANT:** UUID generation formula consistent between Node.js and Python: `uuid5(NAMESPACE_OID, "${id}|${sourceAssigningAuthority}")`.

---

## 86. Document Processing Pipeline

**INVARIANT:** Supports CCDA-to-FHIR, HL7-to-FHIR, and direct FHIR bundle pass-through. Selfiie maps: "ccd binary" → CCDAConverter, "fhir bundle" → FHIRConverter, unknown → CCDAConverter with warning.

**INVARIANT:** Every resource from document conversion gets `meta.security` stamped with owner, vendor code, and connectionType.

**INVARIANT:** When `enable_deterministic_ids=true`, resource IDs regenerated deterministically from patient demographics. All non-Patient resources get IDs rewritten, all intra-bundle references updated.

**INVARIANT:** Provenance resource created linking all derived FHIR resources to source DocumentReference. Uses same DocumentReference ID as its own ID.

**INVARIANT:** Owner attribution from Selfiie: if exactly one unique custodian Organization in all Composition resources, that org's id becomes owner_code. Multiple/missing → fallback to data_source parameter.

---

## 87. Source Patient Classification

**INVARIANT:** Classification rules (first match wins): (1) owner=="bwell" → False (Master Patient), (2) connectionType in {"proa","ias"} → True, (3) owner in SOURCE_PATIENT_OWNER_RULES with rule=ALWAYS → True, (4) owner in rules with IF_NO_MASTER_ID → True when no `master-person-fhir-id` identifier, (5) otherwise → False.

**INVARIANT:** Only source patients with active permit consent (category=`cms:share:records`) on their immediate Person are eligible for linking during person-match.

---

## 88. Data Freshness & Refresh Tiers

**INVARIANT:** Tier 2 (URGENT priority): Users who previously received data, re-fetched if stale 7+ days.

**INVARIANT:** Tier 3 (ROUTINE priority): Users who never received data, re-fetched if stale 14+ days.

**INVARIANT:** ThedaCare weekly full-refresh on Sundays (weekday=6). All events carry `force_full_refresh=True` to bypass incremental watermarks.

**INVARIANT:** Vendor connection graph supports incremental via `{ifModifiedSince}` parameter placeholder.

---

## 89. Clinical Data Normalization

**INVARIANT:** Default status values per resource when source lacks status: CarePlan=unknown, CareTeam=active, Device=unknown, DiagnosticReport=unknown, DocumentReference=current, Encounter=unknown, Immunization=completed, MedicationRequest=unknown, MedicationStatement=unknown, Observation=unknown, Procedure=unknown, ServiceRequest=unknown, Specimen=available.

**INVARIANT:** SubscriptionStatus tracks: token_status (CONNECTED, NEW, DISCONNECTED, ERROR, EXPIRED, DELETED, ACCESS_ENDED) and data_connection_status (PENDING, RETRIEVING, RETRIEVED, ERROR, DELETING, DATA_DELETED).

**INVARIANT:** IntegrationTypes: DIRECT, DIRECT_IAS, INDIRECT_IAS, PROA. If member already has non-Smart-Connect subscription for a service_slug, new Smart Connect Task NOT created.

---

## 90. SDK Result Types & Lifecycle

**INVARIANT:** All SDK operations return typed Result objects, never throw. Mutations return `BWellTransactionResult<T, E>` (success XOR failure). Queries return `BWellQueryResult<T, E>` (can carry both data AND error for partial success).

**INVARIANT:** `BWellTransactionResult` has type narrowing via `.success()`/`.failure()`. Calling `.data()` on failure throws. Calling `.error()` on success throws. Enforces exhaustive handling.

**INVARIANT:** SDK lifecycle strictly ordered: `new BWellSDK(config)` → `await sdk.initialize()` → `await sdk.authenticate(credentials)`. Accessing any manager before auth throws `Error("Uninitialized")`.

**INVARIANT:** SDKs are thin mappers. Must NOT perform domain logic, traverse FHIR extensions, interpret contained resources, or conditionally parse raw JSON.

**INVARIANT:** Runtime dependencies strictly limited: `graphql-request` and `@opentelemetry/*` only. New deps require explicit approval.

---

## 91. Token Refresh & Storage

**INVARIANT:** `getAccessToken()` transparently checks expiry. If expired, calls `refreshAccessToken()` before returning. Invisible to caller.

**INVARIANT:** Default token storage is `InMemoryTokenStorage` (volatile). Consumers inject custom `TokenStorage` for persistence.

**INVARIANT:** `authenticateFromStorage()` immediately triggers `refreshAccessToken()` to validate freshness. If refresh fails, returns failure result.

**INVARIANT:** `refreshTokens` GraphQL query returns only `{ accessToken, idToken }` — no new refreshToken issued on refresh.

**INVARIANT:** Default HTTP timeout: 30,000ms. Default retry: 3 attempts with 1,000ms interval. Remote config can override.

---

## 92. Pagination & Feature Flags

**INVARIANT:** All paged requests: `page` (0-indexed, >= 0) and `pageSize` (default 20, max 100). Violations return ValidationError.

**INVARIANT:** Feature flags delivered via `initSdk` remote config as `featureFlagDefinitions[]`. Each has `id`, `name`, `variants[]` with `name`, `percent`, `value` for A/B testing.

**INVARIANT:** Clients must handle unknown enum values and new fields without failing. Schema evolution additive only.

---

## 93. Push Notifications & Deep Linking

**INVARIANT:** OneSignal push vendor. iOS: `promptForPushNotificationsWithUserResponse`. Android: `requestNotifications(["alert"])`.

**INVARIANT:** Foreground notifications intercepted and injected into WebView as message (NOT shown as system notification). WebView handles display.

**INVARIANT:** Deep links captured via React Native Linking API, forwarded to WebView as `deepLinkingURL` messages. Web app handles routing, not native layer.

**INVARIANT:** Device registration requires: `deviceToken`, `platformName` (IOS/ANDROID), `applicationName`. All validated before submission.

---

## 94. Security Tag Race Conditions

**INVARIANT:** Concurrent $merge operations MUST deduplicate meta.security tags before persisting. After N merges with same 3 tags, stored result must have exactly 3 tags, not 3*N.

**INVARIANT:** Resource MUST NEVER persist with empty meta.security array. Fail-closed: empty tags = rejected, not silently saved with no access controls.

**INVARIANT:** Resource with only "unclassified" tag (no owner tag) must be rejected on write.

**INVARIANT:** When optimistic-concurrency retry fires, retry path MUST NOT duplicate meta.security tags even when tag ORDER differs between payloads.

**INVARIANT:** On $merge 403 for one resource in batch: does NOT fail entire request. Returns 200 with partial results. Denied resource in preCheckErrors only.

**INVARIANT:** Write access validation during $merge validates against EXISTING resource in database (if found), not incoming resource. Prevents attacker from sending crafted security tags.

---

## 95. Cross-Tenant Identity Grafting Prevention

**INVARIANT:** Person.link referencing Person/Patient in different tenant MUST be rejected when caller is access-scoped. Same-tenant links allowed. Prevents cross-tenant identity graph grafting.

**INVARIANT:** Self-granted Consent (Tenant B creates Consent referencing Tenant A's patient) does NOT leak data UNLESS Tenant B also grafts a Person.link. Consent alone insufficient; link graft is the necessary second step.

**INVARIANT:** Patient-scoped caller MUST NOT write to non-patient-filterable resource types (Organization, Practitioner, PractitionerRole, Location, HealthcareService, ValueSet, CodeSystem, StructureDefinition, CapabilityStatement, OperationDefinition, SearchParameter, NamingSystem, ConceptMap, Endpoint, InsurancePlan, Medication).

**INVARIANT:** PATCH attempting to modify meta.security owner tags or meta.source silently reverted by `overWriteNonWritableFields`, even for full-access callers.

**INVARIANT:** PATCH adding access tag caller is not authorized for returns 403. Caller with `access/clientA.*` cannot add `access/clientB` via JSON Patch.

---

## 96. SHL Passcode & Access Limit Mechanics

**INVARIANT:** Passcode lockout threshold: default 5 failed attempts (configurable per-Consent via `max-attempts`). Check is `>=` (at threshold = blocked).

**INVARIANT:** Lockout duration stored in Redis as seconds (minutes * 60). Default 60 minutes = 3600s TTL.

**INVARIANT:** Lockout metric fires exactly once (on increment crossing threshold, not on every subsequent retry).

**INVARIANT:** `incrementFailedAttempts` uses Redis distributed lock with fencing token. If lock cannot be acquired after retries: proceeds WITHOUT lock (fail-open for increment). Never deletes lock it didn't acquire.

**INVARIANT:** Access limits default to 2 when no shl-config extension present. Uses `>=` comparison. NaN cached values treated as 0 (not lockout).

**INVARIANT:** Access count TTL derived from SHL expiration date (seconds until expiry), not fixed TTL.

**INVARIANT:** Whitespace-only passcode treated as empty/missing → BAD_REQUEST (not UNAUTHORIZED). Error message always "Incorrect passcode" regardless of empty vs wrong (information hiding).

**INVARIANT:** SHL `expirationMinutes` hard range: 1-2880 (1 min to 48 hours). SHL encryption keys must decode to exactly 32 bytes.

---

## 97. SSE Event Security Filtering

**INVARIANT:** SSE event security uses dual-dimension model: BOTH access codes AND owner codes must match. Access overlap without owner match = denied. Owner match without access match = also denied.

**INVARIANT:** Admin users bypass ALL event security filtering.

**INVARIANT:** Untagged events (no access/owner codes) pass through to ALL connections (fail-open for untagged resources).

**INVARIANT:** When pre-extracted codes unavailable, filter falls back to parsing FHIR Bundle JSON from event data field. Invalid JSON treated as untagged (pass-through), not denied.

**INVARIANT:** Scopes arrive as JSON array OR space-separated string. Both supported. Group claims merged with scope claim.

**INVARIANT:** Client revocation terminates ALL SSE connections for that clientId, sends `client-revoked` event before disconnecting.

**INVARIANT:** Subscription IDs must match restricted pattern (alphanumeric, hyphens, underscores, dots). SQL injection/XSS payloads rejected (defense-in-depth against ClickHouse injection).

---

## 98. Memory & Worker Scaling

**INVARIANT:** Per-worker heap = `(CONTAINER_MEM_REQUEST / WORKER_COUNT) * 90%`. 10% safety margin for off-heap (sockets, buffers, native addons).

**INVARIANT:** Readiness probe fails when RSS exceeds `CONTAINER_MEM_REQUEST`. Soft circuit-breaker: pod drained from service before OOM-kill.

**INVARIANT:** Readiness also fails when request count exceeds `NO_OF_REQUESTS_PER_POD` (default 1000).

**INVARIANT:** `WORKER_COUNT` controls Node.js cluster mode. Workers auto-restart on crash unless primary shutting down.

---

## 99. Health Probes & Graceful Shutdown

**INVARIANT:** Liveness: `/health` (simple 200 if process alive). Readiness: `/ready` (memory + request count check).

**INVARIANT:** Graceful shutdown: `SHUTDOWN_DELAY_MS` (default 15.1s for LB deregistration) → `GRACEFUL_TIMEOUT_MS` (default 29s, force-kill). Under k8s `terminationGracePeriodSeconds` of 30s.

**INVARIANT:** On shutdown: flush all buffers (PostRequestProcessor, PostSaveProcessor, AuditLogger, AccessLogger), disconnect Kafka producer.

**INVARIANT:** Socket timeout = 10 min. Keep-alive timeout = 10 min. Idle connections held open that long.

**INVARIANT:** OpenTelemetry ignores `/health`, `/live`, `/ready` from tracing (no probe noise in spans).

**INVARIANT:** MongoDB OTel: `db.statement` removed for non-read operations to avoid logging write payloads containing PHI.

---

## 100. Feature Flags & Thresholds

**INVARIANT:** `ENABLE_CLICKHOUSE=1` + `CLICKHOUSE_ONLY_RESOURCES=AuditEvent` means AuditEvent stored ONLY in ClickHouse, not MongoDB.

**INVARIANT:** `MONGO_WITH_CLICKHOUSE_RESOURCES=Group` means Group uses dual-write: metadata in MongoDB, member events in ClickHouse (event-sourced).

**INVARIANT:** `GRIDFS_RESOURCES=DocumentReference` restricts GridFS to DocumentReference only. Code throws if other types configured.

**INVARIANT:** `UNCLASSIFIED_TAGGING_RESOURCES` (~29 resource types) defines which get automatic "unclassified" sensitivity tag on write if no classification present.

**INVARIANT:** `MAX_GROUP_MEMBERS_PER_PUT=50000` hard limit on Group.member for CREATE/PUT. PATCH bypasses this (uses event-sourced ClickHouse appends).

**INVARIANT:** `GROUP_PATCH_OPERATIONS_LIMIT=10000` max JSON Patch operations per PATCH for Group.member.

**INVARIANT:** `BASE64_FIELD_DATA_THRESHOLD_KB=64` — binary payloads over 64KB offloaded to S3 (when enabled). SHA-256 content-addressed. Async chunked hashing (1MB chunks) for payloads over 256KB to avoid blocking event loop.

**INVARIANT:** `POST_REQUEST_FLUSH_TIME` = every 10 seconds. `POST_REQUEST_BATCH_SIZE=50`. Buffered async operations flush on this schedule.

**INVARIANT:** `KAFKA_MAX_RETRY=3`. Patient data change events: topic `fhir.patient_data.change.events`. Person: `fhir.person_data.change.events`.

**INVARIANT:** `AUDIT_EVENT_MAX_RANGE_PERIOD` default 30 days. AuditEvent queries cannot span more than 30 days. `REQUIRED_AUDIT_EVENT_FILTERS=date` forces date filter.

**INVARIANT:** `CMS_ALLOWED_PURPOSE_OF_USE=TREAT,HPAYMT` — only these purposeOfUse codes accepted from CMS partner tokens.

**INVARIANT:** `AUTH_REMOVE_SCOPE_PREFIX=fhir/dev/` — scope strings stripped of this prefix before evaluation (environment-specific namespacing).

---

## 101. Person Resource Rules

**INVARIANT:** Person GET $everything is remapped to Patient GET $everything using proxy patient IDs (`person.<uuid>` prefix). Person $summary similarly remapped to Patient $summary.

**INVARIANT:** Person has a dedicated deletion graph (`personEverythingForDeletionGraph`) for DELETE $everything that cascades through linked Patients to all clinical data.

**INVARIANT:** Person writes trigger `validateNewPersonLinkTargetsBelongToCallersTenant` — any NEW link targets in Person.link MUST belong to a tenant the caller has write access to. Unparseable references fail-closed rejected.

**INVARIANT:** Person resources with patient scope CANNOT add new references to Person.link (length change rejected). Existing references must match exactly.

**INVARIANT:** Person always runs `validatePatientReference` on creation (even without currentResource) — the ONLY resource type that does this.

**INVARIANT:** Person link traversal: max recursion depth 4 levels when expanding Person→Patient.

**INVARIANT:** Person link expansion applies access-tag checks at every hop when `addTopPersonAccessCheck=true`. Caller must hold matching access tag for every Person reached transitively.

**INVARIANT:** Person has separate configurable access-tags index (`ACCESS_TAGS_INDEXED_PERSON`).

**INVARIANT:** Person data changes produce `PersonDataChangeEvent` Kafka events, aggregating downstream Patient changes by walking Person.link reverse mappings.

---

## 102. Patient Resource Rules

**INVARIANT:** Patient uses `id` as patient filter property (self-referencing). Patient id field changes silently ignored on update — `validatePatientReference` skipped for Patient.

**INVARIANT:** Proxy patient IDs (`person.<uuid>`) in search trigger expansion to real Patient UUIDs via `PatientProxyQueryRewriter`.

**INVARIANT:** Patient $everything with proxy patient ID applies sibling-record scoping. Cannot mix proxy and regular patient IDs in same $everything request.

**INVARIANT:** CMS partner users restricted to ONLY Patient resource, ONLY search/everything operations, ONLY GET.

**INVARIANT:** When patient scope active and no patient IDs resolved (empty expansion), query becomes `{ _uuid: '__invalid__' }` returning nothing (unless `doNotRequirePersonOrPatientIdForPatientScope` enabled).

**INVARIANT:** Patient $everything triggers post-request `FhirOperationUsageEvent` (operationType: `AccessedEverything`) for tracking.

**INVARIANT:** Patient data changes produce `PatientDataChangeEvent` Kafka events.

---

## 103. Consent Resource Rules

**INVARIANT:** Consent writes trigger cache invalidation of Patient/$everything Redis cache by incrementing generation counter.

**INVARIANT:** CMS Consent requires category `cms:share:records`. PROA Consent requires category `dataSharing` (configurable). Delegated Consent requires `dataSharingAccess`.

**INVARIANT:** Multiple active Consent for delegated actor = DENIED (ambiguous permissions). Zero = DENIED (not enough permissions).

**INVARIANT:** Consent uses dedicated MongoDB index (`consent_of_linked_person`) for efficient lookup.

**INVARIANT:** Consent nested deny provisions with `securityLabel` become active query filters for delegated access users.

---

## 104. Group Resource Rules

**INVARIANT:** Group with `actual=false` MUST NOT have members (FHIR invariant grp-1). Violation throws BadRequestError before save.

**INVARIANT:** Group with ClickHouse enabled: member array STRIPPED from MongoDB before save. Members stored in ClickHouse as append-only events. MongoDB stores only metadata.

**INVARIANT:** Group gets permanent `externalStorageFields|member` meta.tag once ClickHouse activated. Never removed even if all members deleted.

**INVARIANT:** Group ClickHouse post-save uses SYNCHRONOUS writes (blocks API response) for read-after-write consistency. ClickHouse is source of truth for membership.

**INVARIANT:** Group DELETE does NOT remove ClickHouse membership events — retained as immutable audit trail.

**INVARIANT:** Group UPDATE with `smartMerge=true` only produces MEMBER_ADDED events (no removals). Full PUT (`smartMerge=false`) produces both additions and removals.

**INVARIANT:** If ClickHouse write fails after MongoDB commit for Group: error PROPAGATED (500), not swallowed. Silent data loss unacceptable for clinical cohorts.

---

## 105. AuditEvent Resource Rules

**INVARIANT:** AuditEvent stored in SEPARATE MongoDB database from all other resources.

**INVARIANT:** AuditEvent NEVER audited itself — audit logging skipped for AuditEvent CRUD to prevent infinite recursion.

**INVARIANT:** AuditEvent merge always takes CREATE path (never merge-existing) regardless of whether current resource exists.

**INVARIANT:** AuditEvent has size limit (`AUDIT_EVENT_MAX_SIZE_BYTES`, default 16MB). Exceeding → rejected with `too-long` OperationOutcome.

**INVARIANT:** AuditEvent excluded from: hidden-tag filter, PatientPersonDataChangeEventProducer, Kafka change events, history collection entries, `_uuid` unique index requirement.

**INVARIANT:** AuditEvent can use ClickHouse-only storage (`CLICKHOUSE_ONLY_RESOURCES`) with Kafka ClickPipe strategy.

---

## 106. DocumentReference & Binary Rules

**INVARIANT:** DocumentReference has special GridFS attachment handling for `content[].attachment`, `extension[].valueAttachment`, `modifierExtension[].valueAttachment`. Large attachments stored in GridFS, replaced with `_file_id` references.

**INVARIANT:** DocumentReference `content.attachment.url` in $everything non-clinical extraction filtered to ONLY allow Binary references. Other reference types dropped.

**INVARIANT:** Binary `data` field offloaded to cloud storage (S3) when base64 data exceeds threshold. `_blobMeta` sidecar replaces data inline.

---

## 107. Subscription Family Rules

**INVARIANT:** Subscription uses person-scoped filtering via extension field (system: `https://icanbwell.com/codes/client_person_id`) not standard patient reference.

**INVARIANT:** SubscriptionTopic uses `identifier` field (not extension) for person-scoped filtering.

**INVARIANT:** Subscription-family resources have special ID enrichment: extension/identifier valueString containing non-UUID IDs converted to UUIDv5 using resource's sourceAssigningAuthority.

**INVARIANT:** Subscription uses custom patient filter export logic (`extension.$elemMatch`) instead of standard patient reference field.

---

## 108. Cross-Resource Behavioral Tags

**INVARIANT:** Any resource with meta.security `http://terminology.hl7.org/CodeSystem/v3-Confidentiality` code=R is FORBIDDEN from patient-scoped (end-user) token access.

**INVARIANT:** Any resource with meta.tag `https://fhir.icanbwell.com/4_0_0/CodeSystem/server-behavior` code=hidden is excluded from search results (unless `_includeHidden=true`, searching by ID, DELETE operation, or AuditEvent).

**INVARIANT:** Resources configured in `UNCLASSIFIED_TAGGING_RESOURCES` get automatic "unclassified" sensitivity tag on write if no sensitivity tag exists. Delegated users excluded from seeing these.

---

## 109. Merge Array Semantics

**INVARIANT:** Arrays of primitives are REPLACED (not merged). Arrays of objects use id-matching (merge into matching element) or sequence-number ordering.

**INVARIANT:** Items with id ending in `-delete` trigger DELETION of the matching id from the old array.

**INVARIANT:** Merge uses deep-equal comparison (fast-json-patch `compare`) to determine if changes exist. No patch operations = no database write.

**INVARIANT:** `meta.security` tags deduplicated by `system|code` composite key during merge. Duplicates removed.

---

## 110. Pre-Save Handler Chain (All Resources)

**INVARIANT:** Handler execution order: UUID → SourceId → Owner → SourceAssigningAuthority → Access → ReferenceGlobalId → UnclassifiedSensitivityTag → CodeableConceptId → GroupInvariant.

**INVARIANT:** All resources get `_uuid` generated: if id is UUID use it; if id missing generate random UUID; otherwise UUIDv5 from `id|sourceAssigningAuthority`.

**INVARIANT:** All resources get `_sourceId` set to resource id (if not already set). Identifier with system=sourceId is stripped.

**INVARIANT:** All resources get owner tag auto-populated from first access tag if owner missing.

**INVARIANT:** All resources get `_sourceAssigningAuthority` tag auto-populated from owner tag if missing.

**INVARIANT:** All resources get `_access` internal field populated from meta.security access tags for fast MongoDB querying.

**INVARIANT:** All resource references get `_uuid`, `_sourceId`, `_sourceAssigningAuthority` enrichment on every Reference field before save.

**INVARIANT:** Resources in `PRE_SAVE_CODING_ID_UPDATE_RESOURCES` get deterministic UUIDv5 ids stamped on all Coding elements (`system|code` → id).

---

## END OF DOCUMENT

This document contains the complete set of business rules that define correct system behavior. Any code that violates these rules is buggy — regardless of what the developer's PR description says, regardless of what inline comments claim, regardless of what any user story specifies.

The rules here are the ground truth. Test against them.
