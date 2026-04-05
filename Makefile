LANG=en_US.utf-8

export LANG

.PHONY: help
help: ## Show this help
	@echo "Root Makefile — coordinates both projects"
	@echo ""
	@echo "Projects:"
	@echo "  patient_matching          Python library"
	@echo "  patient_matching_service  FastAPI service"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: init
init: ## Initialize both projects
	$(MAKE) -C patient_matching init
	$(MAKE) -C patient_matching_service devsetup

.PHONY: up
up: ## Start both projects
	$(MAKE) -C patient_matching up
	$(MAKE) -C patient_matching_service up

.PHONY: down
down: ## Stop both projects
	$(MAKE) -C patient_matching_service down
	$(MAKE) -C patient_matching down

.PHONY: tests
tests: ## Run tests for both projects
	$(MAKE) -C patient_matching tests
	$(MAKE) -C patient_matching_service tests

.PHONY: build
build: ## Build both projects
	$(MAKE) -C patient_matching build
	$(MAKE) -C patient_matching_service build

.PHONY: update
update: ## Update dependencies for both projects
	$(MAKE) -C patient_matching update
	$(MAKE) -C patient_matching_service update

.PHONY: setup-pre-commit
setup-pre-commit: ## Install the monorepo pre-commit hook
	cp ./pre-commit-hook ./.git/hooks/pre-commit && \
	chmod +x ./.git/hooks/pre-commit

.PHONY: clean-pre-commit
clean-pre-commit: ## Remove the pre-commit hook
	rm -f .git/hooks/pre-commit

.DEFAULT_GOAL := help