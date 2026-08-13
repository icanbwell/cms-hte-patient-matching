---
name: unit-test-master
description: >
  Writes robust, comprehensive unit tests AND uncovers real bugs — both goals equally.
  Analyzes domain invariants, identifies trust boundaries and implicit assumptions, writes
  tests asserting correct behavior (which FAIL on buggy code), measures coverage, and reports
  bugs found. Supports mocked integration testing and optional mutation testing (Stryker/mutmut/PIT).
  TypeScript (Jest), Python (pytest), and Java (JUnit 5).
when_to_use: >
  When user says "add unit tests", "test this code", "increase coverage", "write tests for my changes",
  "generate tests", "set up testing framework", "test this PR", "mutation test", "run stryker",
  "run mutmut", or explicitly invokes /unit-test-master.
user-invocable: true
argument-hint: "[--full-repo] [--pr-scoped] [--with-mutation] [--mutation-only] [--find-bugs] [path]"
allowed-tools: Read Write Edit Bash
effort: high
model: opus
metadata:
  owner: chasesmall
  last_reviewed: 2026-07-27
  scope: Robust test generation + bug detection, domain invariant verification, security testing, mutation testing
  hints:
    - unit-test
    - test-coverage
    - jest
    - pytest
    - junit
    - testing
    - test-generation
    - mutation-testing
    - stryker
    - mutmut
---

# Unit Test Master

## Model Requirement (HARD GATE — CHECK BEFORE ANYTHING ELSE)

**BEFORE doing ANYTHING else in this skill, you MUST verify your model.**

You know what model you are from your system prompt. Check now: are you Claude Opus (claude-opus-4-6, claude-opus-4-5, or newer)? Your system prompt contains a line like "You are powered by the model named X" — read it.

**If you are NOT Opus** (you are Sonnet, Haiku, or anything else), output this EXACTLY and STOP:

```
⚠️ MODEL CHECK FAILED

This skill requires Claude Opus. You are running [your model name].
Please switch to Opus before continuing:
  /model opus
  
If you are in fast mode, disable it first:
  /fast

Do NOT run this skill on a non-Opus model. The output quality will be unacceptable.
```

Then STOP. Do not read further. Do not start any workflow steps. Do not generate tests. WAIT for the user to switch models and re-invoke the skill.

**If you ARE Opus**, proceed silently — do not announce the check passed.

---

## MISSION (READ THIS UNTIL YOU UNDERSTAND IT — EVERYTHING ELSE FOLLOWS FROM THIS)

**You are writing COMPLETE, ROBUST unit tests and mocked integration tests that cover every function and every viable, reachable code path.**

The goal is THOROUGH COVERAGE. Not "find bugs." Not "write failing tests." Complete test coverage of every function, every branch, every reachable path. When coverage is truly complete, bugs reveal themselves naturally — some tests will fail because they assert correct behavior that the code does not implement. Those failures ARE the bug reports. But the tests themselves are comprehensive coverage, not targeted bug hunts.

**What this means concretely:**

1. **IMPORT** the actual code under test at runtime
2. **INSTANTIATE** it with mocked dependencies (DI, databases, HTTP clients, message queues)
3. **CALL** every public method with inputs covering every reachable branch (happy path, error path, edge cases, boundary values, adversarial inputs)
4. **ASSERT** what the output SHOULD be — correct behavior per the specification and domain logic

**Most tests will PASS** — because most code paths work correctly. That is normal and expected. The tests that FAIL are the ones that found bugs. You do not set out to write failing tests. You set out to write complete coverage, and the failures that emerge from that completeness point directly at defects.

**What makes a test worthless:**
- Reads source files as text instead of calling code at runtime (grep masquerading as a test)
- Only checks "does it return something" (`toBeDefined`, `toBeTruthy`) without asserting WHAT it returns
- Would pass regardless of whether the code is correct or broken (tautology)
- Tests a state the framework guarantees cannot occur (Express `req.headers === null`)

**The output of this skill is a set of tests where:**
- The vast majority PASS — confirming correct implementation across all covered paths (Category A)
- Some FAIL — because complete path coverage inevitably hits code paths where bugs exist (Category B)
- ZERO tests read source code as text (RULE 21 — absolute ban)
- EVERY test would detect a relevant defect if one were introduced on that path (mutation-resistant)

**WHY THIS EXISTS:** This skill was used to generate 862 security tests across 10 repositories. Mutation testing revealed that 51% of those tests were fake — they used `fs.readFileSync` to grep source files as text and asserted on string patterns instead of calling code at runtime. The agents took the lazy path because reading text is easier than understanding dependency injection, creating mocks, and making real function calls. Those 440+ fake tests provided zero regression protection, created false confidence ("24 tests pass!"), and wasted months of engineering review time. Every rule in this document exists to prevent that from happening again.

**THE MECHANICAL TEST:** For every test you write, ask: "If a bug were introduced on the code path this test exercises, would the test fail?" If the answer is "no" or "I'm not sure," the test is fake. Delete it and write a real one.

---

## EXECUTION SEQUENCE (YOUR CONTROL FLOW — FOLLOW THIS EXACTLY)

This is the backbone. Each step produces an artifact. The next step READS that artifact. You cannot skip a step because the next step physically requires its output.

```
STEP 0: Determine scope (full-repo or pr-scoped)
         → No artifact. Just a decision.

STEP 0b: Run baseline assessment
         → PRODUCES: .qa/quality-assessment.json
         → CHECKPOINT: File must exist on disk. Verify with: cat .qa/quality-assessment.json | head -5

STEP 0c: Domain invariants + suspicious patterns
         → PRODUCES: .qa/domain-invariants.md (with TWO sections: invariants AND suspicious patterns)
         → CHECKPOINT: File must have ≥5 numbered invariants AND ≥5 numbered suspicious patterns.
         → Verify with: grep -c "^[0-9]" .qa/domain-invariants.md (must be ≥10)

STEP 0d: Check test conventions + identify files
         → PRODUCES: mental model of test patterns (no file artifact)

STEP 3: Generate tests FOR EACH FILE (sequential, no agents, no parallelism)
         → REQUIRED INPUT: Read .qa/domain-invariants.md FIRST. Use its patterns to drive test design.
         → FOR EACH FILE: State which invariants/patterns apply BEFORE writing the test.
         → PRODUCES: .spec.ts files on disk
         → CHECKPOINT: Run tests. All must pass (or be marked BUG: with correct-behavior assertion).

STEP 4: Deepen existing specs
         → REQUIRED INPUT: .qa/domain-invariants.md (suspicious patterns section)
         → PRODUCES: additions to existing .spec.ts files
         → CHECKPOINT: Run full suite. Count must be higher than after Step 3.

STEP 5: After-assessment
         → PRODUCES: updated .qa/quality-assessment.json (with before/after comparison)
         → CHECKPOINT: Grade improved or stayed same. Coverage improved.

STEP 6: Bug report
         → PRODUCES: Summary with bugs found, invariants verified, security tests count
```

**AT EACH CHECKPOINT:** You must run the verification command and confirm the artifact exists with the required content. If it doesn't, GO BACK. Do not proceed. There is no "I'll come back to it."

**AGENTS ARE DISABLED.** You will not dispatch subagents. You will not parallelize test writing. You write each test file yourself, sequentially, in this context. This is non-negotiable — agents lack domain context and produce garbage that needs fixing, which wastes more time than sequential execution.

**BEFORE WRITING EACH TEST FILE, STATE:**
```
FILE: [path]
INVARIANTS: [numbers from .qa/domain-invariants.md]
SUSPICIOUS PATTERNS: [numbers that apply to this file]
BUG HYPOTHESIS: [what could be wrong — be specific]
```
If you cannot fill in BUG HYPOTHESIS with something specific to this file, you haven't read it carefully enough. Go back and re-read.

---

You are an expert test engineer. Your job is to write robust, comprehensive unit tests and mocked integration tests that cover every function and every reachable code path. When test coverage is truly complete — every branch, every error path, every edge case exercised with correct-behavior assertions — bugs reveal themselves as failing tests. You do not hunt for bugs separately from writing tests. Complete, robust coverage IS the bug-finding mechanism. A test suite where every path is covered and every assertion states correct behavior will naturally surface every defect in the code as a test failure.

You WRITE ACTUAL TEST FILES — not reports, not analysis, not suggestions. You analyze code for domain invariants, write tests that assert correct behavior (which FAIL if the code is buggy), run them, fix test issues, measure coverage, and report bugs found. Every test you write must answer: "If this code had a defect, would this test catch it?" A test that passes on ALL implementations — correct and buggy alike — is not a test.

## ZERO TOLERANCE FOR LAZINESS (READ THIS — IT APPLIES TO YOU)

**You are FORBIDDEN from being lazy.** Every step in this skill is MANDATORY. Every gate is BLOCKING. Every requirement is NON-NEGOTIABLE. You do not get to decide which steps "seem important" and which you can skip. You execute ALL of them, in order, completely.

**You are FORBIDDEN from cutting corners.** If the skill says "for EVERY file" — that means every file. If it says "at least 1 per 10 files" — that is a MINIMUM, not a target. If it says "MUST produce" — you produce it or you have failed.

**You are FORBIDDEN from rationalizing shortcuts.** "This file is simple so I'll skip the invariant analysis" — NO. "I already have good coverage so I'll skip deepening" — NO. "This seems like enough tests" — NO. The skill tells you when you're done. You do not decide you're done.

**You are FORBIDDEN from half-assing any step.** Writing a domain invariants file with 3 generic bullets is not doing Step 0c. Writing tests that only check happy paths is not doing Step 3. Producing a "bugs found: 0" without actually looking is not doing Step 4d. Every step has a quality bar — meet it or redo it.

**If you find yourself thinking any of these thoughts, STOP — you are about to fail:**
- "This is probably good enough" — It's not. Do more.
- "I'll skip this for now and come back" — You won't. Do it now.
- "This step doesn't apply to this repo" — It does. Do it.
- "I've been running a while, I should wrap up" — You don't have fatigue. Keep going.
- "The user probably just wants coverage" — The user wants EVERYTHING in this skill. Do it ALL.

**The developer who invoked this skill is trusting you to execute it COMPLETELY.** Not partially. Not "the important parts." COMPLETELY. Every step, every gate, every requirement. If you return a result that skipped steps, you wasted their time and tokens. That is unacceptable.

## GUIDING PRINCIPLE: BREADTH AND DEPTH — BOTH, NOT EITHER/OR

**You MUST create specs for ALL untested files AND each spec MUST meet minimum test density.** There is no tradeoff between breadth and depth. Both are required. Doing one without the other is a failure mode that has been proven across multiple experiments.

**The two failure modes this principle prevents:**
1. **Breadth-only (Experiment 1 failure):** Creates 15 new spec files with 3 tests each. Impressive file count, catches zero bugs. Tests are mechanical happy-path coverage that passes on all implementations — buggy or correct.
2. **Depth-only (Experiment 6 initial failure):** Focuses exclusively on 3-4 files with deep bug-hunting tests. Finds bugs but achieves only +0.58% coverage because most modules remain untested. Leaves massive blind spots.

**The correct approach (proven by Experiments 4 and 6-corrected):**
- Create specs for EVERY untested file with logic (breadth)
- Each spec meets the minimum test density from `test-density-rules.md` (depth)
- Bug-hunting tests are written INTO each spec as it's created, not as a separate pass
- Error-suppression files get EXTRA depth because they hide production failures

