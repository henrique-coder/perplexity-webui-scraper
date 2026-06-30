# Getting Started

## Installation

Install the package using the extra that matches your use case.

### As a Library

Install only the core python library for integration into your own Python code.

```bash
# From PyPI (stable)
uv add perplexity-webui-scraper

# From GitHub prod branch (latest features and fixes)
uv add git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod
```

### Full Installation (Everything)

Install all optional dependencies (`cli`, `api`, `mcp`) at once. Recommended for users who want to use the CLI tools and the servers without worrying about missing packages.

```bash
uv add "perplexity-webui-scraper[all]"
```

### Command Line Tools (CLI)

Install with the `cli` extra to use the `token` generator and the interactive `chat` command directly from your terminal.

```bash
# From PyPI (stable)
uv add "perplexity-webui-scraper[cli]"

# From GitHub prod branch
uv add "perplexity-webui-scraper[cli] @ git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod"
```

### As MCP Server

No installation required — `uvx` handles everything automatically:

```bash
# From PyPI (stable)
uvx --from perplexity-webui-scraper[mcp]@latest perplexity-webui-scraper mcp

# From GitHub prod branch (latest fixes)
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

### As API Server (OpenAI-compatible)

```bash
# Install with api extra
uv add "perplexity-webui-scraper[api]"

# Start the server — no token needed at startup
perplexity-webui-scraper api

# Custom host and port
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

Authentication is done per-request via `Authorization: Bearer <session_token>`, exactly like the OpenAI API.

## Requirements

- **Perplexity account**: free accounts can use `perplexity/best`; Pro/Max-only models require the matching paid tier.
- **Session token** (`__Secure-next-auth.session-token` cookie)

## Getting Your Session Token

### Option 1: Automatic (CLI Tool)

The library includes an interactive tool to fetch your token via email magic link or verification code.

```bash
# Using the library if you installed with [cli]
uv run perplexity-webui-scraper token

# Running standalone without adding to your project (via uvx)
uvx --from perplexity-webui-scraper[cli] perplexity-webui-scraper token

# Running standalone directly from GitHub prod branch
uvx --from "perplexity-webui-scraper[cli]@git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod" perplexity-webui-scraper token
```

This interactive tool will:

1. Ask for your Perplexity email
2. Send a verification code to your email
3. Accept either a 6-digit code or magic link
4. Extract and display your session token
5. Prompt to safely copy it directly to your clipboard

### Option 2: Manual (Browser)

1. Log in at [perplexity.ai](https://www.perplexity.ai)
2. Open DevTools (`F12`) → Application/Storage → Cookies
3. Copy the value of `__Secure-next-auth.session-token`
4. Store in `.env`: `PERPLEXITY_SESSION_TOKEN="your_token"`
