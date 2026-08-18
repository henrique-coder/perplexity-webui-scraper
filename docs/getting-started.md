# Getting Started

## Installation

Install the package using the extra that matches your use case.

The project is distributed as a Python package through PyPI and as optional container images through GHCR. Release assets do not include native standalone executables; use `uv`, `uvx`, or containers instead.

### As a Library

Install only the core python library for integration into your own Python code.

```bash
# From PyPI (stable)
uv add perplexity-webui-scraper

# From the GitHub production branch
uv add git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod
```

### All optional features

Install the `cli`, `api`, and `mcp` extras together.

```bash
uv add "perplexity-webui-scraper[all]"
```

### Command-line tools

Install with the `cli` extra to use the `token` generator and the interactive `chat` command directly from your terminal.

```bash
# From PyPI (stable)
uv add "perplexity-webui-scraper[cli]"

# From GitHub prod branch
uv add "perplexity-webui-scraper[cli] @ git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod"
```

### MCP server

Run the MCP server in an isolated environment with `uvx`:

```bash
# From PyPI (stable)
uvx --from perplexity-webui-scraper[mcp]@latest perplexity-webui-scraper mcp

# From the GitHub production branch
uvx --from "perplexity-webui-scraper[mcp]@git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod" perplexity-webui-scraper mcp

# From local directory (for development)
uv --directory /path/to/perplexity-webui-scraper run perplexity-webui-scraper mcp
```

Optional Podman image for containerized stdio setups:

```bash
# Pull published MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run MCP server (requires token)
podman run --rm -it -e PERPLEXITY_SESSION_TOKEN=your_token ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

### OpenAI-compatible API server

```bash
# Install with api extra
uv add "perplexity-webui-scraper[api]"

# Start the server; no token is needed at startup
perplexity-webui-scraper api

# Custom host and port
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

Each request supplies the Perplexity session token through `Authorization: Bearer <session_token>`.

## Requirements

- **Perplexity account**: free accounts can use `perplexity/best`; Pro/Max-only models require the matching paid tier.
- **Session token** (`__Secure-next-auth.session-token` cookie)

## Getting Your Session Token

### Option 1: CLI

The library includes an interactive tool to fetch your token via email magic link or verification code.

```bash
# Using the library if you installed with [cli]
uv run perplexity-webui-scraper token

# Run without adding the package to your project (via uvx)
uvx --from perplexity-webui-scraper[cli] perplexity-webui-scraper token

# Run directly from GitHub prod branch
uvx --from "perplexity-webui-scraper[cli]@git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod" perplexity-webui-scraper token
```

The command:

1. Ask for your Perplexity email
2. Send a verification code to your email
3. Accept either a 6-digit code or magic link
4. Extract and display your session token
5. Offer to copy it to the clipboard

### Option 2: Browser

1. Log in at [perplexity.ai](https://www.perplexity.ai)
2. Open DevTools (`F12`), then Application/Storage, then Cookies
3. Copy the value of `__Secure-next-auth.session-token`
4. Store it securely. If your application loads a `.env` file, use `PERPLEXITY_SESSION_TOKEN="your_token"`.
