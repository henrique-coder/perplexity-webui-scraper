# Getting started

## Installation

The package is published to PyPI (`requires-python >=3.11, <3.16`). API and MCP container images are published to GHCR. GitHub Releases include the wheel and source distribution, not standalone executables.

### Python library

Install the core Python library without optional CLI/server dependencies:

```bash
uv add perplexity-webui-scraper
```

### Optional extras

Install only the features you need:

```bash
uv add 'perplexity-webui-scraper[token]'  # Token generator and converter CLI
uv add 'perplexity-webui-scraper[api]'    # OpenAI-compatible REST API server
uv add 'perplexity-webui-scraper[mcp]'    # MCP stdio server
uv add 'perplexity-webui-scraper[all]'    # All optional features
```

## Next steps

1. Obtain or convert a credential in [Session Token](token.md) (`wsk_` compact token or raw session cookie pair).
2. Start building with the [Python Client](python-client/usage.md).
3. Explore the [CLI](cli.md), [OpenAI-Compatible API](rest-api.md), or [MCP Server](mcp-server.md).
