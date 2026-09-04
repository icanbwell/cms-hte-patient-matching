# Session 13 — Publish `cms-hte-patient-matching` to PyPI

**Status:** pending — design capture only, not yet scoped/sized for execution. Package name is
decided (see Open Question 1). One `NEEDS HUMAN DECISION`/action item remains (minting a PyPI
API token — see Open Question 2, now well-evidenced as Imran's own action, not an external
unknown) and blocks starting a feature branch.
**Thread:** `Phase 2: production candidate-retrieval scaling` (same thread as session 12 —
distribution packaging for the sibling `cms-hte-patient-matching-service` to consume).
**Estimated size:** S — the packaging fixes are small and mechanical; the remaining blocker is a
5-minute manual step (mint a PyPI API token) rather than an organizational unknown.

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

**Which sibling pattern to follow — resolved by looking at `helix.fhir.client.sdk` specifically
(Imran's direction):** two different publishing mechanisms exist across these repos, and
`helix.fhir.client.sdk` is the tie-breaker, not just one data point among equals:

- **`helix.fhir.client.sdk`** — a **public** repo, the highest-velocity package by far (releases
  land almost daily: `5.0.10` → `5.0.13` across 2026-08-31 → 2026-09-04 alone; the `python-publish.yml`
  workflow itself dates to 2021-03-29). Mechanism: plain **API-token twine upload** — `runs-on:
  ubuntu-latest`, no OIDC, no GitHub Environment, `TWINE_USERNAME: __token__` /
  `TWINE_PASSWORD: ${{ secrets.PYPI }}`, `python setup.py sdist bdist_wheel && twine upload
  dist/*`. `helix.personmatching` (this repo's closest sibling — same author, same
  matching-library-for-a-thin-service architecture) uses the identical mechanism, just on a
  self-hosted `runs-on: main` runner. Both repos' `python-publish.yml` were authored by
  `imranq2 <imranq2@hotmail.com>` (confirmed via `git log --follow --diff-filter=A`) — i.e.,
  **Imran's own PyPI-linked identity**, not a shared EA/DevOps account. This is the dominant,
  longest-proven, most-actively-exercised mechanism in the org for exactly this kind of
  library-behind-a-service package.
- **`fhir-schema-py` / `language-model-common`** — OIDC **Trusted Publishing**
  (`permissions: id-token: write`, `environment: pypi`, `pypa/gh-action-pypi-publish`). Also
  real and working (`language-model-common`'s last 5 releases all succeeded in ~30s each), but
  lower-velocity, more recently introduced, and requires an extra one-time step this repo can't
  do internally: registering the project as a Trusted Publisher on pypi.org itself.
- **This repo's existing `.github/workflows/python-publish.yml`** was already scaffolded to the
  *second* (OIDC) pattern — `gh api repos/icanbwell/cms-hte-patient-matching/environments`
  confirms a `pypi` GitHub Environment already exists here (created 2026-09-03) with zero
  secrets, consistent with OIDC. **Recommendation, per Imran's steer toward
  `helix.fhir.client.sdk`'s pattern: rewrite this workflow to the token-based twine mechanism**
  instead of pursuing Trusted-Publisher registration. Concretely: drop `permissions: id-token:
  write` and the `pypa/gh-action-pypi-publish` step; add `pip install twine` + `twine upload
  dist/*` with `TWINE_USERNAME: __token__` / `TWINE_PASSWORD: ${{ secrets.PYPI }}`. Keep
  `environment: pypi` on the job (unlike either token-based sibling) and put the `PYPI` secret
  *in* that environment rather than at repo level — the environment already exists here for
  free and gives this repo an approval gate the SDK/`helix.personmatching` don't bother with,
  at no extra setup cost.
  - **What's still needed and can't be done from this repo alone**: someone with access to the
    icanbwell PyPI identity mints an API token (scoped to the `cms-hte-patient-matching` project
    once it exists, or account-wide for the first upload) and adds it as the `PYPI` secret in
    this repo's `pypi` environment. Strong evidence (the git-blame finding above) says that
    person is **Imran** — see Open Question 2.
2. **`pyproject.toml` has no `[build-system]` table.** `helix.personmatching` and
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
3. **A second, stray package directory exists**: `patientmatching/` (no underscore — just
   `__init__.py` + `py.typed`) sits at repo root next to the real `patient_matching/`.
   `setup.py`'s `packages=find_packages()` would pick up both, silently shipping an
   essentially-empty extra top-level package in the built wheel.
4. **`setup.cfg`'s `[mypy]`/`[tool:pytest]` sections duplicate `pyproject.toml`'s
   `[tool.mypy]`/`[tool.pytest.ini_options]`** (already the modern, actually-used config per
   `conventions.md`'s exact command list). `setup.cfg`'s copies are dead weight once `setup.py`
   is removed, except its `[flake8]` section — check whether anything still invokes flake8
   directly (ruff appears to be the actual lint tool per `.pre-commit-config.yaml`) before
   deciding whether `[flake8]` is also dead.
5. **`README.md`/`CONTRIBUTING.md` already document `make testpackage` / `make package`**, but
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
6. **Repo visibility**: `cms-hte-patient-matching` is a **private** GitHub repo. Publishing to
   PyPI makes the source (matching logic, Table 2/3 constants) publicly downloadable even though
   the GitHub repo itself stays private. Confirmed this is already accepted practice here, not a
   novel exception: `helix.personmatching`, `fhir-schema-py`, and `device-codex` are all private
   repos with packages already public on PyPI today.
7. **Name availability**: checked `pypi.org/pypi/<name>/json` directly — both `patient-matching`
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

- **A PyPI API token from the icanbwell identity** that already owns `helix.fhir.client.sdk` and
  `helix.personmatching` on pypi.org, pasted into this repo's `pypi` GitHub Environment as the
  `PYPI` secret. See Open Question 2 — strong evidence this is Imran's own action, not a
  separate person/team to track down.
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
- Rewrite `.github/workflows/python-publish.yml` from OIDC Trusted Publishing to token-based
  twine, matching `helix.fhir.client.sdk`/`helix.personmatching` (see "Current state" above):
  drop `id-token: write` and `pypa/gh-action-pypi-publish`; add `pip install twine` + `twine
  upload dist/*` with `TWINE_USERNAME: __token__` / `TWINE_PASSWORD: ${{ secrets.PYPI }}`; keep
  `environment: pypi` on the job so the secret lives scoped to that environment.
- Add the `testpackage`/`package` Makefile targets (twine, token-based) that `README.md`/
  `CONTRIBUTING.md` already document but that don't exist yet — same mechanism as the CI change
  above, so local and CI publishing match.
- Do a TestPyPI dry run (`make testpackage`) to verify the built wheel installs cleanly and
  declares the right dependencies, before trusting the real release path.
- Cut the first real release once the above is verified, exercising `python-publish.yml`
  end-to-end for the first time.
- Update `README.md`'s install instructions once published.

### Out of scope

- Minting the PyPI API token itself and adding it as a GitHub secret — Imran's action (Open
  Question 2), not a repo code change.
- Any change to `build_and_test.yml` or this repo's own JFrog-backed dependency resolution.
- Any change to `docs/handoff/README.md` (frozen historical snapshot — see Open Question 3).
- Migrating any sibling repo's publishing mechanism.
- Anything from session 12 (MongoDB cache) — separate, independent piece of work on the same
  thread.

## Tasks

1. Confirm Open Question 2 below (Imran mints the PyPI token) — blocking.
2. `pyproject.toml`: rename `[project] name` to `cms-hte-patient-matching`; add `[build-system]`,
   `[tool.setuptools.packages.find]`, `[tool.setuptools.package-data]`, `[project.urls]`.
3. Delete `setup.py`; trim `setup.cfg` to only what's still live.
4. Resolve the `patientmatching/` stray directory (Open Question 5).
5. Rewrite `.github/workflows/python-publish.yml` to token-based twine (matching
   `helix.fhir.client.sdk`), keeping `environment: pypi`.
6. `Makefile`: add `testpackage`/`package` targets (same token-based twine mechanism).
7. `make build` locally; inspect the built wheel's `METADATA` to confirm dependencies and
   `python_requires` match `pyproject.toml` (catches the `install_requires=[]` class of bug
   before any upload).
8. `make testpackage`; `pip install` the TestPyPI result into a scratch venv; confirm
   `import patient_matching` works and pulls the declared deps.
9. Imran mints a PyPI API token from the icanbwell identity and adds it as the `PYPI` secret in
   this repo's `pypi` GitHub Environment.
10. Cut a GitHub Release (tag `v0.1.0` or as decided) to exercise `python-publish.yml` for real.
11. Update `README.md`'s Installation section with the real `pip install cms-hte-patient-matching`
    command.

## Unit tests required

None — packaging-only change, no matching-logic behavior change. The verification is the
TestPyPI install dry run (task 7), not a pytest addition.

## Validation

- [ ] `make build` produces a wheel whose `METADATA` lists all of `pyproject.toml`'s declared
      dependencies (not empty).
- [ ] `make testpackage` succeeds; the resulting TestPyPI package `pip install`s cleanly in a
      scratch venv and `import patient_matching` succeeds.
- [ ] No second top-level package (`patientmatching`) ships in the built wheel.
- [ ] `python-publish.yml` succeeds end-to-end on a real GitHub Release, after the `PYPI` token
      secret is in place.
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
2. **`NEEDS HUMAN ACTION` (very likely Imran) — mint the PyPI API token.** `git log
   --follow --diff-filter=A` on both `helix.fhir.client.sdk/.github/workflows/python-publish.yml`
   (2021-03-29) and `helix.personmatching/.github/workflows/python-publish.yml` (2022-12-10)
   shows the same author, `imranq2 <imranq2@hotmail.com>` — strong evidence Imran personally
   holds the icanbwell PyPI identity these sibling packages publish under, rather than a
   separate EA/DevOps-owned account. Not fully closed only because git-blame is circumstantial
   (someone could have added the workflow file without being the account holder) — worth a
   one-line confirmation from Imran before task 9, but this is no longer treated as an unknown
   third party to track down.
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
