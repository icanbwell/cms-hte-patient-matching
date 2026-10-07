.PHONY: venv download calculate all test clean

PYTHON := .venv/bin/python

venv:
	python3.12 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

download: ## Download all raw Census/ACS sources into data/raw/ (idempotent)
	$(PYTHON) run_all.py --download-only

calculate: ## Compute u-probabilities from data already in data/raw/, print + write outputs/
	$(PYTHON) run_all.py --compute-only

all: ## Download and compute in one pass
	$(PYTHON) run_all.py

test:
	$(PYTHON) -m pytest tests/

clean:
	rm -rf data/processed outputs/u_probabilities.csv outputs/u_probabilities.md
