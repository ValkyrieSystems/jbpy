# Commands used by CI

.PHONY: format lint build test

format:
	ruff check --fix
	ruff format

lint:
	ruff check
	ruff format --diff
	mypy jbpy

build:
	python -m pip wheel --no-deps . --wheel-dir dist/

test:
	pytest
