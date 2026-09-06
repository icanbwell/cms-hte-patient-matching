# Session 14 — Async cache/matching pipeline (avoid blocking the event loop)

**Status:** in_review — executed 2026-09-06 on branch `session-14/async-cache-backend`, PR
[#48](https://github.com/icanbwell/cms-hte-patient-matching/pull/48), **stacked on PR #45
(session 12, `session-12/mongo-atlas-cache`)**. Cannot merge until PR #45 merges first — the
branch point is `session-12/mongo-atlas-cache`, not `main`, because this session needs
`MongoAtlasCache` to already exist to have anything to fix.
**Thread:** `Phase 2: production candidate-retrieval scaling` (same thread as sessions 12/13).
**Estimated size:** M — mechanical but wide: touches the cache interface, both cache
implementations, the matching engine/manager, the service layer, the FastAPI handlers, and
every test in all of those modules.

> Read `../conventions.md` first.

## Why this session exists

Raised directly by Imran while reviewing PR #45: `MongoAtlasCache` uses plain synchronous
`pymongo.MongoClient`, called synchronously all the way up through
`CacheMatchingBackend.search()` → `MatchingEngine.match()` → `PatientMatcherService.match_patient()`
→ FastAPI's `async def fhir_match()` handler — with no `await`, no
`run_in_executor`/`anyio.to_thread.run_sync` anywhere. `mongo_atlas_cache.py`'s own module
docstring already admits "a full match can mean dozens of round-trips to Atlas," and this
session's benchmark shows p99 latency ~0.7s for a single match. Every one of those round-trips
ran directly on the asyncio event loop thread, meaning a single slow `MongoAtlasCache`-backed
request would stall every other concurrent request on that FastAPI worker for the duration —
directly undercutting the feature's own motivation (a shared cache so multiple replicas don't
duplicate load, when in practice each replica could still only serve one slow request at a
time).

