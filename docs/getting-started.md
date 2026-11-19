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

!!! warning "Perplexity session credential"

    The client accepts either the raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair or a compact `wsk_` token. `wsk_` is a reversible representation of the raw cookie, not encryption or authenticated integrity. Treat both formats as account passwords. This library reuses an existing account session; it does not authenticate from a cookie alone without a valid Perplexity session.

```bash
# Pull published MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run MCP server (requires account session-cookie pair)
podman run --rm -it -e PERPLEXITY_SESSION_TOKEN="__Secure-pplx.session.<account UUID>=YOUR_VALUE" ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

Use either a raw `__Secure-pplx.session.<UUIDv4>=<JWE>` pair or a compact `wsk_` token for `PERPLEXITY_SESSION_TOKEN`, API `Authorization`, and the Python `session_token` parameter. Both forms resolve to the same cookie. The compact form is reversible obfuscation, not encryption or authenticated integrity.

### OpenAI-compatible API server

```bash
# Install the API extra from PyPI
uv add 'perplexity-webui-scraper[api]'

# Start the server; clients provide a UUID-suffixed cookie pair per request
perplexity-webui-scraper api

# Custom host and port
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

Without a server-default credential, each request may supply either the raw `__Secure-pplx.session.<UUIDv4>=<JWE>` pair or the compact `wsk_` token through `Authorization`. To configure a server-default credential, also set a gateway key; the same two input formats are accepted there.

```bash
PERPLEXITY_SESSION_TOKEN="__Secure-pplx.session.<account UUID>=YOUR_VALUE" PERPLEXITY_API_KEY="$GATEWAY_KEY" perplexity-webui-scraper api
```

## Requirements

- Account-scoped session credential: raw `__Secure-pplx.session.<UUIDv4>=<JWE>` pair or compact `wsk_` token.
- The `token` extra retrieves the cookie through email OTP/magic-link and optional TOTP, then emits compact format.

## Getting a session credential

The token CLI retrieves the account-scoped cookie after email OTP/magic-link and optional TOTP verification, then prints a compact `wsk_` v1 token. It accepts exactly six ASCII digits or an HTTPS Perplexity email callback link for the requested account. Malformed input is rejected locally. Invalid verification responses prompt for a new code without resending the email or discarding the current session.

```bash
# Install the token extra before invoking the command.
uv add 'perplexity-webui-scraper[token]'
uv run perplexity-webui-scraper token
uv run perplexity-webui-scraper token --email user@example.com

# Run without adding the package to your project
uvx --from 'perplexity-webui-scraper[token]' perplexity-webui-scraper token --email user@example.com
```

The token command offers clipboard copy. To convert a copied raw cookie or validate a compact token entirely offline, run `perplexity-webui-scraper token --convert`; the input prompt is masked. This conversion does not encrypt the cookie or improve its security.
