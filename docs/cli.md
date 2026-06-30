# CLI Reference

The package exposes one command:

```bash
perplexity-webui-scraper
```

Install the `cli` extra for terminal chat and token generation:

```bash
uv add "perplexity-webui-scraper[cli]"
```

Install every optional tool at once:

```bash
uv add "perplexity-webui-scraper[all]"
```

## Commands

| Command                               | Purpose                                                               |
| ------------------------------------- | --------------------------------------------------------------------- |
| `perplexity-webui-scraper token`      | Generate a session token through Perplexity email OTP/magic-link auth |
| `perplexity-webui-scraper chat`       | Chat with Perplexity from the terminal                                |
| `perplexity-webui-scraper chat setup` | Save an encrypted token and default model for chat                    |
| `perplexity-webui-scraper api`        | Start the OpenAI-compatible REST API server                           |
| `perplexity-webui-scraper mcp`        | Start the MCP stdio server                                            |

## Token

```bash
perplexity-webui-scraper token
perplexity-webui-scraper token you@example.com
```

The token command signs in with Perplexity's email flow, supports TOTP challenges, and prints the `__Secure-next-auth.session-token` cookie. The CLI never pushes this token anywhere; you decide where to store it.

## Chat Setup

```bash
perplexity-webui-scraper chat setup
```

The setup wizard stores:

- the session token, encrypted with Fernet in the platform config directory
- the default model used by `chat`

## Chat

Interactive mode:

```bash
perplexity-webui-scraper chat
```

Single prompt:

```bash
perplexity-webui-scraper chat "Explique computação quântica em termos simples"
```

Override token without saving it:

```bash
perplexity-webui-scraper chat "Hello" --token "$PERPLEXITY_SESSION_TOKEN"
```

Plain output for scripts:

```bash
perplexity-webui-scraper chat "Resumo rápido" --raw
```

Attach files:

```bash
perplexity-webui-scraper chat "Descreva esta imagem" --file .debug/img1.jpg
```

File attachments require a paid Perplexity account. Free accounts can still use text prompts with `perplexity/best`.

`perplexity/best` adapts to the authenticated account: free accounts use Perplexity's internal `turbo` preference, while Pro/Max accounts use `pplx_pro_upgraded`; both use `copilot` mode.

Useful options:

| Option                       | Values                                        | Description                                        |
| ---------------------------- | --------------------------------------------- | -------------------------------------------------- |
| positional `model`           | any model ID                                  | Override the saved/default model                   |
| `--search-focus`, `-sf`      | `web`, `writing`                              | Use web search or pure generation                  |
| `--source-focus`, `-SF`      | `web`, `academic`, `social`, `finance`, `all` | Restrict source category                           |
| `--time-range`, `-tr`        | `all`, `day`, `week`, `month`, `year`         | Restrict result recency                            |
| `--citation-mode`, `-cm`     | `default`, `markdown`, `clean`                | Control citation formatting                        |
| `--language`, `-l`           | BCP-47 tag                                    | Response language, for example `pt-BR`             |
| `--timezone`, `-tz`          | IANA timezone                                 | Localization timezone                              |
| `--latitude` / `--longitude` | floats                                        | Location-aware results; both are required together |
| `--space`, `-s`              | UUID                                          | Save the conversation into a Perplexity Space      |
| `--save` / `--no-save`       | boolean                                       | Save or avoid saving in the Perplexity library     |
| `--copy`, `-cp`              | flag                                          | Copy the final answer to clipboard                 |
| `--raw`, `-r`                | flag                                          | Disable Rich UI and print only the answer          |

When `perplexity/best` fails in web-search mode with Perplexity's generic processing error, the CLI retries once using `writing` mode. You can choose that mode directly:

```bash
perplexity-webui-scraper chat "oi" --search-focus writing
```

## API Server

```bash
perplexity-webui-scraper api
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

The API server does not need a token at startup. Pass the session token per request:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"perplexity/best","messages":[{"role":"user","content":"Hello"}]}'
```

## MCP Server

```bash
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" perplexity-webui-scraper mcp
```

The MCP server reads the token from `PERPLEXITY_SESSION_TOKEN` and registers one tool per model in the JSON registry.

## Troubleshooting

`ResponseParsingError: Query processing failed` means Perplexity accepted the request but its backend returned a failed SSE status. Try `--search-focus writing`, a shorter prompt, or a different model.

`ModelAccessError` means the selected model requires a higher Perplexity account tier. Use `perplexity/best` for the adaptive default model that works on free and paid accounts, or choose a model available to your account.

`FileAccessError` means the current session is a free account and the request included file attachments. Upgrade the account or send a text-only prompt.
