LANG=en_US.utf-8
export LANG

# Bridge the org-standard JFrog vars to what native uv expects (index name: jfrog).
# Username is optional -- a bare token authenticates against the virtual-pypi index.
UV_INDEX_JFROG_USERNAME ?= $(JFROG_READ_USER)
UV_INDEX_JFROG_PASSWORD ?= $(JFROG_READ_TOKEN)
export UV_INDEX_JFROG_USERNAME
export UV_INDEX_JFROG_PASSWORD

.PHONY: sync
sync: ## Create/update the local .venv (deps + dev group)
	uv sync --all-extras --group dev

.PHONY: uv.lock
uv.lock: ## Regenerate uv.lock from pyproject.toml
	uv lock

.PHONY: devsetup
devsetup: sync setup-pre-commit ## one time setup for devs
	make tests

.DEFAULT_GOAL := help
.PHONY: help
help: ## Show this help.
	# from https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: tests
tests: ## Runs all the tests
	uv run pytest .

.PHONY: clean-pre-commit
clean-pre-commit: ## removes pre-commit hook
	uv run pre-commit uninstall

.PHONY: setup-pre-commit
setup-pre-commit: ## Install the pre-commit git hook (uv-managed)
	uv run pre-commit install

.PHONY: run-pre-commit
run-pre-commit: ## Run all pre-commit hooks over all files (no install needed)
	uv run --frozen --no-sync pre-commit run --all-files

.PHONY: dist
dist: ## Build the sdist + wheel into dist/
	rm -rf dist/
	uv build

.PHONY: testpackage
testpackage: dist ## Upload the built distribution to TestPyPI (token in TWINE_PASSWORD)
	uv run --frozen --no-sync twine upload -u __token__ --repository testpypi dist/*

.PHONY: package
package: dist ## Upload the built distribution to PyPI (token in TWINE_PASSWORD)
	uv run --frozen --no-sync twine upload -u __token__ --repository pypi dist/*
