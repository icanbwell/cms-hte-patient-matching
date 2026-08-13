---
id: cross-tenant-soft-reference-join
class: cross-tenant-soft-reference-join
impact_if_present: critical
pattern_origin: >
  Structural pattern. A related-resource query matches on a source patient identifier
  plus a service identifier without including the per-person client discriminator, while
  the resource's security tags are assigned from the data vendor rather than the owning
  client — so neither the query filter nor tag-based filtering isolates the tenant.
---

## Root Cause Pattern

A query joins on "soft reference" fields (extensions, identifiers, string matches) using a PARTIAL key set. The key uniquely identifies the real-world entity but NOT the tenant relationship. When two tenants have relationships with the same entity, the query returns both tenants' records.

Two compounding factors, and both must be checked independently:
1. **Incomplete query filter** — joins on entity-identifying fields without a tenant-discriminating field
2. **Incorrect security tagging** — `owner`/`access` tags use the vendor/provider identifier instead of the client/tenant identifier, so standard access-tag filtering provides no isolation

Either factor alone is a defect. Together they remove both layers of isolation at once, which is why this class is rated critical: the usual reasoning "even if the query is loose, access tags will catch it" does not hold.

Common manifestations:
- Custom queries matching on a source patient identifier plus a service identifier (both shared across tenants) without the per-person client identifier (unique per tenant)
- Extension-based lookups where the extension value is shared (e.g. an external MRN) without a tenant qualifier
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

For each custom query or extension-based join found:
1. List the fields used in the query match
2. Identify which fields are SHARED across tenants (entity-level identifiers)
3. Identify which field would DISTINGUISH tenants (client person identifier, owner tag, etc.)
4. If the distinguishing field is missing from the query → BUG

Then separately verify the tagging: for the same resource, confirm `owner`/`access` derive from the client, not the vendor. A query fix with the tagging left wrong is only half the defect.

## Test Template

```javascript
test('BUG: [resourceType] query leaks across tenants when [sharedField] matches', () => {
    // Setup: two tenants, same real-world entity
    const tenantA = { personId: 'tenant-a-person', owner: 'tenant-a' };
    const tenantB = { personId: 'tenant-b-person', owner: 'tenant-b' };
    const sharedIdentifier = 'EXTERNAL-ID-12345';  // same value at both tenants

    // The query/mapper definition
    const resourceConfig = mapper.relatedResources('Patient', null)
        .find(r => r.type === '[ResourceType]');

    // CORRECT: query MUST include a tenant-discriminating field
    expect(resourceConfig.customQuery.query).toContain('[tenantField]');
    // CORRECT: requiredValues MUST include the tenant parameter
    expect(resourceConfig.customQuery.requiredValues).toContain('[tenantParam]');
});
```

## Critical Variant: Same-Tenant Sibling Isolation

The cross-tenant case (different owner tags) is the obvious scenario. The subtle variant is **same-tenant sibling isolation**: two distinct persons or apps within the SAME tenant share the same `owner`/`access` security tags AND the same service identifier, but must NOT see each other's data.

In this platform:
- `owner`/`access` tags identify the **tenant**, not the **person**
- the service identifier identifies the **health system connection**, which is shared across sibling apps in the same tenant
- the **client person identifier** is the only discriminator between sibling apps within the same tenant

**The mistake that is easy to make, including for experienced engineers:** assuming "same security tag = same identity = safe to share." Tag equality means "same tenant," which is necessary but NOT sufficient for access. The person-level discriminator must also match.

**Detection:** if a query filters by source patient identifier plus service identifier but NOT the client person identifier, it can return data belonging to a sibling app in the same tenant. Security-tag filtering cannot catch this, because both siblings carry identical tags. Any test that only varies the owner tag will pass while the defect remains.

This variant is the single highest-value check in this pattern file. It is invisible to access-tag reasoning, invisible to scanners, and the code reads as correct.

## Where This Class Tends To Live

| Category | What to check |
|---|---|
| `$everything` and `$graph` related-resource mappers | Every custom query carries a tenant discriminator and a person discriminator |
| Subscription and connection-status resources | Joined on entity identifiers rather than FHIR references |
| Extension- or identifier-based lookups | The matched value is not shared across organizations |
| Security tag assignment pipeline | `owner`/`access` derive from the client, never from the data vendor |
