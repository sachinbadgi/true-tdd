.PHONY: test lint format typecheck all clean

## Run the unit test suite
test:
	pytest tests/ -q

## Run tests with coverage report
test-cov:
	pytest tests/ --cov=truetdd --cov-report=term-missing --cov-fail-under=80

## Check linting with ruff
lint:
	ruff check truetdd tests

## Format code with ruff
format:
	ruff format truetdd tests

## Check formatting (CI mode — no writes)
format-check:
	ruff format --check truetdd tests

## Run mypy type checks
typecheck:
	mypy truetdd tests

## Run all checks (lint + format-check + typecheck + test)
all: lint format-check typecheck test

## Remove generated build artifacts
clean:
	rm -rf dist/ build/ *.egg-info true_tdd.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
