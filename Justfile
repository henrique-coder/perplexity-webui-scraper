default:
    @just --list

update:
    uv sync --upgrade --all-extras --all-groups
    pnpm update

format:
    uv run --no-dev --group lint ruff check --fix
    uv run --no-dev --group lint ruff format
    pnpm prettier --write .
    pnpm taplo format *.toml

lint:
    uv run --no-dev --group lint --group test ruff check
    uv run --no-dev --group lint --group test ty check
    pnpm prettier --check .
    pnpm taplo lint *.toml
    uv run --no-dev --group lint --group test zizmor .github/workflows
    uv run --no-dev --group lint --group test scripts/render_model_docs.py --check

model-docs:
    uv run --no-dev scripts/render_model_docs.py

model-docs-check:
    uv run --no-dev scripts/render_model_docs.py --check

test:
    uv run --no-dev --group test pytest

docs:
    uv run --no-dev --group docs mkdocs serve --watch docs --watch src

build-container:
    podman build -t perplexity-webui-scraper .

run-container:
    podman run --rm -p 8000:8000 --name perplexity-api perplexity-webui-scraper

stop-container:
    podman stop perplexity-api
