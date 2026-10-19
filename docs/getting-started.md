# Getting started

## Installation

The package is published to PyPI. API and MCP container images are published to GHCR. GitHub Releases include the wheel and source distribution, not standalone executables.

### Python library

Install the core Python library for use as a dependency.

```bash
# Install from PyPI
uv add perplexity-webui-scraper
```

### Optional features

Install only the optional features you need, or install all extras together.

```bash
# PyPI: choose one extra or install all
uv add 'perplexity-webui-scraper[token]'
uv add 'perplexity-webui-scraper[api]'
uv add 'perplexity-webui-scraper[mcp]'
uv add 'perplexity-webui-scraper[all]'
```

### MCP server

Run the MCP server in an isolated environment with `uvx`:

```bash
# Install and run the MCP server from PyPI
uvx --from 'perplexity-webui-scraper[mcp]' perplexity-webui-scraper mcp

# From local directory (for development)
uv --directory /path/to/perplexity-webui-scraper run perplexity-webui-scraper mcp
```

The MCP container image is for stdio-based client setups:

```bash
# Pull published MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run MCP server (requires token)
podman run --rm -it -e PERPLEXITY_SESSION_TOKEN=your_token ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

### OpenAI-compatible API server

```bash
# Install the API extra from PyPI
uv add 'perplexity-webui-scraper[api]'

# Start the server; clients provide a token with each request
perplexity-webui-scraper api

# Custom host and port
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

Without a server-default token, each request supplies the Perplexity session token with `Authorization: Bearer $PERPLEXITY_SESSION_TOKEN`. To configure a server-default token, also set a gateway key:

```bash
PERPLEXITY_SESSION_TOKEN="$PPLX_TOKEN" PERPLEXITY_API_KEY="$GATEWAY_KEY" perplexity-webui-scraper api
```

## Requirements

- **Perplexity account**: free accounts can use `perplexity/best`; Pro/Max-only models require the matching paid tier.
- **Session token** (`__Secure-next-auth.session-token` cookie)

## Getting a session token

### CLI

The token generator signs in through Perplexity email verification using a code or magic link. Install it with the `[token]` extra.

```bash
# Install the token extra before invoking the command.
uv add 'perplexity-webui-scraper[token]'
uv run perplexity-webui-scraper token
uv run perplexity-webui-scraper token --email user@example.com

# Run without adding the package to your project
uvx --from 'perplexity-webui-scraper[token]' perplexity-webui-scraper token --email user@example.com
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
4. Store it securely. If your application loads a `.env` file, use `PERPLEXITY_SESSION_TOKEN='your_token'`.
