# Session 13 — Publish `cms-hte-patient-matching` to PyPI

**Status:** pending — design captured, both blocking decisions resolved (package name and
publishing mechanism decided; the pypi.org pending publisher is registered — see Open Questions
1 and 2). Ready to size and execute as a real feature branch; no remaining blocker outside this
repo.
**Thread:** `Phase 2: production candidate-retrieval scaling` (same thread as session 12 —
distribution packaging for the sibling `cms-hte-patient-matching-service` to consume).
**Estimated size:** S — the packaging fixes are small and mechanical; this repo's
`python-publish.yml` already implements the chosen mechanism, and the pypi.org side is now set
up too.

> Read `../conventions.md` first.

## Why this session exists

Imran asked for a tech design for publishing this package to PyPI, specifically **the icanbwell
org's PyPI presence** (public pypi.org, not the internal JFrog Artifactory index this repo
already uses as its default `uv` index for consuming dependencies — those are two different
things; see "Two distinct 'PyPI' targets" below).

## Scope anchor (Outcome purpose)

`docs/handoff/README.md` §2 names the intended architecture directly: **"`helix.personmatching`
(current scoring library, PyPI)"** feeding **"`person-matching-service` (FastAPI FHIR `$match`,
prod for WellSense)"**. That is: the matching *algorithm* ships as an installable PyPI library,
and a separate FastAPI service consumes it as a normal pip dependency. `cms-hte-patient-matching`
(this repo) is the CMS v3.3 replacement for `helix.personmatching` in that same architecture, and
`cms-hte-patient-matching-service` (the sibling repo session 12 also references, currently in its
own design phase) is the replacement for `person-matching-service`. Confirmed directly:
`cms-hte-patient-matching-service/pyproject.toml` does **not** yet depend on this package at
all — it has no path to consume `PatientMatcherService`/`MatchingEngine` today except vendoring
or a git dependency. Publishing to PyPI is what makes the intended architecture (library + thin
service wrapper, mirroring `helix.personmatching` + `person-matching-service`) actually possible
for the CMS engine, the same way `person-matching-service`'s `pyproject.toml` today declares
`helix.personmatching>=3.0.1` as a normal PyPI dependency (confirmed: its `uv.lock` resolves that
from `https://artifacts.bwell.com/artifactory/api/pypi/virtual-pypi/simple` — JFrog's mirror of
public PyPI, not a git reference).

## Two distinct "PyPI" targets — don't conflate them

- **This repo's own dependency resolution** (`pyproject.toml`'s `[[tool.uv.index]] name = "jfrog"
  ... default = true`) already routes through JFrog Artifactory's `virtual-pypi` (a proxy/cache
  in front of public PyPI, per `~/git/bwell-repo-wiki/concepts/dependency-supply-chain.md`'s
  Root.io hardening migration). This is unrelated to this session and needs no change.
- **What this session is about**: publishing *this package* outward, to public pypi.org, under
  icanbwell's account — the same thing `helix.fhir.client.sdk`, `helix.personmatching`,
  `fhir-schema-py`, and `language-model-common` already do. Internal consumers (like
  `cms-hte-patient-matching-service`)
  will then pull it back in through the same JFrog `virtual-pypi` mirror, automatically, with no
  special config on their end — exactly how `person-matching-service` already consumes
  `helix.personmatching`.

## Current state — what's already here, and what's broken

Verified directly against this repo and five sibling icanbwell repos (`helix.fhir.client.sdk`,
`helix.personmatching`, `fhir-schema-py`, `language-model-common`, `device-codex`) before
proposing anything.

**Publishing mechanism: Trusted Publishing (OIDC) — decided.** Two different mechanisms exist
across these repos:

- **Token-based twine** (`helix.fhir.client.sdk`, `helix.personmatching`): plain API-token
  upload — `TWINE_USERNAME: __token__` / `TWINE_PASSWORD: ${{ secrets.PYPI }}`, no OIDC, no
  GitHub Environment. This is the org's longest-proven mechanism for exactly this kind of
  library-behind-a-service package — `helix.fhir.client.sdk` in particular is the highest-
  velocity package by far (releases land almost daily: `5.0.10` → `5.0.13` across
  2026-08-31 → 2026-09-04 alone; its `python-publish.yml` dates to 2021-03-29). Considered and
  **not chosen** for this repo — see below.
