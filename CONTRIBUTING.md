# Contributing

## Development
- `make devsetup` to set up the local dev environment.
- `make tests` to run the test suite.

## Quality Checks
- `make run-pre-commit` to run linting and formatting hooks.
- Pre-commit hooks are managed at the repo root. Run `make setup-pre-commit` from the repo root to install.

## Packaging
- `make dist` to build the sdist/wheel into `dist/`.
- `make testpackage` for a local TestPyPI dry run (needs a TestPyPI token in `TWINE_PASSWORD`).
- `make package` for a local PyPI dry run (needs a PyPI token in `TWINE_PASSWORD`).
- Real releases publish via `.github/workflows/python-publish.yml` (PyPI Trusted Publishing,
  triggered on a GitHub Release) rather than `make package`.

