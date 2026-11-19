# Command-line interface

The base package installs the `perplexity-webui-scraper` command and root help. Install the matching extra to use a feature command.

```bash
perplexity-webui-scraper --help
```

| Invocation                                        | Extra   | Purpose                                                        |
| ------------------------------------------------- | ------- | -------------------------------------------------------------- |
| `perplexity-webui-scraper token -e/--email EMAIL` | `token` | Authenticate and print a compact `wsk_` session credential.    |
| `perplexity-webui-scraper token convert`          | `token` | Convert a raw cookie or validate a compact credential offline. |
| `perplexity-webui-scraper token deconvert`        | `token` | Restore a compact credential to its raw cookie pair.           |
| `perplexity-webui-scraper api`                    | `api`   | Start the OpenAI-compatible REST API server.                   |
| `perplexity-webui-scraper mcp`                    | `mcp`   | Start the MCP server.                                          |

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

The token CLI retrieves the UUID-suffixed account session cookie after email OTP/magic-link and optional TOTP verification, then prints it in compact `wsk_` v1 form. Email codes must be exactly six ASCII digits. Magic links must be HTTPS `www.perplexity.ai/api/auth/callback/email` links for the selected account; additional query parameters are allowed. Malformed codes and links are rejected locally without another authentication request. Invalid server responses prompt for a fresh code while retaining the current login session, and do not resend the email.

The library accepts raw `__Secure-pplx.session.<UUIDv4>=<JWE>` pairs and compact `wsk_` tokens. `convert` and `deconvert` prompt for masked input and repeat the prompt when validation fails. `convert` emits a compact token; `deconvert` restores its raw cookie pair. `token -c` opens the convert prompt. Both commands show the result and ask before copying it to the clipboard. The default is no. Do not pass credentials as positional command-line arguments; shells may retain them in history or expose them through process listings.

```bash
perplexity-webui-scraper token convert

# Restore a compact token to its raw cookie pair.
perplexity-webui-scraper token deconvert
```

The prompt masks the input. The compact format is reversible obfuscation, not encryption or authenticated integrity; protect it as an account password.

## API server

Without a server-default credential, clients can provide either a raw `__Secure-pplx.session.<UUIDv4>=<JWE>` pair or a compact `wsk_` token through `Authorization`. Use `perplexity-webui-scraper token convert` to convert or validate a credential offline. The compact format is reversible obfuscation, not encryption or authenticated integrity.

```bash
perplexity-webui-scraper api
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

To configure a server-side upstream token, set both it and a separate gateway API key:

```bash
PERPLEXITY_SESSION_TOKEN="__Secure-pplx.session.<account UUID>=YOUR_VALUE" PERPLEXITY_API_KEY="$GATEWAY_KEY" perplexity-webui-scraper api
```

Requests may omit `Authorization` and use the server-default token, but must include `X-API-Key`. A client Bearer token overrides the server default; it must still provide the gateway key.

`POST /v1/chat/completions` is the only text-generation endpoint. It supports streaming, validated base64 image data URLs, and account-scoped thread continuation through `perplexity.thread_uuid`. Responses contain final assistant text, not hidden reasoning or client-executable tools. `GET /v1/models` remains available.

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_SESSION_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"model":"perplexity/best","messages":[{"role":"user","content":"Hello"}]}'
```

## MCP server

Set `PERPLEXITY_SESSION_TOKEN` before launching the server:

```bash
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" perplexity-webui-scraper mcp
```

The MCP server registers one tool per model in the JSON registry.
