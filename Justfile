default:
    @just --list

install:
    uv sync --upgrade --all-extras --all-groups
    pnpm update

format:
    uv run ruff check --fix
    uv run ruff format
    pnpm prettier --write .
    pnpm taplo format *.toml

lint:
    uv run ruff check
    uv run ty check
    pnpm prettier --check .
    pnpm taplo lint *.toml

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
