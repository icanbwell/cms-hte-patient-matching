---
id: INC-332
class: cross-tenant-soft-reference-join
severity: critical
discovered: 2026-07-28
source_incident: >
  SubscriptionStatus $everything query matches on source_patient_id + service_slug
  WITHOUT filtering by client_person_id. Two tenants sharing the same real patient at
  the same health system get each other's connection records. Security tags were set to
  the vendor (acme_health) instead of the client (alpha_health / beta_insurance).
---

## Root Cause Pattern

A query joins on "soft reference" fields (extensions, identifiers, string matches) using a PARTIAL key set. The key uniquely identifies the real-world entity but NOT the tenant relationship. When two tenants have relationships with the same entity, the query returns both tenants' records.

Two compounding factors:
1. **Incomplete query filter** — joins on entity-identifying fields without a tenant-discriminating field
2. **Incorrect security tagging** — `owner`/`access` tags use the vendor/provider identifier instead of the client/tenant identifier, so standard access-tag filtering provides no isolation

Common manifestations:
- `customQuery` matching on `source_patient_id + service_slug` (shared across tenants) without `client_person_id` (unique per tenant)
- Extension-based lookups where the extension value is shared (e.g., external MRN) without a tenant qualifier
- Identifier-based lookups where `system + value` matches across organizations
- `$everything` related-resource fetches that use entity-level identifiers without tenant scoping
- Resources whose `meta.security` tags are scoped to the data vendor rather than the owning client

## Detection Heuristic

```bash
# Find all customQuery definitions (these bypass standard FHIR reference-based filtering)
grep -rn "customQuery" src/ --include="*.js" --include="*.ts" | grep -v node_modules | grep -v test

# Find extension-based queries (joining on extension fields)
grep -rn "extension.*elemMatch\|extension.*url.*valueString" src/ --include="*.js" | grep -v node_modules | grep -v test

# Find identifier-based queries
grep -rn "identifier.*elemMatch\|identifier.*system.*value" src/ --include="*.js" | grep -v node_modules | grep -v test

# Find $everything resource mapper definitions
grep -rn "type:.*customQuery\|params:.*{ref}" src/operations/everything/ --include="*.js"

# Find security tag assignment (check what value goes into owner/access)
grep -rn "meta\.security\|owner.*sourceAssigningAuthority\|access.*sourceAssigningAuthority" src/ --include="*.js" | grep -v node_modules | grep -v test

# Find resources that only have extension-based patient links (no proper FHIR reference)
grep -rn "fieldForParentLookup.*extension\|fieldForParentLookup.*identifier" src/ --include="*.js" | grep -v node_modules | grep -v test
```

For each customQuery or extension-based join found:
1. List the fields used in the query match
2. Identify which fields are SHARED across tenants (entity-level identifiers)
3. Identify which field would DISTINGUISH tenants (client_person_id, owner tag, etc.)
4. If the distinguishing field is missing from the query → BUG

## Test Template

```javascript
test('BUG: [resourceType] query leaks across tenants when [sharedField] matches', () => {
    // Setup: Two tenants, same real-world entity
    const tenantA = { personId: 'alpha-bob', owner: 'alpha_health' };
    const tenantB = { personId: 'beta-bob', owner: 'beta_insurance' };
    const sharedIdentifier = 'EXTERNAL-ID-12345';  // same at both tenants

    // The query/mapper definition
    const resourceConfig = mapper.relatedResources('Patient', null)
        .find(r => r.type === '[ResourceType]');

    // CORRECT: query MUST include a tenant-discriminating field
    expect(resourceConfig.customQuery.query).toContain('[tenantField]');
    // CORRECT: requiredValues MUST include the tenant parameter
    expect(resourceConfig.customQuery.requiredValues).toContain('[tenantParam]');
});
```

## CRITICAL VARIANT: Same-Tenant Sibling Isolation (DCON-4669)

The cross-tenant case (different owner tags) is the obvious scenario. The SUBTLE variant is **same-tenant sibling isolation**: two distinct persons/apps within the SAME tenant share the same `owner`/`access` security tags AND the same `service_slug`, but should NOT see each other's data.

In this system:
- `owner`/`access` tags identify the **tenant**, not the **person**
- `service_slug` identifies the **health system connection** (shared across sibling apps in the same tenant)
- `client_person_id` is the **only discriminator** between sibling apps within the same tenant

**The mistake everyone makes (including experienced engineers):** Assuming that "same security tag = same identity = safe to share." This is WRONG. Tag equality means "same tenant," which is necessary but NOT sufficient for access. The person-level discriminator (`client_person_id`) must also match.

**Detection:** If a query filters by `source_patient_id` + `service_slug` but NOT `client_person_id`, it will leak data between sibling apps in the same tenant. Security tag filtering won't catch this because both siblings have identical tags.

**Prior art:** RNGR-38 flagged this exact pattern before INC-332 confirmed it in production.

## Known Instances

| Location | Shared Fields | Missing Tenant Filter | Status |
|----------|--------------|----------------------|--------|
| `everythingRelatedResourcesMapper.js:374` (Subscription) | source_patient_id, service_slug | client_person_id | Confirmed (INC-332) |
| `everythingRelatedResourcesMapper.js:383` (SubscriptionStatus) | source_patient_id, service_slug | client_person_id | Confirmed (INC-332) |
| `everythingRelatedResourcesMapper.js:392` (SubscriptionTopic) | source_patient_id, service_slug | client_person_id | Confirmed (INC-332) |
| `everythingRelatedResourcesMapper.js` (BiologicallyDerivedProduct) | TBD | TBD | Under investigation |
| Security tag assignment pipeline | owner=vendor instead of owner=client | N/A (tag-level fix) | Confirmed |
