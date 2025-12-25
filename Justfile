default:
    @just --list

lint:
    npx prettier --check .
    uv run ruff check
    uv run ty check

format:
    npx prettier --write .
    uv run ruff format
    uv run ruff check --fix

install:
    uv sync --upgrade --all-extras --all-groups

test:
    uv run pytest -v --xfail-tb
