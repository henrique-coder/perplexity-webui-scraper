# Command-line interface

The base package installs the `perplexity-webui-scraper` command and root help. Install the matching extra to use a feature command.

```bash
perplexity-webui-scraper --help
```

| Invocation                                        | Extra   | Purpose                                                         |
| ------------------------------------------------- | ------- | --------------------------------------------------------------- |
| `perplexity-webui-scraper token -e/--email EMAIL` | `token` | Generate a session token through Perplexity email verification. |
| `perplexity-webui-scraper api`                    | `api`   | Start the OpenAI-compatible REST API server.                    |
| `perplexity-webui-scraper mcp`                    | `mcp`   | Start the MCP server.                                           |

The CLI provides token-generation, API, and MCP commands. Use the Python client to create conversations.

Use either `-h` or `--help` with the root command and each subcommand. The token command accepts `-e` or `--email` for the account address.

Install the feature extras required by the commands you use:

```bash
# Install from PyPI
uv add 'perplexity-webui-scraper[token]'
uv add 'perplexity-webui-scraper[api]'
uv add 'perplexity-webui-scraper[mcp]'
uv add 'perplexity-webui-scraper[all]'
```

For local development, run the command through `uv --directory /path/to/perplexity-webui-scraper run`.

## Token generator

```bash
perplexity-webui-scraper token
perplexity-webui-scraper token -e user@example.com
perplexity-webui-scraper token --email user@example.com
```

The token command signs in through Perplexity email verification, supports TOTP challenges, displays the session cookie, and offers clipboard copy. Treat the token as a password.

## API server

Without a server-default token, clients provide their Perplexity session token with `Authorization: Bearer $PERPLEXITY_SESSION_TOKEN`.

```bash
perplexity-webui-scraper api
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

To configure a server-side upstream token, set both it and a separate gateway API key:

```bash
PERPLEXITY_SESSION_TOKEN="$PPLX_TOKEN" PERPLEXITY_API_KEY="$GATEWAY_KEY" perplexity-webui-scraper api
```

Requests may omit `Authorization` and use the server-default token, but must include `X-API-Key`. A client Bearer token overrides the server default; it must still provide the gateway key.

The recommended endpoint is `/v1/responses`; `/v1/chat/completions` remains supported for legacy clients. Responses accepts text and base64 data-URL image inputs, streams text events, and supports in-memory `previous_response_id` continuation. Tool calls and unknown request fields are rejected. Response history is process-local and expires. Remote image URLs are not fetched.

```bash
curl http://127.0.0.1:8000/v1/responses \
  -H 'Authorization: Bearer $PERPLEXITY_SESSION_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"model":"perplexity/best","input":"Hello"}'
```

## MCP server

Set `PERPLEXITY_SESSION_TOKEN` before launching the server:

```bash
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" perplexity-webui-scraper mcp
```

The MCP server registers one tool per model in the JSON registry.
