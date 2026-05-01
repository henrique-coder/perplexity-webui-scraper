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

docs:
    uv run mkdocs serve --watch docs --watch src

build-container:
    podman build -t perplexity-webui-scraper .

run-container:
    podman run --rm -p 8000:8000 --name perplexity-api perplexity-webui-scraper

stop-container:
    podman stop perplexity-api
