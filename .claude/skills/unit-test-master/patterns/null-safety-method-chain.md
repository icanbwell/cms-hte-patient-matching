---
id: null-safety-method-chain
class: null-safety-method-chain
impact_if_present: high
pattern_origin: >
  Structural pattern. Most FHIR fields are optional, so any method chained onto a
  resource field is unguarded unless the field is verified first. Typical shapes are
  reduce on an absent link array, join on an absent given name, and startsWith on an
  absent reference string. The class is rated high rather than medium because a crash
  inside an access-enforcing path can convert a denial into an error path whose handler
  may continue with a permissive default.
---

## Root Cause Pattern

Code calls a method on a value that can be null/undefined without a guard check. In FHIR resources, most fields are optional — any `.field.method()` chain is unsafe unless the field is verified to exist.

Critical when the crash occurs in:
- Security enforcement code (access denied → crash → request fails with 500 instead of 403, or worse, the crash is caught and execution continues with a permissive default)
- Data filtering code (crash → unfiltered data returned)
- Patient scope enforcement (crash → scope not applied)

Common manifestations:
- `resource.field.method()` where `field` is optional in the FHIR spec
- `array[0].property` where array could be empty
- `obj.nested.deep.value` without optional chaining or null checks
- `.forEach()`, `.map()`, `.reduce()`, `.filter()` called on potentially-null arrays
- `.startsWith()`, `.includes()`, `.split()` called on potentially-null strings
- `...spread` on null/undefined values

## Detection Heuristic

```bash
# Find method chains on FHIR resource fields (common crash points)
grep -rn "\.link\.\|\.name\[.\]\.\|\.extension\.\|\.identifier\.\|\.coding\.\|\.reference\.\|\.address\.\|\.telecom\." src/ --include="*.js" | grep -v node_modules | grep -v test | grep -v "if.*\." | head -50

# Find array methods called without null check
grep -rn "\.forEach\(\|\.map\(\|\.reduce\(\|\.filter\(\|\.find\(" src/ --include="*.js" | grep -v node_modules | grep -v test | grep -v "|| \[\]" | grep -v "?." | head -50

# Find string methods on potentially-null values
grep -rn "\.startsWith\(\|\.endsWith\(\|\.includes\(\|\.split\(\|\.replace\(" src/ --include="*.js" | grep -v node_modules | grep -v test | grep -v "if.*\." | head -50

# Find spread operator on potentially-null values
grep -rn "\.\.\." src/ --include="*.js" | grep -v node_modules | grep -v test | grep "resource\|result\|data\|response" | head -30
```

For each match:
1. Check if the value being accessed can be null/undefined (is it optional in FHIR?)
2. Check if there's a guard (if check, optional chaining, nullish coalescing)
3. If no guard and the value is optional → BUG
4. Extra severity if the crash is in a security-enforcement code path

## Test Template

```javascript
test('BUG: [method] crashes when [field] is null/undefined', () => {
    const resource = { /* valid resource with [field] set to null */ };
    
    // CORRECT: should handle gracefully (not crash)
    expect(() => method(resource)).not.toThrow();
    // OR for async:
    await expect(method(resource)).resolves.not.toThrow();
});
```

## Where This Class Tends To Live

Sweep by category. Instances are numerous and move with the code, so a fixed list goes stale faster than the heuristic does.

| Category | Typical unguarded shape |
|---|---|
| Admin and migration runners | Array methods on optional resource collections |
| Person/Patient link traversal | `reduce`/`filter` on an absent link array |
| Reference handling | `startsWith`/`split` on an absent reference string |
| Name, address and telecom formatting | Indexing element 0 of a possibly-empty array |
| Audit and logging helpers | Property access on an absent actor or meta block |
| Storage and transport clients | Methods on an absent response body |
| Patient scope enforcement | `includes` on a collection that may not have been populated |

**Prioritise by path, not by count.** A crash in name formatting is a defect; the same crash in scope enforcement is a security finding. When sweeping, rank matches by whether the enclosing function participates in an authorization decision, and check what the caller's error handler does with the exception.
