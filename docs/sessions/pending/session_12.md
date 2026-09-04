# Session 12 — MongoDB Atlas Search-Backed `CacheBackend` (Design Only — Not Ready to Execute)

**Status:** pending — **design/decision doc only; do not start via the normal "start the next
session" protocol until every `NEEDS HUMAN DECISION` below is resolved.**
**Thread:** none yet. Proposed new thread, **`NEEDS HUMAN DECISION`**: neither existing thread
(`Line B: CMS v3.3 migration`, `Evaluation & Statistical Rigor`) fits — see "Why this session is
unusual" below. Working name: `Phase 2: production candidate-retrieval scaling`.
**Estimated size:** L — new infra dependency (MongoDB/Atlas Search), a new module, a new
testcontainer pattern for this repo, and cross-repo context (`cms-hte-patient-matching-service`,
currently in its own design phase).

> Read `../conventions.md` first.

## Why this session is unusual

Every other session in this backlog traces to a specific line in `docs/handoff/README.md`
(Line A/Line B) or a specific CMS v3.3 spec section — `conventions.md`'s "Scope anchor" rule.
**This one can't.** `docs/handoff/README.md` §2's two lines of work are both about the *matching
algorithm* (DOB/gender tuning, and replacing the weighted-rule scorer with CMS v3.3
Probability-of-Collision). Neither says anything about candidate-retrieval infrastructure. The
CMS v3.3 spec itself is silent on backend implementation entirely — Table 2 defines *which*
field combinations approve a match, not *how* a system should fetch candidates to check them
against.

This session exists because of a **different, external motivation**: a sibling repo,
`cms-hte-patient-matching-service`, is currently being designed (as of 2026-09-04) to wrap this
package's `PatientMatcherService`/`MatchingEngine` as a production HTTP microservice. That
design surfaced two things worth bringing back here rather than solving entirely in that repo:

1. `DuckDBCache`'s fuzzy search is an O(n) Python loop (`duckdb_cache.py::_fuzzy_search` pulls
   every distinct value for a field and runs `DamerauLevenshtein.distance` in Python) — a real
   scaling concern once a service runs this per-request against a non-trivial candidate
   population.
2. If that service runs with Kubernetes HPA (2-10+ replicas, per the sibling design's reference
   architecture, `person-matching-service`), each replica building/refreshing its **own**
   in-process `DuckDBCache` means N independent caches with no shared state — consistency drift
   and duplicated upstream (FHIR server) load, scaling with replica count.

A MongoDB Atlas Search-backed `CacheBackend` would address both: Atlas Search replaces the O(n)
Python fuzzy loop with an indexed search, and a shared Mongo store replaces N independent
in-process caches with one. But this repo's own `docs/PROJECT_MAP.md` states plainly: **"This
repo is a from-scratch build of [the CMS v3.3] engine, done in isolation — no production
traffic, no deploy target... Connecting it to production ('Phase 2') is a separate, currently
unscoped effort in those other repos."** Whether "those other repos" now includes
`cms-hte-patient-matching-service`, and whether that means *this* repo's scope has quietly
grown to include production-backend work, is exactly the kind of call this doc can't make on
its own — see Open Questions.

This doc exists to capture the design **before it's lost**, the same way session_7 captured the
delegated-access design discussion — not to claim this is scoped, sized, or ready for a feature
branch.

## Related prior art already in this backlog

`index.md`'s "Candidate future sessions" already lists: *"Add a real indexed blocking key to
`InMemoryBackend.search()` (e.g. by `(soundex(last_name), dob_year)`), replacing its current
O(n) linear-scan-per-query behavior... matters once actual `match()`/`match_batch()` calls need
to scale against a large corpus."* That item is about improving the **in-process** backend.
This session proposes a **different, larger step**: an external, shared backend, which is a
bigger commitment (new infra dependency, new test pattern, cross-repo implications) than an
in-process indexing improvement. If the human decision below is "not yet" or "no," that
smaller, already-logged item remains the lower-risk way to address the same O(n) concern without
taking on MongoDB as a dependency at all.

## Outcome purpose

Add `MongoAtlasCache`, a new `CacheBackend` implementation (alongside the existing
`DuckDBCache`) backed by MongoDB + Atlas Search, so that a production wrapping service has the
option of a shared, indexed candidate store instead of N independent in-process DuckDB caches.
Ships as a `CacheBackend` — the same abstraction `DuckDBCache` already implements — so it plugs
into the existing `CacheMatchingBackend` adapter with **zero changes** to `MatchingEngine`,
`PatientMatcherService`, or `CacheMatchingBackend`.

