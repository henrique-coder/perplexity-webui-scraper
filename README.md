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
- **Key Features:** Full model support (GPT-5.4, Opus 4.6, Deep Research…), file attachments, streaming, MCP Server, OpenAI-compatible API.

## Installation

```bash
# Core library only
uv add perplexity-webui-scraper

# Interactive session token generator (adds rich)
uv add "perplexity-webui-scraper[cli]"

# MCP Server for AI agents (adds fastmcp)
uv add "perplexity-webui-scraper[mcp]"

# OpenAI-compatible API server (adds fastapi + uvicorn + typer)
uv add "perplexity-webui-scraper[api]"

# Everything at once
uv add "perplexity-webui-scraper[cli,mcp,api]"
```

## Quick Start

### 1. Get your session token

```bash
# Interactive CLI wizard — walks you through email auth
uv run get-perplexity-session-token
```

Or retrieve `__Secure-next-auth.session-token` manually from your browser cookies on `perplexity.ai`.

### 2. Basic usage

```python
from perplexity_webui_scraper import Perplexity

client = Perplexity(session_token="YOUR_TOKEN")
conversation = client.create_conversation()

conversation.ask("What is quantum computing?")
print(conversation.answer)

# Follow-ups preserve context automatically
conversation.ask("Explain it simpler")
print(conversation.answer)
```

### 3. Streaming

```python
for chunk in conversation.ask("Explain AI", stream=True):
    if chunk.last_chunk:
        print(chunk.last_chunk, end="", flush=True)
```

### 4. Choose a model

```python
from perplexity_webui_scraper import ConversationConfig

conversation = client.create_conversation(ConversationConfig(model="openai/gpt-5.4-thinking"))
conversation.ask("Solve this step by step: ...")
print(conversation.answer)
```

## Available CLIs

| Command                        | Extra | Description                                               |
| ------------------------------ | ----- | --------------------------------------------------------- |
| `get-perplexity-session-token` | `cli` | Interactive email auth wizard to generate a session token |
| `perplexity-webui-scraper-mcp` | `mcp` | Start the MCP server (used via MCP config, not directly)  |
| `perplexity-webui-scraper-api` | `api` | Start the OpenAI-compatible REST API server               |

## OpenAI-Compatible API

Run a local server that accepts OpenAI-formatted requests and forwards them to Perplexity. Works as a **drop-in replacement** for any OpenAI client — authentication is done per-request via `Authorization: Bearer`, exactly like the real API.

```bash
# Start the server (no token needed at startup)
perplexity-webui-scraper-api

# Custom host and port
perplexity-webui-scraper-api --host 0.0.0.0 --port 8080

# Development mode with auto-reload
perplexity-webui-scraper-api --reload
```

### Running via Container (Podman / Docker)

You can seamlessly run the REST API using the provided `Containerfile` via Podman or Docker. This is the recommended way to securely isolate the server. The project utilizes a modern Python 3.14 Alpine container powered by `uv` for lightning-fast builds.

```bash
# 1. Build the lightweight image
podman build -t perplexity-api .

# 2. Run the server (exposing port 8000)
podman run --rm -it -p 8000:8000 perplexity-api
```

_> You can safely replace `podman` with `docker` in the commands above as the Containerfile is fully OCI-compatible._

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
  -d '{"model": "openai/gpt-5.4", "messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_SESSION_TOKEN",  # sent as Authorization: Bearer automatically
)

response = client.chat.completions.create(
    model="openai/gpt-5.4",
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
        "perplexity-webui-scraper-mcp"
      ],
      "env": { "PERPLEXITY_SESSION_TOKEN": "your_token_here" }
    }
  }
}
```

See the [full MCP documentation](https://henrique-coder.github.io/perplexity-webui-scraper/mcp-server/) for all tools and configuration details.

## Disclaimer

This is an **unofficial** library. It uses internal APIs that may change without notice. Use at your own risk. By using this library, you agree to Perplexity AI's [Terms of Service](https://www.perplexity.ai/hub/legal/terms-of-service).
