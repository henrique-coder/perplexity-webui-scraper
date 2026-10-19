FROM ghcr.io/astral-sh/uv:python3.15-alpine

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --python 3.15 --frozen --no-install-project --no-dev --extra api

COPY . /app/
RUN uv sync --python 3.15 --frozen --no-dev --no-editable --extra api

EXPOSE 8000

ENTRYPOINT ["/app/.venv/bin/perplexity-webui-scraper", "api", "--host", "0.0.0.0", "--port", "8000"]