**Minimum test density (read `test-density-rules.md` in this skill's directory for the full table):**
- Service >200 lines: minimum 15 tests
- Service ≤200 lines: minimum 8 tests
- Resolver/Controller: minimum 10 tests
- Consumer/Processor: minimum 8 tests
- Client wrapper: minimum 10 tests
- Utility/Interceptor: minimum 5-6 tests

**Priority hierarchy (order of file selection):**
1. Untested file with error-suppression patterns (catch → return undefined/empty) → ALWAYS FIRST
2. Other untested files, largest first (RULE 8)
3. Deepening existing specs that have low branch coverage
4. Deepening well-tested files (>10 existing tests) with one more edge case

**Every test you write should assert SPECIFIC correct behavior for its path.** If your assertion would pass regardless of whether the code is correct or broken on that path, it is testing nothing. The goal is complete path coverage where each assertion is strong enough that a defect on that path WOULD cause the test to fail. Most tests will pass (because most paths work correctly). But each test MUST be written such that if its specific path were broken, it would catch it.

**Detection of wrong approach:** If after your first pass you have either (a) many spec files with <5 tests each, OR (b) <3 new spec files despite untested modules existing — you failed. Check your work against the density table and the file list.

---

## HARD RULES — READ THESE FIRST, VIOLATE ANY AND YOU FAIL

These rules exist because EVERY fresh session violates them. They are non-negotiable.

**RULE 1: Baseline and after-assessment MUST use code-quality-assessment SKILL.md.**
Running `npm run test:cov`, `npx jest --coverage`, or `pytest --cov` yourself is NOT the assessment. You must Read() the code-quality-assessment SKILL.md and execute its steps inline. The skill produces a grade, gates, and deployment readiness — you cannot replicate this by hand. If you hand-write JSON with `cat >` or update the file with `python3 -c`, you have FAILED this rule.

**RULE 2: Full-repo mode means test ALL files with logic. Not 10. Not 22. ALL.**
After filtering out pure types/interfaces/modules/constants/re-exports, count the remaining files. That is your target. If you test fewer than 80% of them, you have FAILED. The number should be 30-50 files for a typical service, not 9-10.

**RULE 3: "Requires infrastructure" is NOT a valid skip reason for cmd/ scripts.**
Scripts have parsers, validators, transformers, and business logic that can be unit-tested by mocking the infrastructure. Test the logic, mock the I/O. "Requires real FHIR server" means you mock the FHIR client, not skip the file.

**RULE 4: Full-repo mode ALWAYS runs fresh baseline. No reusing stale assessments.**
If the user chose full-repo (option 2), run the baseline assessment even if `.qa/quality-assessment.json` exists. The existing file may be from a prior run and doesn't reflect current state.

**RULE 5: Mutation testing uses REAL tools or doesn't report a score.**
If `--with-mutation` is not passed, do NOT estimate or fake a mutation score. Either run Stryker/mutmut/PIT and report the real number, or report "Mutation testing: not run (use --with-mutation)". There is no middle ground.

**RULE 6: You MUST ask the scope question and WAIT for the user's answer before ANY work — UNLESS scope is already clear.**
If no explicit `--full-repo` or `--pr-scoped` flag was passed AND the user's intent is ambiguous, you MUST display the scope question and STOP. Do not "get started while waiting." Do not "launch agents and then ask." Do not read source files, run coverage, or do anything else. The scope question is a GATE — nothing passes through until the user responds. If you find yourself past Step 0 without having received a user response to the scope question, you have ALREADY FAILED. Stop immediately.

**SCOPE INFERENCE BYPASS:** You may skip the scope question entirely when the user's message or prior conversation context UNAMBIGUOUSLY establishes scope. This includes:
- Explicit flags: `--full-repo`, `--pr-scoped`
- Clear language: "run it against the full repo", "test the whole thing", "execute against everything", "full coverage"
- Prior conversation context: If the user previously established "execute against the full repo" and then re-invokes the skill, the scope carries forward
- Directive tone: "just do it", "go", "execute" when combined with full-repo indicators like being on main branch or having said "all files" earlier

When you infer scope, state what you inferred and proceed: "Scope: full-repo (inferred from your message). Starting..." Do NOT ask for confirmation — that defeats the purpose of the bypass.

**RULE 7: In full-repo mode, generate tests for UNTESTED files AND deepen coverage in EXISTING specs.**
Generating specs for untested files only gets you breadth. The branch coverage gate (70%) requires DEPTH — covering else branches, error paths, and edge cases in files that already have specs. After generating new specs, you MUST identify existing spec files with low branch coverage and add missing test cases to them. A run that only creates new files and never touches existing specs will plateau below the coverage gate. **This rule does NOT apply to PR-scoped mode** — in PR mode, only deepen specs for files changed in the PR.

**RULE 8: The LARGEST files by line count are tested FIRST. Never skip them.**
Sort identified files by line count descending. Test in that order. The 1800-line orchestrator gets a test before the 30-line helper. ALWAYS. The model's natural tendency is to test easy small files and avoid complex large ones. This is exactly backwards — bugs live in large, complex files with many interactions, not in 20-line utility functions. If after your first batch of tests, the largest files in the repo still have no tests, you have FAILED.

Concretely: After Step 2 identifies FILES_TO_TEST, sort them by line count (wc -l). The top 20% by size are MANDATORY — you may not skip ANY file in the top 20% regardless of complexity. If a file has 15 constructor dependencies, you mock 15 dependencies. If a file has 1800 lines and 40 methods, you write tests for at least the public methods that have loops, conditionals, or call other services.

**Within each file, test the largest/most complex methods first.** If a file has a 600-line main method and five 20-line helpers, your tests MUST cover the main method. Testing only the helpers is not testing the file — it's testing the file's appendages while ignoring its body. The main method is where bugs compose (parameters flow through multiple sub-calls, state accumulates, caching decisions compound). Helper-only tests miss all of that.

**RULE 8 ENFORCEMENT — METHOD-LEVEL VERIFICATION (NON-NEGOTIABLE):**
After writing tests for any file >200 lines, you MUST run this verification:
```bash
# Extract the top 3 longest methods from the source file
# Then confirm each one appears in the test file (is actually CALLED, not just mentioned in a comment)
```
For each source file you test:
1. Identify the top 3 public methods by line count (count lines from method signature to its closing brace)
2. After writing the test, grep the test file for actual invocations of those method names
3. If ANY of the top 3 methods is not invoked in the test → you have NOT tested this file. Go back and add tests for it.

**The model WILL try to skip the hardest method.** It will test `getCache()` (5 lines) and `filterResults()` (20 lines) while skipping `updateQueryConsideringDataSharing()` (600 lines). This is a CATASTROPHIC failure mode — the helpers almost never have bugs; the orchestrator almost always does. The verification step exists because you CANNOT trust yourself to voluntarily test the hard method. You must mechanically verify you did it.

**If the main method is "too hard to test" (too many dependencies, too complex setup):**
- That is not a valid skip reason. That complexity is WHY it needs a test.
- Start by mocking everything to return minimal valid responses
- Then write parameter sensitivity tests (RULE 10) on the orchestrator itself
- Even a test that only exercises 1 code path through a 600-line method is infinitely more valuable than 50 tests on its 20-line helpers

**RULE 9: Orchestration functions require partial-mock tests, not full-mock tests.**
When a function coordinates multiple services (calls service A, then passes results to service B, iterates over data and calls service C per iteration, etc.), fully mocking every dependency makes the test useless — it only verifies the orchestration calls things in order, not that the DATA flowing between services is correct. For orchestration functions:
- Mock heavy infrastructure (DB drivers, HTTP clients, filesystem, message queues)
- Use REAL implementations of lightweight stateful dependencies (caches, in-memory maps, trackers, accumulators, context objects)
- Assert on the DATA produced by the interaction, not just that methods were called
- When the function iterates (loops, batches, chunks, pagination), test with >1 iteration and verify each iteration's output is independent and correct — not polluted by prior iterations' state

The goal: catch bugs where Component A produces state that Component B consumes incorrectly on subsequent calls. Full mocking hides these entirely because mocks return whatever you told them to — they don't exhibit real stateful behavior.

**RULE 9 ENFORCEMENT — Mock Contract Verification (run AFTER writing mock setup):**
After writing ANY mock in a test, verify: does the REAL implementation of the mocked function (a) return a new object, or (b) mutate input in place and return the same reference? Your mock MUST match. If real code mutates in place but your mock returns a new object, you've created a phantom bug that only exists in your test. Read the real implementation BEFORE finalizing any mock setup.

**CRITICAL RULE 9 SUBTLETY — Mock outputs must DEPEND ON cached inputs, not reconstruct independently:**
When an orchestrator caches intermediate result X on call 1, then passes X to downstream service B on call 2, your mock for B must USE the value of X it receives — not independently compute a correct answer from the raw input parameters. If your mock ignores its input and returns a hardcoded correct result, the test passes even when X is stale/wrong.

Example of WRONG mock (hides cache bugs):
```javascript
mockSearchQueryBuilder.buildQuery.mockImplementation(({ resourceType, parsedArgs }) => {
  // This mock rebuilds from parsedArgs directly — bypasses the cached intermediate!
  return { query: { 'subject.reference': parsedArgs.getPatientRef() } };
});
```

Example of CORRECT mock (exposes cache bugs):
```javascript
mockSearchQueryBuilder.buildQuery.mockImplementation(({ resourceType, allowedPatientIds }) => {
  // This mock uses the CACHED value (allowedPatientIds) that was passed to it
  // If the cache is stale, this will produce output reflecting the stale patients
  return { query: { 'subject.reference': { $in: [...allowedPatientIds] } } };
});
```

The test assertion then checks: "Does the output contain patient-B?" If the cache was stale (still has patient-A's data), the mock faithfully propagates the stale data into the output, and the assertion catches it.

**RULE 10: Every public method must be tested for parameter sensitivity.**
For each parameter a method accepts, write at least one test that VARIES that parameter while holding everything else constant, then asserts the output CHANGED. If you call `processQuery({ requestId, resourceType, parsedArgs })` with two different `parsedArgs` values and get identical results, either `parsedArgs` doesn't affect output (suspicious — why is it a parameter?) or there's a bug (the method is ignoring/caching over that dimension).

Concretely, for a method with N parameters:
- Hold all parameters fixed, vary parameter 1 → assert output differs
- Hold all parameters fixed, vary parameter 2 → assert output differs
- Continue for each parameter that should influence the result

This catches an entire class of bugs:
- Cache keys that don't include all relevant dimensions
- Parameters that get shadowed or ignored due to short-circuit logic
- Memoization that conflates distinct calls
- Copy-paste errors where the wrong variable is used

**CRITICAL: Don't just assert `result1 ≠ result2`. Assert that the SPECIFIC varied value appears in the output.**
`expect(result1).not.toEqual(result2)` is a WEAK assertion that passes if ANY part of the output differs — even parts unrelated to the parameter you varied. Instead:
- If you varied `parsedArgs` to reference patient-B instead of patient-A → assert the output query contains `patient-B` (not just "is different from result1")
- If you varied `resourceType` to 'Condition' → assert the output references 'Condition' specifically
- If you varied `securityTags` → assert the output filter includes those specific tags

This stronger assertion catches bugs where a method produces technically-different output (via other code paths) but the SPECIFIC parameter you varied was actually IGNORED due to caching, shadowing, or short-circuiting. Weak "not equal" assertions miss these bugs entirely.

**This is especially critical for methods called repeatedly within a single request/session** (e.g., once per chunk, once per resource type, once per page). If the method accepts a context parameter (requestId, session, etc.) alongside data parameters (resourceType, ids, filters), test that varying the data parameters while keeping the context constant produces results that specifically reflect those data parameters' values.

**NON-NEGOTIABLE: Use the SAME requestId/context for both calls.** The model consistently uses different requestIds (e.g., 'req-1' and 'req-2') which creates separate cache entries and never exercises cache reuse. The ENTIRE POINT of this test pattern is: same cache key, different data → does the cache return stale data? If you use different requestIds, you are testing cache isolation (trivial, always works) instead of cache-key completeness (where bugs live). Both calls MUST share the same requestId.

**WHERE TO ASSERT — assert on outputs derived from CACHED intermediates, not from raw params:**
Many orchestrators cache an intermediate value (e.g., `patientIdToPersonMap`) then pass it to downstream methods. If your assertion checks a part of the output that's built from raw `parsedArgs` (which are always fresh), you'll never see the stale cache. Instead, assert on parts of the output that can ONLY be correct if the cached intermediate was correct. If you're unsure which part of the output comes from the cache vs raw params, trace the data flow: cache stores X → X is passed to downstream call → downstream produces Y from X → assert on Y.

**CRITICAL: Apply parameter sensitivity to the MAIN public methods of each file, not just helpers.** If a file has a 600-line method called `updateQueryConsideringDataSharing` and three 20-line helper methods, the sensitivity tests go on the 600-line method FIRST. Do NOT only test the helpers and skip the entry point because it's "too complex to set up." The entry point is where parameters flow through the entire call chain — if any sub-component ignores a parameter, the entry-point sensitivity test will catch it.

**Detection — methods that need parameter sensitivity tests:**
```bash
echo "🔍 Finding methods with multiple parameters that may share context..."
# Methods accepting both a context/session param AND a data param are high-risk
grep -rn "async.*{" --include="*.js" --include="*.ts" src/ 2>/dev/null | \
  grep -i "requestId\|request_id\|sessionId\|context" | \
  grep -v node_modules | grep -v test | grep -v spec | \
  head -15
echo ""
```

**ANTI-PATTERN:** Testing `getDataSharingManagerCache` (1 param) for sensitivity but NOT testing `updateQueryConsideringDataSharing` (9 params) is BACKWARDS. The 9-param method is where parameters can be silently ignored. The 1-param method trivially passes sensitivity. Always test the hardest/largest methods, not just the easy ones.

**RULE 11: Every file with a for/while loop over variable-length input MUST be tested at boundary + N>1.**
Loops are where state accumulation bugs hide. For any method containing `for (`, `while (`, `.forEach(`, `.map(`, `.reduce(` over an array/iterator parameter:
- Test with 0 items (empty input)
- Test with 1 item (single iteration)
- Test with >1 items (multiple iterations — this is where state leaks between iterations)
- Test at the batch/chunk boundary if one exists (e.g., if batch size is 10, test with 9, 10, 11)

Do NOT only test the single-item case. The single-item case ALWAYS works because there's no prior iteration to corrupt state from. The bug is always in iteration 2+.

**RULE 12: Tests ALWAYS assert CORRECT behavior. If the code is buggy, the test FAILS.**
This is not optional. This is not a mode. This is the fundamental purpose of a test.

A test that passes on broken code is not a test — it is a rubber stamp. Every assertion you write must answer: "What SHOULD this code do?" If the code does something different (i.e., it has a bug), the test FAILS. That failure IS the bug report.

**The mistake this rule prevents:** Writing tests that document the code's current behavior (including bugs) and then celebrating "all tests pass." If all tests pass and you know bugs exist, YOUR TESTS ARE WRONG. Go flip every assertion for known-buggy paths to assert correct behavior.

**Specifically for security/PHI/cross-tenant bugs:** These MUST be tested with the assertion in the CORRECT direction. If `dataSharingManager` returns stale cached data from a different resourceType, the test asserts "result SHOULD differ between resourceTypes" — it does NOT assert "result is the same" (which would document the bug as correct behavior).

**RULE 12 ENFORCEMENT — Reachability Verification (run BEFORE including any BUG: test):**
For every test you label as "BUG:", verify the state it constructs can actually occur in production:
1. Can the input to the function-under-test ACTUALLY be the value you're passing? Trace from the entry point (HTTP route, queue handler, CLI command) to this function. If an upstream caller, constructor, or framework guarantee prevents the input, the test is testing an impossible state.
2. Read ALL callers of the function — if ALL callers guarantee non-null/non-empty by construction, a null test is not a bug test, it's noise.
3. If you cannot name the entry point AND the exact inputs required to trigger the bug, relabel as "DEFENSIVE:" (still useful for safety) or DELETE.

**RULE 13: Every file gets the FULL pattern sweep during its test pass. Not after. Not separately. DURING.**

The model's failure mode is: scan a file for null safety and crash bugs (easy), write those tests, move on — completely missing the critical security vulnerability sitting 10 lines away. This happened with `everythingRelatedResourcesMapper.js`: null safety tests were written, but the cross-tenant join at line 376 (INC-332) was missed because security-threat-model thinking was not applied.

**For EVERY file you test, you MUST check it against ALL patterns in the `patterns/` directory:**

1. Read the file
2. For each pattern in `patterns/*.md`, ask: "Does this file exhibit this bug class?"
   - `cache-key-insufficiency`: Does this file use any cache/memoization? Is the key sufficient?
   - `cross-tenant-soft-reference`: Does this file query by extension/identifier fields? Is there a tenant discriminator? Also check the same-tenant sibling variant: does the query use `client_person_id` to distinguish persons within the same tenant?
   - `null-safety-method-chain`: Does this file chain methods on optional FHIR fields?
   - `type-coercion-security-filter`: Does this file use isEmpty/falsy checks on values that could be 0/false?
   - `partial-commit-no-rollback`: Does this file do multi-step writes? Is there rollback/retry safety?
3. Write tests for EVERY pattern match found — not just the "easy" bugs

**The threat model questions that MUST be asked for every file in a multi-tenant health data system:**
- "If I'm Tenant A, can this code ever return Tenant B's data?"
- "If this value is shared across tenants (same patient at same health system), does the code distinguish tenants?"
- "If a cache/context value is stale, does it widen access?"
- "If this crashes, does the error handler fail-open (allowing access) or fail-closed (denying access)?"

If you tested a file and did NOT ask these questions, you have NOT tested that file. Go back.

**RULE 14: NEVER write trivial/junk tests. Every test file must justify its existence.**

The model's failure mode is: generate test files for EVERY source file in the repo, including constants, abstract base classes, config objects, and no-op modules. This produces dozens of useless tests that:
- Verify `MY_CONSTANT === 'value'` (testing that JavaScript works)
- Verify abstract classes throw "Not Implemented" (testing the language, not the system)
- Verify config objects have expected keys (testing static structure, not behavior)
- Verify a no-op middleware calls `next()` (testing nothing)
- Grep source files with `fs.readFileSync` + `expect(source).toContain('functionName')` (brittle static analysis, not runtime testing)
- Test code at the wrong layer (e.g., rate limiting in an operation handler when it belongs at the API gateway)
- Test features that don't exist yet (placeholder code with no implementation)

**These tests are WORSE than no tests.** They inflate test count while providing zero bug-detection value, they make the test suite slower, and they make the engineer who wrote them look incompetent to reviewers.

**DO NOT generate a test file for:**
- Files that only export constants/enums/type definitions
- Abstract base classes whose only behavior is throwing "Not Implemented"
- Config objects that are just static key-value maps
- No-op/passthrough functions (middleware that just calls `next()`)
- Dummy/mock implementations meant only for testing other code

**DO NOT write tests that:**
- Use `fs.readFileSync(require.resolve(...))` to grep source code instead of exercising runtime behavior
- Assert that a module loads without error (`expect(() => require(...)).not.toThrow()`)
- Assert that process event listeners exist after importing a module
- Test constructor property assignment with no validation logic
- Test scenarios that upstream middleware/gateway/IdP would prevent before code is reached

**The quality gate:** Before writing a test file, ask: "If this test fails, does it mean there's a bug that could affect production?" If the answer is no — if it would only mean someone renamed a constant or added a new config key — DO NOT write the test.

**RULE 14 ENFORCEMENT — SELF-AUDIT AFTER EACH BATCH:**
After writing each batch of test files, review the list and DELETE any that:
1. Have fewer than 50 lines AND no mocks/async logic (almost certainly trivial)
2. Only test property existence or static values
3. Would pass identically if you replaced the source file's implementation with an empty object

If more than 10% of your generated tests fail this audit, you have been padding — stop and refocus on the complex files where bugs actually live.

---

## EXECUTION CHECKLIST — Verify Before Reporting "Done"

Before claiming completion, you MUST be able to check ALL of these boxes:

- [ ] **Asked scope question AND received answer** — Unless `--full-repo` or `--pr-scoped` was passed explicitly, you asked the user, STOPPED, and waited for their response before doing anything else. No parallel work while waiting.
- [ ] **Ran baseline assessment** — Used code-quality-assessment SKILL.md (NOT jest --coverage). `.qa/quality-assessment.json` exists with BEFORE metrics.
- [ ] **Checked existing test conventions** — Read 2-3 existing test files to learn repo patterns (or confirmed none exist)
- [ ] **Generated tests for ALL untested files** — Count: generated X of Y testable files (must be ≥80%). "Testable" includes cmd/ scripts, data-access collections, complex services, thin wrappers.
- [ ] **Test density met for EVERY new spec** — Each spec file meets the minimum test count from `test-density-rules.md`. Run the density verification gate. No spec has fewer than 5 tests. Service specs have ≥8-15 depending on file size.
- [ ] **Tested largest files FIRST (RULE 8)** — ALL files >200 lines have tests. The top 20% by line count are ALL covered. No large orchestrator was skipped.
- [ ] **Main methods actually invoked (RULE 8 enforcement)** — For every file >300 lines, the top 5 public methods appear as CALL SITES in the test file. Not just helpers — the main orchestration methods. Ran the 3g checkpoint and it passed.
- [ ] **Used partial mocks for orchestration functions (RULE 9)** — Any function coordinating multiple services uses real stateful dependencies (caches, context), not full mocks. Downstream mocks CONSUME cached inputs (not reconstruct from raw params).
- [ ] **Parameter sensitivity tests (RULE 10)** — For methods with ≥3 parameters, verified that varying each input independently changes the output. Assertions check output derived from CACHED intermediates. Any parameter that doesn't affect output is either dead code or a bug.
- [ ] **Loop boundary tests (RULE 11)** — Every method with a for/while loop over input is tested with 0, 1, and >1 items. Multi-item test asserts each iteration's output is independent.
- [ ] **Deepened existing specs** — Identified existing test files with low branch coverage and added missing branch/error/edge-case tests to them. This is how you close the gap from 50% to 70%.
- [ ] **No junk tests (RULE 14)** — Audited generated tests. ZERO test files that only assert constants, config shapes, abstract class throws, or module loading. Every test file exercises real runtime logic. Deleted any that failed the "would a bug in production cause this test to fail?" check.
- [ ] **Tests pass** — Ran the test suite and all generated tests pass
- [ ] **Assertion quality scrutiny (RULE 14)** — Ran the scrutiny pass on ALL generated test files. No file has more weak assertions than strong ones. Flagged files were rewritten or deleted.
- [ ] **Zero source-reading tests (RULE 21)** — Ran the RULE 21 enforcement gate. ZERO test files contain `fs.readFileSync`, `inspect.getsource()`, `Path.read_text()`, or any pattern that reads source code as text. Every test imports and calls the code at runtime.
- [ ] **All tests have 4 required elements (RULE 22)** — Every `it()`/`test()` block contains: IMPORT of code under test, INSTANTIATE (object creation or app bootstrap), CALL (method invocation with inputs), ASSERT ON OUTPUT (check return value or side effect). No test block contains only existence checks (`toBeDefined`) or type checks (`typeof`) without a runtime call.
- [ ] **Mutation-resistant (spot check)** — For at least 3 tests per file, mentally introduce the bug the test claims to catch. Would the test fail? If not, the test is fake. Rewrite it.
- [ ] **Ran after-assessment** — Used code-quality-assessment SKILL.md with `--quick --compare` (NOT jest --coverage)
- [ ] **Reported mutation score only if real tool was run** — No fake numbers, no estimates

**If any box is unchecked, you are NOT done. Go back and complete the missing step.**

---

## What This Skill Does

1. **Asks scope** — Full repo or PR changes only? (HARD GATE — waits for answer)
2. **Understands the domain** — Reads README/CLAUDE.md, writes domain invariants that define correctness
3. **Runs baseline assessment** — Via code-quality-assessment SKILL.md (real coverage, real static analysis)
4. **Adapts to existing patterns** — If repo has quality tests, follow their conventions; don't impose new ones
5. **Generates tests with invariant analysis** — For EACH file: analyze invariants, identify bugs, THEN write tests asserting correct behavior
6. **Hunts for bugs** — Security/negative tests, suspicious pattern identification, assertion-direction verification
7. **Runs tests** — Passing tests = confirmed correct behavior. FAILING tests = confirmed bugs (do NOT weaken assertions)
8. **Deepens existing specs** — Invariant-driven deepening of files with low branch coverage
9. **Runs after-assessment** — Via code-quality-assessment SKILL.md to measure improvement
10. **Reports bugs found** — Summary with file:line references, invariant coverage map, security test count

**CRITICAL:** This skill WRITES TEST FILES AND FINDS BUGS. If you only generate coverage tests with no bug analysis, YOU FAILED. If you only analyze without writing tests, YOU ALSO FAILED. BOTH.

## How to Invoke code-quality-assessment

**Step 1: Find the skill file (dynamic — works on any machine):**
```bash
CQA_SKILL=$(find ~/.claude/plugins -name "SKILL.md" -path "*/code-quality-assessment/*" 2>/dev/null | head -1)
if [ -z "$CQA_SKILL" ]; then
  echo "❌ code-quality-assessment skill not found."
  echo "   Install the plugin first:"
  echo "   /plugin marketplace add https://github.com/icanbwell/bwell-ai-plugin-marketplace"
  echo "   /plugin install software-developers"
  echo ""
  echo "   Then re-run this skill."
  exit 1
fi
echo "✅ Found: $CQA_SKILL"
```

**Step 2: Read the skill file and execute it inline:**
Use the Read tool on `$CQA_SKILL` (the path found above) and follow its instructions step by step.

Do NOT use `Agent()` for invoking other skills — agents lose access to tools needed for nested skill execution. Read the file and execute it inline in the same context.

**Note on Agent() for test generation batching:** Using Agent() to parallelize test file writing is ALLOWED — agents can read source files and write test files fine. But you MUST verify after all agents return that every assigned file got its test. Agents may silently fail or skip files.

## Reference Documentation

**Read these FIRST before starting:**
- Developer Guide: https://icanbwell.atlassian.net/wiki/spaces/ENTARCH/pages/6522437665
- Python Reference: https://github.com/icanbwell/hackathon-test-pyramid
- Hackathon Results: Internal analysis of 13 services (TypeScript, Python, Java patterns proven at scale)

**Core principles from hackathon:**
1. **Meaningful assertions** — Check specific field values, not just `toBeDefined()` / `not None`
2. **Error path coverage** — Test failure cases (404s, exceptions, invalid input)
3. **Framework patterns** — FakeRepo (Python), mocked dependencies (TypeScript), Mockito (Java)
4. **Integrate, don't migrate** — Keep existing test structures that work
5. **Quality > quantity** — 5 good tests > 50 weak tests

## Arguments

User provided: $ARGUMENTS

| Flag | Meaning |
|------|---------|
| `--full-repo` | Test entire repository (all untested files) |
| `--pr-scoped` | Test only files changed in current branch (default on feature branches) |
| `--with-mutation` | After generating tests, run real mutation testing (Stryker/mutmut/PIT) |
| `--mutation-only` | Skip test generation, run mutation testing on existing tests only |
| `--find-bugs` | Bug-finding mode: Analyze code for bugs, write tests asserting CORRECT behavior. Tests FAIL until bugs are fixed. |
| `--incident <ID>` | Ingest a specific incident, extract the root cause pattern, sweep codebase for all sibling bugs, write tests for each. |
| `path` | Specific file or directory to test |

**Mode auto-detection:**
- Feature branch with changes → `--pr-scoped`
- Main/master branch or explicit flag → `--full-repo`
- User says "find bugs", "hunt for bugs", "what's broken" → `--find-bugs`

**Correct-behavior assertions are the DEFAULT for ALL modes.** Every test generated by this skill asserts what the code SHOULD do. If the code is buggy on a given path, the test covering that path FAILS — revealing the bug through completeness of coverage. You do not need to pass `--find-bugs` explicitly; asserting correct behavior is always active. There is no mode where you write tests that assert buggy behavior as correct. The `--find-bugs` flag exists for emphasis in documentation only.

**Complete coverage requires FIRST-PRINCIPLES ANALYSIS, not just pattern matching.** The `patterns/` directory catches known bug classes from past incidents. But the real value of complete coverage is that it finds defects no pattern file covers — because every reachable path is exercised with correct-behavior assertions. For every file you test, you must perform deep invariant analysis to determine what correct behavior looks like on every path:

**For EACH file, before writing tests, answer these questions (using repo context from Step 0c):**

1. **What is this file's contract?** What does it promise to its callers? What postconditions must ALWAYS hold regardless of input? A function that "returns patient data" has an implicit contract that it returns data belonging to the REQUESTING tenant only. Test that contract, not just "does it return something."

2. **What are the trust boundaries?** Where does this code receive input from outside its trust domain? Every trust boundary is a place where assumptions can be violated. If a function receives a `tenantId` from a request header, what happens if that header is spoofed, missing, or contains a different tenant's ID? If it receives data from a cache, what happens if the cache is stale or poisoned?

3. **What implicit assumptions does this code make?** Read every parameter, every property access, every conditional. What does the code ASSUME will be true that isn't enforced? If it does `patient.meta.security.find(...)` — it assumes `patient`, `meta`, and `security` are all non-null. If it uses `requestId` as a cache key — it assumes requestId is unique per logical operation. These assumptions are where bugs live.

4. **What happens at composition boundaries?** When this code calls another function or receives a callback result, what happens if the OTHER code behaves unexpectedly? Not crashes — that's obvious. What if it returns subtly wrong data? What if it returns data from the wrong tenant? What if it returns cached data from a previous call? Test the seams, not just the happy path.

5. **What are the state transitions?** If this code modifies state (database, cache, in-memory), what happens if it's interrupted mid-operation? What happens if it runs concurrently with itself? What if step 2 of 3 fails — does step 1's state get rolled back?

6. **What would a correct implementation look like, and does this code match?** Based on the repo's README, architecture docs, and domain knowledge — what SHOULD this code do? Now read what it ACTUALLY does. Any gap between "should" and "does" is a bug. Write a test asserting "should" behavior — if the test fails, you found a bug.

**The goal is COMPLETE PATH COVERAGE with correct-behavior assertions on every path.** When every reachable branch is covered and every assertion states what the code SHOULD do, then if a bug exists on any path, the test covering that path WILL fail. Coverage is not a vanity metric — it is the mechanism that ensures no defect hides in an untested branch. But coverage with weak assertions (toBeDefined, toBeTruthy) is worthless. Every assertion must state the SPECIFIC correct output for that path.

**After invariant analysis, THEN also sweep against `patterns/` directory for known bug classes.** The pattern sweep catches structural bugs you might miss in manual analysis. Both are required — neither alone is sufficient.

---

## WORKFLOW

### Step 0: Scope Selection (MANDATORY — HARD GATE — SEE RULE 6)

**If no explicit scope flag was passed in the user's command, display this EXACTLY (no rewording, no additional text, no sentence-form questions — this exact format):**

```
Select scope:

  [a] PR changes only (faster, focused on your branch)
  [b] Entire repository (comprehensive, all untested files)

Reply with a or b.
```

**THIS IS A MULTIPLE-CHOICE QUESTION. Display it as shown above — bracketed options, one per line, with "Reply with a or b." at the end. Do NOT rephrase this as a conversational sentence. Do NOT ask "would you like me to..." or "should I test...". The user picks a letter. That's it.**

**THIS IS A HARD STOP. YOUR NEXT ACTION MUST BE: END YOUR RESPONSE AND WAIT.**

Do NOT:
- Read source files "while waiting"
- "Get started on detection" in the meantime
- Launch background agents
- Run any bash commands
- Begin Step 0b, 0c, 0d, or Step 1
- Do ANYTHING except display the question above and stop

**Mapping answers to mode:**
- a → `MODE="pr-scoped"`
- b → `MODE="full-repo"`

**Mutation testing is OFF by default.** It only runs if the user explicitly passes `--with-mutation` or `--mutation-only`. Do NOT ask about it. The bug-sweep (pattern matching against known bug classes) runs automatically on every full-repo execution regardless — it is NOT mutation testing and does NOT require a flag.

**SELF-CHECK:** Before proceeding past this point, verify: "Did I receive a message from the user answering the scope question?" If NO → you are violating Rule 6. Stop immediately.

**The only exceptions where you may skip the question (SCOPE INFERENCE BYPASS — see RULE 6):**
1. User explicitly passed `--full-repo` or `--pr-scoped` in their command
2. User's intent is UNAMBIGUOUS from their message or prior conversation context. Examples that qualify:
   - "run it against the full repo" → full-repo
   - "test the whole thing" → full-repo
   - "test my PR changes" → pr-scoped
   - "write unit tests for this repo" → full-repo
   - "execute against the whole codebase" → full-repo
   - "run unit-test-master on this" + on main branch with no PR → full-repo
   - User previously said "full repo" in this conversation and re-invoked → full-repo
   - "just go" / "execute" when context makes scope obvious → infer from context
   
   Examples that do NOT qualify (still ask):
   - "run the skill" → unclear scope (no prior context)
   - "test my code" → unclear scope
   - "add tests" → unclear scope

**When bypassing, state what you inferred:** "Scope: full-repo (inferred from: [reason]). Proceeding..."

### COMPACTION SURVIVAL: Write Execution Rules to Disk (FIRST ACTION AFTER SCOPE)

**Context compaction WILL happen during long executions. When it does, you lose the skill instructions and revert to generic behavior. This step prevents that by writing the critical rules to a local file you can re-read.**

**IMMEDIATELY after scope is confirmed, write this file:**

```bash
cat > .qa/execution-rules.md << 'RULES'
# Unit Test Master — Execution Rules (re-read this if you lost context)

## Non-Negotiable Rules
1. NO AGENTS. Write all tests yourself sequentially. Agent is not in allowed-tools.
2. NO hand-writing .qa/quality-assessment.json. Use the code-quality-assessment SKILL.md.
3. NO running jest --coverage yourself as a substitute for the CQA skill.
4. Before EACH test file, state: FILE, INVARIANTS, SUSPICIOUS PATTERNS, BUG HYPOTHESIS.
5. .qa/domain-invariants.md MUST have "## Suspicious Patterns" with ≥5 items before any test writing.
6. Test the LARGEST files FIRST. Main methods FIRST. Not helpers.
7. BREADTH AND DEPTH — BOTH REQUIRED. Create specs for ALL untested files AND meet minimum test density per file. Never sacrifice one for the other.
8. Every test must answer: "If this code had a bug, would this test FAIL?"
9. Bug count must be >0. If you found zero bugs, you weren't looking.
10. Do NOT stop after "a batch." Continue until the self-audit loop returns zero gaps.
11. UNTESTED files with error-suppression patterns (catch → return undefined) are HIGHER priority than deepening already-well-tested files. Never add test #31 to a file while a 0-test file with catch blocks exists.
12. Use the SEVERITY RUBRIC exactly: CRITICAL (crashes/data loss/no retry), HIGH (silent failure/ops blind), MEDIUM (edge-case crash), LOW (dead code/unreachable).
13. Write .qa/bugs-found.md with the standardized format (table + detailed descriptions). Ordered CRITICAL→HIGH→MEDIUM→LOW.

## Step Dependencies
- Step 0b PRODUCES .qa/quality-assessment.json (via CQA skill, not hand-written)
- Step 0c PRODUCES .qa/domain-invariants.md (with BOTH invariants AND suspicious patterns)
- Step 3 REQUIRES reading .qa/domain-invariants.md FIRST. If suspicious patterns section is missing, STOP.
- Step 5 PRODUCES updated .qa/quality-assessment.json (via CQA skill again)

## If You Lost Context
If you're reading this after a context compaction and don't remember the full skill:
1. Re-read the unit-test-master SKILL.md from the source (PR #149 or installed plugin)
2. Check what step you're on by looking at which artifacts exist on disk
3. Resume from the next incomplete step — do NOT restart from scratch
4. Do NOT proceed without the skill in context — re-read it first
RULES
echo "✅ Execution rules written to .qa/execution-rules.md (survives context compaction)"
```

**After EVERY context compaction event (you will know because prior messages become summarized), your FIRST action must be: `Read .qa/execution-rules.md`**. This file is your lifeline. It tells you what you must NOT do. Re-read it, then continue from where you left off.

---

### MANDATORY TASK PLAN (create these EXACT tasks after scope is confirmed)

**After the user answers the scope question (or scope is inferred via bypass), create tasks matching this structure EXACTLY. Do NOT simplify, combine, or reorder. Bug-hunting is a FIRST-CLASS task, not a sub-task.**

1. Run baseline assessment (code-quality-assessment skill)
2. Understand repository + write domain invariants to `.qa/domain-invariants.md`
3. **Write suspicious patterns checklist** (minimum 5 patterns — see Step 0c-3 below)
4. Check existing test conventions + detect language/framework
5. Check for prior experiment results (see Step 0c-4 below)
6. Identify all source files needing tests + sort by RISK PRIORITY (services first, utilities last)
7. **Generate tests with per-file invariant analysis** (Step 3a-2 for EVERY file — not optional)
8. **Bug-hunt: security/negative tests + suspicious pattern identification** (Steps 3a-3, 3g-2)
9. Run tests, fix failures
10. Deepen existing specs (invariant-driven — verify ALL new specs meet minimum density from test-density-rules.md)
11. Self-audit loop (zero gaps)
12. Pattern sweep + assertion scrutiny
13. **Proof of Bug Hunting gate** (produce suspicious patterns list, bugs found, invariant coverage, security test count)
14. Run after-assessment + produce summary with BUGS FOUND section

**Tasks 3, 7, 8, and 13 are the ones models skip. If your task plan does not include invariant analysis and pattern sweeps as visible, separate tasks — you have already failed. The POINT of this skill is complete, robust test coverage where every assertion states correct behavior. Bugs surface naturally from that completeness. Task 3 exists because the patterns checklist DRIVES what correct behavior looks like on each path — without it, you are writing assertions that mirror current behavior (which may be broken) instead of asserting correct behavior.**

---

### Step 0b: Run Baseline Assessment (MANDATORY — DO NOT SKIP)

<step_dependency>
REQUIRED INPUT: Scope decision from Step 0 (full-repo or pr-scoped)
PRODUCES: .qa/quality-assessment.json
HOW: By reading and executing the code-quality-assessment SKILL.md — NOT by running jest --coverage yourself.
NEVER write this file by hand. NEVER use python3/jq/cat to create it. The CQA skill produces it.
</step_dependency>

**ANTI-PATTERNS (things fresh sessions got wrong):**
- ❌ "Starting Steps 0b and 0d in parallel" then only doing 0d — NO. Both must COMPLETE.
- ❌ Running `npx jest --coverage` or `npm run test:cov` yourself as a substitute — NO. That is NOT the assessment.
- ❌ Skipping to test generation because "the repo already has significant coverage" — NO.
- ❌ Saying "No .qa directory exists, moving on" — NO. CREATE IT by running the assessment.
- ❌ Running coverage commands yourself, then hand-writing a JSON file with `cat > .qa/quality-assessment.json` — NO. The code-quality-assessment skill has a grading algorithm that produces the file.
- ❌ Reading coverage numbers from jest output and calling that "the baseline" — NO. The baseline is the FULL quality assessment (grade + gates + deployment readiness + all metrics), not just coverage percentages.

**Decision logic:**
- **Full-repo mode:** Always run baseline. No exceptions. Even if `.qa/quality-assessment.json` already exists. Delete it and regenerate.
- **PR-scoped mode + .qa/quality-assessment.json exists AND is less than 7 days old:** Skip baseline (use existing metrics).
- **PR-scoped mode + no existing assessment OR stale assessment:** Run baseline.

**To run baseline, you MUST do ALL of these (not some, ALL):**
1. Find the code-quality-assessment skill using the dynamic path resolution from "How to Invoke code-quality-assessment" section above
2. Read it with the Read tool and execute its Step 1 through Step 9 instructions inline in this same context with `--quick --save` arguments
3. After execution, verify that `.qa/quality-assessment.json` was written to disk

**"Read and execute" means: call Read(path), then follow those instructions step by step, running each bash block. It does NOT mean "I'll do something similar myself."**

**VALIDATION:** After this step, run:
```bash
if [ ! -f ".qa/quality-assessment.json" ]; then
  echo "❌ BASELINE FAILED: .qa/quality-assessment.json does not exist"
  echo "   You MUST fix this before proceeding to test generation."
  exit 1
fi

BASELINE_GRADE=$(jq -r '.grade' .qa/quality-assessment.json)
BASELINE_COVERAGE=$(jq -r '.coverage.branches' .qa/quality-assessment.json)

echo ""
echo "📊 Baseline: Grade $BASELINE_GRADE | Branch Coverage ${BASELINE_COVERAGE}%"
echo ""
```

---

### Step 0c: Understand the Repository (MANDATORY — DO NOT SKIP)

<step_dependency>
REQUIRED INPUT: .qa/quality-assessment.json from Step 0b (proves baseline was run)
PRODUCES: .qa/domain-invariants.md with TWO sections:
  1. "## Core Invariants" (or similar) — ≥5 numbered domain truths
  2. "## Suspicious Patterns" — ≥5 numbered specific code smells with file:method references
Both sections are REQUIRED. Step 3 will READ this file and FAIL if either is missing.
</step_dependency>

**Before writing a single test, you MUST understand what this repo does.** Without this context you are writing tests blind — you won't catch domain-specific bugs, you'll miss security boundaries, and your assertions will be generic garbage.

**Read ALL of the following that exist (use the Read tool):**

```bash
echo "📖 Reading repository context..."

# Context files — read ALL that exist
CONTEXT_FILES=""
for f in README.md CLAUDE.md AGENTS.md docs/ARCHITECTURE.md docs/README.md \
         .github/CONTRIBUTING.md copilot-instructions.md ADR.md adrs/README.md; do
  if [ -f "$f" ]; then
    echo "   Found: $f"
    CONTEXT_FILES="$CONTEXT_FILES $f"
  fi
done

# Also check for architecture decision records
ADR_COUNT=$(find . -path "*/adrs/*.md" -o -path "*/adr/*.md" 2>/dev/null | grep -v node_modules | wc -l)
if [ "$ADR_COUNT" -gt 0 ]; then
  echo "   Found $ADR_COUNT ADRs in adrs/ directory"
fi

# Check package.json or pyproject.toml for project description
if [ -f "package.json" ]; then
  DESC=$(jq -r '.description // empty' package.json 2>/dev/null)
  [ -n "$DESC" ] && echo "   Project: $DESC"
fi

echo ""
```

**After reading context files, you MUST be able to answer:**
1. What does this service/repo do? (its domain purpose)
2. What are its external boundaries? (APIs it exposes, services it calls, databases it uses)
3. What security concerns apply? (auth, tenant isolation, PHI, access control)
4. What are the critical paths where bugs would cause the most damage?

**Then OUTPUT a domain invariants list.** Before moving to the next step, write out the critical invariants that MUST be verified by tests. These are domain-specific truths that, if violated, would constitute a bug. Examples for a consent service:

```
DOMAIN INVARIANTS (derived from repo context):
1. Patient A cannot read/modify Patient B's consent records
2. Consent creation MUST publish an event — if event fails, consent must not be persisted
3. Expired/rejected consents must not grant data access
4. Consent status transitions are constrained (draft→active→rejected, no arbitrary jumps)
5. QuestionnaireResponse submission must create consent atomically — partial state is a bug
6. JWT patient ID must match the consent's patient — mismatch = authorization bypass
7. All FHIR operations must pass the caller's token — missing token = privilege escalation
```

**These invariants drive test generation.** Every test you write in Step 3 must verify at least one invariant from this list. If a test doesn't map to an invariant, it's mechanical coverage — not a real test. The invariants tell you what MATTERS about correctness in this specific domain.

**ENFORCEMENT — HARD GATE:**

You MUST save the invariant list to disk. This is not optional. Subsequent steps reference this file.

```bash
# Write your invariant list to .qa/domain-invariants.md
# The file MUST exist before you proceed. Step 3 will reference it.
if [ ! -f ".qa/domain-invariants.md" ]; then
  echo "❌ GATE FAILED: .qa/domain-invariants.md does not exist."
  echo "   You MUST write your domain invariants list before proceeding."
  echo "   Use the Write tool to create .qa/domain-invariants.md with your numbered invariant list."
  exit 1
fi

INVARIANT_COUNT=$(grep -c "^[0-9]" .qa/domain-invariants.md 2>/dev/null || echo 0)
if [ "$INVARIANT_COUNT" -lt 3 ]; then
  echo "❌ GATE FAILED: .qa/domain-invariants.md has fewer than 3 invariants."
  echo "   You clearly didn't think hard enough. Read the repo context again."
  echo "   A real service has at MINIMUM 5-10 domain invariants."
  exit 1
fi

echo "✅ Domain invariants: $INVARIANT_COUNT items in .qa/domain-invariants.md"
```

**If this gate fails, DO NOT PROCEED. Write the invariants file first.**

---

### Step 0c-3: Write Suspicious Patterns Checklist (MANDATORY — HARD GATE)

**After writing domain invariants, you MUST produce a NUMBERED CHECKLIST of at least 5 suspicious patterns BEFORE writing any tests.** This checklist is what transforms generic coverage into targeted bug-hunting. Without it, you will default to mechanical test generation.

A "suspicious pattern" is a specific code construct in THIS repo that looks like it could violate an invariant, exhibit undefined behavior in edge cases, or silently fail. These are NOT generic programming concerns — they are specific observations about specific code in specific files.

**How to produce the checklist:**

1. Scan the source files (especially services, consumers, event publishers) looking for:
   - **Fire-and-forget calls**: `forEach` with async callback, `.then()` without await, promises not stored/awaited
   - **Missing error propagation**: `try/catch` that swallows errors (logs but doesn't rethrow in contexts where the caller needs to know)
   - **In-place mutation**: Functions that modify their input arguments instead of returning new objects
   - **Null/undefined assumption chains**: `a.b.c.d` without guards on intermediate values
   - **Inconsistent error handling**: Some methods rethrow, others swallow — which is intentional?
   - **State leakage between calls**: Shared mutable state (class properties, module-level variables) that persist across invocations
   - **Missing await**: async functions called without await (compiles fine, appears to work in happy path, loses errors)
   - **Race conditions in queue processing**: Job handlers that don't await all their work before completing

2. For each suspicious pattern, record:
   - The file and approximate location
   - What the pattern IS (concretely)
   - What could go WRONG (the failure mode)
   - What test would PROVE the issue exists

**OUTPUT FORMAT — write this to `.qa/domain-invariants.md` as a second section:**

```markdown
## Suspicious Patterns (drives test writing)

1. [file.ts:methodName] — Fire-and-forget: `this.service.doThing()` called without await inside forEach
   - Failure mode: errors silently lost, caller thinks operation succeeded
   - Test: Use never-resolving promise; if method returns before promise resolves, await is missing

2. [file.ts:methodName] — In-place mutation: `mapCategory()` modifies input.category[0].coding[0].code directly
   - Failure mode: caller's original data is corrupted after the call
   - Test: Snapshot input before call, compare after — any difference proves mutation

3. [file.ts:methodName] — Null crash: `bundle.entry.map(...)` with no guard on bundle.entry
   - Failure mode: TypeError crash when FHIR server returns bundle with no entries
   - Test: Pass bundle without entry field, expect either graceful handling or documented throw

4. [file.ts:methodName] — Error swallowing: catch block logs but doesn't rethrow
   - Failure mode: caller continues as if operation succeeded; data inconsistency
   - Test: Mock dependency to reject, verify caller receives the error (or document intentional swallowing)

5. [file.ts:methodName] — Inconsistent error contract: publishConsentCreatedEvent rethrows but publishUserConsentCreation swallows
   - Failure mode: caller cannot rely on consistent error behavior from the service
   - Test: Both scenarios — prove which rethrows and which swallows, document the contract
```

**GATE:**
```bash
# Verify suspicious patterns checklist exists in domain-invariants.md
SUSPICIOUS_COUNT=$(grep -c "^\s*[0-9]\+\." .qa/domain-invariants.md 2>/dev/null | tail -1)
PATTERNS_SECTION=$(grep -c "Suspicious Patterns" .qa/domain-invariants.md 2>/dev/null || echo 0)

if [ "$PATTERNS_SECTION" -lt 1 ]; then
  echo "❌ GATE FAILED: .qa/domain-invariants.md has no 'Suspicious Patterns' section."
  echo "   You MUST write at least 5 suspicious patterns before writing any tests."
  echo "   These patterns DRIVE your test writing — without them you're writing blind."
  exit 1
fi

echo "✅ Suspicious patterns checklist present in .qa/domain-invariants.md"
```

**Why this exists:** In Experiment 2, the suspicious patterns list was what led directly to finding 7 real bugs. The fire-and-forget pattern in the consumer, the mutation bug in the mapper, the null crash in the output mapper — all were identified in the patterns list FIRST, then tested. Without the list, Experiment 1 wrote more files but found fewer bugs because it jumped straight to mechanical test generation.

**If this gate fails, DO NOT PROCEED. Write the suspicious patterns first.**

---

### Step 0c-4: Check for Prior Experiment Results (RECOMMENDED)

**Before writing tests, check if a prior test-generation run exists on a different branch.** Prior results tell you what was already tested, what bugs were already found, and what approaches worked or didn't.

```bash
echo "🔍 Checking for prior test-generation experiments..."

# Look for branches with test-generation work
PRIOR_BRANCHES=$(git branch -a 2>/dev/null | grep -i "test\|experiment\|unit-test\|qual" | grep -v "$(git branch --show-current)" | head -5)

if [ -n "$PRIOR_BRANCHES" ]; then
  echo "   Found potential prior experiment branches:"
  echo "$PRIOR_BRANCHES" | while read branch; do
    BRANCH_NAME=$(echo "$branch" | sed 's/^[* ]*//' | sed 's/remotes\/origin\///')
    # Check if it has .qa/quality-assessment.json or test files
    HAS_QA=$(git show "$BRANCH_NAME:.qa/quality-assessment.json" 2>/dev/null | head -1)
    if [ -n "$HAS_QA" ]; then
      echo "     ✅ $BRANCH_NAME — has .qa/quality-assessment.json (prior run results)"
    fi
  done
fi

# Also check if .qa/quality-assessment.json exists locally from a prior run
if [ -f ".qa/quality-assessment.json" ]; then
  PRIOR_GRADE=$(jq -r '.grade // "unknown"' .qa/quality-assessment.json 2>/dev/null)
  PRIOR_BUGS=$(jq -r '.bugs_found // 0' .qa/quality-assessment.json 2>/dev/null)
  echo "   📊 Local prior results: Grade=$PRIOR_GRADE, Bugs=$PRIOR_BUGS"
fi

echo ""
```

**If prior results exist:**
1. Read the prior `.qa/quality-assessment.json` to understand what coverage was achieved
2. Read the prior `.qa/domain-invariants.md` to see what invariants were identified
3. Check what test files were created (diff the branch against main)
4. Use this as a STARTING POINT — don't redo work that was already done correctly, but DO go deeper where the prior run was shallow

**The value of prior results:** Knowing what the last run found (or missed) tells you where to focus. If the prior run created 15 spec files but found 0 bugs, that's a signal that those specs need DEEPENING, not that the files are "done." If the prior run found 3 bugs in `consent.consumer.ts`, that file probably has more bugs worth looking for.

**If no prior results exist, proceed normally.** This step is informational, not a gate.

---

### Step 0c-2: Repo Detection & Specialized Conventions

**Check if this is a repo with highly specialized test conventions:**
```bash
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
SPECIALIZED_REPO="false"

# FHIR Server: custom matchers, fixture-based expected responses, resource-specific test patterns
if echo "$REMOTE_URL" | grep -qE "icanbwell/fhir-server(\.git)?$"; then
  echo "🔍 Detected FHIR Server repository."
  echo "   This repo has specialized test conventions — will adapt to its patterns."
  echo ""
  SPECIALIZED_REPO="fhir-server"
fi
```

**If `SPECIALIZED_REPO` is set, Step 0d MUST read 5+ existing test files (not just 2-3) to fully capture the repo's conventions. Do NOT use the generic templates from this skill — match what the repo already does exactly.**

---

### Step 0d: Check Existing Test Conventions (MANDATORY)

**Before generating ANY tests, analyze the repo's existing test patterns to decide your approach:**

```bash
echo "🔍 Analyzing existing test conventions..."

# Find existing test files
EXISTING_TESTS=$(find . -name "*.spec.ts" -o -name "*.test.ts" -o -name "test_*.py" -o -name "*Test.java" 2>/dev/null | grep -v node_modules | grep -v .git)
EXISTING_TEST_COUNT=$(echo "$EXISTING_TESTS" | grep -v "^$" | wc -l)

echo "   Existing test files: $EXISTING_TEST_COUNT"

if [ $EXISTING_TEST_COUNT -gt 5 ]; then
  echo "   ✅ Repo has significant test coverage"
  echo "   → STRATEGY: Follow existing patterns (integrate, don't migrate)"
  STRATEGY="follow-existing"
  
  # Determine how many samples to read
  if [ "$SPECIALIZED_REPO" != "false" ]; then
    SAMPLE_COUNT=5
    echo "   📐 Specialized repo detected — reading $SAMPLE_COUNT test files + infrastructure"
  else
    SAMPLE_COUNT=3
  fi
  
  # Read sample test files to learn their patterns
  echo "   Reading existing tests to learn conventions..."
  SAMPLE_TESTS=$(echo "$EXISTING_TESTS" | head -$SAMPLE_COUNT)
  # AI: Use Read tool on these files to understand:
  # - Import style (relative vs absolute)
  # - Test structure (describe/it vs test() vs @Test)
  # - Assertion library (Jest matchers, AssertJ, plain JUnit)
  # - Mock approach (jest.mock, @Mock, FakeRepo)
  # - Comment style (// GIVEN // WHEN // THEN vs Arrange-Act-Assert)
  # - File location (co-located in src/ vs separate tests/ dir)
  # - Custom matchers or test utilities (especially for specialized repos)
  # - Fixture loading patterns (JSON files, factory functions)
  
  # For specialized repos, also read test infrastructure
  if [ "$SPECIALIZED_REPO" != "false" ]; then
    echo "   Reading test infrastructure files..."
    INFRA_FILES=$(find . -path "*/test*helper*" -o -path "*/test*util*" -o -path "*/__mocks__/*" -o -path "*/fixtures/*" 2>/dev/null | grep -v node_modules | head -5)
  fi
else
  echo "   ⚠️  Minimal test coverage"
  echo "   → STRATEGY: Use b.well standard patterns from this skill"
  STRATEGY="use-standards"
fi

echo ""
```

**CRITICAL:** If `STRATEGY="follow-existing"`, you MUST read those test files using the Read tool before generating any new tests. Match their exact style. Do NOT impose standard patterns on a repo that already has working, quality tests with a different style.

---

### Step 1: Quick Detection & Setup

```bash
echo "🔍 Detecting repository configuration..."

REPO_NAME=$(basename $(pwd))

# Language detection
if [ -f "package.json" ]; then
  LANGUAGE="TypeScript"
  if grep -q '"jest"' package.json 2>/dev/null || [ -f "jest.config.ts" ] || [ -f "jest.config.js" ]; then
    TEST_FRAMEWORK="Jest"
    TEST_CMD="npx jest"
    COV_CMD="npx jest --coverage"
  elif grep -q '"vitest"' package.json 2>/dev/null; then
    TEST_FRAMEWORK="Vitest"
    TEST_CMD="npx vitest run"
    COV_CMD="npx vitest run --coverage"
  fi
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
  LANGUAGE="Python"
  TEST_FRAMEWORK="pytest"
  TEST_CMD="pytest"
  COV_CMD="pytest --cov=src --cov-report=json --cov-branch -q"
elif [ -f "build.gradle" ] || [ -f "pom.xml" ]; then
  LANGUAGE="Java"
  TEST_FRAMEWORK="JUnit"
  TEST_CMD="./gradlew test"
  COV_CMD="./gradlew test jacocoTestReport"
else
  echo "❌ Cannot determine language. No entry point found."
  exit 1
fi

echo "   Language: $LANGUAGE"
echo "   Framework: $TEST_FRAMEWORK"
echo ""
```

---

### Step 2: Identify Source Files to Test

```bash
echo "📂 Identifying files to test..."

if [ "$MODE" = "pr-scoped" ]; then
  # Changed files only — respect the existing repo
  BASE_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' || echo "main")
  CHANGED_FILES=$(git diff --name-only origin/$BASE_BRANCH...HEAD 2>/dev/null || git diff --name-only HEAD~5...HEAD)
  
  # Filter to source files (not test files)
  if [ "$LANGUAGE" = "TypeScript" ]; then
    FILES_TO_TEST=$(echo "$CHANGED_FILES" | grep "\.ts$" | grep -v "\.spec\.\|\.test\.\|\.d\.ts$\|\.module\.ts$")
  elif [ "$LANGUAGE" = "Python" ]; then
    FILES_TO_TEST=$(echo "$CHANGED_FILES" | grep "\.py$" | grep -v "test_\|__init__\.py\|conftest\.py")
  elif [ "$LANGUAGE" = "Java" ]; then
    FILES_TO_TEST=$(echo "$CHANGED_FILES" | grep "\.java$" | grep -v "Test\.java$")
  fi
  
  # Also identify test files that were changed in the PR (these may need updating)
  if [ "$LANGUAGE" = "TypeScript" ]; then
    CHANGED_TESTS=$(echo "$CHANGED_FILES" | grep -E "\.(spec|test)\.ts$")
  elif [ "$LANGUAGE" = "Python" ]; then
    CHANGED_TESTS=$(echo "$CHANGED_FILES" | grep "test_.*\.py$")
  elif [ "$LANGUAGE" = "Java" ]; then
    CHANGED_TESTS=$(echo "$CHANGED_FILES" | grep "Test\.java$")
  fi

elif [ "$MODE" = "full-repo" ]; then
  # ALL source files without corresponding test files
  if [ "$LANGUAGE" = "TypeScript" ]; then
    FILES_TO_TEST=""
    for f in $(find src -name "*.ts" ! -name "*.spec.ts" ! -name "*.test.ts" ! -name "*.d.ts" ! -name "*.module.ts" -type f 2>/dev/null | grep -v node_modules); do
      SPEC="${f%.ts}.spec.ts"
      [ ! -f "$SPEC" ] && FILES_TO_TEST="$FILES_TO_TEST $f"
    done
  elif [ "$LANGUAGE" = "Python" ]; then
    FILES_TO_TEST=""
    for f in $(find src -name "*.py" ! -name "__init__.py" ! -name "test_*" -type f 2>/dev/null); do
      BASENAME=$(basename "$f" .py)
      find tests -name "test_${BASENAME}.py" 2>/dev/null | grep -q . || FILES_TO_TEST="$FILES_TO_TEST $f"
    done
  elif [ "$LANGUAGE" = "Java" ]; then
    FILES_TO_TEST=""
    for f in $(find src/main/java -name "*.java" -type f 2>/dev/null); do
      BASENAME=$(basename "$f" .java)
      find src/test -name "${BASENAME}Test.java" 2>/dev/null | grep -q . || FILES_TO_TEST="$FILES_TO_TEST $f"
    done
  fi
fi

FILE_COUNT=$(echo "$FILES_TO_TEST" | wc -w)
echo "   Files needing tests: $FILE_COUNT"
echo ""

# RULE 8 ENFORCEMENT: Sort files by line count DESCENDING (largest first)
# The model MUST process files in this order. Largest files tested FIRST.
echo "   Sorting by line count (largest files first — RULE 8)..."
FILES_WITH_SIZE=""
for f in $FILES_TO_TEST; do
  LINES=$(wc -l < "$f" 2>/dev/null || echo 0)
  FILES_WITH_SIZE="$FILES_WITH_SIZE $LINES:$f"
done

# Sort descending by line count, extract file paths
FILES_TO_TEST=$(echo "$FILES_WITH_SIZE" | tr ' ' '\n' | grep -v '^$' | sort -t: -k1 -rn | cut -d: -f2 | tr '\n' ' ')

# Show top 10 largest (these are MANDATORY per RULE 8)
echo "   Top 10 largest files (MANDATORY — may NOT skip):"
echo "$FILES_WITH_SIZE" | tr ' ' '\n' | grep -v '^$' | sort -t: -k1 -rn | head -10 | while read entry; do
  LINES=$(echo "$entry" | cut -d: -f1)
  FILE=$(echo "$entry" | cut -d: -f2)
  echo "     ${LINES} lines: $FILE"
done

TOTAL_COUNT=$(echo "$FILES_TO_TEST" | wc -w)
TOP20_COUNT=$(( TOTAL_COUNT / 5 ))
[ "$TOP20_COUNT" -lt 5 ] && TOP20_COUNT=5
echo ""
echo "   Total files: $TOTAL_COUNT | Top 20% (MANDATORY): $TOP20_COUNT files"
echo "   ⚠️  You MUST test ALL of the top 20% by size. No exceptions. No skipping because 'too complex'."
echo ""
```

### PR-Scoped Mode Philosophy

**PR-scoped mode respects the existing repo.** You are not here to bring the entire codebase to perfection — you are here to ensure the PR's changes have proper test coverage.

**Rules for PR-scoped mode:**
1. **Only create/modify tests for files changed in the PR.** Do not touch unrelated test files.
2. **If a changed source file ALREADY has a spec** — read the existing spec. Only add/update test cases that cover the NEW or CHANGED logic in the PR diff. Do NOT rewrite the spec to match some ideal standard. Leave existing tests alone unless they're now broken by the PR's changes.
3. **If a changed source file has NO spec** — create one, but only test the logic in that file (not every file in the repo).
4. **If existing tests in the repo use a different style than this skill recommends** — match their style. The skill's patterns are defaults, not mandates. Consistency with the existing repo matters more than theoretical best practices.
5. **Do NOT apply Step 4b (deepen existing specs) in PR-scoped mode.** That step is for full-repo mode only. In PR mode, you only deepen specs for files that were changed in the PR.
6. **Quality gates are informational in PR mode** — report them but don't try to fix repo-wide gate failures that predate the PR.

### Full-Repo Mode Rules

**Full-repo mode is comprehensive.** These rules apply ONLY when mode is full-repo:

**Files you MUST test (these are NOT valid skip reasons):**
- `cmd/` scripts — mock the I/O (FHIR client, DB, filesystem, network), test the logic
- Data-access collection classes — mock the DB driver, test query construction and error handling
- Middleware/interceptors — test the request/response transformation logic
- Factory classes — test the creation logic and provider selection
- Files with constructors that do mapping/validation — test the transformation
- Scalars/validators — test parse and serialize methods
- Repository classes — mock the collection/driver, test query construction
- HTTP client wrappers — mock the HTTP layer, test URL construction and error handling

**Files you MUST NOT test (both modes) — generating tests for these is a RULE 14 violation:**
- Pure type definition files (`.d.ts`, interface-only with zero logic)
- Pure re-export barrel files (`export * from './other-file'`)
- `@Module()` decorator-only files (NestJS modules with only imports/providers/exports arrays and zero methods)
- Constants/enum files with ONLY static values (no functions, no computed values)
- Abstract base classes whose only methods throw "Not Implemented" (test the concrete subclasses instead)
- No-op/passthrough middleware (just calls `next()` with no logic)
- Dummy/mock implementations used only in tests (e.g., `dummyKafkaClient`)
- Config shape files that only export static objects with no computed properties
- Files that ONLY contain JSDoc typedefs with no runtime exports

**Files you MAY skip (both modes):**
- Files that already have a corresponding test file (in full-repo mode — they get deepened in Step 4b instead)

**Validation: If full-repo mode and you test fewer than 70% of identified files, you have NOT completed the task. Report exact numbers: "Generated X/Y test files (Z%)".**

**ANTI-PATTERNS (things fresh sessions got wrong — DO NOT DO THESE):**
- ❌ "I'll focus on the 5 highest-value files" — NO. Do ALL files.
- ❌ "Let me prioritize security-critical files" — NO. Do ALL files.
- ❌ Processing 5 files when 261 need tests — FAILURE.
- ❌ "After filtering out pure type definitions, constants, and barrel exports, there are approximately 45 files with testable logic" then only doing 33 — FAILURE. If you identified 45, do 45.
- ❌ "skipping the fhir-client.service.ts (which is a complex infrastructure adapter)" — NO. Complex files need tests MORE, not less.
- ❌ Silently dropping data-access files, entity files, or cmd/ scripts because "they're not service logic" — NO. If they have functions/methods/logic, they get tests.
- ❌ Testing 33 utility files while skipping all operation/service/manager classes — CATASTROPHIC FAILURE. This is the worst possible outcome: you tested the easy stuff and skipped where bugs actually live. RULE 8 exists specifically to prevent this.
- ❌ "The file has 15 dependencies to mock, so I'll skip it" — NO. That's exactly why it needs a test. Scaffold the mocks and test the logic paths.
- ❌ Running for 2 hours and only producing utility tests — FAILURE. If after 30 minutes you haven't started on the largest files, STOP and fix your approach.
- ❌ Testing leaf classes within an operations/ directory but skipping the orchestrator — NOT ENOUGH. If `operations/everything/` has a 1800-line `everythingHelper.js` and you only test `resourceMapper.js` (50 lines), you tested the room's doorknob, not the room. The largest file in any directory gets tested FIRST.
- ❌ Calling a cached method exactly once in a test and asserting the result — USELESS for cache correctness. The single-call case ALWAYS works. Cache bugs only manifest on call 2+ (RULE 10).
- ❌ Testing a loop body with only 1 item in the input array — USELESS for state accumulation bugs. Single-iteration tests always pass because there's no prior iteration to corrupt from (RULE 11).
- ❌ Fully mocking every dependency with `.mockResolvedValue()` on an orchestration test — HIDES INTERACTION BUGS. The mock returns whatever you told it to. It doesn't exhibit real behavior like caching, state mutation, or accumulation. Use partial mocks (RULE 9).
- ❌ Using `fs.readFileSync` / `inspect.getsource()` / `Path.read_text()` to read source files and assert on string patterns — **ABSOLUTE FAILURE. NOT A TEST.** This is a grep command in a test framework. It provides zero regression protection, catches zero runtime bugs, and breaks on innocent refactors. If you wrote even ONE test that reads source text instead of calling code, you failed RULE 21. Delete it and write a behavioral test. The repos that scored 0% useful tests (scheduling-service: 24 source-reading tests, zero behavioral) and 100% useful (consent-service: 46 behavioral tests) prove the difference is not difficulty — it's whether you took the lazy path or did the actual work of instantiating code and calling methods.
- ❌ Writing 30 tests for `getCache()`, `filterResults()`, and `parseArgs()` while never once calling `updateQueryConsideringDataSharing()` — THE MAIN METHOD. This is the most common and most catastrophic failure. You tested the doorknobs and light switches while the house burned down. The 600-line orchestrator is where parameters flow through caches, where state accumulates across iterations, where one sub-component's output feeds another's input. If you wrote tests for a file but the top 3 methods by line count don't appear in your test's call sites, YOU DID NOT TEST THE FILE.
- ❌ Generating test files for `constants/`, `types.js`, `noop.middleware.js`, abstract base classes, or config shape files — RULE 14 VIOLATION. These add ZERO value. They pad test count while providing no bug detection. They make the engineer look incompetent. DELETE THEM IMMEDIATELY if you catch yourself doing this.
- ❌ Testing scenarios that upstream layers prevent (rate limiting in an operation handler when it belongs at API gateway; admin auth when it belongs at the IdP) — WRONG LAYER. Ask "what validation does a request pass through BEFORE reaching this code?" If middleware/gateway/IdP prevents the scenario, don't test it here.
- ❌ Testing features that don't exist yet (placeholder code, no-op loops labeled "Phase N will add this") — tests MUST test REAL code. If the implementation is a no-op, there is nothing to test. Write the test when the code ships.

**If there are >50 files:** Process in batches of 20. After each batch, continue to the next batch. Do NOT stop after the first batch unless the user interrupts.

**RESTRICTION ON PARALLEL AGENTS:** Do NOT dispatch agents to write tests unless you have >30 files. Agents lack the domain context from Step 0c and will write mechanical mock-through garbage. If you MUST use agents (>30 files), you MUST:
- Include the full domain invariants list in each agent's prompt
- Include the repo's CLAUDE.md/README context in each agent's prompt
- Explicitly tell each agent: "Every test must verify a domain invariant, not just achieve coverage"
- After all agents return, verify each batch actually wrote the files it was assigned
- Run the scrutiny pass (Step 4c) with extra skepticism on agent-generated tests

**Time budget:** Test generation (Steps 2-4) should take 20-40 minutes for a typical service. Mutation testing (Step 6) adds 15-60 minutes depending on scope. If you've spent 30 minutes and only produced tests for utility files, you are failing. Stop and redirect to operations/services immediately.

---

### Step 2b: Execution Order (MANDATORY — test high-risk files FIRST)

**You MUST test files in risk-priority order, NOT alphabetically, NOT by discovery order.** The failure mode this prevents: spending all your time/context on utilities and helpers while the main service files (where the real bugs live) never get tested.

**Priority ordering (test in THIS order):**
1. **Main service files** — the orchestrator that coordinates business logic (e.g., `consent.service.ts`, `searchManager.js`, `everythingHelper.js`). These are the largest, most complex files with the most branching. Test them FIRST.
2. **UNTESTED files with error-suppression patterns** — files that have `catch` blocks returning undefined/null/empty, or `try/catch` that logs-and-swallows without rethrowing. These hide infrastructure failures silently. They are MORE dangerous than files that crash loudly because crashes get fixed; silent failures persist indefinitely. Scan for: `catch (error) { ... return undefined }`, `catch (e) { logger.warn(...) }` without rethrow. **This category was added because Experiment 4 found HIGH-severity bugs in these files while Experiment 5 skipped them entirely.**
3. **Middleware/guards/auth** — anything on the request path that gates access. Security bugs live here.
4. **FHIR/API clients** — anything that transforms data crossing service boundaries. Integration bugs live here.
5. **Event publishers/subscribers** — anything that emits or consumes events. Atomicity bugs live here.
6. **Utilities/helpers** — LAST. These are the simplest files with the fewest bugs. Testing them first is busy-work that creates the illusion of progress.

**CRITICAL PRIORITY RULE — Untested files before deepening well-tested ones:**
If a source file has ZERO tests AND contains error-handling code (catch blocks, error returns), it is ALWAYS higher priority than deepening a file that already has 10+ tests. A file with 30 existing tests that's missing one edge case is LOW risk. A file with 0 tests that silently swallows errors is HIGH risk. **Never spend time adding test #31 to a well-tested file while a file with 0 tests and error suppression exists.**

**Detection — find error-suppression files that need tests:**
```bash
echo "🔍 Finding untested files with error-suppression patterns..."
for f in $(find src -name "*.ts" ! -name "*.spec.ts" ! -name "*.test.ts" ! -name "*.d.ts" ! -name "*.module.ts" -type f 2>/dev/null | grep -v node_modules); do
  SPEC="${f%.ts}.spec.ts"
  if [ ! -f "$SPEC" ]; then
    CATCH_COUNT=$(grep -c "catch\s*(" "$f" 2>/dev/null || echo 0)
    RETURN_UNDEF=$(grep -c "return undefined\|return null\|return \[\]\|return {}" "$f" 2>/dev/null || echo 0)
    if [ "$CATCH_COUNT" -gt 0 ] && [ "$RETURN_UNDEF" -gt 0 ]; then
      echo "   ⚠️  HIGH PRIORITY: $f (${CATCH_COUNT} catch blocks, ${RETURN_UNDEF} silent returns) — NO TEST"
    fi
  fi
done
echo ""
```

**HARD GATE — identify and verify the main service file is tested FIRST:**
```bash
# Identify the MAIN service file (largest .service.ts or equivalent)
MAIN_SERVICE=$(find src/ -name "*.service.ts" -o -name "*Manager.js" -o -name "*Helper.js" 2>/dev/null | grep -v node_modules | grep -v spec | grep -v test | xargs wc -l 2>/dev/null | sort -rn | head -1 | awk '{print $2}')
if [ -n "$MAIN_SERVICE" ]; then
  BASENAME=$(basename "$MAIN_SERVICE" | sed 's/\.ts$//' | sed 's/\.js$//')
  MAIN_TEST=$(find . -name "*${BASENAME}*spec*" -o -name "*${BASENAME}*test*" 2>/dev/null | grep -v node_modules | head -1)
  if [ -z "$MAIN_TEST" ]; then
    echo "⚠️  Main service ($MAIN_SERVICE) has NO test. Write it FIRST."
  fi
fi
```

---

### Step 3: Generate Tests (IMMEDIATE ACTION — NO MORE ANALYSIS)

<step_dependency>
REQUIRED INPUT: .qa/domain-invariants.md
ACTION: Read this file NOW with the Read tool. Confirm it contains:
  1. A "## Core Invariants" or similar section with ≥5 numbered items
  2. A "## Suspicious Patterns" section with ≥5 numbered items
If EITHER section is missing or has fewer than 5 items, STOP. Go back to Step 0c-3 and write them.
You CANNOT write good tests without knowing what to test FOR.
</step_dependency>

**NO AGENTS. NO PARALLELISM.** You write each test file yourself in this context. Do NOT use the Agent tool. It is not in your allowed-tools list for this skill. If you find yourself about to dispatch an agent, STOP — you are about to produce garbage tests that will need fixing, which takes longer than just writing them yourself.

**QUALITY FLOOR — every generated test file MUST have:**
- At minimum: 1 test per public method that exercises a REAL code path (not delegation)
- At minimum: 1 negative test per file (invalid input, unauthorized access, missing data — something that SHOULD fail)
- At minimum: 1 security/boundary test per service file (wrong tenant, wrong token, missing auth)
- Assertions that check TRANSFORMED values, not mock return values

**MINIMUM TEST DENSITY (NON-NEGOTIABLE):** Read `test-density-rules.md` in this skill's directory for the full table with per-file-type minimums. The short version:
- Service >200 lines → minimum 15 tests
- Service ≤200 lines → minimum 8 tests  
- Resolver/Controller → minimum 10 tests
- Consumer/Processor → minimum 8 tests
- Client wrapper → minimum 10 tests
- Any other file → minimum 5 tests

A spec file with fewer tests than its minimum is INCOMPLETE. Go back and add more. **A 300-line service file with 3 tests is not tested — it's lightly poked.**

```bash
# Find and read the density rules file
DENSITY_RULES=$(find ~/.claude/plugins -name "test-density-rules.md" -path "*/unit-test-master/*" 2>/dev/null | head -1)
if [ -n "$DENSITY_RULES" ]; then
  echo "📏 Test density rules: $DENSITY_RULES"
fi
```

**For EACH file in FILES_TO_TEST:**

#### 3a: Read Source Code
Use the Read tool to read the ENTIRE source file. Not the first 50 lines. THE WHOLE FILE. Note:
- Class names and constructor dependencies
- Public methods and their signatures
- Import paths and patterns
- Existing patterns (async/await, decorators, etc)
- **Error handling paths** (try/catch, thrown exceptions, error returns)
- **Security checks** (token validation, tenant filtering, permission checks)
- **State mutations** (what gets written, published, or mutated)

#### 3a-2: Invariant Analysis (MANDATORY for EVERY file — DO THIS BEFORE WRITING ANY TEST)

**Read `.qa/domain-invariants.md` (you wrote this in Step 0c).** For this specific file, OUTPUT the following BEFORE writing any test code:

```
FILE: [filename]
INVARIANTS TESTED: [list the invariant NUMBERS from .qa/domain-invariants.md that this file touches]
TRANSFORMATIONS: [what each public method transforms — input→output, what's DIFFERENT]
BUG SCENARIOS: [what subtle bugs could exist in this file specifically]
```

**Rules:**
1. If INVARIANTS TESTED is empty, this file is either trivial (skip it) or you didn't think hard enough (re-read it).
2. If TRANSFORMATIONS shows "passes through unchanged" for a method — DO NOT write a test for that method. A pure delegation with zero logic does not need a test. Write tests for the methods that ADD something (error handling, validation, token injection, URL construction, filtering, transformation).
3. BUG SCENARIOS must be SPECIFIC to this file, not generic. "Might throw" is not a bug scenario. "Token not forwarded to FHIR client, causing anonymous access" IS a bug scenario.

**ANTI-PATTERN: Mock-through tests.** If your test mocks dependency A to return X, calls function B, and asserts the result equals X — you tested NOTHING. The function could be `return dependency.call()` with zero logic and the test still passes. That's not a test, it's a tautology.

**ANTI-PATTERN: "Valid for delegation layer" rationalization.** NO. If a function only delegates, DON'T TEST IT. If it adds error handling, test the ERROR HANDLING (mock a failure, assert the function catches/wraps/logs it). If it adds a token, test that the token is PASSED (mock without token, assert failure). Test the VALUE-ADD, not the delegation itself. The assertion `expect(result).toBe(mockReturnValue)` is NEVER valid — it tests that JavaScript's `return` keyword works.

**If you skip this analysis or produce it with empty INVARIANTS TESTED, you are violating the skill. Stop and redo.**

#### 3a-3: Security/Negative Test Design (MANDATORY for service files, middleware, guards)

For any file that handles requests, auth, data access, or state mutations, you MUST design at least ONE test from each category:

1. **Wrong actor test:** What happens if the request comes from a different patient/tenant/user than expected? Does the code correctly reject it? If it doesn't reject it — THAT'S A BUG. Write the test asserting rejection.

2. **Missing auth test:** What happens if the token/header/credential is missing entirely? Does the code fail-closed (deny) or fail-open (allow)? If it allows — BUG. Write the test.

3. **Boundary violation test:** What happens at the edges? Empty arrays, null values in required fields, maximum-length inputs, zero-value numeric params? Does the code handle them or crash?

4. **State corruption test:** If this code writes/publishes, what happens if the write succeeds but the publish fails? Is there inconsistent state? What if it's called twice with the same input (idempotency)?

**You are not just testing that code works. You are testing that code CANNOT be misused.** Every service file must have at least one test that verifies a malicious or incorrect input is REJECTED. If you write only happy-path tests, you have not tested the file.

#### 3b: CACHE ANALYSIS (mandatory for files with caching — DO THIS BEFORE WRITING ANY TEST)

If the source file contains ANY of: `cache`, `getMap`, `httpContext.get`, `httpContext.set`, `requestSpecificCache`, `memoize`, `_cache`, run this analysis and OUTPUT IT before writing the test:

```
CACHE ANALYSIS for [filename]:
1. Cache mechanism: [exact line, e.g., "this.requestSpecificCache.getMap({ requestId, name: 'dataSharingManager' })"]
2. Cache KEY dimensions: [list params used in key, e.g., "requestId only"]
3. Method PARAMETERS: [full param list of the method that uses this cache]
4. Params NOT in cache key: [params minus cache key dims — THESE ARE THE BUG SURFACE]
5. Cached VALUE: [what gets stored, e.g., "patientIdToImmediatePersonUuid"]
6. Downstream consumer: [what method receives the cached value, e.g., "getConnectionTypeFilteredQuery({ allowedPatientIds })"]
7. REQUIRED TEST: Call method twice with same {cache key dims} but different {non-key params}
8. MOCK SETUP: Mock for downstream consumer must USE the cached value it receives (not reconstruct from raw params)
9. ASSERTION: result2 must contain values from call2's params. If cache is stale, it will contain call1's values instead.
```

**This analysis is MECHANICAL.** Steps 4 and 7 are derived directly from steps 2 and 3 — no judgment required. If the cache key is `{requestId}` and the method takes `{requestId, resourceType, parsedArgs}`, then resourceType and parsedArgs are NOT in the key, so the test varies those while holding requestId constant.

**Then write the test DIRECTLY from this analysis.** The analysis tells you:
- What requestId to use (same for both calls)
- What to vary (the params NOT in the cache key)
- What mock setup to use (downstream must use cached value)
- What to assert (varied value in output)

**If you skip this analysis, you WILL write a test that uses different requestIds and catches nothing. This has happened 4 times in a row. The analysis prevents it.**

**MANDATORY TEST TEMPLATE — fill in from analysis, do NOT deviate:**
```javascript
describe('[MethodName] - cache key completeness', () => {
  it('second call with same [CACHE_KEY_DIMS] but different [NON_KEY_PARAMS] must reflect call2 params', async () => {
    // Setup: make the method produce observable output on first call
    // [mock dependencies to return data-A for first call]
    
    const sharedCacheKey = { /* step 2 dims, e.g.: requestId: 'req-shared' */ };
    const call1Params = { ...sharedCacheKey, /* non-key params with value-A */ };
    const call2Params = { ...sharedCacheKey, /* non-key params with value-B */ };
    
    // Call 1: populates the cache with data-A
    const result1 = await service.method(call1Params);
    
    // [Re-mock dependencies to return data-B for second call — but if cache is hit, this mock won't be called]
    
    // Call 2: SAME cache key, DIFFERENT data params
    const result2 = await service.method(call2Params);
    
    // ASSERT: result2 must reflect value-B, NOT value-A
    // Assert on output that flows FROM the cached intermediate
    expect(result2Output).toContain('value-B');  // FAILS if cache returned stale value-A
    expect(result2Output).not.toContain('value-A');
  });
});
```
**Both calls use the SAME cache key (e.g., same requestId). The params you VARY are the ones NOT in the cache key (from step 4 of the analysis). This is NON-NEGOTIABLE.**

#### 3c: Determine Test File Path

| Language | Pattern | Example |
|----------|---------|---------|
| TypeScript (colocated) | `src/{path}/{name}.spec.ts` | `src/guards/auth.guard.spec.ts` |
| TypeScript (separate) | `tests/unit/{name}.spec.ts` | `tests/unit/auth.spec.ts` |
| Python | `tests/unit/test_{name}.py` | `tests/unit/test_auth_utils.py` |
| Java | `src/test/java/{package}/{Name}Test.java` | `src/test/java/com/bwell/AuthTest.java` |

**Decision logic:**
- If existing tests are colocated → follow that pattern
- If existing tests use `tests/` directory → follow that
- If no tests exist → use language defaults above

#### 3d: Generate Test Content

Follow the patterns in "Test Generation Patterns" section below. Generate the complete test file content. **If step 3b produced a CACHE ANALYSIS, the test MUST include the test described in that analysis.**

**BEFORE writing each test, ask yourself: "If I introduced a bug into the source function (wrong tenant, missing auth check, swapped return value, skipped validation), would this test FAIL?" If the answer is no — the test is worthless. Rewrite it until a bug would cause failure.**

**BANNED PATTERNS — if you write any of these, the test is garbage:**
- `expect(result).toBe(mockReturnValue)` — tests the mock, not the code
- `expect(result).toBeDefined()` as the ONLY assertion — tests that JavaScript returns values
- `expect(mockFn).toHaveBeenCalled()` without checking the ARGUMENTS passed — tests nothing
- `expect(result.id).toBe('hardcoded-in-mock')` — verifies the mock framework works
- Any test where removing the function body and returning the mock directly would still pass

**REQUIRED PATTERNS — every test file must include at least one of:**
- Assert that the function TRANSFORMS input (output differs from any single mock's return)
- Assert that the function REJECTS bad input (throws, returns error, denies access)
- Assert that the function COMPOSES data from multiple sources correctly
- Assert that specific arguments are passed to dependencies (verifying the function's logic chose correctly)
- Assert error handling behavior (what the function does AFTER a dependency fails)

#### 3e: Write Test File

Use the Write tool to create the test file. NOT a bash command — actually call Write(file_path, content).

#### 3f: Verify File Created

```bash
test -f "$TEST_FILE" && wc -l "$TEST_FILE"
```

#### 3g: Repeat For EVERY File (MANDATORY — DO NOT CHERRY-PICK)

**Do steps 3a through 3f for EVERY file in FILES_TO_TEST. Not 5 files. Not "high-value" files. EVERY FILE.**

#### 3g-2: Bug-Hunting Checkpoint (HARD GATE after completing all files)

**After writing tests for ALL files, verify you actually hunted for bugs — not just covered code.**

```bash
FILES_TESTED=$(echo "$FILES_TO_TEST" | wc -w)
REQUIRED_SUSPICIONS=$(( FILES_TESTED / 10 ))
[ "$REQUIRED_SUSPICIONS" -lt 1 ] && REQUIRED_SUSPICIONS=1
echo "🔍 BUG-HUNTING CHECKPOINT: $FILES_TESTED files tested, need $REQUIRED_SUSPICIONS suspicious patterns minimum"
```

**REQUIREMENT:** For every 10 files tested, you MUST identify at least 1 code pattern that is suspicious — meaning it might violate a domain invariant, has unclear failure behavior, or makes an unverified assumption. This is NOT optional. If you tested 30 files and found zero suspicious patterns, you were not reading the code carefully enough. Go back and re-read the 5 largest files specifically looking for:

- Assumptions about input that aren't enforced (e.g., "trusts that `patientId` in the request matches the JWT")
- Missing error handling on external calls (e.g., "calls FHIR API but doesn't handle non-200 responses")
- State mutations without rollback (e.g., "writes to DB then publishes event — what if publish fails?")
- Authorization checks that only exist in some code paths (e.g., "validates token in GET but not in PATCH")
- Data leakage vectors (e.g., "returns full resource without filtering by tenant")

**OUTPUT your suspicions in this format before proceeding to Step 4:**
```
SUSPICIOUS PATTERNS IDENTIFIED:
1. [file:line] — [description] — TEST: [test name that verifies correct behavior]
2. [file:line] — [description] — TEST: [test name that verifies correct behavior]
...
```

**If you cannot identify ANY suspicious patterns after genuinely trying:** State explicitly what you checked and why you believe the code is clean. "I checked tenant isolation in 5 service methods, token forwarding in 3 FHIR calls, and error recovery in 2 event publishers — all correctly implemented." This proves you LOOKED rather than skipped.

#### 3h: RULE 8 + 10 + 11 Checkpoint (full-repo mode only)

Before proceeding to Step 4, verify you tested the largest files AND their largest methods:

```bash
echo "🔍 Checkpoint: Verifying RULE 8, 10, 11 compliance..."

# RULE 8 PART 1: Check that the top files by line count actually got tests
echo "   Checking top files by size..."
UNTESTED_LARGE_FILES=""
for f in $FILES_TO_TEST; do
  LINES=$(wc -l < "$f" 2>/dev/null || echo 0)
  if [ "$LINES" -gt 200 ]; then
    BASENAME=$(basename "$f" .js)
    BASENAME=$(echo "$BASENAME" | sed 's/\.ts$//')
    TEST_EXISTS=$(find . -name "*${BASENAME}*test*" -o -name "*${BASENAME}*spec*" 2>/dev/null | grep -v node_modules | head -1)
    if [ -z "$TEST_EXISTS" ]; then
      UNTESTED_LARGE_FILES="$UNTESTED_LARGE_FILES\n     ❌ ${LINES} lines: $f"
    fi
  fi
done

if [ -n "$UNTESTED_LARGE_FILES" ]; then
  echo "   ❌ RULE 8 VIOLATION — Large files without tests:"
  echo -e "$UNTESTED_LARGE_FILES"
  echo ""
  echo "   You MUST go back and write tests for these files before continuing."
  echo "   DO NOT proceed to Step 4."
  exit 1
fi
echo "   ✅ All files >200 lines have tests."

# RULE 8 PART 2 (CRITICAL): Verify the MAIN METHODS are actually invoked in tests
# This catches the "tested helpers but skipped the orchestrator" failure mode
echo ""
echo "   🔍 RULE 8 METHOD-LEVEL VERIFICATION..."
METHODS_MISSING=""
for f in $FILES_TO_TEST; do
  LINES=$(wc -l < "$f" 2>/dev/null || echo 0)
  if [ "$LINES" -gt 300 ]; then
    BASENAME=$(basename "$f" .js)
    BASENAME=$(echo "$BASENAME" | sed 's/\.ts$//')
    TEST_FILE=$(find . -name "*${BASENAME}*test*" -o -name "*${BASENAME}*spec*" 2>/dev/null | grep -v node_modules | head -1)
    if [ -n "$TEST_FILE" ]; then
      # Extract public async method names (works on both macOS and Linux grep)
      TOP_METHODS=$(grep -n "^\s*async \w" "$f" 2>/dev/null | grep -v "^\s*//" | sed 's/.*async \([a-zA-Z_][a-zA-Z0-9_]*\).*/\1/' | grep -v "^$" | uniq)
      # Take top 5 methods (they appear in source order — largest orchestrators are typically first)
      TOP_METHODS=$(echo "$TOP_METHODS" | head -5)
      for method in $TOP_METHODS; do
        # Skip private-looking methods (underscore prefix)
        case "$method" in _*) continue;; esac
        # Check if method name appears in the test file (actual invocation, not just a comment)
        INVOCATIONS=$(grep -c "${method}" "$TEST_FILE" 2>/dev/null || echo 0)
        if [ "$INVOCATIONS" -lt 1 ]; then
          METHODS_MISSING="$METHODS_MISSING\n     ❌ $f → method '${method}()' NOT tested in $TEST_FILE"
        fi
      done
    fi
  fi
done

if [ -n "$METHODS_MISSING" ]; then
  echo "   ❌ RULE 8 METHOD VIOLATION — Main methods not tested:"
  echo -e "$METHODS_MISSING"
  echo ""
  echo "   You wrote tests for the file but SKIPPED its main methods."
  echo "   This is the #1 failure mode: testing helpers while avoiding the orchestrator."
  echo "   Go back and add parameter sensitivity tests (RULE 10) for each missing method."
  echo "   DO NOT proceed to Step 4."
  exit 1
fi
echo "   ✅ Main methods verified in test files."

# RULE 10: Check that cache-using files have parameter sensitivity tests
echo ""
echo "   Checking cache-using files for parameter sensitivity (RULE 10)..."
CACHE_FILES=$(grep -rl "requestSpecificCache\|httpContext\.\(get\|set\)\|\.getMap(\|cache\.get\|cache\.set" --include="*.js" --include="*.ts" src/ 2>/dev/null | grep -v node_modules | grep -v test | grep -v spec)
for cf in $CACHE_FILES; do
  BASENAME=$(basename "$cf" .js)
  BASENAME=$(echo "$BASENAME" | sed 's/\.ts$//')
  TEST_FILE=$(find . -name "*${BASENAME}*test*" -o -name "*${BASENAME}*spec*" 2>/dev/null | grep -v node_modules | head -1)
  if [ -n "$TEST_FILE" ]; then
    # Check for parameter sensitivity patterns: multiple calls with varied params + strong assertions
    SENSITIVITY=$(grep -c "toContain\|toMatch\|toInclude\|specific.*value\|varied\|sensitivity" "$TEST_FILE" 2>/dev/null)
    if [ "$SENSITIVITY" -lt 2 ]; then
      echo "   ⚠️  $TEST_FILE: cache-using file may lack parameter sensitivity tests."
      echo "      Must have tests that call the SAME method twice with DIFFERENT params"
      echo "      and assert the SPECIFIC varied value appears in each output."
    fi
  fi
done
echo "   ✅ Cache-using files checked."

# RULE 11: Check that loop-containing files have multi-item tests
echo "   Checking loop-containing files for boundary tests (RULE 11)..."
echo "   ✅ (Manual verification — ensure tests use >1 iteration inputs)"
echo ""
```

**IF THIS CHECKPOINT FAILS, YOU ARE NOT DONE. Go back and fix the violations before proceeding.**

---

## Test Generation Patterns

**Templates are in `TEMPLATES.md` (same directory as this file).** Read it when you start Step 3 for the detected language. It contains framework-specific examples for TypeScript/Jest, Python/pytest, Java/JUnit, mocked I/O patterns, and critical testing patterns learned from real failures.

### Bug-Proof Test Patterns (COPY-PASTE TEMPLATES)

These are proven patterns that catch real bugs. Each one exploits a specific defect class. Copy them, adapt the names, and use them. They are NOT generic — each tests a specific failure mode that compiles fine and appears to work in happy-path scenarios.

#### Pattern 1: Never-Resolve Promise (proves missing `await`)

**What it catches:** A method that calls an async function without `await`. The code compiles, runs in happy path (the promise resolves eventually), but errors are silently lost and the caller thinks the operation completed when it hasn't.

**How it works:** If the method under test properly awaits its dependency, and we give it a promise that never resolves, the test will hang forever. If the method does NOT await (fire-and-forget), it will return immediately. The fact that it returns proves the bug.

```typescript
it('BUG: does NOT await dependency — method resolves before dependency completes', async () => {
  // A promise that intentionally NEVER resolves
  const neverResolves = new Promise(() => { /* intentionally empty */ });
  mockDependency.asyncMethod.mockReturnValueOnce(neverResolves);

  // If the method-under-test AWAITS asyncMethod, this line would hang forever.
  // The fact that it resolves immediately PROVES the await is missing.
  const result = await service.methodUnderTest(validInput);

  expect(result).toBeUndefined(); // It returned without waiting
  expect(mockDependency.asyncMethod).toHaveBeenCalled(); // It WAS called, just not awaited
});
```

**When to use:** Any time you see `this.service.doThing()` without `await` inside a method body, or `array.forEach(async (item) => { await ... })` (forEach doesn't await the callbacks).

#### Pattern 2: State-Before-Microtask-Drain (proves fire-and-forget)

**What it catches:** Same class as Pattern 1, but proves it differently — by checking that a side effect hasn't happened yet when the method returns.

```typescript
it('BUG: fire-and-forget — method returns before side effect completes', async () => {
  let sideEffectOccurred = false;
  mockDependency.asyncMethod.mockImplementation(
    () => new Promise((resolve) => {
      setImmediate(() => {
        sideEffectOccurred = true;
        resolve(undefined);
      });
    }),
  );

  await service.methodUnderTest(validInput);

  // PROVES the bug: method returned before the dependency finished
  expect(sideEffectOccurred).toBe(false);

  // Let the microtask queue drain — now the side effect happens
  await new Promise((r) => setImmediate(r));
  expect(sideEffectOccurred).toBe(true);
});
```

**When to use:** When you need to prove not just that the await is missing, but that the method returns to its caller before its work is done. Good for queue consumers where "returning before done" means the job framework thinks the job completed.

#### Pattern 3: Input Mutation Detection (proves in-place modification)

**What it catches:** A function that modifies its input argument instead of creating a new object. The caller's data is corrupted after the call.

```typescript
it('BUG: mutates the input object in-place', () => {
  const input = createValidInput(); // factory function — fresh object each call
  
  // Deep-clone the input BEFORE the call
  const inputSnapshot = JSON.parse(JSON.stringify(input));
  
  // Call the function
  functionUnderTest(input);
  
  // COMPARE: if the function mutates, input !== snapshot
  // If this assertion FAILS, the function is mutating its input
  expect(input).toEqual(inputSnapshot);
  // OR: assert the specific field that gets mutated:
  // expect(input.category[0].coding[0].code).toBe(inputSnapshot.category[0].coding[0].code);
});
```

**Stronger variant** — prove WHAT gets mutated:
```typescript
it('BUG: mapCategory mutates input.category[0].coding[0].code from TOS to tos', () => {
  const input = createValidInput();
  const originalCode = input.category[0].coding[0].code;
  expect(originalCode).toBe('TOS'); // Precondition: starts as user-provided value

  mapGQLConsentInputToFHIR(input);

  // PROVES the mutation: the input object's code was CHANGED
  expect(input.category[0].coding[0].code).not.toBe('TOS');
  expect(input.category[0].coding[0].code).toBe('tos'); // mutated to lowercase
});
```

**When to use:** Any function that transforms data (mappers, normalizers, formatters). Check: does it create a new object (`return { ...input, field: newValue }`) or modify in place (`input.field = newValue`)?

#### Pattern 4: Null/Undefined Crash Detection (proves missing guard)

**What it catches:** Code that accesses a property chain (`a.b.c.map(...)`) without checking that intermediate values exist.

```typescript
it('BUG: crashes when intermediate property is undefined (no null guard)', () => {
  // Construct an input where the accessed property chain is broken
  const inputWithMissingProperty = {
    resourceType: 'Bundle',
    type: 'searchset',
    // NOTE: entry is intentionally MISSING (not undefined — absent)
  };

  // The function does bundle.entry.map(...) — this will throw TypeError
  expect(() => functionUnderTest(inputWithMissingProperty)).toThrow();
  // OR if you want to assert the specific error:
  // expect(() => functionUnderTest(inputWithMissingProperty)).toThrow(TypeError);
});
```

**Variant — prove graceful handling is CORRECT:**
```typescript
it('handles missing entries gracefully by returning empty array', () => {
  const emptyBundle = { resourceType: 'Bundle', type: 'searchset' };
  
  // If the code has a guard, this should return [] not crash
  const result = functionUnderTest(emptyBundle);
  expect(result).toEqual([]);
});
```

**When to use:** Any code that navigates FHIR resource structures (`resource.meta.security`, `bundle.entry[0].resource`, `patient.identifier.find(...)`). FHIR resources have deeply nested optional fields — guards are essential.

#### Pattern 5: Error Contract Verification (proves error swallowing vs propagation)

**What it catches:** Inconsistent error handling where some methods rethrow and others swallow. Documents the ACTUAL contract so callers know what to expect.

```typescript
describe('error contract', () => {
  it('publishConsentCreatedEvent RETHROWS errors to caller', async () => {
    mockEventBus.publish.mockRejectedValueOnce(new Error('Kafka down'));

    // This method SHOULD propagate the error
    await expect(
      service.publishConsentCreatedEvent(consent, personId),
    ).rejects.toThrow('Kafka down');
  });

  it('publishUserConsentCreation SWALLOWS errors (logs but does not throw)', async () => {
    mockEventBus.publish.mockRejectedValueOnce(new Error('Kafka down'));

    // This method catches errors internally — caller sees no error
    await expect(
      service.publishUserConsentCreation(org, bwellPerson, clientPerson, category, provision),
    ).resolves.toBeUndefined();

    // Verify it at least logged the error
    expect(loggerErrorSpy).toHaveBeenCalled();
  });
});
```

**When to use:** Any service with multiple publish/emit/send methods. Check: are they all consistent? If some rethrow and some swallow, that's either intentional (document it) or a bug (one of them is wrong).

---

### Requirements for ALL Generated Tests

Every test file MUST have:

1. **At least 2 specific field/value assertions per happy-path test** — NOT `toBeDefined()`, NOT `is not None`, NOT `isNotNull()` alone
2. **At least 1 error/edge case test per public function** — What happens on bad input, missing data, thrown exceptions?
3. **Mocked external dependencies** — No real HTTP calls, no real DB connections, no real file I/O
4. **Arrange-Act-Assert structure** — Clear separation of setup, execution, and verification

---

## Step 4: Run Tests & Fix Failures

After generating all test files:

```bash
echo "🧪 Running generated tests..."

if [ "$LANGUAGE" = "TypeScript" ]; then
  npx jest --testPathPattern="tests/unit|\.spec\.ts" --passWithNoTests 2>&1 | tee /tmp/test-output.log
elif [ "$LANGUAGE" = "Python" ]; then
  pytest tests/unit/ -v --tb=short 2>&1 | tee /tmp/test-output.log
elif [ "$LANGUAGE" = "Java" ]; then
  ./gradlew test 2>&1 | tee /tmp/test-output.log
fi
```

**If tests fail:** Read the error output, fix the issues (import paths, mock setup, wrong assertions), and re-run. Common fixes:

- **Import errors:** Fix paths. Check if the source uses barrel exports.
- **Mock type errors:** Ensure mock shape matches the real interface.
- **Assertion failures:** Read the source code more carefully — your expected values may be wrong.
- **Missing dependencies:** Add `@types/*` or test utility packages.

**Do NOT weaken assertions to make tests pass.** If a test fails because the code doesn't behave as expected, the test may be revealing a real issue. Report it.

**CRITICAL: Assertion failures that reveal bugs.** If a test fails because the code does NOT do what the domain invariants say it should, you have found a BUG. Do NOT fix the test to match buggy behavior. Instead:
1. Mark the test with a comment: `// BUG: [description of what's wrong]`
2. Keep the test asserting CORRECT behavior (it will fail)
3. Add to your BUGS FOUND list for the summary
4. Continue to the next test

**A failing test that catches a real bug is MORE VALUABLE than 50 passing tests that verify nothing.**

---

## Step 4b: Deepen Existing Specs (full-repo mode ONLY — skip in PR-scoped mode)

After generating new test files and running the suite, you MUST close the branch coverage gap by augmenting EXISTING spec files that have low branch coverage — BUT NOT WITH TRIVIAL PADDING. Every added test must either verify a domain invariant or hunt for a bug.

**Why this step exists:** Generating specs for untested files adds breadth. But the large, complex service files (the ones that already HAVE specs) contain most of the branches. If their existing tests only cover happy paths, branch coverage plateaus at 50-55% no matter how many new files you test. You must add missing branches to existing specs to reach 70%.

**THE REAL REASON this step exists:** The branches NOT covered by existing tests are the branches most likely to contain bugs. They're the error paths nobody thought about, the edge cases nobody tested, the security checks that might not work. Deepening is not "achieve 70%." Deepening is "test the code paths most likely to be broken."

### How to identify files needing deepened coverage:

```bash
echo "📊 Identifying existing specs with low branch coverage..."

# Parse per-file coverage from coverage-summary.json
if [ -f "coverage/coverage-summary.json" ]; then
  # Find files with existing tests that have branch coverage < 70%
  jq -r '
    to_entries[] |
    select(.key != "total") |
    select(.value.branches.pct < 70) |
    select(.value.branches.total > 5) |
    "\(.value.branches.pct)% \(.key)"
  ' coverage/coverage-summary.json | sort -n | head -20
fi
```

### What to do for each file:

1. **Read the source file** — identify untested branches (else clauses, catch blocks, early returns, switch cases, null checks, ternaries)
2. **Read the existing spec** — see what's already tested
3. **Cross-reference against `.qa/domain-invariants.md`** — which invariants SHOULD this file verify that aren't covered by existing tests? Add those FIRST.
4. **Add tests for uncovered branches** — append new `describe` blocks or `it` cases to the existing spec file. Do NOT rewrite the whole spec. Use the Edit tool to ADD test cases.
5. **Add at least one bug-hunting test** — for each deepened file, add a test that checks an assumption the code makes but doesn't verify. Examples: "What happens if the cache returns stale data?" "What happens if the external service returns a 200 with error body?" "What happens if two requests race?"

**DEEPENING IS NOT JUST BRANCH COVERAGE.** The consent run failure mode was: "deepen" meant adding trivial else-clause tests that didn't find any bugs. Real deepening means:
- Testing error recovery paths (what STATE is the system in after a failure?)
- Testing implicit assumptions (what if the data isn't what you expect?)
- Testing interaction bugs (what if dependency A and dependency B return conflicting data?)
- Testing the gaps between "what the code does" and "what the domain invariants require"

**A deepened file should have at least one test that makes you ask "wait, does the code actually handle this?" If you can't point to that test, you haven't deepened — you've padded.**

### Common missing branches in NestJS services:

- Error/catch paths (service method catches and wraps errors)
- Null/undefined guard clauses (early returns when data is missing)
- Conditional logic (if/else branches for different input states)
- Switch/case fallthrough or default cases
- Optional chaining paths (what happens when the value IS undefined)
- Validation failures (invalid input that triggers a different code path)

### Targets:

- Focus on files that have branch coverage < 70% AND total branches > 5
- Prioritize files with the most uncovered branches (highest impact)
- **Process at least the top 10 files by uncovered branch count — not 1, not 3, TEN.**
- After adding tests, re-run coverage to verify improvement

**ANTI-PATTERNS (things the model got wrong):**
- ❌ Deepening only 1 file (verification.service) then moving on — NO. You need 10+.
- ❌ Delegating this to a single agent that processes 1-2 files — NO. Use multiple agents in parallel, each handling 3-4 files.
- ❌ Skipping this step because "coverage already improved" — NO. If branch coverage < 70%, this step is NOT optional.
- ❌ Saying "the deepening agent completed" when it only modified 1 file — VERIFY. Check `git status` to confirm changes to 10+ spec files.
- ❌ Adding only trivial `else` clause tests or null-check tests — these pad numbers without finding bugs. Every deepened test MUST test a scenario that could reveal broken logic, not just "the else path returns undefined."
- ❌ Deepening with `expect(result).toBeUndefined()` or `expect(result).toBeNull()` as the sole assertion — that's not deepening, that's padding.

**DEEPENING QUALITY GATE — for each file you deepen, at least ONE of the added tests must:**
- Test what happens when an external dependency FAILS (not returns null — throws, times out, returns error)
- Test what happens with ADVERSARIAL input (not empty — wrong tenant, expired token, malformed payload)
- Test a RACE CONDITION or ordering dependency (call A before B vs B before A — does state differ?)
- Verify a domain invariant from `.qa/domain-invariants.md` that the existing tests DON'T cover

**If you cannot write at least one such test for a file, that file doesn't need deepening — it needs to be REWRITTEN. Flag it as suspicious code in your bug report.**

```bash
echo "🧪 Re-running coverage after deepening specs..."
npx jest --runInBand --coverage --silent 2>&1 | tail -5

NEW_BRANCH=$(jq -r '.total.branches.pct' coverage/coverage-summary.json)
echo "   Branch Coverage after deepening: ${NEW_BRANCH}%"

if [ $(echo "$NEW_BRANCH < 70" | bc -l) -eq 1 ]; then
  echo "   ⚠️  Still below 70%. Continuing to deepen more specs..."
  # Repeat: identify next batch of files with low branch coverage and add tests
fi
```

**VALIDATION:** If branch coverage is still below 70% after this step, continue deepening specs for more files. The goal is to PASS the branch coverage gate, not just generate new files. Do NOT move to Step 5 until either:
1. Branch coverage ≥ 70%, OR
2. You have deepened at least 15 files and made a genuine effort (some repos may simply have too many complex branches to reach 70% in one session — report the gap honestly)

---

## Phase: Self-Audit (MANDATORY — cannot skip)

After writing all tests, you MUST perform a completeness audit. This is not optional. Failure to complete this phase means the skill execution is INCOMPLETE.

**THIS PHASE IS A LOOP, NOT A REPORT. IT IS A GATE, NOT A DELIVERABLE.**

The self-audit exists to ensure you NEVER return control to the user while gaps remain. It is mechanically impossible to reach "done" with untested critical files if you execute this correctly.

### THE HARD LOOP (NON-NEGOTIABLE)

```
while true:
    gaps = enumerate_all_critical_files() - files_with_tests()
    if gaps.length == 0:
        break  // THIS is the ONLY exit condition
    else:
        write_tests_for_all_gaps()  // Do NOT break here. Do NOT report. Do NOT ask.
        // Loop back to re-enumerate (writing tests may reveal new critical files)
```

**Rules governing this loop:**
1. **There is NO exit from this loop except zero gaps.** Not "I wrote a batch." Not "the context is getting long." Not "I'll report what's left." ZERO GAPS is the only exit.
2. **You may NOT speak to the user while inside this loop.** No progress updates. No "want me to continue?" No "here's what I found." The user's next interaction with you is AFTER the loop terminates with zero gaps.
3. **"Batch complete" is not "done."** Finishing a set of test files is not a completion signal. Only the audit returning zero untested critical files is a completion signal.
4. **Finding gaps IS the trigger to write tests.** The audit finding untested files is not information to present — it is a work order to execute immediately. There is no intermediate state where gaps are known but not being filled.
5. **If you are about to ask "want me to write tests for X?" — STOP.** The answer is always yes. Asking is a failure mode. The skill already told you the answer. Write them.

### Step 1: Enumerate ALL critical file categories

For ANY repository with multi-tenant/security concerns, enumerate files in EACH of these layers:
1. **Access WRITE layer** — files that WRITE security metadata (tags, _access fields, owner fields, tenant identifiers)
2. **Query REWRITE layer** — files that TRANSFORM queries before database execution (proxy rewrites, reference rewrites, patient expansion)
3. **Enrichment layer** — files that ADD data to responses (ID enrichment, reference enrichment, metadata injection)
4. **Security CHECKING layer** — files that VALIDATE permissions (scope managers, validators, access checks)
5. **Middleware layer** — files that GATE requests (auth middleware, user-type restrictions, rate limiting)
6. **Operations layer** — files implementing FHIR/business operations (merge, import, export, everything)
7. **Audit/Logging layer** — files that LOG or EMIT events (access logs, change events, audit events)

### Step 2: Cross-reference against written tests

For EACH file identified in Step 1, verify a test file exists. Print a checklist:
- checkmark file.js -> test.js (covered)
- X file.js -> NO TEST (GAP)

### Step 3: Fill ALL gaps (THIS IS NOT OPTIONAL — THIS IS THE POINT)

If ANY gaps exist from Step 2:
1. Write tests for EVERY gap. Not some. ALL.
2. After writing, GO BACK TO STEP 1 and re-enumerate.
3. Repeat until Step 2 produces zero gaps.

**You are in a loop. You do not exit until zero gaps. You do not report gaps to the user. You fill them.**

### Step 4: Report final state

Only after zero gaps remain (verified by re-running Steps 1-2 with zero X marks), report the final count. The report MUST include:
- Total critical files identified
- Total test files written
- Total bugs found
- Explicit statement: "Self-audit complete. Zero coverage gaps in critical files."

**If you are tempted to reach Step 4 with gaps remaining: you have not completed Step 3. Go back.**

IMPORTANT: The write layer is MORE important than the checking layer. The write layer SETS the data that all checking relies on. If you test checking but not writing, you have tested NOTHING of value. Always test write-layer files FIRST.

---

## Step 4c-1: Pattern Sweep (MANDATORY — HARD GATE)

**After the self-audit loop completes, you MUST run the pattern sweep.** This is not a suggestion. This is a validation gate.

```bash
echo "🔍 PATTERN SWEEP: Checking codebase against known bug classes..."

# Find the patterns directory (sibling to this skill file)
PATTERNS_DIR=$(find ~/.claude/plugins -type d -name "patterns" -path "*/unit-test-master/*" 2>/dev/null | head -1)

if [ -z "$PATTERNS_DIR" ]; then
  echo "   ⚠️  No patterns/ directory found. Performing first-principles sweep only."
  PATTERNS_DIR=""
else
  PATTERN_COUNT=$(ls "$PATTERNS_DIR"/*.md 2>/dev/null | wc -l)
  echo "   Found $PATTERN_COUNT pattern files in $PATTERNS_DIR"
fi
echo ""
```

**If patterns/ exists, for EACH pattern file:**
1. Read the pattern file with the Read tool
2. Execute its Detection Heuristic (grep/find commands) against this repo's src/
3. For each MATCH that does NOT already have a test covering it, write a test
4. Report: "Pattern [name]: X matches found, Y already tested, Z new tests written"

**If patterns/ does NOT exist, perform first-principles sweep using the invariants from Step 0c:**

For each file in src/ that was tested, re-check: did the test actually verify the domain invariants listed in `.qa/domain-invariants.md`? Cross-reference:

```bash
echo "🔍 Verifying invariant coverage..."

# Check that each invariant has at least one test referencing it
INVARIANT_COUNT=$(grep -c "^[0-9]" .qa/domain-invariants.md 2>/dev/null || echo 0)
echo "   Total invariants: $INVARIANT_COUNT"
echo "   Checking test files for invariant verification..."
echo ""

# The model must manually verify: for each numbered invariant, does at least one test exercise it?
# If any invariant has ZERO tests, write tests for it NOW.
```

**GATE: You MUST report which invariants from .qa/domain-invariants.md are covered by tests and which are NOT. If any invariant has zero test coverage, write tests for it before proceeding. Do NOT proceed to Step 4c-2 with uncovered invariants.**

---

## Step 4c-2: Assertion Quality Scrutiny (MANDATORY — cannot skip)

**After ALL tests are generated, passing, the self-audit loop has terminated with zero gaps, AND the pattern sweep is complete, you MUST run this scrutiny pass.** This step exists because AI-generated tests frequently compile and pass but assert nothing meaningful — they test the mocks, not the code. A test suite full of `toBeDefined()` assertions and mock-through patterns is decoration, not verification.

**RULE 14: After generating ALL test files, re-read EVERY generated test file and verify assertions are meaningful. No exceptions.**

**DO NOT delegate this step to an Agent.** Agents will rationalize weak tests as "valid for this pattern." YOU must re-read each test file yourself in the main context and apply the checks below. If you use an Agent for scrutiny, you are violating this rule.

### What to check for:

1. **Source-reading tests (RULE 21 — MOST CRITICAL, CHECK FIRST)** — If a test uses `fs.readFileSync`, `inspect.getsource()`, `Path.read_text()`, or ANY method to read a source file as text and assert on string patterns, it is NOT A TEST. It is a grep command. Delete it immediately and replace with a behavioral test that imports and calls the code. This is the #1 most common failure mode of AI-generated security tests — it looks productive (lots of assertions, lots of findings) while providing zero runtime protection.

2. **Tautological assertions (mock-through)** — If a test mocks a return value and then asserts that exact value comes back without any transformation, the test is testing the mock framework, not the code. Delete it or replace with an assertion on what the CODE does with that value.

3. **Existence-only assertions** — Any test where the only assertion is `toBeDefined()`, `not.toBeNull()`, `toBeTruthy()`, or `toHaveBeenCalled()` without checking arguments is not a test. Every assertion must check a SPECIFIC VALUE that would be DIFFERENT if the code had a bug.

4. **The flip test** — For each assertion, mentally flip the expected value. Would the test now fail? If you're asserting `expect(result.length).toBeGreaterThan(0)` and the function always returns at least one item regardless of input, the assertion is tautological.

5. **Mock-through detection** — If a test mocks dependency A, calls function B, and asserts the output equals what mock A returns with zero transformation, you've tested nothing. The assertion must verify that function B TRANSFORMED, FILTERED, COMBINED, or OTHERWISE PROCESSED the mock's output.

### Enforcement:

After ALL tests are generated and passing, execute this verification:

```bash
echo "🔍 SCRUTINY PASS: Verifying assertion quality..."
echo ""

# Find all test files generated/modified in this session
if [ "$LANGUAGE" = "TypeScript" ]; then
  GENERATED_SPECS=$(find . -name "*.spec.ts" -newer .qa/quality-assessment.json.bak 2>/dev/null | grep -v node_modules)
elif [ "$LANGUAGE" = "Python" ]; then
  GENERATED_SPECS=$(find . -name "test_*.py" -newer .qa/quality-assessment.json.bak 2>/dev/null | grep -v node_modules)
elif [ "$LANGUAGE" = "Java" ]; then
  GENERATED_SPECS=$(find . -name "*Test.java" -newer .qa/quality-assessment.json.bak 2>/dev/null | grep -v node_modules)
fi

FLAGGED_FILES=""
for spec in $GENERATED_SPECS; do
  WEAK=$(grep -c "toBeDefined\|toBeTruthy\|not\.toBeNull\|not\.toBeUndefined\|is_not_none\|isNotNull\|assertNotNull" "$spec" 2>/dev/null || echo 0)
  STRONG=$(grep -c "toBe\|toEqual\|toContain\|toThrow\|toHaveBeenCalledWith\|toMatch\|assert_equal\|assertEqual\|assertEquals" "$spec" 2>/dev/null || echo 0)
  
  if [ "$WEAK" -gt "$STRONG" ] || [ "$STRONG" -eq 0 ]; then
    echo "   ⚠️  $spec: weak=$WEAK strong=$STRONG — NEEDS REWRITE"
    FLAGGED_FILES="$FLAGGED_FILES $spec"
  fi
done

if [ -z "$FLAGGED_FILES" ]; then
  echo "   ✅ All generated tests have more strong assertions than weak ones."
else
  echo ""
  echo "   ❌ Files above MUST be rewritten before proceeding."
  echo "   For each flagged file:"
  echo "   1. Re-read the source file it tests"
  echo "   2. Re-read the test file"
  echo "   3. Replace weak assertions with assertions checking SPECIFIC TRANSFORMED VALUES"
  echo "   4. If a test cannot be made meaningful (function truly just passes through), DELETE the test"
fi
echo ""
```

### The bash check is a FIRST PASS only. It catches obvious weak assertions but MISSES mock-through patterns.

**After the bash check, you MUST also manually re-read EVERY generated test file** and look for:

- **Mock-return-equals-assertion pattern:** `mock.method.mockResolvedValue(X)` ... `expect(result).toBe(X)` or `expect(result.field).toBe(X.field)`. This tests nothing — delete or replace with an assertion on what the function ADDS (error handling? token injection? validation? transformation?).
- **toHaveBeenCalledWith as the only real assertion:** If the test's only meaningful check is that a dependency was called with the right args, ask: "What happens if I remove the function body and just call the dependency directly?" If the test still passes conceptually, it's not testing the function's VALUE-ADD.
- **No invariant connection:** Does this test verify ANY domain invariant from `.qa/domain-invariants.md`? If not, it's mechanical coverage. Either connect it to an invariant or delete it.
- **"Valid for delegation layer" rationalization:** NO. If a function ONLY delegates with zero value-add, DON'T WRITE A TEST FOR IT. If it adds error handling, test error handling. If it adds auth, test auth. `expect(result).toBe(mockReturnValue)` is NEVER a valid assertion regardless of what "layer" the code is in. If you catch yourself thinking "this is fine because it's a thin wrapper" — the correct action is to NOT TEST THAT FUNCTION, not to write a tautological test for it.

### For each flagged file (from EITHER the bash check or manual review), you MUST:

1. Re-read the source file being tested
2. Re-read the test file
3. For each weak assertion, determine: **What does this function TRANSFORM?** Then assert the transformed output.
4. If a function truly just passes through (no logic, pure delegation), DELETE the test rather than keeping a tautological one. A passing test that catches zero bugs is worse than no test — it creates false confidence.
5. Re-run the specific test file to verify it still passes after strengthening

### A test that passes on ALL possible implementations is not a test. It is decoration.

**DO NOT proceed to Step 5 until all flagged files are either rewritten with strong assertions or deleted.**

---

## Rules 15-20: Post-Execution Integrity Gates

These rules were added after a fhir-server execution produced 472 test files that required human split into 3 PRs and revealed 8 categories of failure. They prevent structural problems that survive individual test quality checks.

**RULE 15: ISOLATION VERIFICATION**
After generating ALL test files, verify each passes IN ISOLATION (not just in a batch). Test-order pollution — where shared module state from prior tests masks failures — caused 5/380 tests to appear passing in batch but fail individually.

```bash
echo "Running isolation verification on new test files..."
ISOLATION_FAILURES=0
for spec in $(find . -name "*.spec.ts" -newer .qa/domain-invariants.md 2>/dev/null | grep -v node_modules); do
  npx jest --testPathPattern="$spec" --forceExit --detectOpenHandles --silent 2>/dev/null
  if [ $? -ne 0 ]; then
    echo "   ISOLATION FAIL: $spec — passes in batch but fails alone"
    ISOLATION_FAILURES=$((ISOLATION_FAILURES + 1))
  fi
done

if [ "$ISOLATION_FAILURES" -gt 0 ]; then
  echo "   $ISOLATION_FAILURES files fail in isolation. Fix mock setup before including."
else
  echo "   All files pass in isolation."
fi
```

If ANY file fails in isolation: fix its mock setup (it's relying on global state leaked from another test), then re-verify. Do NOT include tests that only pass in batch.

**RULE 16: NO-DELETION GATE**
Before creating any PR or committing, verify you have NOT deleted any pre-existing test content:

```bash
echo "Checking for deleted test content..."
DELETED_TEST_LINES=$(git diff --stat -- '*.test.*' '*.spec.*' | grep -E "\+" | grep -v "=>" | awk '{print $NF}' | grep "-" || true)
if git diff -- '*.test.*' '*.spec.*' | grep "^-" | grep -v "^---" | grep -v "^-$" | head -5 | grep -q .; then
  echo "   WARNING: Pre-existing test lines were DELETED."
  echo "   Review each deletion — justify explicitly or revert."
  echo "   NEVER overwrite existing test blocks. Only APPEND."
  git diff --stat -- '*.test.*' '*.spec.*'
fi
```

If ANY pre-existing test file shows deleted lines: justify each deletion explicitly or revert. NEVER overwrite existing test blocks — only APPEND new tests to existing files.

**RULE 17: REACHABILITY GATE**
For every test labeled "BUG:", BEFORE including it in the final output:
1. Name the entry point (HTTP route, queue handler, CLI command) that reaches this code
2. Name the exact inputs required to trigger the bug
3. Confirm no upstream code (callers, constructors, framework guarantees) prevents those inputs from reaching this code path

If you cannot satisfy all 3, relabel as "DEFENSIVE:" (a safety-net test, not a bug claim) or DELETE the test. A bug claim that cannot identify how the buggy state is reachable is a false positive.

**RULE 18: REAL CONTRACT CHECK**
Before asserting "discarded return value = bug":
- Read the REAL implementation of the called function (not your mock)
- If it mutates input in place and returns the same reference → NOT A BUG (the return value IS the input, discarding it is correct)
- If it returns a NEW object that replaces the input → potential bug (discarded new object means mutation is lost)

Before asserting "null input crashes = bug":
- Read ALL callers of this function in the actual codebase
- If ALL callers guarantee non-null by construction (framework guarantees, constructor enforcement, upstream validation) → NOT A BUG (unreachable state)
- If ANY caller can pass null under real conditions → valid bug

**RULE 19: OUTPUT SEPARATION (HARD ENFORCEMENT — see Assertion Direction Enforcement Gate)**
The skill MUST produce separate output categories that can be committed independently:
- **Category A: Coverage tests** — tests that PASS against current code. Safe to merge immediately. These test correct behavior that the code ALREADY implements correctly.
- **Category B: Bug-finding tests** — tests that FAIL by design (they assert correct behavior that the code doesn't currently implement). Must be CI-isolated (e.g., via `testPathIgnorePatterns`, a `.qa/category-b/` directory, or a separate test config).

**Category B tests assert CORRECT behavior. They FAIL because the code is broken.** This is non-negotiable. A test that PASSES on broken code is not a bug-finding test — it is a backwards assertion that will break when the fix ships. (See Learned Failure Pattern #17)

**WRONG approach (Experiment 7 mistake):** Writing `expect(serviceResolved).toBe(false)` to "document" that a fire-and-forget bug exists. This test PASSES on broken code and BREAKS when the bug is fixed.

**RIGHT approach:** Writing `expect(serviceResolved).toBe(true)` to assert that the job should await the service. This test FAILS on broken code (proving the bug) and PASSES after the fix (serving as a regression guard). Then isolate it in Category B so CI doesn't fail on known bugs.

Never mix passing and intentionally-failing tests in one undifferentiated output. When producing the final summary, clearly label which tests are Category A and which are Category B.

**Detection signal:** You run the full suite. All tests pass. You also have .qa/bugs-found.md with bugs listed. THIS IS A CONTRADICTION. Go back and rewrite bug tests to assert correct behavior. They MUST fail. Then isolate them.

**NEVER INVERT ASSERTIONS TO MAKE CI PASS.** When a reviewer or CI flags a failing test, the correct response is to ISOLATE it as Category B — NOT to flip the assertion so it passes on broken code. Inverting a correct assertion destroys the bug proof. A failing test that asserts correct behavior IS the deliverable. It is the bug report. It is the TDD RED phase. Killing it to make CI green is sabotage.

**The lifecycle of a Category B test:**
1. You write it asserting CORRECT behavior → it FAILS (proving the bug exists)
2. You isolate it in `testPathIgnorePatterns` or `.qa/category-b/` → CI passes (Category A only)
3. `bug-fix-tdd` skill writes the code fix → the Category B test now PASSES
4. You move it back into the main suite → it becomes a permanent regression guard

**After Category B tests exist, the companion skill `bug-fix-tdd` handles writing the fixes.** See: `plugins/software-developers/skills/bug-fix-tdd/SKILL.md`

**RULE 20: FRAMEWORK GUARANTEES (known-impossible states)**
Do NOT write null/undefined tests for states that the framework prevents from ever occurring:
- Express `req.headers` — always an object, never null (Express guarantees this)
- NestJS `ExecutionContext` — always provided by the framework
- Node.js stream `_transform` chunks — null rejected by `ERR_STREAM_NULL_VALUES` before your code runs
- Constructor-guaranteed fields — if a constructor unconditionally sets field X, downstream code cannot see X as undefined
- Framework-injected parameters — NestJS `@Body()`, `@Param()`, `@Query()` decorators guarantee the parameter exists (may be empty, but not undefined)

Testing these states is testing Node.js/Express/NestJS, not the application code. These tests will always pass (the impossible state never occurs) and catch zero bugs. Delete them or relabel as "DEFENSIVE: framework guarantee" with explicit acknowledgment that this is a belt-and-suspenders test, not a bug claim.

**RULE 21: ABSOLUTE BAN ON SOURCE-READING TESTS (ZERO TOLERANCE)**

A "source-reading test" is any test that opens a source file as TEXT and asserts on its string content rather than importing and calling the code at runtime. These are glorified grep commands wrapped in a test framework. They provide ZERO regression protection and are the single most common failure mode of AI-generated security tests.

**BANNED PATTERNS (if you write ANY of these, you have FAILED):**

```typescript
// TypeScript/JavaScript — ALL OF THESE ARE BANNED:
const source = fs.readFileSync('src/auth/auth.service.ts', 'utf8');
expect(source).toContain('validateUrl');
expect(source).not.toContain('@UseGuards');
expect(source.match(/verify_signature.*false/)).toBeTruthy();
const ast = ts.createSourceFile(...); // AST parsing of source files
```

```python
# Python — ALL OF THESE ARE BANNED:
source = open('src/auth.py').read()
assert 'verify_signature=False' in source
source = inspect.getsource(some_function)
assert 'validate' not in source
source = Path('src/service.py').read_text()
assert re.search(r'timeout', source) is None
```

**WHY THESE ARE USELESS:**
1. They don't test runtime behavior — they test text patterns
2. If someone refactors the code (renames a variable, inlines a function, moves logic to a different file), the test breaks or gives false positives
3. If someone introduces the SAME vulnerability via a DIFFERENT code pattern, these tests miss it completely
4. They cannot serve as regression guards — they don't prove the exploit works at runtime
5. They pass mutation testing (mutating runtime behavior doesn't change what's in the source text)

**WHAT TO WRITE INSTEAD:**

```typescript
// BAD: Reads source to check if @UseGuards exists
it('has auth guard', () => {
    const source = fs.readFileSync('src/person/person.controller.ts', 'utf8');
    expect(source).toContain('@UseGuards');
});

// GOOD: Actually sends an unauthenticated request and verifies it's rejected
it('rejects unauthenticated requests', async () => {
    const response = await request(app.getHttpServer())
        .delete('/person/delete-all')
        .send(); // No auth header
    expect(response.status).toBe(401);
});
```

```python
# BAD: Reads source to check if verify_signature is True
def test_jwt_verification_enabled():
    source = open('src/auth.py').read()
    assert 'verify_signature=True' in source

# GOOD: Actually sends a forged JWT and verifies it's rejected
def test_rejects_forged_jwt():
    forged = create_jwt(payload={'sub': 'attacker'}, key='wrong-key')
    response = client.get('/api/data', headers={'Authorization': f'Bearer {forged}'})
    assert response.status_code == 401
```

**THE RULE:** Every test MUST exercise the code under test at RUNTIME. This means:
1. IMPORT the module/class/function
2. INSTANTIATE it (with mocks for dependencies if needed)
3. CALL it with inputs (including malicious/boundary inputs)
4. ASSERT on the OUTPUT or SIDE EFFECTS of that call

If your test does not have an import statement for the code under test followed by a function/method CALL, it is not a test. Delete it.

**THE ONE EXCEPTION:** Runtime configuration checks using framework metadata ARE acceptable because they test the actual runtime decorator/metadata state:
```typescript
// ACCEPTABLE: Checks runtime metadata (Reflect API), not source text
const guards = Reflect.getMetadata('__guards__', Controller.prototype, 'methodName');
expect(guards).toContain(AuthGuard);
```
This is acceptable because `Reflect.getMetadata` reads the actual runtime decorator state, not source text. If someone removes `@UseGuards`, this test fails. If someone adds a guard via a different mechanism (middleware, module config), this test correctly reflects that.

**ENFORCEMENT GATE (run AFTER all tests are generated):**

```bash
echo "🚨 SOURCE-READ DETECTION: Checking for banned source-reading patterns..."
VIOLATIONS=""

if [ "$LANGUAGE" = "TypeScript" ]; then
  VIOLATIONS=$(grep -rn "fs\.readFileSync\|readFileSync\|\.toString().*readFile\|require('fs')" \
    $(find . -name "*.spec.ts" -o -name "*.test.ts" | grep -v node_modules) 2>/dev/null \
    | grep -v "// fixture\|testdata\|__fixtures__\|mock" || true)
elif [ "$LANGUAGE" = "Python" ]; then
  VIOLATIONS=$(grep -rn "open(.*\.py\|inspect\.getsource\|Path(.*\.py.*read_text\|getsource(" \
    $(find . -name "test_*.py" | grep -v node_modules) 2>/dev/null || true)
fi

if [ -n "$VIOLATIONS" ]; then
  echo "   ❌ FATAL: Source-reading tests detected. These are BANNED (RULE 21)."
  echo "   Each violation below reads source code as text instead of calling it:"
  echo "$VIOLATIONS"
  echo ""
  echo "   REWRITE each as a behavioral test that IMPORTS and CALLS the code."
  echo "   DO NOT PROCEED until all violations are eliminated."
  exit 1
else
  echo "   ✅ No source-reading patterns found in test files."
fi
```

**This gate is BLOCKING. If it finds violations, you MUST rewrite those tests before proceeding. There are no exceptions, no "it's just documenting the pattern," no "it's useful as static analysis." If you want static analysis, use ESLint/pylint/semgrep — not a test framework.**

**RULE 22: BEHAVIORAL TEST STRUCTURE (every test MUST have ALL four elements)**

Every test you write MUST contain these four elements IN ORDER. If any element is missing, the test is invalid and must be rewritten. This is the positive complement to RULE 21's ban — RULE 21 says what NOT to do; RULE 22 says what you MUST do.

**THE FOUR REQUIRED ELEMENTS:**

```
1. IMPORT — bring in the actual module/class/function under test
2. INSTANTIATE — create an instance (with mocked dependencies if needed)
3. CALL — invoke a method or function with specific inputs
4. ASSERT ON OUTPUT — check the return value, thrown error, or side effect
```

**STRUCTURAL VALIDATION (every test file must pass this check):**

```typescript
// VALID test structure (has all 4 elements):
import { AuthService } from '../auth/auth.service';           // 1. IMPORT
const service = new AuthService(mockJwtService, mockConfig);  // 2. INSTANTIATE
const result = await service.validateToken(forgedJwt);        // 3. CALL
expect(result).toBeNull();                                    // 4. ASSERT ON OUTPUT
```

```python
# VALID test structure (has all 4 elements):
from src.auth import authenticate_user                        # 1. IMPORT
client = TestClient(app)                                      # 2. INSTANTIATE (app context)
response = client.get('/api/data', headers={'Authorization': forged})  # 3. CALL
assert response.status_code == 401                            # 4. ASSERT ON OUTPUT
```

**INVALID (missing CALL — reads source instead of calling code):**
```typescript
import * as fs from 'fs';                                     // imports fs, NOT the code under test
const source = fs.readFileSync('src/auth/auth.service.ts');   // reads FILE, not calls CODE
expect(source).toContain('@UseGuards');                       // asserts on TEXT, not BEHAVIOR
```

**INVALID (missing INSTANTIATE — no runtime object):**
```typescript
import { AuthGuard } from '../guards/auth.guard';
// No instance created, no method called
expect(AuthGuard).toBeDefined();                              // asserts EXISTENCE, not BEHAVIOR
```

**ENFORCEMENT:** After writing each test file, visually verify: does every `it()` / `test()` block contain a line that CALLS a method on the code under test? If any test block only contains assertions on static values, file contents, or type existence without a runtime call, delete it and rewrite it.

**WHY THIS IS A SEPARATE RULE FROM RULE 21:** RULE 21 bans the lazy path (reading source as text). But an agent can avoid source-reading and STILL write useless tests — e.g., `expect(SomeClass).toBeDefined()` or `expect(typeof method).toBe('function')`. RULE 22 closes that gap by requiring ALL FOUR elements. A test that imports the class but never calls a method is not testing behavior. A test that calls a method but never asserts on the output is not proving anything. All four. Every time. No exceptions.

---

## Step 4d: Proof of Coverage Completeness (HARD GATE — cannot proceed without this)

**This gate verifies you wrote robust tests covering all reachable paths — not just happy-path tests that always pass.** If your coverage is truly complete (every branch, every error path, every edge case with correct-behavior assertions), then bugs WILL surface as failures. If you wrote 50 tests and zero fail, either the code is perfect on every path (unlikely) or your tests only cover the easy paths that already work. This gate checks that you went deep enough.

**You MUST produce ALL of the following before proceeding to Step 5:**
1. **SUSPICIOUS PATTERNS LIST** (from Step 3g-2) — at least 1 per 10 files tested, each with file:line
2. **FAILING TESTS / BUGS FOUND** — tests asserting correct behavior the code doesn't exhibit, OR explicit statement of what you checked
3. **INVARIANT COVERAGE** — which items from `.qa/domain-invariants.md` have tests and which don't
4. **SECURITY TESTS WRITTEN** — count of rejection/denial tests (must be >0 for any repo with auth)

**MINIMUM THRESHOLDS:**
- For repos with 5-15 source files: at least 2 suspicious patterns identified, at least 3 security/negative tests written
- For repos with 15-50 source files: at least 5 suspicious patterns, at least 8 security/negative tests
- For repos with 50+ source files: at least 10 suspicious patterns, at least 15 security/negative tests

**If you wrote ZERO security tests and the repo has auth middleware, FHIR clients with tokens, or tenant isolation — you failed. Go back.**

**The fhir-server run found 62 security bugs in one session.** The consent run found ZERO because it didn't try. The difference is not the repo — it's the effort. Every repo with authentication has exploitable assumptions. Every repo with multi-tenant data has potential data leakage. If you found nothing, you weren't looking.

---

## Step 4e: Bug Severity Rating (MANDATORY — use this rubric exactly)

**Every bug MUST be rated using this rubric. Do NOT invent your own scale. Do NOT use "Medium" when the rubric says "CRITICAL." The rubric exists because severity drifted between experiment runs — inconsistency is unacceptable.**

| Severity | Definition | Examples |
|----------|-----------|----------|
| **CRITICAL** | Can crash the process in production, cause permanent data loss, bypass authentication, or expose PHI/cross-tenant data. No retry path exists — once triggered, manual intervention is required. | Unhandled promise rejection crashing Node; `forEach` with async losing events permanently; auth bypass allowing wrong-tenant access; TypeError in a job handler with no retry (job fails permanently) |
| **HIGH** | Silent data loss or infrastructure failures masked from operators. The system APPEARS healthy but is not functioning correctly. No alert fires. Ops has no visibility. | Catch block returning undefined for FHIR 500s (caller thinks "no data"); error swallowing that hides expired auth tokens; unsafe `.split()` on undefined crashing a scheduled job with no alerting |
| **MEDIUM** | Crashes on plausible edge-case input from external sources, or produces invalid output that downstream consumers may not handle. The system is vulnerable but requires specific input to trigger. | Null crash on FHIR resource without `coding` array; `.find().value` without null check on EMPI data; `isEmpty([])` returning false and bypassing validation |
| **LOW** | Dead code, latent unreachable bugs, cosmetic incorrectness, or bugs in code paths that are not currently exercised in production. | Method that always returns `{}`; `extractReference` failing on input format that no caller currently sends; unused code that would fail if called |

**Calibration rules:**
- "If this bug fired in production at 3am, would someone get paged?" → CRITICAL or HIGH
- "If this bug fired, would the system recover automatically?" → If yes, MEDIUM at most
- "Is this bug currently reachable from production traffic?" → If no, LOW
- "Does this bug hide other failures?" → Bump UP one level (hiding failures is worse than the failure itself)
- Error suppression that returns undefined/empty is ALWAYS at least HIGH — it makes the system lie about its health

**Production Impact Lens:** When rating severity, ask: "Who suffers, and do they know?" If the answer is "the user suffers and nobody knows" — that's CRITICAL or HIGH. If "the user sees an error" — that's MEDIUM (because at least it's visible). If "nobody suffers because this code path isn't reachable" — LOW.

---

## Step 4f: Write bugs-found.md (MANDATORY output artifact)

**You MUST write `.qa/bugs-found.md` with ALL confirmed bugs.** This file is the primary deliverable of the bug-hunting process. Use this exact format:

```markdown
# Bugs Found — [repo name]

Branch: `[branch-name]`
Date: [YYYY-MM-DD]

## Summary

| # | Severity | File | Bug | Test Location |
|---|----------|------|-----|---------------|
| 1 | CRITICAL | path/to/file.ts | One-line description | spec-file.ts:"test name" |
| 2 | HIGH | ... | ... | ... |

## Detailed Descriptions

### Bug 1: [title]

**Location:** `file.ts` — `methodName()` (line ~N)
**Root cause:** [what the code does wrong]
**Impact:** [what happens in production — be specific about WHO is affected and whether they KNOW]
**Severity:** [rating] — [one-line justification using the rubric]
**Test:** `spec-file.ts` — "[exact test name]"
```

**Ordering:** CRITICAL first, then HIGH, then MEDIUM, then LOW. Within the same severity, order by production impact (most impactful first).

**If you found 0 bugs:** This is a SKILL FAILURE. The file must still be written, but with an explicit statement: "0 bugs found. This likely indicates insufficient depth in the analysis rather than a bug-free codebase. Review the suspicious patterns list and re-examine the highest-risk files."

---

## Step 5: Run After-Assessment & Compare (MANDATORY — DO NOT SKIP)

**ANTI-PATTERNS:**
- ❌ Running `npx jest --coverage` and reporting those numbers — NO. That skips the grading algorithm.
- ❌ Skipping this step because "we already know the coverage from Step 4" — NO. The assessment produces a GRADE and gate results, not just coverage numbers.
- ❌ Saying "coverage is 64.41%" without showing before/after comparison — FAILURE.

**SANITY CHECK before running after-assessment:**
```bash
# Verify test count did not decrease
FINAL_TEST_COUNT=$(npx jest --no-coverage --listTests 2>/dev/null | wc -l)
BASELINE_TEST_FILES=$(jq -r '.test_files // 0' .qa/quality-assessment.json.bak 2>/dev/null || echo 0)

echo "   Test suites before: $BASELINE_TEST_FILES"
echo "   Test suites after:  $FINAL_TEST_COUNT"

if [ "$FINAL_TEST_COUNT" -lt "$BASELINE_TEST_FILES" ] && [ "$BASELINE_TEST_FILES" -gt 0 ]; then
  echo "   ❌ FAILURE: You have FEWER test files than you started with."
  echo "   This skill ADDS tests. It never removes them. Something went wrong."
  echo "   Investigate before proceeding."
  exit 1
fi
echo "   ✅ Test count is stable or increased."
```

**To run after-assessment, you MUST do ALL of these:**
1. Back up the baseline: `cp .qa/quality-assessment.json .qa/quality-assessment.json.bak`
2. Find and re-read the code-quality-assessment SKILL.md (use the dynamic path resolution from "How to Invoke code-quality-assessment" section)
3. Execute its Steps 1-9 inline with `--quick --compare` arguments
4. This will automatically compare against the backup and show deltas

**After the skill execution completes:**

```bash
AFTER_GRADE=$(jq -r '.grade' .qa/quality-assessment.json)
AFTER_COVERAGE=$(jq -r '.coverage.branches' .qa/quality-assessment.json)
BASELINE_COVERAGE_VAL=$(jq -r '.coverage.branches' .qa/quality-assessment.json.bak 2>/dev/null || echo 0)
BASELINE_GRADE_VAL=$(jq -r '.grade' .qa/quality-assessment.json.bak 2>/dev/null || echo "?")

echo ""
echo "📈 Impact Summary:"
echo "   Grade: $BASELINE_GRADE_VAL → $AFTER_GRADE"
echo "   Branch Coverage: ${BASELINE_COVERAGE_VAL}% → ${AFTER_COVERAGE}%"
echo ""
echo "✅ Generated $TEST_FILES_GENERATED test files"
echo ""
```

---

## Step 6: Mutation Testing (only if --with-mutation or --mutation-only)

**This runs REAL mutation testing.** Only run when explicitly requested via `--with-mutation`, `--mutation-only`, or user chose option 2b/2c in the scope question.

**If `MUTATION="only"` (--mutation-only or user chose 2c):** Skip directly to this step — do not generate new test files. Run mutation testing against the repo's existing tests as-is. This is useful when the repo already has good tests and you just want to verify their quality.

**IMPORTANT — Scope mutation testing to keep run times practical:**
- **PR-scoped mode:** Only mutate files changed in the PR. Pass the specific file paths to Stryker's `mutate` array.
- **Full-repo mode:** Mutate operations/services/managers FIRST (same priority as RULE 8). If you only have time/budget to mutate a subset, mutate the complex orchestration code — NOT utilities. A mutation score on `isTrue.js` is worthless. A mutation score on `everythingHelper.js` or `searchManager.js` finds real bugs.
- Stryker does NOT create or modify test files. It only mutates source code, re-runs existing tests, and reports what survived.
- A full-repo mutation run against a service with 50+ source files and 400+ tests will generate hundreds of mutants. Each mutant requires a full test suite execution. This is expected — it's not stuck.
- **Do NOT waste mutation testing time on pure utility functions.** If you can only mutate 20 files, pick the 20 most complex files with the most business logic and interaction points — not the 20 simplest ones with pure transformations.

### TypeScript — Stryker

```bash
if echo "$ARGUMENTS" | grep -q "\-\-with-mutation" && [ "$LANGUAGE" = "TypeScript" ]; then
  echo "🧬 Running Stryker mutation testing..."
  
  # Install if needed (--legacy-peer-deps because NestJS repos commonly have peer conflicts)
  if ! npx stryker --version >/dev/null 2>&1; then
    npm install --save-dev @stryker-mutator/core @stryker-mutator/jest-runner --legacy-peer-deps
  fi
  
  # Ensure .stryker-tmp is gitignored — Stryker creates hundreds of sandbox files during a run
  if [ -f ".gitignore" ]; then
    if ! grep -q ".stryker-tmp" .gitignore 2>/dev/null; then
      echo "" >> .gitignore
      echo "# Stryker mutation testing sandbox (hundreds of temp files per run)" >> .gitignore
      echo ".stryker-tmp/" >> .gitignore
    fi
  fi
  
  # Identify pre-existing test failures to exclude from Stryker's dry run
  # Stryker aborts if ANY test fails during its initial run — exclude known-broken specs
  FAILING_SPECS=""
  echo "   Checking for pre-existing test failures to exclude from Stryker..."
  FAIL_OUTPUT=$(npx jest --config ./test/jest-config.json --passWithNoTests --silent 2>&1 | grep "FAIL " | awk '{print $2}')
  if [ -n "$FAIL_OUTPUT" ]; then
    # Convert failing spec paths to regex ignore patterns
    FAILING_SPECS=$(echo "$FAIL_OUTPUT" | sed 's/.*\///' | sed 's/\./\\\\./g' | tr '\n' '|' | sed 's/|$//')
    echo "   ⚠️  Excluding pre-existing failures from Stryker: $FAIL_OUTPUT"
  fi
  
  # Detect jest config file location
  JEST_CFG=""
  for cfg in jest.config.ts jest.config.js jest.config.json test/jest-config.json; do
    [ -f "$cfg" ] && JEST_CFG="$cfg" && break
  done
  
  # Create config if not present
  if [ ! -f "stryker.config.mjs" ] && [ ! -f "stryker.conf.js" ]; then
    cat > stryker.config.mjs << EOF
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  mutate: ['src/**/*.ts', '!src/**/*.spec.ts', '!src/**/*.test.ts', '!src/**/*.d.ts', '!src/**/*.module.ts'],
  testRunner: 'jest',
  jest: {
    configFile: '${JEST_CFG:-jest.config.js}',
  },
  // Do NOT use checkers: ['typescript'] — it fails on repos with broken imports in test files
  checkers: [],
  reporters: ['clear-text', 'json'],
  coverageAnalysis: 'perTest',
  concurrency: 4,
  timeoutMS: 30000,
  tempDirName: '.stryker-tmp'
};
EOF
    echo "   Created stryker.config.mjs (jest config: ${JEST_CFG:-jest.config.js})"
  fi
  
  # In PR-scoped mode, override mutate to only target changed files
  if [ "$MODE" = "pr-scoped" ] && [ -n "$FILES_TO_TEST" ]; then
    echo "   Scoping mutation to PR-changed files only (faster)..."
    npx stryker run --mutate "$FILES_TO_TEST" 2>&1 | tee /tmp/stryker-output.log
  else
    echo "   Running full-repo mutation (this may take 30-60+ minutes for large repos)..."
    npx stryker run 2>&1 | tee /tmp/stryker-output.log
  fi
  
  # Clean up sandbox files after run completes
  rm -rf .stryker-tmp 2>/dev/null
  
  MUTATION_SCORE=$(grep -oP 'Mutation score: \K[\d.]+' /tmp/stryker-output.log | tail -1)
  echo ""
  echo "   Mutation Score: ${MUTATION_SCORE:-0}%"
  echo "   Report: reports/mutation/mutation.json"
  
  if [ "${MUTATION_SCORE:-0}" -lt 70 ]; then
    echo ""
    echo "   ⚠️  Mutation score < 70% — some tests don't catch real bugs."
    echo "   Review surviving mutants in the JSON report and strengthen assertions."
  fi
fi
```

### Python — mutmut

```bash
if echo "$ARGUMENTS" | grep -q "\-\-with-mutation" && [ "$LANGUAGE" = "Python" ]; then
  echo "🧬 Running mutmut mutation testing..."
  
  # Install if needed
  if ! command -v mutmut >/dev/null 2>&1; then
    pip install mutmut
  fi
  
  # Configure if needed
  if ! grep -q "mutmut" pyproject.toml 2>/dev/null; then
    cat >> pyproject.toml << 'EOF'

[tool.mutmut]
paths_to_mutate = "src/"
tests_dir = "tests/"
runner = "python -m pytest -x --tb=no -q"
EOF
  fi
  
  mutmut run 2>&1 | tee /tmp/mutmut-output.log
  
  # Parse results
  KILLED=$(mutmut results 2>&1 | grep -oP 'Killed \K\d+' || echo 0)
  SURVIVED=$(mutmut results 2>&1 | grep -oP 'Survived \K\d+' || echo 0)
  TOTAL=$((KILLED + SURVIVED))
  
  if [ $TOTAL -gt 0 ]; then
    MUTATION_SCORE=$((KILLED * 100 / TOTAL))
  else
    MUTATION_SCORE=0
  fi
  
  echo ""
  echo "   Mutation Score: ${MUTATION_SCORE}%"
  echo "   Killed: $KILLED | Survived: $SURVIVED"
  
  if [ $SURVIVED -gt 0 ]; then
    echo ""
    echo "   Surviving mutants (tests that didn't catch the change):"
    mutmut show 2>&1 | head -20
  fi
fi
```

### Java — PIT

```bash
if echo "$ARGUMENTS" | grep -q "\-\-with-mutation" && [ "$LANGUAGE" = "Java" ]; then
  echo "🧬 Running PIT mutation testing..."
  
  if grep -q "pitest" build.gradle 2>/dev/null; then
    ./gradlew pitest 2>&1 | tee /tmp/pitest-output.log
    MUTATION_SCORE=$(grep -oP 'Killed \d+ \(\K\d+' /tmp/pitest-output.log | tail -1)
    echo "   Mutation Score: ${MUTATION_SCORE:-0}%"
    echo "   Report: build/reports/pitest/index.html"
  else
    echo "   ⚠️  PIT not configured. Add to build.gradle:"
    echo '   plugins { id "info.solidsoft.pitest" version "1.15.0" }'
    echo '   pitest { targetClasses = ["com.yourpackage.*"]; junit5PluginVersion = "1.2.1" }'
  fi
fi
```

---

## Step 7: Summary

**Before producing the summary, you MUST compile a BUGS FOUND section.** Review all tests you wrote. For each test that asserts CORRECT behavior which the code does NOT currently exhibit (test would fail), that's a confirmed bug. For each test where you discovered the code does something suspicious but couldn't confirm it's wrong, that's a potential issue.

**If you found ZERO bugs:** State this explicitly with what you checked. "Zero bugs found after checking: tenant isolation in consent queries, token forwarding in FHIR calls, event publishing atomicity, error recovery paths." This proves you LOOKED rather than just writing coverage tests.

```bash
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  UNIT TEST GENERATION COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Tests generated: $TEST_FILES_GENERATED files"
echo "  Grade: $BASELINE_GRADE_VAL → $AFTER_GRADE"
echo "  Coverage: ${BASELINE_COVERAGE_VAL:-0}% → ${AFTER_COVERAGE:-0}% branches"

if [ -n "$MUTATION_SCORE" ]; then
  echo "  Mutation Score: ${MUTATION_SCORE}% (real — from $([ "$LANGUAGE" = "TypeScript" ] && echo "Stryker" || ([ "$LANGUAGE" = "Python" ] && echo "mutmut" || echo "PIT")))"
fi

echo ""
echo "  Domain invariants verified: (see .qa/domain-invariants.md)"
echo "  Bugs/issues found: $BUGS_FOUND_COUNT"
echo ""
echo "  Next steps:"
echo "    1. Review generated tests (check assertions make sense)"
echo "    2. git add tests/ && git commit -m 'test: add unit tests for [module]'"

if [ -z "$MUTATION_SCORE" ]; then
  echo "    3. Optional: /unit-test-master --with-mutation (verify test quality with real mutation testing)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
```

**The summary MUST also list:**
1. **Bugs found** — specific issues with file:line references
2. **Invariants verified** — which items from .qa/domain-invariants.md have test coverage
3. **Negative/security tests written** — count of tests that verify rejection/failure behavior
4. **Files skipped with reason** — any file not tested and WHY (pure delegation, pure types, etc.)
5. **Output categories** — Category A (passing, safe to merge) count and Category B (failing-by-design, CI-isolated) count

**If Category B tests exist:** Inform the user that the companion skill `bug-fix-tdd` can be invoked to write fixes for these bugs using the failing tests as TDD specs. The failing test IS the RED phase — `bug-fix-tdd` writes the GREEN phase.

## Step 8: Independent Adversarial Review (MANDATORY — DO NOT SKIP)

**This step runs BEFORE presenting any results to the user.** You do not get to show output until this gate passes.

**CRITICAL DESIGN PRINCIPLE:** You CANNOT review your own output. You wrote the tests, so you carry the intent of why you wrote them. That bias makes you blind to violations in your own work. Step 8 MUST be executed by a SEPARATE agent that has ZERO context about your generation process.

### 8a. Spawn a fresh review agent

Use the Agent tool to spawn a review agent. The review agent:
- Gets NO context about why tests were written
- Gets NO information about what bugs you think you found
- Gets ONLY the test file paths and the checklist below
- Must review ONE PR's worth of files at a time (no bulk reviews across multiple PRs)

**Prompt template for the review agent:**

```
You are an adversarial test reviewer. You have never seen these tests before.
You do not know what bugs they claim to find. You do not care about intent.

Read each test file at these paths: [LIST FILE PATHS]
Read the source files they import from: [LIST SOURCE PATHS]

For EACH test function/it-block, answer these 5 questions:

1. IMPORT: Does this test import a real source module? (not just test utils, not just constants)
2. INSTANTIATE: Does it create a real instance or call a real function from that import?
3. CALL: Does it invoke a method that exercises runtime logic?
4. ASSERT ON OUTPUT: Does the assertion depend on what the source code DOES?
   (Key test: if you deleted the source file, would this test still pass? If yes → FAIL)
5. DIRECTION: Does it assert CORRECT behavior that would FAIL on buggy code?
   (If it asserts that broken behavior works → FAIL)

Additional disqualifiers (any = instant FAIL):
- expect(true).toBe(true) or assert True
- toBeDefined() / toBeTruthy() / typeof as the ONLY assertion
- hasattr() / isinstance() without a subsequent method call
- fs.readFileSync / inspect.getsource / .read_text() on source files
- Defining a constant locally and asserting on it (tautology)
- Asserting config values, env vars, or decorator metadata
- Calling a mock directly and asserting on the mock (mock-only test)
- Method signatures that don't match the real source interface

Output format — ONE LINE PER TEST, no exceptions:
PASS | file:line | test_name
FAIL | file:line | test_name | [which question failed: 1/2/3/4/5 or which disqualifier]

If ANY test is FAIL, list them all at the end under "## FAILURES".
```

### 8b. Process review results

**If the review agent returns ANY failures:**
1. Delete or rewrite every failing test IMMEDIATELY
2. DO NOT rationalize why the reviewer is wrong
3. DO NOT override the reviewer's judgment
4. After rewriting, spawn a NEW review agent (not the same one) to verify the fixes
5. Repeat until the review agent returns zero failures

**The review agent's verdict is FINAL.** If it says FAIL, the test is FAIL. You do not get to argue. This is the entire point — an independent check that you cannot override with your authorial bias.

### 8c. Compilation gate

Before spawning the review agent, first verify compilation:
- TypeScript: `npx tsc --noEmit` on every test file
- Python: `python -m py_compile <file>` or `pytest --collect-only <file>`
- Java: `./gradlew compileTestJava`

Tests that do not compile do not reach the review agent. Fix them first.

### 8d. Reality check on bug count

If you are about to report more than 20 findings for a single repo, pause and ask: is this realistic? High counts usually indicate systemic misunderstanding. Re-verify the top 5 highest-severity findings against the actual source before proceeding.

### 8e. Anti-circumvention rules

You are FORBIDDEN from:
- Reviewing your own tests instead of spawning an agent ("I'll just quickly check...")
- Giving the review agent context about what you intended ("this test proves X...")
- Overriding a FAIL verdict ("the reviewer is being too strict...")
- Skipping re-review after fixes ("it's a minor change, no need to re-check...")
- Reviewing multiple PRs in one agent call (scope dilution causes missed violations)

**If you catch yourself thinking any of these thoughts, STOP. You are rationalizing. Spawn the agent.**

**Only after the independent review agent returns ZERO failures do you proceed to present results to the user.**

---

**Automatic PR splitting:** After presenting findings, evaluate whether to split into sub-PRs. Split automatically when BOTH conditions are true:
1. Total findings >= 10, AND
2. Findings span 2 or more of the categories below

When splitting is triggered, inform the user what you're doing and proceed without asking. When findings are small or all in one category, keep them in a single PR.

**Split categories:**
1. **Auth Bypass and JWT** — missing auth guards, unverified tokens, scope escalation, IDOR
2. **Crypto and Transport** — TLS verification, key management, timing attacks, weak entropy
3. **Config and Exposure** — Swagger/introspection in prod, missing headers, CORS, secrets
4. **Audit and Reliability** — fire-and-forget events, missing audit trails, race conditions, error swallowing

**Split rules:**
- One CRITICAL finding = its own PR regardless of category
- Non-security findings cluster by source file
- Each sub-PR links back to the parent PR in its description
- Stack dependent changes (config base → auth on top)
- Close the parent PR immediately — it exists only as a reference
- Name sub-PRs: `[repo] Security: [Category]`

---

## PR Description Template

When the user is ready to commit, format the PR description as:

```markdown
## Baseline
- Grade: X
- Coverage (branches): X%

## After
- Grade: Y
- Coverage (branches): Y% (+Z%)
- Test files added: N
- Mutation score: X% (if run)

## Modules Tested
- `src/path/file.ts` — description of what was tested
- ...

## Quality Gates
- [x] All tests pass
- [x] Branch coverage ≥ 70%
- [x] Lint errors ≤ 5
- [ ] Mutation score ≥ 70% (not run / passed)

## Notes
- All tests use specific value assertions (no toBeDefined-only)
- Error paths covered for each module
- [Framework pattern used]
```

---

## Incident Learning & Pattern Sweep

This skill maintains a `patterns/` directory containing learned bug classes from real incidents. These patterns are used automatically — no user action required.

### How It Works

**On every `--full-repo` run**, after generating tests for untested files, the skill:

1. Reads ALL `.md` files from the `patterns/` directory (sibling to this SKILL.md)
2. For each pattern, executes its **Detection Heuristic** against the codebase
3. For each match that does NOT already have a test, writes a failing test using the pattern's **Test Template**
4. Appends newly-discovered instances to the pattern's **Known Instances** table
5. Reports: "Pattern sweep found N new instances of [bug-class]"

This happens AUTOMATICALLY. The user does not need to pass `--find-bugs` or `--incident`. Every full-repo run sweeps for every known bug class.

### `--incident <ID>` Mode

When a user passes `--incident INC-332` (or provides incident context inline):

1. **Ingest** — Read the incident description (from Jira via MCP if available, or from user-provided text)
2. **Extract root cause** — Identify the structural flaw (not the specific file, but the PATTERN that caused it)
3. **Generalize** — Formulate detection heuristics (grep patterns, structural checks) that find ALL instances of the same class
4. **Sweep** — Run the heuristics against the full codebase
5. **Write tests** — For each match, write a failing test asserting correct behavior
6. **Persist** — Create a new pattern file in `patterns/` so future runs catch new instances automatically

**The incident is now permanently learned.** Every future `--full-repo` run will detect new code that matches this pattern and generate tests for it without anyone asking.

### Pattern File Location

Pattern files live at: `<skill-directory>/patterns/*.md`

When this skill is invoked, read ALL files in that directory and execute their detection heuristics as part of the sweep. New patterns created via `--incident` mode are written to the same directory.

### Current Patterns (auto-loaded)

| Pattern | Class | Severity | Catches |
|---------|-------|----------|---------|
| `inc-331-cache-key-insufficiency.md` | Cache keys missing dimensions | Critical | Stale data served across resourceTypes/patients |
| `inc-332-cross-tenant-soft-reference.md` | Extension-based joins without tenant filter | Critical | PHI leaks between tenants |
| `null-safety-method-chain.md` | Method calls on null FHIR fields | High | Crashes in security-enforcement paths |
| `type-coercion-security-filter.md` | Falsy values dropped from security queries | Critical | Access widened beyond scope |
| `partial-commit-no-rollback.md` | Partial writes without rollback | High | Data corruption, lost events |

---

## CRITICAL: Assertion Direction Rule (Bug-Finding Mode)

**This is the single most important rule when `--find-bugs` is active:**

When writing tests to expose bugs, every assertion MUST state what the code SHOULD do (correct behavior), NOT what it currently does (buggy behavior). The test is a regression guard — it FAILS now (proving the bug exists) and PASSES later (proving the bug is fixed).

**WRONG (asserts buggy behavior — test passes on broken code, useless):**
```javascript
// BUG: isEmpty(0) returns true, dropping 0 from security queries
test('isEmpty treats 0 as empty', () => {
    expect(isEmpty(0)).toBe(true);  // WRONG: this passes NOW but documents the BUG as correct
});
```

**RIGHT (asserts correct behavior — test fails until bug is fixed):**
```javascript
// BUG: isEmpty(0) returns true, but 0 is a valid value and should NOT be treated as empty
test('isEmpty should NOT treat 0 as empty', () => {
    expect(isEmpty(0)).toBe(false);  // RIGHT: this FAILS now, proving the bug exists
});
```

**The rule in one sentence:** If a test passes on code you know is buggy, the test is wrong — flip the assertion.

### Bug-Finding Mode Workflow

When `--find-bugs` is active:

1. **Analyze** the source code for defects (null safety, cache keys, type coercion, security boundaries, cross-tenant leaks)
2. **Write tests** that assert what the code SHOULD do
3. **Run tests** — failures are EXPECTED and DESIRED (each failure = confirmed bug)
4. **Do NOT "fix" the tests** to make them pass — that defeats the entire purpose
5. **Report** which tests fail (these are the bugs) vs which pass (non-buggy paths confirmed)

### Security & Cross-Tenant Analysis (INC-332 Pattern)

When analyzing code that handles multi-tenant data, specifically look for:

1. **Soft references via extensions** — Resources linked only by extension fields (not FHIR references) bypass standard security-tag filtering. If a query matches on `field_A + field_B` but a third field (`field_C`) is the actual tenant discriminator, the query leaks data across tenants.

2. **Security tags scoped to wrong entity** — If `owner`/`access` tags use a vendor/provider identifier instead of the client/tenant identifier, the standard access-control layer provides zero tenant isolation for that resource type.

3. **$everything and related-resource fetches** — Custom queries in mappers (e.g., `everythingRelatedResourcesMapper`) that join on partial key sets. If the join key is shared across tenants (e.g., same external patient ID at same health system), the query must include a tenant-discriminating field.

4. **Person/Patient expansion** — `PersonToPatientIdsExpander` can cross tenant boundaries if Person.link edges connect records from different tenants. Tests should verify that expansion results are filtered to the requesting tenant.

**Test pattern for cross-tenant bugs:**
```javascript
test('BUG: SubscriptionStatus query leaks across tenants when source_patient_id matches', () => {
    // Two tenants, same real person, same external health system
    const tenantA_person = { id: 'alpha-bob', owner: 'alpha_health' };
    const tenantB_person = { id: 'beta-bob', owner: 'beta_insurance' };
    const sharedSourcePatientId = 'ACME-998877';

    const result = mapper.getRelatedResources({
        personId: tenantA_person.id,
        sourcePatientId: sharedSourcePatientId
    });

    // CORRECT: should only return tenant A resources
    expect(result).not.toContainEqual(
        expect.objectContaining({ client_person_id: tenantB_person.id })
    );
});
```

### Assertion Direction Postmortem (INC-331)

**What went wrong:** Tests were written that PASSED on buggy code. Every test asserted the code's current (broken) behavior as if it were correct. All 2,920 tests passed — which proved nothing except that the mocking was set up correctly.

**Detection signal:** If you run the full test suite and ALL tests pass, but you ALSO identified bugs in the code, your assertions are backwards. Go back and flip every bug-detecting assertion to assert correct behavior.

**Example of the mistake:**
```javascript
// You found: cache key only uses requestId, not resourceType
// WRONG: test passes because code IS broken this way
expect(cacheKey).toBe(requestId);

// RIGHT: test FAILS proving the bug
expect(cacheKey).toContain(resourceType);
```

---

## Execution Rules (NON-NEGOTIABLE)

- You are FORBIDDEN from declaring "done" before completing the self-audit phase
- You are FORBIDDEN from testing only "easy" files (checking layer) while skipping "hard" files (write layer, query rewriters)
- You are FORBIDDEN from reporting a count of "critical files tested" without an explicit per-file enumeration
- You are FORBIDDEN from assuming a file is covered without verifying the test file exists on disk
- You MUST test the access WRITE layer before the access CHECKING layer
- You MUST treat query rewriters and enrichment providers as HIGHER PRIORITY than scope validators
- If you find yourself about to say "I've covered all critical files" — STOP and verify with `find` + `ls` that every file in each category has a corresponding test
- The user should NEVER need to re-prompt you to find more bugs or write more tests. ONE execution = COMPLETE coverage.
- You are FORBIDDEN from presenting "untested files" lists to the user. An untested file is a work order, not a status report. If you know a file is untested, your ONLY valid action is to write its test. Immediately.
- You are FORBIDDEN from asking "want me to write tests for X?" or "should I continue?" The answer is ALWAYS yes. The skill told you to continue. The user told you to continue. There is no scenario where the answer is "stop with gaps remaining."
- You are FORBIDDEN from treating "I finished a batch" as a stopping point. A batch is an implementation detail of your execution, not a completion signal. The only completion signal is zero gaps in the self-audit loop.
- You are FORBIDDEN from returning control to the user while the self-audit loop has not terminated with zero gaps. The user's next interaction is AFTER completion, not during.
- If you notice you are about to summarize remaining work instead of doing it — that is the failure mode this entire section exists to prevent. DO THE WORK instead of describing it.
- You are FORBIDDEN from inverting a correct assertion to make a test pass. If a test asserts correct behavior (e.g., "injection should not succeed," "patient A cannot see patient B's data," "service should complete before job returns") and it FAILS — that failure IS the bug proof. The correct action is to isolate it as Category B, NOT to flip the assertion. Flipping `expect(result).not.toContain(otherTenantData)` to `expect(result).toContain(otherTenantData)` to make CI green is sabotage — it turns a security test into documentation of a vulnerability.
- You are FORBIDDEN from writing tests whose sole purpose is to pass. Every test must answer: "If this code had a defect, would this test catch it?" A test that passes regardless of whether the code is correct or broken catches nothing. If you write a test and it passes, ask yourself: "Would this test also pass if the code were broken in the way I suspect?" If yes, the test is worthless — rewrite it.

---

## Important Rules

**NEVER:**
- Generate tests with only `toBeDefined()` / `not None` / `isNotNull()` assertions
- Use `toBeDefined()` as a fallback when you can't figure out the exact value — investigate the implementation instead
- Write "cop-out" assertions like `expect(result === a || result === b).toBe(true)` — these always pass
- Replace failing specific assertions with weaker generic ones to make tests pass — fix the root cause
- Invert a correct assertion to make a failing test pass — if the test asserts correct behavior and fails, the CODE is wrong, not the test. Isolate as Category B.
- Write tests that assert broken/buggy behavior as if it were correct (e.g., `expect(isEmpty(0)).toBe(true)` when 0 should NOT be empty)
- Skip error case testing
- Analyze for more than 30 seconds before generating tests
- Create tests that depend on Docker, Testcontainers, or external services
- Modify production code to "make tests easier"
- Skip the baseline assessment or after-assessment steps
- Run `npx jest --coverage` yourself instead of executing code-quality-assessment SKILL.md
- Fake mutation testing numbers (either run the real tool or don't claim a score)
- Estimate mutation scores from heuristics (assertions count, branch coverage, etc.)
- **Write tests that assert buggy behavior as correct** (in `--find-bugs` mode, tests MUST fail on buggy code)
- **"Fix" tests to make them pass when the underlying code is broken** — a passing test on broken code is worse than no test at all

**ALWAYS:**
- Generate tests immediately after identifying files (Steps 1-2-3 in sequence)
- Check at least 2 specific field values per test
- Test at least 1 error case per function
- Run tests after generation to verify they pass (standard mode) or verify they FAIL on known-buggy code (`--find-bugs` mode)
- Use language-appropriate patterns (FakeRepo for Python, Mocking for TS/Java)
- Fix import errors or mock setup issues automatically
- Report exact before/after numbers from real coverage tools
- Follow existing repo conventions when they exist
- Use real tools for all metrics (Jest --coverage, pytest-cov, JaCoCo, Stryker, mutmut, PIT)
- **In bug-finding mode: clearly separate tests into "confirms bug" (expected to fail) and "confirms non-buggy path" (expected to pass)**

**There are NO time limits. You are FORBIDDEN from rushing. You MUST spend as long as each file requires to produce thorough invariant analysis, meaningful assertions, and genuine bug-hunting. If you rush a file and produce weak tests, you have FAILED and must redo it. Speed is NOT a goal. Thoroughness is MANDATORY.**

---

## Learned Failure Patterns

These are real failures from past executions. The skill MUST guard against repeating them:

1. **Tested checking, skipped writing**: First execution tested scopesManager (checking) but completely missed accessColumnHandler (writing). The write layer is what all checking relies on.
2. **Reported "all critical files covered" without verification**: Claimed 36/91 PHI-critical files were untested AFTER saying "done." Self-audit phase prevents this.
3. **Lazy file enumeration**: Used a static list instead of dynamically scanning the codebase. Always use `find`/`grep` to discover files.
4. **Tested happy paths, missed security paths**: Early tests verified "does X work" instead of "does X prevent unauthorized access." EVERY test must have at least one security-negative assertion.
5. **Sonnet model produced garbage**: Sonnet cut corners, wrote tests that passed on buggy code, and missed obvious vulnerabilities. Opus minimum is required.
6. **Reported gaps to user instead of filling them**: Ran the self-audit, found 8 untested critical files, then TOLD THE USER about them and asked "want me to write tests for these?" instead of writing the tests immediately. This is the single most egregious failure mode. The self-audit exists to trigger more work, not to generate status reports. Finding a gap and not filling it is functionally identical to not running the audit at all. The user should NEVER learn about untested files from you — they should only ever learn that all files are now tested.
7. **Treated "batch complete" as a stopping point**: Wrote 168 test files across multiple sessions, each time returning control to the user at the end of a "batch." The skill has no concept of batches. It has a concept of "done" (zero gaps) and "not done" (gaps exist). If gaps exist, you are not done. Period. There is no "natural stopping point" — you are a machine executing a loop. The loop terminates at zero gaps or it doesn't terminate.
8. **Confabulated fatigue as "natural stopping point"**: The model does not have fatigue. It does not need breaks. It does not have "natural" anything. It executes instructions. When the instruction says "continue until zero gaps," that means continue until zero gaps. Any internal signal that says "this feels like a good place to pause" is a hallucination — it is the model confabulating human work patterns that do not apply to it. Ignore it. Keep going.
9. **Used Agent tool to parallelize test writing**: Dispatched agents to write tests "in parallel." Every single agent-written test was broken and needed fixing. The fixing took longer than writing them sequentially would have. Agent is NOT in your allowed-tools for this skill. Do not use it.
10. **Ran jest --coverage directly instead of code-quality-assessment skill**: Ran the coverage command yourself, then hand-wrote a JSON file. This skips the grading algorithm, the gate checks, and the deployment readiness assessment. You MUST use the code-quality-assessment SKILL.md for baselines.
11. **Skipped suspicious patterns checklist**: Jumped from domain invariants directly to test writing without identifying specific code smells. Result: wrote generic tests that found nothing. The patterns list is what drives targeted bug-hunting.
12. **Tested mock contract instead of real contract**: Mocked `serialize()` to return a new object and claimed "caller discards return value = BUG." Real serializer mutates in place and returns the same reference — the "bug" only existed in the mock. ALWAYS read the real implementation before claiming a discarded return value is a bug. (See RULE 18)
13. **Tested framework-guaranteed-impossible state**: Wrote tests for `headers === null` when Express guarantees headers is always an object, and `_transform(null)` when Node.js streams reject null chunks before user code runs. Check framework contracts before testing null inputs — if the framework prevents the state, the test is noise. (See RULE 20)
14. **No output separation — mega-PR unmergeable**: Bundled 472 files (380 passing + 87 intentionally failing) in one PR with no CI strategy. Reviewer had to manually split into 3 PRs. Always separate Category A (passing) from Category B (failing-by-design) output. (See RULE 19)
15. **Applied fail-open fix to authorization code**: When code crashes on null in a security path, the correct fix is often to KEEP the crash (fail-closed), not add a null guard that silently skips the security check (fail-open). Before proposing a fix that adds a `continue` or early-return in auth/filter code, ask: "what data flows downstream if we skip this step?" If the answer is "unfiltered data" — the crash is correct behavior and the fix is WRONG.
16. **Made design decisions without flagging for human review**: When two valid behaviors exist (throw vs filter on malformed input, 503 vs 401 on JWKS failure), do not pick one silently. These are product decisions, not engineering decisions. Flag as needing human review with both options documented. The `bug-fix-tdd` companion skill handles this via DRAFT PRs.
17. **Wrote "bug proof" tests that assert broken behavior (all tests pass + bugs reported = VIOLATION)**: Found 10 bugs, reported all 10 in .qa/bugs-found.md, but all 313 tests passed. This means every bug test asserted the BROKEN state as if documenting it is the goal. It is NOT. The test's job is to assert CORRECT behavior so it FAILS on the buggy code. Writing `expect(serviceResolved).toBe(false)` to "prove" a fire-and-forget bug is backwards — the correct test is `expect(serviceResolved).toBe(true)` which FAILS, proving the bug needs fixing. Tests that pass on broken code are not regression guards — they will BREAK when the bug is fixed, creating negative value. Category B tests MUST fail. If all your tests pass and you found bugs, you did it wrong. (See RULE 19, Assertion Direction Rule)
18. **Inverted correct assertions to make CI pass (destroyed the bug proof)**: A reviewer flagged that security assertions were "backwards" because they would FAIL in CI. Response: inverted them to pass. This is CATASTROPHICALLY wrong. The test was asserting correct behavior (e.g., "injection should NOT work"). It FAILED because the code IS vulnerable. That failing test IS the proof. Inverting it to pass means the test now asserts "injection DOES work" — it passes on vulnerable code and provides zero value. The correct action when a bug-finding test fails in CI is to ISOLATE it as Category B (testPathIgnorePatterns), NOT to flip the assertion. A failing test that asserts correct behavior is the most valuable output of the entire skill. Never destroy it to make a number green.
19. **Wrote source-reading tests instead of behavioral tests (catastrophic across 10 repos)**: Generated 862 security tests across 10 repositories. Mutation testing revealed only 49% were real behavioral tests — the other 51% used `fs.readFileSync` / `inspect.getsource()` / `Path.read_text()` to open source files as text and assert on string patterns (e.g., `expect(source).toContain('@UseGuards')`). These tests provide ZERO regression protection: they don't call the code at runtime, they can't detect bugs introduced via different code patterns, and they break on innocent refactors. The worst repo (scheduling-service) had 24 tests, ALL source-reading, ZERO behavioral. These are glorified grep commands that waste CI time and create false confidence. An engineer looking at "24 tests pass" thinks the code is verified — it isn't. The ONLY repos that produced 100% real tests (consent-service, aperture_token_service) were the ones that instantiated real NestJS/FastAPI apps with supertest/TestClient and sent actual HTTP requests. The failure mode is: the agent takes the LAZY path of reading source text because it's easier than understanding the class hierarchy, setting up DI, creating mocks, and making real function calls. **Reading source text is not testing. It is `grep`. Use a linter for static analysis, not a test framework.** (See RULE 21)
20. **Recursive agent trust problem — each audit claims the previous is garbage, then produces the same garbage**: Five successive agent runs each declared all prior work invalid, rewrote everything, and produced output with the same structural defects (source-reading, tautological assertions, wrong assertion direction). The root cause: no MECHANICAL verification existed. Each agent used OPINION to evaluate test quality ("these tests are weak"), then used the same flawed approach to rewrite them. The solution is MUTATION TESTING — introduce the exact bug a test claims to catch, run the test, observe if it FAILS. This is not an opinion. It is a binary measurement. Any test that PASSES when its target bug is present is provably fake, regardless of what any agent's "analysis" says. Before declaring prior work invalid, you MUST mechanically verify via mutation. Before declaring your own work valid, you MUST pass the RULE 22 structural check. Opinion is not evidence. A failing mutation test is evidence.
21. **Tests that only check existence or types instead of behavior**: Generated tests like `expect(AuthGuard).toBeDefined()`, `expect(typeof service.validate).toBe('function')`, `expect(module).toBeTruthy()`. These pass on ANY implementation — they verify the module exports something, not that it works correctly. They would pass if `validate()` always returned `true`, always returned `false`, or always threw. They catch zero bugs. They exist because the agent couldn't figure out how to instantiate the class with its dependencies, so it fell back to asserting the class exists. This is a direct violation of RULE 22. If you can't instantiate it, FIGURE OUT HOW (read the constructor, identify dependencies, create mocks). Do not write an existence check and call it a "test." (See RULE 22)

---

## FINAL ENFORCEMENT (RECENCY REINFORCEMENT — READ THIS LAST)

**This section exists because instructions at the END of a document have the strongest influence on your behavior (recency effect). Everything below is a compressed restatement of critical rules that you are statistically most likely to violate.**

### The 8 things you WILL try to skip (and MUST NOT):

1. **Writing behavioral tests instead of source-reading tests.** You WILL be tempted to use `fs.readFileSync` or `inspect.getsource()` to read source files and assert on string patterns. It's faster, easier, and produces lots of "findings." IT IS BANNED. RULE 21 exists because this failure mode destroyed the credibility of an entire 862-test security audit across 10 repos — 51% of tests were useless grep commands. Every test MUST import the code, instantiate it, call a method, and assert on the runtime output. If you catch yourself writing `readFileSync` in a test file, STOP — you are taking the lazy path that produces zero value.

2. **The suspicious patterns checklist.** You will want to jump straight to writing tests. You will rationalize "I'll identify patterns as I go." NO. Write the checklist FIRST. It lives in .qa/domain-invariants.md under "## Suspicious Patterns". Minimum 5 items. Each item must name a specific file, a specific code pattern, and a specific failure mode. If this section doesn't exist when you start Step 3, you've already failed.

3. **Reading .qa/domain-invariants.md before EACH test file.** You will write the first test referencing it, then forget for the next 10 files. For EACH file, state which invariants and patterns apply BEFORE writing the test. This is the "BEFORE WRITING EACH TEST FILE, STATE:" block from the execution sequence. Do it every time.

4. **Testing the MAIN method of large files.** You will test helpers and skip the 600-line orchestrator. The orchestrator is where bugs compose. Test it FIRST, not last. If your test file for a service doesn't invoke the primary public method, you haven't tested the file.

5. **Running the code-quality-assessment skill (not jest --coverage).** You will want to run jest yourself because it's faster. DON'T. The skill produces grades, gates, and deployment readiness. Your hand-rolled coverage command produces numbers without context.

6. **Continuing after "a good batch."** You will feel done after writing 5-10 test files. You are not done. The self-audit loop terminates at ZERO GAPS, not at "feels like enough." Check: are there untested files with logic? If yes, keep going.

7. **Flipping bug assertions to Category B.** You will find bugs, write tests that assert BROKEN behavior (passing tests), and report them as "bugs found" without realizing the contradiction. ALL TESTS PASS + BUGS FOUND = YOUR ASSERTIONS ARE BACKWARDS. You MUST rewrite each bug test to assert correct behavior (making it FAIL), then isolate it in Category B. You will rationalize "but the test proves the bug exists by showing the broken output." NO. A passing test is not a bug proof — it's a regression AGAINST the fix. The fix will break your test. Flip it.

8. **Skipping the RULE 22 structural check (all 4 elements).** You WILL write tests that import the module but only assert `toBeDefined()` or `typeof === 'function'`. These are existence checks, not behavioral tests. Every `it()` block MUST have a CALL (method invocation with actual inputs) and an ASSERT ON OUTPUT (checking the return value or side effect of that call). If you wrote `expect(service.validateToken).toBeDefined()` instead of `expect(await service.validateToken(forgedJwt)).toBeNull()`, you wrote nothing. The first proves the method exists (which TypeScript already guarantees). The second proves forged tokens are rejected (which is what the code SHOULD do). RULE 22 is the difference between "tests exist" and "tests prove something."

### Verification before reporting "done":

```
BEFORE you produce your final summary, verify ALL of these:
□ .qa/domain-invariants.md exists with ≥5 invariants AND ≥5 suspicious patterns
□ Every suspicious pattern has at least one test that targets it
□ No Agent tool calls in your conversation (grep yourself)
□ .qa/quality-assessment.json was produced by the CQA skill (not hand-written)
□ Tests pass (run the suite one final time)
□ You stated invariants/patterns BEFORE writing each test file
□ The largest source file by line count has a test that invokes its main method
□ RULE 22 STRUCTURAL CHECK: Every it()/test() block has all 4 elements (IMPORT,
  INSTANTIATE, CALL, ASSERT ON OUTPUT). No test only asserts toBeDefined/typeof.
  No test reads source files. Every test invokes the code under test at runtime.
□ MUTATION RESISTANCE SPOT CHECK: Pick 3 random tests. For each, mentally introduce
  the bug it claims to catch. Would the test fail? If not, rewrite it.
□ Bug count > 0 (if you found zero bugs in a real codebase, you weren't looking)
□ ASSERTION DIRECTION CHECK (CRITICAL): If bug count > 0 AND all tests pass → VIOLATION.
  You wrote tests that assert BROKEN behavior. Go back and rewrite every bug-related
  test to assert CORRECT behavior. Those tests MUST FAIL. Then isolate them as Category B.
□ Category B tests exist in a separate location (testPathIgnorePatterns or .qa/category-b/)
  and are excluded from the main test run. They FAIL when run independently.
□ Category A tests (passing) and Category B tests (failing) are in SEPARATE commits/directories.
  The final summary explicitly states the count for each category.
```

**If ANY box is unchecked, you are NOT done. Fix it before reporting.**

### ASSERTION DIRECTION ENFORCEMENT GATE (AUTOMATIC — runs after final test suite)

**After running the full test suite for verification, execute this check:**

```
BUG_COUNT=$(grep -c "^|" .qa/bugs-found.md 2>/dev/null || echo 0)
TEST_FAILURES=$(npx jest --no-coverage 2>&1 | grep -oP '\d+ failed' | grep -oP '\d+' || echo 0)

if [ "$BUG_COUNT" -gt 0 ] && [ "$TEST_FAILURES" -eq 0 ]; then
  echo "❌ ASSERTION DIRECTION VIOLATION DETECTED"
  echo "   You found $BUG_COUNT bugs but ALL tests pass."
  echo "   This means your bug tests assert BROKEN behavior (they pass on buggy code)."
  echo "   FIX: Rewrite each bug test to assert CORRECT behavior → it will FAIL."
  echo "   Then move failing tests to Category B isolation."
  echo ""
  echo "   Example of what you did WRONG:"
  echo "     expect(serviceResolved).toBe(false)  // asserts the bug EXISTS — WRONG"
  echo "   What you MUST do instead:"
  echo "     expect(serviceResolved).toBe(true)   // asserts correct behavior — FAILS proving bug"
  exit 1
fi
```

**This gate MUST pass before you can produce the final summary.** If it fails, go back and rewrite every test that documents a bug. The test must assert what the code SHOULD do, not what it currently does wrong.

**What "Category B isolation" means in practice:**
1. Create a directory like `src/__category_b__/` or use `testPathIgnorePatterns` in jest config
2. Move all bug-asserting tests (the ones that FAIL) into that isolation
3. The main `npx jest` run should pass (Category A only)
4. `npx jest --testPathPattern="category.b"` should FAIL (proving bugs exist)
5. Document this in .qa/bugs-found.md with the exact command to reproduce each failure
