# Test Density Rules

## Testing Types

This skill produces **Narrow Integration Tests** — tests that exercise real application logic while mocking external service boundaries (FHIR servers, Kafka, Redis, HTTP APIs). They validate that components integrate correctly with each other but do not require running infrastructure.

These are distinct from:

- **Unit Tests** — test a single function in complete isolation, every dependency stubbed. Useful for pure utility functions and data transformers. This skill writes these for utility/helper files.
- **Broad Integration Tests** — hit actual running services (real FHIR server, real database, real message broker). Require docker-compose or deployed infrastructure. This skill does NOT produce these. They belong in `test:e2e` suites with dedicated infrastructure.

**Why "Narrow Integration" is the default:** Most production bugs at b.well live at the boundary between internal components — a service calls another service's method with the wrong shape, a consumer doesn't await its service call, a mapper mutates its input. Pure unit tests (fully mocked) can't catch these because the mocks hide the interaction. Broad integration tests catch them but are slow and flaky. Narrow integration tests hit the sweet spot: real internal wiring, mocked external I/O.

## Minimum Test Density

These are floors, not targets.

| File Type | Minimum Tests |
|---|---|
| Service (>200 lines) | 15 |
| Service (≤200 lines) | 8 |
| Resolver / Controller | 10 |
| Consumer / Job Processor | 8 |
| Any other file with logic | 5 |

**Each test file must include:**
- Happy path per public method
- Error/failure path per public method that has error handling
- At least one bug-hunting test targeting a suspicious pattern from `.qa/domain-invariants.md`

## Breadth AND Depth — Both Required

There is no tradeoff. Both are mandatory.

- **Breadth**: Every untested source file with logic gets a spec file. No exceptions.
- **Depth**: Every spec file meets the minimum test count above. No exceptions.

If you have 6 untested files and create specs with 3 tests each — FAIL (breadth without depth).
If you have 6 untested files and deeply test only 2 of them — FAIL (depth without breadth).
You create ALL 6 specs AND each meets its minimum.

## Verification Gate

Run after generating all test files:

```bash
echo "Verifying test density..."
FAILURES=0
for spec in $(find src -name "*.spec.ts" -newer .qa/domain-invariants.md 2>/dev/null); do
  TEST_COUNT=$(grep -c "^\s*it(" "$spec" 2>/dev/null || echo 0)
  SOURCE="${spec%.spec.ts}.ts"
  LINES=$(wc -l < "$SOURCE" 2>/dev/null || echo 0)

  if echo "$SOURCE" | grep -qE "\.service\."; then
    if [ "$LINES" -gt 200 ] && [ "$TEST_COUNT" -lt 15 ]; then
      echo "   FAIL: $spec — $TEST_COUNT tests (minimum 15 for service >200 lines)"
      FAILURES=$((FAILURES + 1))
    elif [ "$LINES" -le 200 ] && [ "$TEST_COUNT" -lt 8 ]; then
      echo "   FAIL: $spec — $TEST_COUNT tests (minimum 8 for service)"
      FAILURES=$((FAILURES + 1))
    fi
  elif [ "$TEST_COUNT" -lt 5 ]; then
    echo "   FAIL: $spec — $TEST_COUNT tests (minimum 5)"
    FAILURES=$((FAILURES + 1))
  fi
done

if [ "$FAILURES" -gt 0 ]; then
  echo "   $FAILURES files below minimum. Go back and add tests."
else
  echo "   All files meet minimum test density."
fi
```

## Why This Exists

Experiments 4 through 6 proved the model consistently picks one of two failure modes without a mechanical rule forcing both:

1. **Breadth-only**: Many spec files, 3-4 tests each. Catches nothing.
2. **Depth-only**: Deep bug-hunting in 3-4 files. Misses coverage on everything else.

Experiment 4 proved both are achievable in one pass (306 tests, 29 suites, 87% coverage, 7 bugs). Experiment 6 initially failed with depth-only (255 tests, +0.58% coverage) before being corrected to match (306 tests, 16 bugs). The model needs this rule because its judgment about breadth/depth tradeoffs consistently fails.
