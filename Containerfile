FROM ghcr.io/astral-sh/uv:python3.14-alpine

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra api

COPY . /app/
RUN uv sync --frozen --no-dev --no-editable --extra api

EXPOSE 8000

ENTRYPOINT ["uv", "run", "perplexity-webui-scraper", "api", "--host", "0.0.0.0", "--port", "8000"]
