---
id: INC-331
class: cache-key-insufficiency
severity: critical
discovered: 2026-07-15
source_incident: >
  dataSharingManager.js caches query results keyed ONLY by requestId.
  When the same request queries multiple resource types, the second query
  returns the first query's cached results — Patient A sees Patient B's data.
---

## Root Cause Pattern

A cache, memoization, or request-scoped store uses an insufficient key — one that does not include all dimensions that should differentiate entries. The cache conflates distinct calls that happen to share some (but not all) key components.

Common manifestations:
- Cache key = `requestId` but queries vary by `resourceType`, `parsedArgs`, `securityTags`
- Cache key = `userId` but results vary by `tenantId`, `scope`, `role`
- Cache key = `entityId` but behavior varies by `version`, `timestamp`, `locale`
- Module-level variables that accumulate state across requests
- Singleton maps/sets that are never cleared between calls

## Detection Heuristic

```bash
# Find all cache/memoization implementations
grep -rn "\.get\(\|\.set\(\|cache\[.*\]\|memoize\|_cached\|Map()\|new Map" src/ --include="*.js" --include="*.ts" | grep -v node_modules | grep -v test

# Find httpContext usage (request-scoped sharing)
grep -rn "httpContext\.\(set\|get\)" src/ --include="*.js" --include="*.ts" | grep -v node_modules | grep -v test

# Find functions that accept multiple parameters but cache on fewer
# (manual inspection required — look for cache keys that don't use all method params)
```

For each cache found, verify:
1. List all parameters the containing method accepts
2. List all dimensions in the cache key
3. If (params that affect output) > (dimensions in key) → BUG

## Test Template

```javascript
test('BUG: [cacheName] key does not include [missingDimension]', () => {
    // Call 1: with dimension value A
    const result1 = await method({ requestId: 'same-req', [dimension]: 'A', ...otherParams });

    // Call 2: SAME cache key components, DIFFERENT dimension value
    const result2 = await method({ requestId: 'same-req', [dimension]: 'B', ...otherParams });

    // If cache key is sufficient, results MUST differ when dimension differs
    // If cache is buggy, result2 === result1 (stale cached value)
    expect(result2).not.toEqual(result1);
    // STRONGER: assert the specific varied value appears in result2
    expect(result2).toContain('B');  // or expect(result2.someField).toBe('B')
});
```

## Known Instances

| Location | Cache Key | Missing Dimension | Status |
|----------|-----------|-------------------|--------|
| `src/operations/common/dataSharingManager.js` | `requestId` | `resourceType`, `parsedArgs`, `securityTags` | Confirmed (INC-331) |
| `src/utils/requestSpecificCache.js` | TBD — needs audit | TBD | Under investigation |
| `httpContext` prefix keys | varies | varies | Under investigation |
