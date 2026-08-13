# Root.io/JFrog Migration — learnings from this session (patient-matching)

## 1. `explicit = true` with an empty `[tool.uv.sources]` means nothing is actually protected
This repo already had a `[[tool.uv.index]]` for JFrog before this session, and the
tracker's `using_jfrog: YES` reflected that. But it was `explicit = true` with zero
packages mapped in `[tool.uv.sources]` (just comments) — meaning **no package actually
resolved through it**. This is exactly the gap `must-read.md` warns about generically
("already on JFrog" ≠ "already Root.io-hardened"), but concretely: check whether an
existing JFrog index is `default` or `explicit`, and if `explicit`, whether
`[tool.uv.sources]` actually maps anything to it, before trusting a tracker's `YES`.
Switched to `default = true` so every dependency actually gets Root.io's hardened
versions with PyPI fallback, matching the real intent of this migration.

## 2. The skill's own uv Dockerfile reference has the same empty-username bug found earlier (mcp-server-gateway)
`dockerfile-python-uv.md` in this skill uses `export UV_INDEX_JFROG_USERNAME=""` (empty
username, token-only auth). Confirmed directly in a prior session on a different repo:
Artifactory's virtual-pypi rejects an empty username with 403/connection errors even
given a valid token as the password — `uv` appears to treat an empty env var as "unset"
rather than "set to blank," so it sends no `Authorization` header at all for that index.
Used the real `JFROG_READ_USER` value throughout instead (mounting `jfrog_read_user` as
an additional secret alongside `jfrog_read_token` in every `RUN` that sets these env
vars). Worth fixing in the skill's own reference doc, not just working around it
per-repo each time it's hit.

## 3. Runtime stage was missing `libstdc++` — pre-existing, not introduced by this migration
`duckdb`'s compiled extension (`_duckdb.cpython-312-aarch64-linux-musl.so`) needs
`libstdc++.so.6` at import time. Neither the original nor the migrated `production`/
`development` stages installed it (`apk add --no-cache git` only) — this Dockerfile's
package selection for the runtime stage was untouched by the migration itself. This
almost certainly went undetected because this repo's CI (`build_and_test.yml`)
deliberately runs `pytest` on a bare `ubuntu-latest` runner, not inside this Dockerfile's
image, specifically to avoid a *different* duckdb-on-Alpine problem (see #4) — so nobody
had actually run the test suite inside the built container before. Fixed by adding
`libstdc++` to the production stage's `apk add` line. Caught by actually running
`pytest` inside the built image as part of verifying this migration, not by reading the
Dockerfile — worth doing that for any repo where CI doesn't already exercise the image.

## 4. DuckDB compiles from source under Alpine/musl, and needs real memory headroom
`duckdb` has no musllinux wheel, so `uv sync` under Alpine compiles its C++ engine from
source (~510 build steps). This is already known and documented in this repo's own
`build_and_test.yml` comment (why tests run on `ubuntu-latest` instead of in Docker).
What wasn't previously exercised locally: the compile needs real memory — it OOM-killed
(`g++: fatal error: Killed signal terminated program cc1plus`) with Docker Desktop's
default ~7.6GB allocation, and succeeded cleanly after bumping to ~11.7GB. Anyone
building this image locally on a memory-constrained Docker setup should expect this,
independent of anything in this migration.

## 5. Validating a migration doesn't stop at "the build succeeded"
Given #3 and #4, a clean `docker build` alone would have shipped a Dockerfile where the
app crashes on `import duckdb` the moment anything touches the cache module — the build
itself has no way to catch that, since nothing imports the package at build time. Only
actually running the test suite inside the built image surfaced it. 371/372 tests passed
after the fix (the 1 failure — `test_version_matches_repo_version_file` — is a
test-invocation artifact: it expects a repo-root `VERSION` file that the runtime image
deliberately never copies, not a regression).

---

Claude: update the Root.io/JFrog Migration Guide
(https://icanbwell.atlassian.net/wiki/spaces/CIE/pages/6195544074/Root.io+Jfrog+Migration+Guide)
and the `jfrog-pypi-migrate` skill's `dockerfile-python-uv.md` reference (the empty-username
bug in #2) with these notes, then delete this file.
