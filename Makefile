# Commands used by CI

.PHONY: lint build test

lint:
	ruff check
	ruff format --diff
	mypy jbpy

build:
	python -m pip wheel --no-deps . --wheel-dir dist/

test:
	pytest
