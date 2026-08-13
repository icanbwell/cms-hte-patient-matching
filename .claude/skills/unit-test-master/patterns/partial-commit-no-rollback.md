---
id: partial-commit-no-rollback
class: partial-commit-no-rollback
impact_if_present: high
pattern_origin: >
  Structural pattern. Two recurring shapes. First, a bulk writer that falls back to a
  secondary executor on timeout and hands it the full operation set, including operations
  the primary may already have committed. Second, in-memory tracking state cleared before
  the work it tracks is confirmed, so a failure after the clear leaves nothing to retry
  from.
---

## Root Cause Pattern

A multi-step write operation commits partial results, then encounters an error on subsequent steps. The error handling either:
1. Retries ALL operations (including already-committed ones) → duplicate data
2. Falls back to an alternative writer with the full set → double-writes
3. Clears tracking state BEFORE confirmation → data loss on failure
4. Has no `finally` block to clean up partial state → leaked resources

This is especially dangerous in healthcare data where:
- Duplicate patient records violate data integrity
- Lost audit events mean compliance violations
- Partial writes to ClickHouse + MongoDB mean inconsistent views of patient data

## Detection Heuristic

```bash
# Find try/catch blocks around bulk write operations
grep -rn "try\|catch\|finally" src/ --include="*.js" | grep -v node_modules | grep -v test | grep -i "bulk\|batch\|write\|insert\|update\|delete\|commit" | head -30

# Find fallback/retry patterns
grep -rn "fallback\|retry\|attempt\|backup.*executor\|secondary" src/ --include="*.js" | grep -v node_modules | grep -v test | head -20

# Find Map/Set .clear() calls (state wiped before confirmation)
grep -rn "\.clear()\|\.delete(\|new Map()\|new Set()" src/ --include="*.js" | grep -v node_modules | grep -v test | grep -B2 -A2 "async\|await\|then\|Promise" | head -40

# Find operations WITHOUT finally blocks
grep -rn "try {" src/ --include="*.js" | grep -v node_modules | grep -v test | while read line; do
  file=$(echo "$line" | cut -d: -f1)
  linenum=$(echo "$line" | cut -d: -f2)
  # Check if there's a finally within 50 lines
  if ! sed -n "${linenum},$((linenum+50))p" "$file" | grep -q "finally"; then
    echo "NO FINALLY: $line"
  fi
done 2>/dev/null | head -20
```

For each bulk operation found:
1. What happens if it partially succeeds then fails?
2. Is there a rollback mechanism?
3. Does the fallback/retry receive only UNCOMMITTED operations?
4. Is tracking state cleared BEFORE or AFTER confirmation?

## Test Template

```javascript
test('BUG: [operation] commits partial data then retries all on failure', () => {
    // Simulate: first N operations succeed, then timeout
    mockExecutor.execute.mockResolvedValueOnce({ ok: true })  // first batch
        .mockRejectedValueOnce(new Error('timeout'));  // second batch

    await operation.executeBulk(allOperations);

    // CORRECT: fallback should only receive uncommitted operations
    expect(fallbackExecutor.execute).not.toHaveBeenCalled();
    // OR: if fallback IS called, it should receive only the failed subset
    expect(fallbackExecutor.execute).toHaveBeenCalledWith(
        expect.not.arrayContaining(alreadyCommittedOps)
    );
});

test('BUG: [maps/state] cleared BEFORE processing completes', () => {
    // Simulate: processing fails after state is cleared
    mockProcessor.process.mockRejectedValue(new Error('kafka failure'));

    await expect(producer.flush()).rejects.toThrow();

    // CORRECT: maps should be preserved on failure for retry
    expect(producer.pendingEvents.size).toBeGreaterThan(0);
});
```

## Where This Class Tends To Live

| Category | What to check |
|---|---|
| Bulk write executors with a fallback path | The fallback receives only the uncommitted subset |
| Event producers holding pending state in maps or sets | State is cleared after confirmation, never before |
| Export and long-running job managers | A `finally` block releases cache entries and post-request tasks |
| Scheduled job runners | Failures propagate rather than being logged and swallowed |
| Any writer spanning two stores | A failure in the second store leaves the first in a recoverable state |

**The test that matters is the second-call test.** A single successful bulk write proves nothing about this class. Drive a partial success followed by a failure and assert on what the retry path receives.