- **OIDC Trusted Publishing** (`fhir-schema-py`, `language-model-common`, and already what this
  repo's own `.github/workflows/python-publish.yml` implements): `permissions: id-token: write`,
  `environment: pypi`, `pypa/gh-action-pypi-publish`, no long-lived secret in GitHub at all. Also
  real and working (`language-model-common`'s last 5 releases via this exact mechanism all
  succeeded in ~30s each). **This is Imran's explicit choice for this repo** — no long-lived PyPI
  token sitting in GitHub secrets to leak or rotate, and it's the mechanism GitHub/PyPI
  themselves now recommend as the default for new projects.
- **Consequence: this repo's existing `python-publish.yml` needs no rewrite.** It already
  implements Trusted Publishing correctly (verbatim match for `fhir-schema-py`'s workflow), and
  `gh api repos/icanbwell/cms-hte-patient-matching/environments` confirms a `pypi` GitHub
  Environment already exists here (created 2026-09-03) with zero secrets — exactly right for
  OIDC, which needs none. The only remaining step is external to this repo: registering
  `cms-hte-patient-matching` as a **Trusted Publisher** on pypi.org itself (pypi.org →
  "Publishing" → "Add a pending publisher" — this works even before the project has ever been
  uploaded, naming the GitHub repo/workflow/environment it should trust) — see Open Question 2
  for who does it.

1. **`pyproject.toml` has no `[build-system]` table.** `helix.personmatching` and
   `fhir-schema-py` both declare `[build-system] requires = ["setuptools>=70.3.0", "wheel"]`,
   `build-backend = "setuptools.build_meta"`. Without it, `python -m build` falls back to the
   legacy root `setup.py`, which is stale and wrong:
   - `install_requires=[]` — building via `setup.py` today would ship a wheel with **zero**
     declared runtime dependencies, silently dropping every entry in `pyproject.toml`'s
     `dependencies` list.
   - `python_requires=">=3.10"`, conflicting with `pyproject.toml`'s `requires-python = ">=3.12"`.
   - `url="https://github.com/icanbwell/patient-matching-reference-implementation"` — a
     **different, separate repo** (found at `~/git/patient-matching-reference-implementation
     copy`), not this one. Copy-paste residue from wherever this repo's scaffold originated.
   - Duplicates `long_description`/classifiers that `pyproject.toml` already declares — two
     untracked sources of truth for the same metadata.
2. **A second, stray package directory exists**: `patientmatching/` (no underscore — just
   `__init__.py` + `py.typed`) sits at repo root next to the real `patient_matching/`.
   `setup.py`'s `packages=find_packages()` would pick up both, silently shipping an
   essentially-empty extra top-level package in the built wheel.
3. **`setup.cfg`'s `[mypy]`/`[tool:pytest]` sections duplicate `pyproject.toml`'s
   `[tool.mypy]`/`[tool.pytest.ini_options]`** (already the modern, actually-used config per
   `conventions.md`'s exact command list). `setup.cfg`'s copies are dead weight once `setup.py`
   is removed, except its `[flake8]` section — check whether anything still invokes flake8
   directly (ruff appears to be the actual lint tool per `.pre-commit-config.yaml`) before
   deciding whether `[flake8]` is also dead.
4. **`README.md`/`CONTRIBUTING.md` already document `make testpackage` / `make package`**, but
   these Makefile targets **don't exist yet** in this repo's `Makefile` — the docs describe
   commands that would currently fail. Every sibling repo checked (`helix.personmatching`,
   `fhir-schema-py`, `language-model-common`) has the matching real targets:
   ```makefile
   .PHONY: testpackage
   testpackage: build
   	uv run twine upload -u __token__ --repository testpypi dist/*
   .PHONY: package
   package: build
   	uv run twine upload -u __token__ --repository pypi dist/*
   ```
   (`TWINE_PASSWORD` sourced from the environment — a PyPI API token — not committed anywhere.)
   These are a **secondary, manual/local escape hatch** for ad hoc TestPyPI dry runs; every
   sibling repo keeps both this and the CI Trusted-Publishing workflow side by side, and none of
   them use the token-based path for a real `package:` PyPI release (`helix.personmatching`'s CI
   workflow does use a repo-level `PYPI` token secret rather than OIDC — the one sibling that
   differs — but its own `Makefile` `package` target still mirrors this same pattern for local
   use). `twine>=4.0.2` is already a `dev` dependency in this repo's `pyproject.toml`, so no new
   dependency is needed.
5. **Repo visibility**: `cms-hte-patient-matching` is a **private** GitHub repo. Publishing to
   PyPI makes the source (matching logic, Table 2/3 constants) publicly downloadable even though
   the GitHub repo itself stays private. Confirmed this is already accepted practice here, not a
   novel exception: `helix.personmatching`, `fhir-schema-py`, and `device-codex` are all private
   repos with packages already public on PyPI today.
6. **Name availability**: checked `pypi.org/pypi/<name>/json` directly — both `patient-matching`
   /`patient_matching` (PyPI normalizes `-`/`_` as equivalent) and `cms-hte-patient-matching`
   return 404 (unclaimed) as of 2026-09-04. No collision blocks either choice, but see Open
   Question 1 on which to pick.

## Outcome purpose

Make `cms-hte-patient-matching`'s `patient_matching` package installable via `pip install` from
public PyPI, so `cms-hte-patient-matching-service` (or any future consumer) can depend on it the
same normal way `person-matching-service` depends on `helix.personmatching` today — completing
the architecture parity described in `docs/handoff/README.md` §2.

## Upstream sessions (must be completed first)

None. Independent of sessions 6/8/12 — pure packaging/distribution work, touches no matching
logic.

## Downstream sessions (unblocked by this one)

None authored in *this* repo. The actual consumer is `cms-hte-patient-matching-service` (separate
repo, currently in its own design phase, per session 12) — this session doesn't wire anything
into that service; it only makes the dependency possible.

## Upstream data/system dependencies

- **A `cms-hte-patient-matching` pending Trusted Publisher on pypi.org**, naming this repo,
  `python-publish.yml`, and the `pypi` environment. **Done** — Imran created it in the same
  PyPI account/namespace ("imranq" space) that already owns `fhirschemapy`
  (`fhir-schema-py`'s published package), confirming this follows that exact precedent. See
  Open Question 2.
- No FHIR server, no patient data, no new runtime dependency.

## Downstream data/system dependencies

None. This does not touch any deployed system.

## Scope

### In scope

- Add `[build-system]`, `[tool.setuptools.packages.find]` (excluding `tests*`), and
  `[tool.setuptools.package-data]` to `pyproject.toml`, matching `helix.personmatching`'s pattern.
- Delete `setup.py` (superseded once `pyproject.toml` is self-sufficient — matches
  `helix.personmatching`/`fhir-schema-py`, neither of which ships one; `helix.fhir.client.sdk`
  keeps a trivial `from setuptools import setup; setup()` shim only because its CI still calls
  `python setup.py sdist bdist_wheel` directly — not needed here since this repo's
  `python-publish.yml` already uses `python -m build`, which needs no `setup.py` at all).
- Remove `setup.cfg`'s now-dead-duplicate `[mypy]`/`[tool:pytest]` sections; resolve whether
  `[flake8]` is still live before touching it.
- Resolve and remove (or intentionally document) the stray `patientmatching/` directory —
  see Open Question 5.
- Fix the stale GitHub URL in `pyproject.toml`'s project metadata (add a `[project.urls]` table
  pointing at `icanbwell/cms-hte-patient-matching`, since `setup.py` — the only place that URL
  currently lives — is being deleted).
- No change needed to `.github/workflows/python-publish.yml` — it already implements OIDC
  Trusted Publishing correctly (see "Current state" above).
- Add the `testpackage`/`package` Makefile targets (twine, token-based) that `README.md`/
  `CONTRIBUTING.md` already document but that don't exist yet. These stay token-based even
  though CI is OIDC-based — Trusted Publishing only works from within a GitHub Actions run (it
  authenticates via the runner's OIDC identity token, which doesn't exist on a local machine),
  so a local/manual TestPyPI dry run still needs a plain API token. This matches
  `fhir-schema-py`/`language-model-common` exactly: OIDC in CI, token-based twine in the
  `Makefile` for local use only.
- Do a TestPyPI dry run (`make testpackage`) to verify the built wheel installs cleanly and
  declares the right dependencies, before trusting the real release path.
- Cut the first real release once the above is verified, exercising `python-publish.yml`
  end-to-end for the first time.
- Update `README.md`'s install instructions once published.

### Out of scope

- Registering the PyPI Trusted Publisher itself — manual, one-time, on pypi.org, not a repo
  change (Open Question 2 names who does it).
- Any change to `build_and_test.yml` or this repo's own JFrog-backed dependency resolution.
- Any change to `docs/handoff/README.md` (frozen historical snapshot — see Open Question 3).
- Migrating any sibling repo's publishing mechanism.
- Anything from session 12 (MongoDB cache) — separate, independent piece of work on the same
  thread.

## Tasks

1. ~~Register the pypi.org pending Trusted Publisher~~ — **done** (Imran, see Open Question 2).
2. `pyproject.toml`: rename `[project] name` to `cms-hte-patient-matching`; add `[build-system]`,
   `[tool.setuptools.packages.find]`, `[tool.setuptools.package-data]`, `[project.urls]`.
3. Delete `setup.py`; trim `setup.cfg` to only what's still live.
4. Resolve the `patientmatching/` stray directory (Open Question 5).
5. `Makefile`: add `testpackage`/`package` targets (token-based twine, local dry-run use only —
   see Scope).
6. `make build` locally; inspect the built wheel's `METADATA` to confirm dependencies and
   `python_requires` match `pyproject.toml` (catches the `install_requires=[]` class of bug
   before any upload).
7. `make testpackage`; `pip install` the TestPyPI result into a scratch venv; confirm
   `import patient_matching` works and pulls the declared deps.
8. ~~Register the Trusted Publisher~~ — merged into task 1 above; done.
9. Cut a GitHub Release (tag `v0.1.0` or as decided) to exercise `python-publish.yml` for real —
   this is the actual first end-to-end test of the OIDC path, since Trusted Publishing can't be
   dry-run locally.
10. Update `README.md`'s Installation section with the real
    `pip install cms-hte-patient-matching` command.

## Unit tests required

None — packaging-only change, no matching-logic behavior change. The verification is the
TestPyPI install dry run (task 7), not a pytest addition.

## Validation

- [ ] `make build` produces a wheel whose `METADATA` lists all of `pyproject.toml`'s declared
      dependencies (not empty).
- [ ] `make testpackage` succeeds; the resulting TestPyPI package `pip install`s cleanly in a
      scratch venv and `import patient_matching` succeeds.
- [ ] No second top-level package (`patientmatching`) ships in the built wheel.
- [ ] `python-publish.yml` succeeds end-to-end on a real GitHub Release, after the Trusted
      Publisher is registered.
- [ ] `make tests` and `make run-pre-commit` still pass (packaging changes shouldn't touch
      matching behavior, but confirm regardless).

## Open questions

1. **Decided (Imran, 2026-09-04): package name is `cms-hte-patient-matching`.** Matches the repo
   name 1:1, avoids the generic-name squatting risk, and avoids confusion with the pre-existing,
   separate `icanbwell/patient-matching-reference-implementation` repo that `pyproject.toml`'s
   current name (`patient_matching`) and `setup.py`'s stale URL both accidentally point toward.
   Task 2 below now includes renaming `pyproject.toml`'s `[project] name` from `patient_matching`
   to `cms-hte-patient-matching` (the importable module stays `patient_matching` — PyPI
   distribution names and importable package names don't have to match, and changing the
   `patient_matching/` directory/import path is out of scope here since it would break every
   existing internal import in this repo).
2. **Resolved (Imran, 2026-09-04): the pypi.org pending Trusted Publisher is registered.**
   Confirms the git-blame-based prediction directly above this entry's prior text: Imran created
   it in his own PyPI account/namespace ("imranq" space) — the same one that already owns
   `fhirschemapy` (`fhir-schema-py`'s published package) — matching that exact precedent rather
   than a separate EA/DevOps-owned account. No remaining action needed before this session can
   move to execution.
3. **Not blocking, but flagging**: should `docs/handoff/README.md` §2's repo-list line be updated
   now that "PyPI" is becoming true for the CMS engine too, or is that doc a frozen historical
   snapshot (Zack Malone's 2026-07-20 handoff) not meant to be edited? Default: leave it
   untouched unless told otherwise — it's cited here as evidence, not as a doc this session owns.
4. **Not blocking, but worth confirming**: is there a real, current consumer waiting on this
   (i.e., does `cms-hte-patient-matching-service`'s design actually need `pip install` today), or
   is this purely preparatory ahead of that service's own build-out? Doesn't change the design,
   only the urgency.
5. **`NEEDS HUMAN DECISION` (whoever knows its origin) — the stray `patientmatching/` directory.**
   Delete it (looks like dead scaffold residue — matches no import anywhere found), or is it
   intentionally reserved for something not yet wired in? Default recommendation: delete.

## Execution notes

_(fill in when this session is actually executed — not done as part of this design capture)_
