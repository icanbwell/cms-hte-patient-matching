---
id: cache-key-insufficiency
class: cache-key-insufficiency
impact_if_present: critical
pattern_origin: >
  Structural pattern. A request-scoped cache keyed only on a request correlation
  identifier, used by a method whose output also varies by resource type, parsed
  arguments and security tags. Any second call within the same request returns the
  first call's entry.
---

## Root Cause Pattern

A cache, memoization, or request-scoped store uses an insufficient key — one that does not include all dimensions that should differentiate entries. The cache conflates distinct calls that happen to share some (but not all) key components.

This is a high-impact class because the failure is silent and data-dependent: the code is correct on the first call and wrong on every subsequent one, so it passes any test that exercises a single path.

Common manifestations:
- Cache key = `requestId` but results vary by `resourceType`, `parsedArgs`, `securityTags`
- Cache key = `userId` but results vary by `tenantId`, `scope`, `role`
- Cache key = `entityId` but behavior varies by `version`, `timestamp`, `locale`
- Module-level variables that accumulate state across requests
- Singleton maps/sets that are never cleared between calls

When the conflated dimension is security-relevant — a tenant discriminator, an access tag, a scope — the consequence is a cross-boundary read rather than merely a stale value. Treat that case as the default assumption until proven otherwise.

## Detection Heuristic

```bash
# Find all cache/memoization implementations
grep -rn "\.get\(\|\.set\(\|cache\[.*\]\|memoize\|_cached\|Map()\|new Map" src/ --include="*.js" --include="*.ts" | grep -v node_modules | grep -v test

# Find request-scoped context sharing
grep -rn "httpContext\.\(set\|get\)" src/ --include="*.js" --include="*.ts" | grep -v node_modules | grep -v test

# Find functions that accept multiple parameters but cache on fewer
# (manual inspection required — look for cache keys that don't use all method params)
```

For each cache found, verify:
1. List all parameters the containing method accepts
2. List all dimensions in the cache key
3. If (params that affect output) > (dimensions in key) → BUG

This comparison is mechanical. It requires no judgment and should not be skipped on the grounds that the cache "looks fine."

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

## Where This Class Tends To Live

Search these categories rather than relying on a fixed list — the point of the heuristic is that instances move as code moves.

| Category | What to check |
|---|---|
| Request-scoped caches and context stores | Every dimension the cached method varies on appears in the key |
| Data-sharing and consent resolution helpers | Tenant and person discriminators are part of the key, not just the request ID |
| Generic memoization utilities | Callers cannot supply colliding keys for semantically different queries |
| Module-level maps and singletons | Cleared per request, or keyed such that cross-request collision is impossible |
