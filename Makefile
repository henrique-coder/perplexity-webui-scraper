PYTHON ?= python
VENV := .venv

FIRST_TARGET := $(firstword $(MAKECMDGOALS))
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

.PHONY: lint format install help %
.DEFAULT_GOAL := help

lint:
	npx prettier --check "**/*.{html,css,js,md,json,yaml}"
	ruff check .

format:
	npx prettier --write "**/*.{html,css,js,md,json,yaml}"
	ruff check --fix .
	ruff format .

install:
	uv sync --all-extras --all-groups

help:
	@echo "Available commands:"
	@echo "  lint       - Check code with Prettier and Ruff"
	@echo "  format     - Format code with Prettier and Ruff"
	@echo "  install    - Install dependencies"
	@echo "  help       - Show this help message"

%:
	@if [ "$(FIRST_TARGET)" = "install" ]; then \
		:; \
	else \
		@echo "make: *** Unknown target '$@'. Use 'make help' for available targets." >&2; \
		exit 1; \
	fi
