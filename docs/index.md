# Perplexity WebUI Scraper

Unofficial Python client, CLI, OpenAI-compatible REST API, and MCP server for Perplexity's WebUI-backed conversation endpoints.

## Features

- Typed **Python client** with multi-turn conversations, streaming snapshots, and file uploads
- JSON-backed **model registry** with availability metadata and Perplexity Spaces support
- Interactive **CLI** for token generation, offline `wsk_` conversion, API hosting, and MCP serving
- **OpenAI-compatible REST API** (`/v1/models`, `/v1/chat/completions`) with Bearer authentication modes
- **MCP server** registering one tool per catalog model plus `pplx_custom`

## Quick Navigation

- [Getting Started](getting-started.md) — Install the library and optional extras
- [Session Token](token.md) — Generate, convert, and protect `wsk_` and cookie credentials
- [Python Client](python-client/usage.md) — Primary Python client guide, classes, models, and exceptions
- [CLI](cli.md) — Command-line entry points and options
- [OpenAI-Compatible API](rest-api.md) — Server deployment, Bearer auth modes, and SDK examples
- [MCP Server](mcp-server.md) — Stdio MCP setup and tool catalog

## Disclaimer

This is an **unofficial** library. It uses internal endpoints that may change without notice. Use at your own risk.

By using this library, you agree to Perplexity AI's [Terms of Service](https://www.perplexity.ai/hub/legal/terms-of-service).
