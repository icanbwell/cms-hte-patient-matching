# Bug Class Patterns

Each `.md` file in this directory defines a bug class — a structural code shape that produces a specific kind of defect. The unit-test-master skill loads ALL patterns on every `--full-repo` run and sweeps the codebase for matches.

Patterns describe code shapes, not events. Keep them that way: a pattern is reusable across repositories precisely because it is stated generically. Do not record specific occurrences, locations, dates, tenant or vendor names, or ticket references in these files — that detail belongs in the run summary and the tracker.

## File Format

```yaml
---
id: short-name-for-the-bug-class
class: short-name-for-the-bug-class
impact_if_present: critical|high|medium
pattern_origin: >
  The code shape that produces this class, stated structurally. Describe the flaw,
  not an occurrence of it.
---

## Root Cause Pattern
What structural code flaw causes this class of bug, and why it survives ordinary testing.

## Detection Heuristic
Grep patterns, file patterns, or structural checks to find all instances.

## Test Template
How to write a failing test for each match found.

## Where This Class Tends To Live
Categories of code to sweep, and what to check in each. Categories, not file paths —
a fixed list of locations goes stale faster than the heuristic does.
```

## How Patterns Are Used

1. On `--full-repo` or `--incident` runs, the skill reads ALL pattern files
2. For each pattern, it runs the detection heuristic against the codebase
3. For each match, it checks if a test already exists
4. If not, it writes a failing test using the template
5. Matches found during a run are reported in the run summary, not appended to the pattern file