**Scope anchor caveat**: unlike every other session, this Outcome purpose does not trace to
`docs/handoff/README.md` or the CMS spec — see "Why this session is unusual" above. Per
`conventions.md`'s own rule ("if it doesn't [name a scope anchor], add that sentence now, before
closing out; don't let a session merge without it"), **this session must not move past
`pending/` until Open Question 1 below is resolved and a real anchor (or an explicit charter
change to `PROJECT_MAP.md`) exists.**

## Upstream sessions (must be completed first)

None in this repo's numbered backlog. The `CacheBackend`/`DuckDBCache`/`CacheMatchingBackend`
code this session extends predates the session-tracking system — it shipped in the original
`3abc37e` commit ("add the initial patient_matching implementation with normalization,
matching, cache, FHIR client, IAL2 extraction, and API modules"), referenced in
`conventions.md` as PR #3 ("CMS matching v1: in-memory backend + demo notebook"). Treat that
commit as the implicit prerequisite artifact, not a session dependency.

## Downstream sessions (unblocked by this one)

None currently authored in this repo. The actual consumer is `cms-hte-patient-matching-service`
(a different repo, currently in its own design phase) — this session does not wire anything
into that service; it only makes the `CacheBackend` option available for that service's own
design to choose or not choose.

## Upstream data/system dependencies

- **A MongoDB Atlas Search-capable MongoDB instance for testing.** This repo has never had a
  MongoDB dependency before. Follow `person-matching-service/tests/containers/mongodb.py`'s
  proven pattern: the `mongodb/mongodb-atlas-local:8.0.13` Docker image bundles `mongot` (the
  Atlas Search process), so Atlas Search is testable via `testcontainers` without a real Atlas
  cluster or network access. No new external credentials/service needed for testing.
- No FHIR server, no real patient data — per the PHI/data-handling guardrail, this session's
  tests use only synthetic fixture data (small, hand-built patient dicts), the same way
  `test_duckdb_cache.py`-equivalent tests presumably already do for `DuckDBCache`.

## Downstream data/system dependencies

None. This session does not touch any deployed system — there is none in this repo.

## Scope

### In scope

- New module `patient_matching/cache/mongo_atlas_cache.py`: `MongoAtlasCache(CacheBackend)`,
  implementing all 5 abstract methods (`upsert_patients`, `search_by_field`, `get_patient`,
  `count`, `clear`, `close`).
  - Schema mirrors `DuckDBCache`'s normalized two-collection shape: `patients` (`patient_id`,
    `fhir_resource`) and `field_values` (`patient_id`, `field_name`, `value`).
  - `search_by_field(field_name, value, fuzzy=False)`:
    - `fuzzy=False` → a plain indexed Mongo query (`{field_name, value}` against a compound
      index) — no `$search`, same reasoning `DuckDBCache`'s exact path uses.
    - `fuzzy=True` → an Atlas `$search` compound query (`filter: [{equals: {path:
      "field_name", ...}}]`, `must: [{text: {path: "value", query: value, fuzzy: {maxEdits: 1,
      prefixLength: 0}}}]`), mirroring the index/query shape already proven in this org in two
      places: `patient_matching/fuzzy/fuzzy_db/backends/mongodb.py::_search_atlas` (this
      package's own unused fuzzy toolkit) and `person-matching-service`'s
      `AtlasSearchStrategy`.
    - Wrap the `$search` call in try/except → log + return `[]` on failure, mirroring
      `AtlasSearchStrategy.search`'s graceful degradation (see Open Question 3).
  - `upsert_patients`: `bulk_write` upserts to `patients`; delete+reinsert `field_values` per
    patient (same approach `DuckDBCache` uses).
- `pymongo` as a proper dependency. `pyproject.toml` currently has a stray
  `[[tool.mypy.overrides]] module = ["pymongo.*"]` with **no corresponding runtime
  dependency** — add it properly, likely as a new optional extra (`[project.optional-dependencies]
  mongo = ["pymongo>=4"]`), consistent with the existing `fuzzy[...]` extras pattern.
- A benchmark/perf test (not a correctness test) comparing round-trip count and latency for a
  representative rule set against a realistic candidate-pool size — see Open Question 2 for
  why this is load-bearing before this backend is recommended for real use.
- Unit + testcontainer tests (see "Unit tests required").

### Out of scope

- Wiring `MongoAtlasCache` into any deployed service. That decision belongs to
  `cms-hte-patient-matching-service`'s own design, not this session.
- Any change to `MatchingBackend`, `CacheMatchingBackend`, or `MatchingEngine`'s call pattern
  (e.g. a batched/prefetch search API) — see Open Question 2. Not built speculatively; only
  worth doing if the benchmark in this session's own scope shows the current per-rule,
  per-criterion call pattern is actually a problem.
- `CacheManager`/`FhirClient` changes — this session only adds a `CacheBackend` implementation;
  populating it from a real FHIR server in production is the wrapping service's concern.
- Any change to Table 2 rules, collision probabilities, or matching behavior — this is
  infrastructure, not rule-changing work. The statistical rigor gate does not apply (same
  exemption as sessions 1 and 2, which also don't touch rule behavior).
- Replacing or deprecating `DuckDBCache` — ships as an additional option, not a replacement.

## Tasks

1. Add `pymongo` to `pyproject.toml` as an optional extra (mirror the `fuzzy` extras pattern).
2. Write `patient_matching/cache/mongo_atlas_cache.py` per the "In scope" section above.
3. Write the Atlas Search index definition this backend expects (as a committed JSON file, e.g.
   `patient_matching/cache/mongo_atlas_index.json`, mirroring how `person-matching-service`
   documents its index shape in `docs/hybrid-full-text-search-practitioner.json`) — this is
   documentation/setup instructions, not something the backend can create programmatically
   against a real Atlas cluster (index creation is a cluster-admin action).
4. Add a `testcontainers` fixture for `mongodb/mongodb-atlas-local:8.0.13`, adapted from
   `person-matching-service/tests/containers/mongodb.py` (same `directConnection=true` /
   `runner healthcheck` wait-strategy gotchas apply).
5. Write unit + testcontainer tests (see below).
6. Write the benchmark test comparing `MongoAtlasCache` vs. `DuckDBCache` round-trip
   count/latency for a full 38-rule match against a fixture candidate pool of a chosen
   realistic size (**`NEEDS HUMAN DECISION`** on what "realistic" means — see Open Question 4).
7. Document the tradeoff (round-trip risk, shared-state benefit) directly in this backend's
   module docstring, so a future reader choosing between `DuckDBCache` and `MongoAtlasCache`
   sees the tradeoff without needing this session doc.

## Unit tests required

File: `patient_matching/cache/tests/test_mongo_atlas_cache.py` (new), following this repo's
parameterization convention (`pytest.mark.parametrize`, plain pytest classes).

- `search_by_field(..., fuzzy=False)` returns exact matches only, and returns `[]` for a
  value with no exact match — mirroring whatever `test_duckdb_cache.py`'s exact-path
  assertions look like today (read that file first; match its structure, don't diverge
  gratuitously).
- `search_by_field(..., fuzzy=True)` returns a known near-duplicate (edit distance 1) and
  excludes a known non-match, against the `mongodb-atlas-local` testcontainer with the index
  from Task 3 actually created.
- `upsert_patients` is idempotent (upserting the same patient twice doesn't duplicate
  `field_values` rows/documents).
- Atlas `$search` failure path: simulate a search error (e.g. query against a collection with
  no index yet) and confirm `search_by_field(..., fuzzy=True)` returns `[]` and logs rather than
  raising.
- `CacheMatchingBackend(MongoAtlasCache(...))` produces the same `MatchingEngine.match()`
  outcome as `CacheMatchingBackend(DuckDBCache(...))` for the same fixture patient/candidate
  set — an equivalence test, per `conventions.md`'s "a behavior-preserving change... carries an
  equivalence test" principle. This is the test that actually proves the new backend is a
  drop-in, not just structurally similar.
- Benchmark test (Task 6) — not a pass/fail correctness assertion; report round-trip count and
  p50/p99 latency as output, per `conventions.md`'s "no silent caps" spirit (see Open Question 4
  for what "realistic" pool size means, if not yet decided this can run against a placeholder
  size with that flagged in the test's own docstring).

## Validation (definition of "resolved")

- [ ] `MongoAtlasCache` exists and implements all 5 `CacheBackend` abstract methods.
- [ ] `search_by_field` exact and fuzzy paths both pass their tests against the
      `mongodb-atlas-local` testcontainer.
- [ ] The Atlas `$search` failure path returns `[]` + logs rather than raising.
- [ ] The equivalence test (`MongoAtlasCache` vs. `DuckDBCache` producing the same
      `MatchingEngine.match()` outcome) passes.
- [ ] The benchmark test runs and reports round-trip count + latency (no fixed pass/fail
      threshold required for this session — this is exploratory data for Open Question 2, not
      a gate).
- [ ] `pymongo` is declared as a proper dependency (extra), not just referenced in a mypy
      override with no runtime install.
- [ ] `make tests` is green (full suite, no regression to `DuckDBCache`/`CacheMatchingBackend`
      tests).
- [ ] `make run-pre-commit` is clean.
- [ ] Statistical rigor gate: **exempt** — this session doesn't touch rule behavior.
- [ ] This session's Outcome purpose either (a) names a real scope anchor once Open Question 1
      resolves, or (b) the session is rejected/deferred if the answer is "this doesn't belong
      in this repo."

## Open questions

- **`NEEDS HUMAN DECISION — Sean (project lead) / Imran`**: Does this repo's charter now
  extend to production-backend infrastructure work, given `cms-hte-patient-matching-service` is
  being actively designed against it? `docs/PROJECT_MAP.md` currently says this repo has "no
  production traffic, no deploy target" and that Phase 2 is unscoped "in those other repos."
  If the answer is "yes, and `cms-hte-patient-matching-service` is that Phase 2," this session
  needs `PROJECT_MAP.md` updated as part of its own close-out (not left silently stale). If the
  answer is "no" or "not yet," this session should move to `rejected/` (kept, not deleted, per
  `conventions.md`) rather than proceeding, and the smaller in-process-indexing item already in
  `index.md`'s "Candidate future sessions" is the right-sized alternative.
- **`NEEDS HUMAN DECISION — whoever owns both repos' architecture`**: Should Atlas Search
  integration live in *this* package as a `CacheBackend` (this session's proposal), or entirely
  in the wrapping service as a request-scoped prefetch that hands a pre-fetched candidate list
  to the existing `InMemoryBackend` (mirroring `person-matching-service`'s actual pattern: one
  broad search per request, then local scoring, avoiding the round-trip-per-rule risk below
  entirely)? This session assumes the former because it's the lower-effort, drop-in-shaped
  option, but the latter avoids Open Question 3 entirely by construction. Recommended default
  if this needs to be decided without further discussion: ship this session's `CacheBackend`
  version behind the opt-in framing already in "Out of scope," and let
  `cms-hte-patient-matching-service`'s own design doc decide which one it actually uses — the
  two approaches aren't mutually exclusive as long as this session doesn't hard-couple the
  package to one choice.
- **Not a human-decision item, but load-bearing — resolve via the benchmark itself, not
  argument:** `MatchingEngine.match()` calls `backend.search()` once per Table 2 rule (~38
  rules), and `CacheMatchingBackend.search()` calls `cache.search_by_field()` once per
  criterion within that rule. With `DuckDBCache` this is cheap in-process SQL; with
  `MongoAtlasCache`, a naive implementation means dozens of real network round-trips per match
  request. Recommended default: ship as opt-in (per "Out of scope" above), measure via Task 6's
  benchmark, and only consider a batching/prefetch API change if the benchmark shows it's
  actually a problem at the pool sizes `cms-hte-patient-matching-service` expects to run
  against.
- **`NEEDS HUMAN DECISION — whoever sizes cms-hte-patient-matching-service's expected
  production candidate-pool size`**: the benchmark in Task 6 needs a "realistic" candidate-pool
  size to be meaningful. No one has provided this yet (it's Open Question 5 in the sibling
  service's own design doc, referring to the same underlying unknown). Without it, Task 6 can
  still run against a placeholder size, but its result won't be conclusive for Open Question 2
  above.

## Execution notes

Not yet executed — this is a design-only pass, opened as a PR per `conventions.md`'s "every
session ends with a PR" rule, specifically to surface the `NEEDS HUMAN DECISION` items above
for review before any code is written. Per `conventions.md`'s "Open-questions handling": "The
executing agent resolves every `NEEDS HUMAN DECISION` item before writing any code" — none of
Tasks 1-7 above have been started.
