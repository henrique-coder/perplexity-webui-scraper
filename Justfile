default:
    @just --list

update:
    uv sync --upgrade --all-groups --all-extras
    pnpm update

format:
    uv run --only-group lint ruff check --fix
    uv run --only-group lint ruff format
    pnpm prettier --write .
    pnpm taplo format *.toml

lint:
    uv run --only-group lint ruff check
    uv run --only-group lint ruff format --check
    uv run --no-dev --extra all --group lint --group tests --group scripts ty check
    pnpm prettier --check .
    pnpm taplo lint *.toml
    uv run --only-group workflow zizmor .github/workflows
    uv run --no-dev python scripts/generate_model_docs.py --check

model-docs:
    uv run --no-dev python scripts/generate_model_docs.py

model-docs-check:
    uv run --no-dev python scripts/generate_model_docs.py --check

test:
    uv run --no-dev --extra all --group tests --group scripts pytest
    uv run --isolated --python 3.11 --no-dev --extra all --group tests --group scripts pytest tests/test_sync_model_catalog.py

sync-models:
    uv run --isolated --python 3.11 --no-dev --group scripts python scripts/sync_model_catalog.py

docs:
    uv run --only-group docs zensical serve -a localhost:4000

docs-build:
    uv run --only-group docs zensical build --clean --strict

build:
    uv build

build-container:
    podman build -t perplexity-webui-scraper .

run-container:
    podman run --rm -p 8000:8000 --name perplexity-api perplexity-webui-scraper

stop-container:
    podman stop perplexity-api
