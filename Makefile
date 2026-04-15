SHELL := /bin/bash
PYTHON ?= python3
VENV ?= venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
PYTEST := $(VENV_BIN)/pytest
RUFF := $(VENV_BIN)/ruff
MYPY := $(VENV_BIN)/mypy

.DEFAULT_GOAL := help

.PHONY: help venv bootstrap test lint typecheck simulate-room leaderboard-build leaderboard-reset docker-build docker-test docker-replay clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "; print "Targets:"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

venv: ## Create the local virtual environment at ./venv
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)

bootstrap: venv ## Install bootstrap dependencies into ./venv
	$(VENV_PIP) install --upgrade pip
	@test ! -f requirements.txt || $(VENV_PIP) install -r requirements.txt

test: bootstrap ## Run tests when the suite exists
	@if [[ ! -d tests ]]; then echo "tests/ not implemented yet"; exit 0; fi
	PYTHONPATH=src $(PYTEST) tests -q

lint: bootstrap ## Run Ruff when source files exist
	@if [[ ! -d src ]]; then echo "src/ not implemented yet"; exit 0; fi
	PYTHONPATH=src $(RUFF) check src tests

typecheck: bootstrap ## Run mypy when source files exist
	@if [[ ! -d src ]]; then echo "src/ not implemented yet"; exit 0; fi
	PYTHONPATH=src $(MYPY) src

simulate-room: bootstrap ## Replay fixture sequence through the local engine
	PYTHONPATH=src $(VENV_PYTHON) scripts/replay_fixture.py \
		tests/fixtures/github/issue-open.json \
		tests/fixtures/github/owner-reveal.json \
		tests/fixtures/github/owner-flag.json

leaderboard-build: bootstrap ## Rebuild leaderboard markdown/json/cards from data/games
	PYTHONPATH=src $(VENV_PYTHON) scripts/build_leaderboards.py \
		--games-root data/games \
		--readme README.md \
		--json-out data/leaderboards.json \
		--cards-dir assets

leaderboard-reset: bootstrap ## Reset game records and regenerate empty leaderboard outputs
	rm -rf data/games
	mkdir -p data/games
	PYTHONPATH=src $(VENV_PYTHON) scripts/build_leaderboards.py \
		--games-root data/games \
		--readme README.md \
		--json-out data/leaderboards.json \
		--cards-dir assets

docker-build: ## Build the local Docker image
	docker build -t gh-issue-minesweeper .

docker-test: docker-build ## Run the test suite inside Docker
	docker run --rm gh-issue-minesweeper pytest tests -q

docker-replay: docker-build ## Replay fixtures inside Docker
	docker run --rm gh-issue-minesweeper python scripts/replay_fixture.py \
		tests/fixtures/github/issue-open.json \
		tests/fixtures/github/owner-reveal.json \
		tests/fixtures/github/owner-flag.json

clean: ## Remove local development caches
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage __pycache__
