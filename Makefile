PYTHON ?= python
VENV := .venv

FIRST_TARGET := $(firstword $(MAKECMDGOALS))
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

.PHONY: lint format install tests help %
.DEFAULT_GOAL := help

lint:
	uv run npx prettier --check "**/*.{html,css,js,md,json,yaml}"
	uv run ruff check .

format:
	uv run npx prettier --write "**/*.{html,css,js,md,json,yaml}"
	uv run ruff format .
	uv run ruff check --fix .

install:
	uv sync --upgrade --all-extras --all-groups

tests:
	uv run pytest -v --xfail-tb

help:
	@echo "Available commands:"
	@echo "  lint       - Check code with 'prettier' and 'ruff'"
	@echo "  format     - Format code with 'prettier' and 'ruff'"
	@echo "  install    - Install dependencies with 'uv'"
	@echo "  tests      - Run tests with 'pytest'"
	@echo "  help       - Show this help message"

%:
	@if [ "$(FIRST_TARGET)" = "install" ]; then \
		:; \
	else \
		@echo "make: *** Unknown target '$@'. Use 'make help' for available targets." >&2; \
		exit 1; \
	fi
