default:
    @just --list

install:
    uv sync --upgrade --all-extras --all-groups

format:
    npx prettier --write .
    uv run ruff format
    uv run ruff check --fix

lint:
    npx prettier --check .
    uv run ruff check
    uv run ty check

test:
    uv run pytest
