# OpenAI-Compatible API

The built-in FastAPI server exposes an OpenAI-compatible subset over `GET /v1/models` and `POST /v1/chat/completions`, backed by your Perplexity WebUI session.

Install the `api` extra before starting the server:

```bash
uv add 'perplexity-webui-scraper[api]'
```

## Starting the server

```bash
# Default: localhost:8000, callers supply a Bearer Perplexity token per request
perplexity-webui-scraper api

# Bind to all interfaces; protect exposed hosts with a custom API key or firewall
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

| Option            | Short | Default     | Description                                                                        |
| ----------------- | ----- | ----------- | ---------------------------------------------------------------------------------- |
| `--host`          | `-H`  | `127.0.0.1` | Bind address                                                                       |
| `--port`          | `-p`  | `8000`      | Port to listen on                                                                  |
| `--reload`        |       | `False`     | Enable auto-reload (development only)                                              |
| `--log-level`     |       | `info`      | Uvicorn log level (`debug`, `info`, `warning`, `error`, `critical`)                |
| `--session-token` |       | unset       | Server-default Perplexity token (`PERPLEXITY_SESSION_TOKEN`, `wsk_` or raw cookie) |
| `--api-key`       |       | unset       | Custom `Authorization: Bearer` key required when `--session-token` is set          |

## Authentication modes

HTTP requests always use `Authorization: Bearer ...`. Three server modes are supported:

| Mode                             | Server flags / env                                            | Incoming `Authorization` requirement                             |
| -------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------- |
| Per-request credential (default) | Neither `--session-token` nor `--api-key`                     | Required: `Authorization: Bearer <wsk_ or session cookie>`       |
| Passwordless server credential   | Only `--session-token` (`PERPLEXITY_SESSION_TOKEN`)           | Optional (no password checked; uses the configured server token) |
| Custom API key gate              | Both `--session-token` and `--api-key` (`PERPLEXITY_API_KEY`) | Required: `Authorization: Bearer <custom_api_key>`               |

See [Session Token](token.md) for how to obtain compact `wsk_` tokens or raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pairs. Setting `--api-key` without `--session-token` raises a configuration error at startup (`HTTP 503` if reached dynamically).

```bash
# Mode 1: Callers supply a compact wsk_ token or raw cookie per request
perplexity-webui-scraper api

# Mode 2: Passwordless local server using one configured Perplexity credential
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" perplexity-webui-scraper api

# Mode 3: Custom API key gating access to the configured Perplexity credential
PERPLEXITY_SESSION_TOKEN="$PERPLEXITY_SESSION_TOKEN" \
  PERPLEXITY_API_KEY="my_secret_key_123" \
  perplexity-webui-scraper api
```

## Endpoints

| Method | Path                   | Description                                            |
| ------ | ---------------------- | ------------------------------------------------------ |
| `GET`  | `/v1/models`           | List models usable by the authenticated account's tier |
| `POST` | `/v1/chat/completions` | Chat Completions API (streaming and non-streaming)     |
| `GET`  | `/docs`                | Interactive Swagger UI                                 |
| `GET`  | `/redoc`               | ReDoc API documentation                                |

## `GET /v1/models`

Checks the authenticated account's Perplexity tier (cached in memory per credential for 10 minutes) and returns only usable models:

- `"unavailable"` models are excluded.
- `"free"` and `"unknown"` account tiers receive only models with `min_tier == "free"`.
- `"pro"` accounts receive `"free"`, `"pro"`, and `"unknown"` (`min_tier`) models.
- `"max"` accounts receive all non-`"unavailable"` models.

## `POST /v1/chat/completions`

**Request body:** Requires `model` and `messages`. Each message has a `role` (`system`, `developer`, `user`, or `assistant`) and `content` (text or supported text/image parts). Optional fields include `stream` and `perplexity`. Unsupported OpenAI fields (such as `tools` or `tool_choice`) may be ignored; this is a partial compatibility layer.

When initializing a new thread, the server prepends a master `[System]` instruction clarifying that `/v1/chat/completions` is strictly a read-only Perplexity WebUI mirror for direct Q&A and research, preventing agent harnesses from attempting autonomous tool execution.

Non-streaming responses return assistant text in `choices[0].message.content`. Token counts are reported as zero. Follow-up requests can continue a cached thread by setting `perplexity.thread_uuid` to the previous response's thread UUID. Streaming responses emit standard `data:` SSE chunks ending with `data: [DONE]` and safe `event: error` frames on upstream failure. No hidden reasoning or client-executable tool calls are exposed.

### OpenAI Python SDK and `curl`

```python
from openai import OpenAI

# In Mode 1 pass a wsk_ token or raw cookie pair; in Mode 3 pass your custom --api-key.
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="wsk_YOUR_COMPACT_TOKEN",
)

response = client.chat.completions.create(
    model="perplexity/best",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_OR_SESSION_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Perplexity request options

Pass Perplexity-specific settings under the OpenAI SDK's `extra_body={"perplexity": {...}}` dictionary (or top-level `"perplexity"` JSON key):

```python
response = client.chat.completions.create(
    model="google/gemini-3.1-pro-thinking-low",
    messages=[{"role": "user", "content": "Analyze these recent academic papers"}],
    extra_body={
        "perplexity": {
            "source_focus": "academic",
            "time_range": "year",
            "citation_mode": "markdown",
            "save_to_library": True,
        }
    },
)
print(response.choices[0].message.content)
```

Supported `"perplexity"` fields include `citation_mode`, `save_to_library`, `search_focus`, `source_focus`, `time_range`, `language`, `timezone`, `latitude`, `longitude`, `space_uuid`, `allow_risky_model`, `custom_model_mode`, `research_interaction`, and `thread_uuid`. See [Configuration](python-client/configuration.md) for field constraints.

### Image inputs

`image_url` message parts accept validated base64 Data URLs (`data:image/...;base64,...`). Remote `http(s)` image URLs are ignored to prevent implicit network fetches or SSRF.

```python
from base64 import b64encode
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="wsk_YOUR_COMPACT_TOKEN")

with open("photo.jpg", "rb") as file:
    image_b64 = b64encode(file.read()).decode("utf-8")

response = client.chat.completions.create(
    model="perplexity/best",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }
    ],
)
print(response.choices[0].message.content)
```

## Container deployment with Podman

Multi-arch images (`linux/amd64`, `linux/arm64`) are published to GHCR:

```bash
# Pull and run the published API image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:latest
podman run -d -p 8000:8000 --name perp-api ghcr.io/henrique-coder/perplexity-webui-scraper:latest

# Or build locally from Containerfile
podman build -t perplexity-api -f Containerfile .
podman run --rm -p 8000:8000 --name perp-api perplexity-api
```
