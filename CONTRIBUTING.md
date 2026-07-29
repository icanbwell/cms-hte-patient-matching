# Contributing

## Development
- `make init` to set up the local dev environment.
- `make up` to start the Docker dev stack.
- `make tests` to run the test suite.

## Quality Checks
- `make run-pre-commit` to run linting and formatting hooks.
- Pre-commit hooks are managed at the repo root. Run `make setup-pre-commit` from the repo root to install.

## Packaging
- `make build` to build artifacts.
- `make testpackage` to publish to TestPyPI.
- `make package` to publish to PyPI.

