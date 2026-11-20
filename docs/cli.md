# Command-line interface

The base package installs the `perplexity-webui-scraper` entry point and root help (`-h` / `--help`). Install the matching optional extra to enable each subcommand.

```bash
perplexity-webui-scraper --help
```

| Invocation                                        | Extra   | Purpose                                                        | Guide                                |
| ------------------------------------------------- | ------- | -------------------------------------------------------------- | ------------------------------------ |
| `perplexity-webui-scraper token -e/--email EMAIL` | `token` | Authenticate and print a compact `wsk_` session credential.    | [Session Token](token.md)            |
| `perplexity-webui-scraper token convert`          | `token` | Convert a raw cookie or validate a compact credential offline. | [Session Token](token.md)            |
| `perplexity-webui-scraper token deconvert`        | `token` | Restore a compact credential to its raw cookie pair.           | [Session Token](token.md)            |
| `perplexity-webui-scraper api`                    | `api`   | Start the OpenAI-compatible REST API server.                   | [OpenAI-Compatible API](rest-api.md) |
| `perplexity-webui-scraper mcp`                    | `mcp`   | Start the MCP stdio server.                                    | [MCP Server](mcp-server.md)          |

## Installing extras

```bash
uv add 'perplexity-webui-scraper[token]'
uv add 'perplexity-webui-scraper[api]'
uv add 'perplexity-webui-scraper[mcp]'
uv add 'perplexity-webui-scraper[all]'
```

For local checkout development, invoke commands with `uv --directory /path/to/perplexity-webui-scraper run perplexity-webui-scraper ...`.

## Subcommands

### `token`

Generates a compact `wsk_` credential through email OTP/magic-link and optional TOTP verification, or performs offline conversions via `token convert` and `token deconvert`. See [Session Token](token.md) for security details and examples.

### `api`

Starts the FastAPI server with pure `Authorization: Bearer` authentication:

```bash
# Default: clients pass a wsk_ token or raw cookie in Authorization: Bearer
perplexity-webui-scraper api

# Passwordless server-default token
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" perplexity-webui-scraper api

# Custom API key gating the server token
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" PERPLEXITY_API_KEY="my_secret_key_123" perplexity-webui-scraper api
```

See [OpenAI-Compatible API](rest-api.md) for all flags, endpoints, and client examples.

### `mcp`

Starts the stdio MCP server with `PERPLEXITY_SESSION_TOKEN`:

```bash
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" perplexity-webui-scraper mcp
```

See [MCP Server](mcp-server.md) for client configuration JSON and the generated tool list.
