# Everyday commands. Run from the repository root.
PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
MANAGE := cd taskmanager && ../$(BIN)/python manage.py

.PHONY: help venv migrate run superuser test coverage lint format smoke package docker-build docker-run clean

help:  ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

venv:  ## create .venv and install runtime + dev dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt

migrate:  ## create/upgrade the SQLite database
	$(MANAGE) migrate

run: migrate  ## start the development server on http://127.0.0.1:8000
	$(MANAGE) runserver

superuser:  ## create an admin account for /admin/
	$(MANAGE) createsuperuser

test:  ## run the test-suite
	$(MANAGE) test -v 1

coverage:  ## run the tests with coverage and print the report
	cd taskmanager && ../$(BIN)/coverage run manage.py test -v 0 && ../$(BIN)/coverage report

lint:  ## ruff lint + format check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## auto-format with ruff
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

smoke:  ## end-to-end curl walkthrough against a private server (with a restart)
	scripts/smoke.sh

package:  ## build taskmanager.zip from the project files
	scripts/package.sh

docker-build:  ## build the container image
	docker build -t taskmanager:local .

docker-run:  ## run the container on http://127.0.0.1:8000 with a named volume for data
	docker run --rm -p 8000:8000 -v taskmanager-data:/data taskmanager:local

clean:  ## remove caches, coverage output and the packaged zip
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .ruff_cache taskmanager/.coverage taskmanager/htmlcov *.zip
