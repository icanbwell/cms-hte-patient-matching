# patientmatching

patientmatching

## Quickstart
- `make init` to set up the local dev environment.
- `make up` to start the Docker dev stack.
- `make tests` to run tests in the dev container.

## Common Tasks
- `make shell` to open a shell in the dev container.
- `make run-pre-commit` to run linting and formatting hooks.
- `make build` to build the package artifacts.

## Publishing
- Set a token: `export TWINE_PASSWORD=pypi-xxx`
- `make package` to publish to PyPI or `make testpackage` for TestPyPI.

## Project Metadata
- Repo: https://github.com/icanbwell/patient-matching
- Author: Imran Qureshi <imran.qureshi@bwell.com>