**2026-09-06, same day, addendum.** Imran then asked directly: "are all the calls to this
package now async?" — answer at that point was no. A repo-wide sweep for `httpx.`/`requests.`/
`urlopen`/`socket.`/`urllib` found two more real network-I/O surfaces this first pass hadn't
touched: `FhirClient` (synchronous `httpx.Client`, used by `CacheManager`'s ETL loop) and
`TokenVerifier`/`IAL2Extractor` (`PyJWKClient`'s blocking JWKS fetch, used by
`PatientMatcherService.match_from_token()` — i.e. the `/match/ial2` endpoint has the exact same
class of bug `/Patient/$match` had). Explicit instruction: **"All calls should be async in this
project unless async does not help them."** Converted both into this same PR/branch — see the
second "What changed" block below. Everything else in the package (`NormalizationManager`,
`FieldExtractor`/`FieldComparator`, `IAL2Claims`/`IAL2ToFhirConverter`,
`MatchingEngine.evaluate_pair()`) is pure in-memory computation with no I/O, confirmed by the
same repo-wide grep — correctly left synchronous, since async wouldn't help there.

## Design decisions (both made directly by Imran, no other options explored)

1. **Uniform async `CacheBackend` interface**, not a split sync/async interface. `DuckDBCache`
   implements the same `async def` methods as `MongoAtlasCache`, even though it has no real I/O
   to yield on — one interface, one call chain, no branching logic anywhere for which backend
   you have. The alternative (keep `DuckDBCache` synchronous, give `MongoAtlasCache` a separate
   `AsyncCacheBackend` interface) would have forced `CacheMatchingBackend`/`MatchingEngine`/etc.
   to either support two different backend shapes or wrap `DuckDBCache` in a thread executor
   anyway — no real simplicity win, and it was rejected.
2. **Land as a PR stacked on #45**, not a new branch off `main`, so this work could start
   immediately rather than waiting for #45 to merge first.

## What changed

Every method on `CacheBackend`, `MatchingBackend`, `MatchingEngine.match()`,
`MatchingManager.match()`/`match_batch()`, `CacheManager.build_cache()`/`refresh_cache()`/
`patient_count`, and `PatientMatcherService.match_patient()`/`match_from_token()` is now
`async def`. `MatchingEngine.evaluate_pair()` is the one deliberate exception — it never touches
a backend at all (used directly by `evaluation/rule_eval.py`-style batch scripts over millions
of precomputed pairs), so it stays fully synchronous.

- **`patient_matching/cache/cache_backend.py`** — `CacheBackend` ABC's 6 methods → `async def`.
- **`patient_matching/cache/duckdb_cache.py`** — same 6 methods → `async def` (trivial wraps;
  `_fuzzy_search`'s short-string fallback recurses into `search_by_field`, so it had to become
  `async def` too).
- **`patient_matching/cache/mongo_atlas_cache.py`** — genuine async conversion via pymongo's
  native `AsyncMongoClient`/`AsyncCollection` (pymongo 4.9+; this repo has 4.17.0). Two real
  pymongo API gotchas hit along the way (see Execution notes): `aggregate()`/
  `list_search_indexes()` are themselves coroutines that must be awaited to *get* the cursor,
  unlike `find()`, which returns an async-iterable cursor directly with no await needed on the
  call itself. Index creation moved out of `__init__` (which can't be `async`) into a lazy
  `_ensure_indexes()` called from every public method — see the collection-existence bug this
  caused, below.
- **`patient_matching/matching/backend.py`** — `MatchingBackend.search()` → `async def`.
- **`patient_matching/matching/in_memory_backend.py`** — `InMemoryBackend.search()` →
  `async def` (trivial; still zero real I/O).
- **`patient_matching/cache/matching_adapter.py`** — `CacheMatchingBackend.search()` →
  `async def`, awaits each `cache.search_by_field()` call.
- **`patient_matching/matching/matching_engine.py`** — `match()` and
  `_evaluate_household_individual_rule()` → `async def`; `evaluate_pair()` untouched.
- **`patient_matching/matching/matching_manager.py`** — `match()`/`match_batch()` →
  `async def`.
- **`patient_matching/cache/cache_manager.py`** — `build_cache()`/`refresh_cache()`/
  `_refresh_internal()` → `async def`; `self._lock` switched from `threading.Lock` to
  `asyncio.Lock`; `patient_count` changed from a `@property` to an `async def` method (a
  property can't be async); `start_scheduled_refresh()` switched from APScheduler's
  `BackgroundScheduler` to `AsyncIOScheduler`, since `refresh_cache` is now a coroutine function
  a plain thread-based scheduler can't await. Note: `FhirClient.fetch_all_patients()` itself is
  still a synchronous generator (unconverted) — only the cache-write side of the ETL loop is
  awaited now. Converting the FHIR client is a separate, larger change, out of scope here.
- **`patient_matching/api/service.py`** / **`patient_matching/api/app.py`** — the whole
  `match_patient`/`match_from_token`/`_match_and_respond` chain → `async def`; the two FastAPI
  handlers (already `async def`) now actually `await` the service call instead of blocking the
  loop inside a coroutine.
- **Every test** in `patient_matching/cache/tests/`, `patient_matching/matching/tests/`,
  `patient_matching/api/tests/`, and `tests/_null_backend.py` updated to match — `async def
  test_...` plus `await` at each now-async call site, and every `DuckDBCache`/`MongoAtlasCache`
  pytest fixture converted to an async generator fixture.
- **`README.md`** — Quick Start and the "Choosing a Cache Backend" examples updated to show
  `asyncio.run(...)`/`await` usage; noted the uniform-async-interface rationale.

### Second pass: `FhirClient` and `TokenVerifier`/`IAL2Extractor`

- **`patient_matching/fhir_client/auth.py`** — `ClientCredentialsAuth.get_access_token()`/
  `_request_token()` → `async def`, take `httpx.AsyncClient` instead of `httpx.Client`.
  `invalidate()` untouched (no I/O).
- **`patient_matching/fhir_client/client.py`** — `fetch_all_patients()` is now an **async
  generator** (`async def ... -> AsyncGenerator[...]`, `async with httpx.AsyncClient(...)`,
  `yield` unchanged); `fetch_patient()`, `_authenticated_get()` → `async def`;
  `_create_http_client()` now returns `httpx.AsyncClient`. A genuine async conversion (httpx has
  native async support), not thread-offloaded.
- **`patient_matching/ial2_extraction/token_verifier.py`** — `verify()` and the
  `from_oidc_discovery()` classmethod → `async def`, both via `asyncio.to_thread()`. PyJWT's
  `PyJWKClient` (and the plain `urlopen()` in `from_oidc_discovery`) have no async API at all, so
  this is a deliberate thread-offload rather than a native async rewrite — it still moves the
  blocking JWKS/discovery HTTP call off the event loop, which is what "async where it helps"
  means for a dependency with no async alternative. The original blocking body of `verify()` is
  now a private `_verify_sync()` helper that `verify()` awaits via `to_thread`.
- **`patient_matching/ial2_extraction/ial2_extractor.py`** — `extract()`/`extract_claims()` →
  `async def`, await `self._verifier.verify(token)`. `IAL2Claims.from_token_claims()` and
  `IAL2ToFhirConverter.convert()` untouched — pure data mapping, no I/O.
- **`patient_matching/api/service.py`** — `match_from_token()` now awaits
  `self._ial2_extractor.extract(token)`.
- **`patient_matching/cache/cache_manager.py`** — `_refresh_internal()`'s fetch loop is now
  `async for patient_dict in self._fhir_client.fetch_all_patients(...)`.
- **Tests** — `fhir_client/tests/test_auth.py` and `test_client.py`: mocks switched from
  `MagicMock()` to `MagicMock(spec=httpx.AsyncClient)` (so `.post`/`.get` auto-become
  `AsyncMock`, since the spec class's methods are now coroutine functions — no need to
  hand-configure each one) and `__enter__`/`__exit__` → `__aenter__`/`__aexit__`.
  `ial2_extraction/tests/test_ial2_extractor.py`: same spec-based approach for the mocked
  `TokenVerifier`. `cache/tests/test_cache_manager.py`: `mock_fhir_client.fetch_all_patients`
  needed a small `_async_iter()` helper (a plain list isn't async-iterable) since
  `CacheManager` now does `async for` over it.

## Execution notes — real bugs the async conversion surfaced

**Methodology:** wrote all the source changes first, then ran `mypy --strict` across the whole
package and let its "Coroutine[...] has no attribute X — maybe you forgot await?" errors point
at every one of the ~500 call sites needing an `await`, rather than manually auditing each test
file by hand. This caught a real source bug immediately (`DuckDBCache._fuzzy_search`'s recursive
call into `search_by_field`) that a manual line-by-line pass could easily have missed. Full
`mypy` sweep across `patient_matching/` + `tests/` came back clean before running the suite.
Second-pass gotcha: my own ad-hoc `uv run mypy patient_matching tests` invocations weren't
passing `--strict`, unlike the pre-commit hook's actual invocation (`args: [--strict,
--python-version=3.12, --show-error-codes]`) — a bare `list` type-arg violation slipped through
my own checks and was only caught when I ran `pre-commit run` for real. Re-ran `mypy --strict`
directly against every file changed on this branch afterward to close that gap; all 29 clean.

1. **pymongo's `aggregate()`/`list_search_indexes()` are coroutines themselves** (must `await`
   to get the cursor), unlike `find()` (returns an async-iterable cursor directly, no await on
   the call). Confirmed directly via `inspect.iscoroutinefunction()` against pymongo 4.17.0's
   `AsyncCollection` rather than assumed — got this wrong on the first pass (`async for doc in
   self._field_values.aggregate(pipeline)` without awaiting `aggregate()` first) and mypy caught
   it immediately (`"Coroutine[...]" has no attribute "__aiter__"`).
2. **Lazy index creation broke a hidden assumption.** The old synchronous `MongoAtlasCache.__init__`
   created the two regular indexes eagerly, which — as an incidental MongoDB side effect —
   auto-created the `field_values` collection too. Moving index creation to a lazy
   `_ensure_indexes()` (required, since `__init__` can't be `async`) meant the collection no
   longer existed by the time test helpers called `create_search_index()` before any upsert,
   which fails with `NamespaceNotFound` (unlike a regular index, Atlas Search index creation
   does **not** auto-create the collection). Fixed by having the test helper call
   `await cache._ensure_indexes()` first.
3. **`AsyncMongoClient` is bound to the event loop it was created on.** The test suite's
   session-scoped Mongo fixture (shared across tests to avoid paying the Atlas Search index's
   ~60s setup cost per test) needs `pytest_asyncio.fixture(scope="session", loop_scope="session")`
   plus a matching `@pytest.mark.asyncio(loop_scope="session")` on every test class that uses it
   — without it, pytest-asyncio's default per-test event loop meant the shared client's teardown
   (`cache.clear()`) silently ran on a different loop than it was created on and failed, which
   surfaced as test data leaking between tests (counts off by exactly the previous test's rows)
   rather than an obvious error at first.
4. **An unspec'd `MagicMock()` doesn't auto-detect a spec class's async methods.**
   `test_service.py`'s mocked `IAL2Extractor` was a plain `MagicMock()`, so
   `mock_extractor.extract.return_value = {...}` configured a *sync* mock — awaiting it raised
   `TypeError: object dict can't be used in 'await' expression`. `MagicMock(spec=MagicMock)`
   only auto-creates `AsyncMock` for methods when given a `spec=<the real class>` to introspect;
   without it, every attribute is a generic `MagicMock` regardless of what the real method looks
   like. Fixed by passing `spec=IAL2Extractor`. This is the same pattern already used correctly
   elsewhere (`test_ial2_extractor.py`'s `MagicMock(spec=TokenVerifier)`,
   `test_client.py`/`test_auth.py`'s `MagicMock(spec=httpx.AsyncClient)`) — worth defaulting to
   `spec=` on any mock standing in for a class with async methods, rather than a bare
   `MagicMock()`, so a sync/async mismatch fails at mock-creation intent rather than at
   await-time.

**Full verification, twice per pass** (once via `uv run pytest` on host, once via `make tests` —
the actual Docker-Compose-wrapped gate, per PR #45's own established practice this session
inherited): **478 tests pass** on both passes, including the full `MongoAtlasCache` suite and
the docker-outside-of-docker network self-attach mechanism, inside the real `dev` image built
from the actual `Dockerfile`. `ruff check`/`ruff format --check`/`mypy --strict`/`bandit` all
clean on every changed file (29 files across both passes).

## Left open, not self-merged

Left in `in_review/`, not `completed/` — **cannot merge before PR #45 merges** (this branch is
stacked on it), and per this repo's convention a human should look at a change this wide
(touches the public API of every class in `patient_matching.cache` and
`patient_matching.matching`) before it lands regardless of stacking.
