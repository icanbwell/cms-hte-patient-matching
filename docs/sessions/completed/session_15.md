# Session 15 — Remove FastAPI + Docker: this repo is a pure Python package

**Status:** completed — executed 2026-09-06, same conversation as session 14, on the same
branch (`session-14/async-cache-backend`, [PR #48](https://github.com/icanbwell/cms-hte-patient-matching/pull/48),
merged 2026-09-07) since it directly touches files that PR already modifies.
**Thread:** `Phase 2: production candidate-retrieval scaling` (same thread as sessions 12/13/14).
**Estimated size:** M — a full Dockerfile/docker-compose removal plus an HTTP-layer removal,
touching Makefile, pyproject.toml, README, CI comments, and the MongoDB testcontainer fixtures.

> Read `../conventions.md` first.

## Why this session exists

While reviewing session 14's async work, Imran asked whether the package's public entry points
were all async. Answering that required walking `patient_matching/api/__init__.py`'s exports,
which surfaced `create_app()` — a full FastAPI application (`/Patient/$match`, `/match/ial2`,
`/health`) that's been in this repo since its very first commit. Imran's reaction: **this repo
is not supposed to implement a web service at all.** The sibling repo
`cms-hte-patient-matching-service` (confirmed to exist at
`~/git/cms-hte-patient-matching-service`, real GitHub remote
`icanbwell/cms-hte-patient-matching-service`) is the FastAPI layer — it wraps this package's
`PatientMatcherService`/`MatchingEngine` as a production HTTP microservice (per
`docs/PROJECT_MAP.md`'s own Phase 2 description, and confirmed directly by Imran in this
session). This repo shipping its own parallel FastAPI app was true redundancy, not a reference
implementation kept on purpose.

Once the FastAPI removal was under way, Imran extended the direction further: **this project
should be a pure Python project, like `~/git/helix.personmatching`.** Checked directly —
`helix.personmatching` has no Dockerfile, no docker-compose.yml, and no Docker anywhere in its
Makefile; `uv run pytest` runs directly on the host. Confirmed via `AskUserQuestion` before
executing (full Docker removal, not a partial keep): **yes, remove Docker entirely, and
simplify the MongoDB testcontainer fixtures accordingly**, since the docker-outside-of-docker /
self-attach-to-network mechanism those fixtures grew (sessions 12/14's Dockerfile-fix work)
existed *only* because `make tests` used to run pytest inside a `dev` container. Once pytest
runs on the host like `helix.personmatching`, testcontainers talks to the host Docker daemon
directly and that whole mechanism is dead weight.

## What changed

### FastAPI removal
- Deleted `patient_matching/api/app.py` and `patient_matching/api/tests/test_app.py`.
- `patient_matching/api/__init__.py` — no longer exports `create_app`; only
  `PatientMatcherService`/`ServiceConfig` (the framework-agnostic orchestrator the `-service`
  repo actually consumes). Module docstring rewritten to say so explicitly.
- `pyproject.toml` — removed `fastapi`/`uvicorn` from `dependencies`, removed the `api` extra
  entirely, removed both from the `all` extra.
- `uv.lock` regenerated — 4 packages dropped (`fastapi`, `starlette`, `uvicorn`, and
  `annotated-doc`, a `fastapi` transitive dep); everything else unchanged, still JFrog-sourced.
- `README.md` — removed the "HTTP API" overview bullet, the FastAPI box from the architecture
  diagram, the `[api]` install extra, the entire "Run the HTTP API" section + curl example, and
  reworded the `patient_matching.api` module-reference entry. Added an explicit pointer to
  `cms-hte-patient-matching-service` as where the HTTP layer actually lives.

### Docker removal
- Deleted `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docker.env`, `.env.example` (the
  last two were Docker-`env_file`-era artifacts with no consumer once docker-compose is gone —
  `helix.personmatching` has no equivalent file either; JFrog creds are exported directly into
  the shell per its own README convention, which this repo's README already documented as an
  option).
- **`Makefile`** — fully rewritten to the `helix.personmatching` pattern: `sync`, `uv.lock`,
  `devsetup`, `tests` (`uv run pytest .`), `run-pre-commit`/`setup-pre-commit`/
  `clean-pre-commit`, `dist`/`testpackage`/`package` (these three already matched, unchanged).
  Removed: `build`, `up`, `down`, `shell` (all Docker-specific; `up`/`down` were already dead
  code before this — their health-check logic referenced a `patient_matching_service` container
  name that never existed in `docker-compose.yml`, which only ever defined a `dev` service).
  JFrog creds now bridge directly from `JFROG_READ_USER`/`JFROG_READ_TOKEN` env vars into
  `UV_INDEX_JFROG_USERNAME`/`PASSWORD` (`?=` in the Makefile), matching
  `helix.personmatching`'s own Makefile exactly.
- **`patient_matching/cache/tests/containers/network.py`** — removed `self_container_id()` and
  the "attach own container to the test network" step from `docker_network()`. The network
  fixture itself stays (test-container isolation), but nothing about it depends on pytest being
  containerized anymore.
- **`patient_matching/cache/tests/containers/mongodb.py`** — `MongoDBService` no longer has
  `internal_url`/`external_url`/a `connection_string` *property* that branches on
  containerization; it's now a single `connection_string` field, always the host-mapped URL.
  Dropped the now-unused network alias (`with_network_aliases`) on the container too.
- **`docs/sessions/conventions.md`** — updated the test-runner convention (no more `docker
  compose run --rm dev pytest ...`), the "Exact commands for this project" example block, and
  the security-guardrail line referencing `docker.env` (now `.env`, the actual gitignored file).
- **`.github/workflows/build_and_test.yml`** — updated a comment that referenced "the
  Alpine-based Dockerfile" and "the production Dockerfile" as context for why CI runs on plain
  `ubuntu-latest`; that comparison point no longer exists. The workflow's actual steps needed no
  change — it already ran directly on the runner via `uv`, never through Docker.
- **`CONTRIBUTING.md`** — `make init`/`make up` → `make devsetup` (matches the new Makefile).

### Deliberately left untouched
- **`ROOTIO_MIGRATION_LEARNINGS.md`** — a cross-repo historical learnings doc that cites this
  repo's (now-deleted) Dockerfile as evidence from when it existed. Frozen record, not a live
  "how this repo works" doc; not rewritten, same principle as not editing
  `docs/sessions/completed/*.md`.
- **`patient_matching/api/service.py`** and its tests — `PatientMatcherService` has no FastAPI
  import at all; it's exactly the framework-agnostic orchestrator
  `cms-hte-patient-matching-service` is meant to consume. Kept in place, unchanged by this
  session (session 14 already made it async).

## Execution notes

Verified with the same rigor as sessions 12/14: `mypy --strict` and the full test suite (`uv run
pytest .`, now the *only* way to run it — no more parallel Docker-based verification path to
also check) both clean after every structural change. `docker_network`'s Docker-unavailable
skip path (added in session 12, kept in this simplification) was re-verified the same way as
before: pointing `DOCKER_HOST` at an unreachable address and confirming every Mongo-dependent
test skips cleanly rather than erroring.

## Left open, not self-merged

Same reasoning and same stack as sessions 12/14 — left in `in_review/`, landed on the
`session-14/async-cache-backend` branch (PR #48) rather than a new stacked branch, since it
directly modifies files that PR already touches (`patient_matching/api/__init__.py`,
`pyproject.toml`, `uv.lock`, `README.md`) and splitting it into yet another stacked PR layer
would add review overhead without a clear benefit. Flagged to Imran that PR #48's title/scope
description needs updating to reflect this — it's no longer just "make things async."
