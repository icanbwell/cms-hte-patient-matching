---
id: type-coercion-security-filter
class: type-coercion-security-filter
impact_if_present: critical
pattern_origin: >
  Structural pattern. A shared query-simplifier utility implements an emptiness test
  using JavaScript falsy semantics, so a filter value of 0 or false is discarded before
  the query is built. Where that value was a security predicate, removing it widens the
  result set rather than narrowing it.
---

## Root Cause Pattern

A utility function uses JavaScript's falsy semantics (`!value`, `value || default`, `if (value)`) to check for "empty" or "missing" values. In JavaScript, `0`, `false`, `""`, and `NaN` are all falsy but may be VALID, meaningful values — especially in security-critical contexts where they represent:
- A numeric security level of 0 (minimum privilege)
- A boolean `false` meaning "access denied"
- An empty string that is a valid identifier
- A count of 0 that should result in "no results" (not "skip this filter")

When these valid values are treated as "empty" and dropped from a security query, the query becomes LESS restrictive — returning data the user should not see.

## Detection Heuristic

```bash
# Find isEmpty/isNull/isBlank utility functions
grep -rn "function isEmpty\|const isEmpty\|isEmpty.*=\|function isNull\|function isBlank" src/ --include="*.js" --include="*.ts" | grep -v node_modules | grep -v test

# Find falsy checks that might drop valid values
grep -rn "if (!.*)\|!.*&&\||| \[\]\||| {}\||| ''" src/ --include="*.js" | grep -v node_modules | grep -v test | grep -i "security\|filter\|query\|scope\|access\|tag" | head -30

# Find the actual isEmpty implementation and check if it uses !value
grep -rn "isEmpty" src/utils/ --include="*.js" -l | head -5
# Then read each file and check: does it use !value, value == null, or value === undefined?

# Find value || default patterns in security-related code
grep -rn "|| \[\]\||| null\||| undefined\||| ''" src/operations/security/ src/operations/query/filters/ --include="*.js" | grep -v node_modules | grep -v test | head -30
```

For each isEmpty/falsy-check found:
1. What values does it treat as "empty"?
2. Are any of those values VALID in the context where the function is called?
3. Is the function used in a security filter, query builder, or access control path?
4. If valid values are dropped from a security query → CRITICAL BUG

## Test Template

```javascript
test('BUG: [function] treats [validValue] as empty, dropping it from security queries', () => {
    // 0 and false are valid values that should NOT be treated as empty
    expect(isEmpty(0)).toBe(false);
    expect(isEmpty(false)).toBe(false);
    // Only truly empty values should return true
    expect(isEmpty(null)).toBe(true);
    expect(isEmpty(undefined)).toBe(true);
    expect(isEmpty('')).toBe(true);  // empty string MAY be truly empty depending on context
});
```

## Where This Class Tends To Live

| Category | What to check |
|---|---|
| Shared emptiness/blankness utilities | Whether `0`, `false` and `''` are distinguished from `null`/`undefined` |
| Query simplifiers and builders | Whether a falsy predicate is dropped rather than preserved |
| Security tag and scope filter assembly | Whether removing a predicate widens or narrows the result set |
| Default-value coalescing (`|| []`, `|| {}`) in access paths | Whether the default is more permissive than the real value |

**Direction of failure is the thing to test.** A dropped predicate that narrows results is a correctness bug; one that widens them is a security bug. Assert on the resulting query, not on the utility's return value alone.
