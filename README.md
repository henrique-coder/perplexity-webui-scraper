<div align="center">

<img src="docs/assets/icon.png" width="128" alt="Logo">

# Perplexity WebUI Scraper

Python scraper to extract AI responses from [Perplexity's](https://www.perplexity.ai) web interface.

[![PyPI](https://img.shields.io/pypi/v/perplexity-webui-scraper?color=blue)](https://pypi.org/project/perplexity-webui-scraper)
[![Python](https://img.shields.io/pypi/pyversions/perplexity-webui-scraper)](https://pypi.org/project/perplexity-webui-scraper)
[![License](https://img.shields.io/github/license/henrique-coder/perplexity-webui-scraper?color=green)](./LICENSE)

</div>

---

**📚 Full Documentation & Advanced Guide:** [https://henrique-coder.github.io/perplexity-webui-scraper](https://henrique-coder.github.io/perplexity-webui-scraper)

---

## What is this?

This library lets you interact with Perplexity AI programmatically using the same web endpoints as the browser — no official API key required. It supports conversations, file uploads, streaming, an MCP server for AI agents, and a drop-in OpenAI-compatible REST API.

- **Requirements:** A Perplexity Pro or Max account and your browser session token.
- **Key Features:** 15 models (GPT-5.4, Claude Opus, Gemini, Deep Research…), file attachments (images, PDFs, …), streaming, MCP Server for AI agents, OpenAI-compatible REST API, multi-turn conversation thread continuation.

## Installation

Install the package depending on your use case:

This project is distributed as a Python package on PyPI and as optional container images on GHCR. GitHub Releases contain the Python wheel and source distribution; native standalone executables are not published.

### As a Core Library

Install only the core python library without any extra dependencies.

```bash
uv add perplexity-webui-scraper
```

### Full Installation (Everything)

Install all optional dependencies (`cli`, `api`, `mcp`) in one go. Recommended if you want to use all tools out-of-the-box.

```bash
uv add "perplexity-webui-scraper[all]"
```

### CLI Tools

Install with terminal UX dependencies to use the interactive `chat` and `token` CLI commands.

```bash
uv add "perplexity-webui-scraper[cli]"
```

### External Servers

Install dependencies required for the MCP Server or the OpenAI-compatible REST API.

```bash
# MCP Server for AI agents
uv add "perplexity-webui-scraper[mcp]"

# OpenAI-compatible API server
uv add "perplexity-webui-scraper[api]"
```

## Quick Start

### 1. Get your session token

```bash
# Interactive CLI wizard — walks you through email auth
uv run perplexity-webui-scraper token
```

Or retrieve `__Secure-next-auth.session-token` manually from your browser cookies on `perplexity.ai`.

### 2. Basic usage

```python
from perplexity_webui_scraper import Perplexity

client = Perplexity(session_token="YOUR_TOKEN")
conversation = client.create_conversation()

print(client.get_account_profile().account_tier)

conversation.ask("What is quantum computing?")
print(conversation.answer)

# Follow-ups preserve context automatically
conversation.ask("Explain it simpler")
print(conversation.answer)
```

Before each prompt, the library checks `/api/auth/session` and raises `ModelAccessError` if the selected model requires a higher tier than the authenticated account. When the session payload does not expose enough subscription data, it falls back to `/rest/user/settings`. Free accounts can use text prompts, but file attachments raise `FileAccessError`.

`perplexity/best` adapts to the account tier: free accounts use Perplexity's internal `turbo` preference, while Pro/Max accounts use `pplx_pro_upgraded`; both use `copilot` mode.

### 3. Streaming

```python
for chunk in conversation.ask("Explain AI", stream=True):
    if chunk.last_chunk:
        print(chunk.last_chunk, end="", flush=True)
```

### 4. Choose a model

```python
from perplexity_webui_scraper import ConversationConfig

conversation = client.create_conversation(ConversationConfig(model="perplexity/best"))
conversation.ask("Solve this step by step: ...")
print(conversation.answer)
```

### 5. List all available models

```python
from perplexity_webui_scraper import MODELS

for model in MODELS.list_all():
    print(f"{model.id:40} {model.name}")
```

## Available CLI

| Command                               | Extra | Description                                                                   |
| ------------------------------------- | ----- | ----------------------------------------------------------------------------- |
| `perplexity-webui-scraper token`      | `cli` | Interactive email auth wizard to generate a session token (supports TOTP 2FA) |
| `perplexity-webui-scraper chat`       | `cli` | Ask Perplexity AI questions with real-time streaming output                   |
| `perplexity-webui-scraper chat setup` | `cli` | Configure saved token and default model for the chat command                  |
| `perplexity-webui-scraper mcp`        | `mcp` | Start the MCP server                                                          |
| `perplexity-webui-scraper api`        | `api` | Start the OpenAI-compatible REST API server                                   |

## OpenAI-Compatible API

Run a local server that accepts OpenAI-formatted requests and forwards them to Perplexity. Works as a **drop-in replacement** for any OpenAI client — authentication is done per-request via `Authorization: Bearer`, exactly like the real API.

```bash
# Start the server (no token needed at startup)
perplexity-webui-scraper api

# Custom host and port
perplexity-webui-scraper api --host 0.0.0.0 --port 8080

# Development mode with auto-reload
perplexity-webui-scraper api --reload
```

### Running via Container (Podman)

```bash
# Pull the published multi-arch API image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:latest

# Run the server (exposing port 8000)
podman run --rm -p 8000:8000 ghcr.io/henrique-coder/perplexity-webui-scraper:latest
```

Optional MCP image for containerized stdio setups:

```bash
# Pull the published multi-arch MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run MCP server (requires token)
podman run --rm -e PERPLEXITY_SESSION_TOKEN=your_token ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

For local development, you can still build the provided container files:

```bash
# API image: installs the `api` extra, exposes port 8000, and starts the REST server.
podman build -t perplexity-api -f Containerfile .
podman run --rm -it -p 8000:8000 perplexity-api

# MCP image: installs the `mcp` extra and starts the stdio MCP server. It does not expose an HTTP port.
podman build -t perplexity-mcp -f Containerfile.mcp .
podman run --rm -it -e PERPLEXITY_SESSION_TOKEN=your_token perplexity-mcp
```

### CLI options

| Option        | Short | Default     | Description              |
| ------------- | ----- | ----------- | ------------------------ |
| `--host`      | `-H`  | `127.0.0.1` | Bind address             |
| `--port`      | `-p`  | `8000`      | Port to listen on        |
| `--reload`    |       | `False`     | Enable auto-reload (dev) |
| `--log-level` |       | `info`      | Uvicorn log level        |

### Authentication

Pass your Perplexity session token as the API key in every request — exactly like the OpenAI API:

```bash
# curl
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello!"}]}'

# Streaming
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_SESSION_TOKEN",  # sent as Authorization: Bearer automatically
)

response = client.chat.completions.create(
    model="perplexity/best",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

### API endpoints

| Method | Path                   | Description                                 |
| ------ | ---------------------- | ------------------------------------------- |
| `GET`  | `/v1/models`           | List all available models                   |
| `POST` | `/v1/chat/completions` | Chat completion (streaming + non-streaming) |
| `GET`  | `/docs`                | Interactive Swagger UI                      |
| `GET`  | `/redoc`               | ReDoc documentation                         |

> Fields not supported by Perplexity (e.g. `temperature`, `top_p`) are accepted for client compatibility but silently ignored.

## MCP Server

Expose every Perplexity model as a separate tool for AI agents (Claude Desktop, Antigravity, etc.):

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uvx",
      "args": [
        "--from",
        "perplexity-webui-scraper[mcp]@latest",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": { "PERPLEXITY_SESSION_TOKEN": "your_token_here" }
    }
  }
}
```

See the [full MCP documentation](https://henrique-coder.github.io/perplexity-webui-scraper/mcp-server/) for all tools and configuration details.

## Disclaimer

This is an **unofficial** library. It uses internal APIs that may change without notice. Use at your own risk. By using this library, you agree to Perplexity AI's [Terms of Service](https://www.perplexity.ai/hub/legal/terms-of-service).
