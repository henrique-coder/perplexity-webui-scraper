PYTHON ?= python3
VENV := .venv

.PHONY: lint format help
.DEFAULT_GOAL := help

lint:
	poetry run ruff check

format:
	poetry run ruff format

help:
	@echo "Available commands:"
	@echo "  install     - Update dependencies, poetry.lock file, and install project"
	@echo "  lint        - Check code with ruff"
	@echo "  format      - Format code with ruff"
	@echo "  tests       - Run tests with pytest"
	@echo "  demo        - Generate a gif demonstrating the TurboDL CLI functionality and upload it to asciinema"
	@echo "  help        - Show this help message"
