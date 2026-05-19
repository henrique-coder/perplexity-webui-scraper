# API Reference

## `Perplexity(session_token, config?)`

Main client — create once and reuse across multiple conversations.

| Parameter       | Type           | Description                                               |
| --------------- | -------------- | --------------------------------------------------------- |
| `session_token` | `str`          | Browser cookie value (`__Secure-next-auth.session-token`) |
| `config`        | `ClientConfig` | Timeout, retry, TLS, and logging settings                 |

```python
from perplexity_webui_scraper import ClientConfig, Perplexity

client = Perplexity(
    session_token="YOUR_TOKEN",
    config=ClientConfig(
        timeout=7200,
        max_retries=3,
        logging_level="debug",
        log_file=".debug/perplexity.log",
    ),
)
```

### Methods

| Method                         | Returns        | Description               |
| ------------------------------ | -------------- | ------------------------- |
| `create_conversation(config?)` | `Conversation` | Create a new conversation |
| `close()`                      | `None`         | Close the HTTP session    |

Supports context manager (`with` statement) — closes automatically on exit.

---

## `client.create_conversation(config?)`

Returns a `Conversation` object. Each conversation maintains its own context for follow-up questions.

```python
from perplexity_webui_scraper import ConversationConfig

conversation = client.create_conversation(ConversationConfig(model="perplexity/best"))
```

---

## `Conversation.ask(query, model?, files?, citation_mode?, stream?)`

| Parameter       | Type                      | Default                      | Description                  |
| --------------- | ------------------------- | ---------------------------- | ---------------------------- |
| `query`         | `str`                     | _(required)_                 | The question to ask          |
| `model`         | `str \| None`             | `None` → `"perplexity/best"` | Model ID string              |
| `files`         | `list[FileInput] \| None` | `None`                       | File attachments             |
| `citation_mode` | `str \| None`             | `None`                       | Override conversation config |
| `stream`        | `bool`                    | `False`                      | Yield chunks as they arrive  |

Returns `self` (the `Conversation`) for method chaining or streaming iteration.

### Conversation Properties

| Property         | Type                     | Description                      |
| ---------------- | ------------------------ | -------------------------------- |
| `answer`         | `str \| None`            | Full response text               |
| `search_results` | `list[SearchResultItem]` | Source URLs used in the response |
| `uuid`           | `str \| None`            | Conversation backend UUID        |

---

## Models

Models are specified as plain strings — the same style as the OpenAI SDK:

```python
ConversationConfig(model="perplexity/best")
conversation.ask("...", model="google/gemini-3.1-pro-thinking-low")
```

| Model ID                                | Name                         | Description                                         | Min. Tier |
| --------------------------------------- | ---------------------------- | --------------------------------------------------- | --------- |
| `"perplexity/best"`                     | Pro                          | Perplexity Pro (Auto-select). Tier: Pro.            | pro       |
| `"perplexity/deep-research"`            | Deep research                | Perplexity Deep Research. Tier: Pro.                | pro       |
| `"perplexity/sonar-2"`                  | Sonar 2                      | Perplexity Sonar 2. Tier: Pro.                      | pro       |
| `"openai/gpt-5.4"`                      | GPT-5.4                      | OpenAI GPT-5.4. Tier: Pro.                          | pro       |
| `"openai/gpt-5.4-thinking"`             | GPT-5.4 Thinking             | OpenAI GPT-5.4 (Thinking). Tier: Pro.               | pro       |
| `"openai/gpt-5.5-thinking"`             | GPT-5.5 Thinking             | OpenAI GPT-5.5 (Thinking). Tier: Max.               | max       |
| `"google/gemini-3.1-pro-thinking-low"`  | Gemini 3.1 Pro Thinking Low  | Google Gemini 3.1 Pro (Thinking Low). Tier: Pro.    | pro       |
| `"google/gemini-3.1-pro-thinking-high"` | Gemini 3.1 Pro Thinking High | Google Gemini 3.1 Pro (Thinking High). Tier: Pro.   | pro       |
| `"anthropic/claude-opus-4.6"`           | Claude Opus 4.6              | Anthropic Claude Opus 4.6. Tier: Max.               | max       |
| `"anthropic/claude-opus-4.6-thinking"`  | Claude Opus 4.6 Thinking     | Anthropic Claude Opus 4.6 (Thinking). Tier: Max.    | max       |
| `"anthropic/claude-opus-4.7"`           | Claude Opus 4.7              | Anthropic Claude Opus 4.7. Tier: Max.               | max       |
| `"anthropic/claude-opus-4.7-thinking"`  | Claude Opus 4.7 Thinking     | Anthropic Claude Opus 4.7 (Thinking). Tier: Max.    | max       |
| `"moonshot/kimi-k2.6-instant"`          | Kimi K2.6 Instant            | Moonshot AI Kimi K2.6 Instant. Tier: Pro.           | pro       |
| `"moonshot/kimi-k2.6-thinking"`         | Kimi K2.6 Thinking           | Moonshot AI Kimi K2.6 (Thinking). Tier: Pro.        | pro       |
| `"nvidia/nemotron-3-super-thinking"`    | Nemotron 3 Super Thinking    | NVIDIA Nemotron 3 Super 120B (Thinking). Tier: Pro. | pro       |

Inspect models programmatically:

```python
from perplexity_webui_scraper import MODELS

for model in MODELS.list_all():
    print(f"{model.id!r:35} → {model.name} [{model.min_tier}]")
```

---

## `citation_mode`

Controls how `[1]`-style citation markers are formatted in response text.

| Mode         | Output format  | Description               |
| ------------ | -------------- | ------------------------- |
| `"default"`  | `text[1]`      | Keep original markers     |
| `"markdown"` | `text[1](url)` | Convert to markdown links |
| `"clean"`    | `text`         | Remove all citations      |

```python
from perplexity_webui_scraper import ConversationConfig

config = ConversationConfig(citation_mode="markdown")
```

---

## Configurations

### `ConversationConfig`

| Parameter         | Type                                             | Default                      | Description                                        |
| ----------------- | ------------------------------------------------ | ---------------------------- | -------------------------------------------------- |
| `model`           | `str \| None`                                    | `None` (`"perplexity/best"`) | Model ID string                                    |
| `citation_mode`   | `Literal["default", "markdown", "clean"]`        | `"clean"`                    | Citation format                                    |
| `save_to_library` | `bool`                                           | `False`                      | Save conversation to Perplexity library            |
| `search_focus`    | `Literal["web", "writing"]`                      | `"web"`                      | Search type                                        |
| `source_focus`    | `str \| list[str]`                               | `"web"`                      | Source types (web, academic, social, etc.)         |
| `time_range`      | `Literal["all", "day", "week", "month", "year"]` | `"all"`                      | Recency filter for results                         |
| `language`        | `str`                                            | `"en-US"`                    | Language for the response                          |
| `timezone`        | `str \| None`                                    | `None`                       | IANA timezone (e.g. `"America/Sao_Paulo"`)         |
| `coordinates`     | `Coordinates \| None`                            | `None`                       | Geographic location (lat/lng)                      |
| `space_uuid`      | `str \| None`                                    | `None`                       | UUID of the Perplexity Space to post the thread to |

> **How to obtain `space_uuid`:** The URL slug (e.g. `questions-abcdef123456`) is **not** the UUID. Use one of these methods:
>
> - **Browser DevTools** — open the Space on perplexity.ai, make any query, open the Network tab, find the `perplexity_ask` request, and copy the `target_collection_uuid` value from the JSON payload.
> - **[Complexity browser extension](https://github.com/pnd280/complexity)** — surfaces Space metadata (including UUIDs) directly in the Perplexity UI.

### `ClientConfig`

| Parameter               | Type                      | Default      | Description                                 |
| ----------------------- | ------------------------- | ------------ | ------------------------------------------- |
| `timeout`               | `int`                     | `3600`       | Request timeout in seconds                  |
| `impersonate`           | `str`                     | `"chrome"`   | Browser fingerprint to impersonate          |
| `max_retries`           | `int`                     | `3`          | Maximum retry attempts on transient errors  |
| `retry_base_delay`      | `float`                   | `1.0`        | Initial backoff delay in seconds            |
| `retry_max_delay`       | `float`                   | `60.0`       | Maximum backoff delay in seconds            |
| `retry_jitter`          | `float`                   | `0.5`        | Jitter factor for retry delay randomization |
| `requests_per_second`   | `float`                   | `0.5`        | Rate limit (requests per second)            |
| `rotate_fingerprint`    | `bool`                    | `True`       | Rotate browser fingerprint on each retry    |
| `max_init_query_length` | `int`                     | `2000`       | Truncate init query to avoid HTTP 414       |
| `logging_level`         | `str`                     | `"disabled"` | Log verbosity (`disabled`, `debug`, etc.)   |
| `log_file`              | `str \| PathLike \| None` | `None`       | Write logs to file instead of stderr        |

---

## Parameter Values

### `source_focus`

| Value        | Targets                                |
| ------------ | -------------------------------------- |
| `"web"`      | General web search                     |
| `"academic"` | Academic papers and scholarly articles |
| `"social"`   | Social media (Reddit, Twitter, etc.)   |
| `"finance"`  | SEC EDGAR filings                      |
| `"all"`      | Web, Academic, and Social blended      |

### `search_focus`

| Value       | Description          |
| ----------- | -------------------- |
| `"web"`     | Search the web       |
| `"writing"` | Writing-focused mode |

### `time_range`

| Value     | Description    |
| --------- | -------------- |
| `"all"`   | No time filter |
| `"day"`   | Last 24 hours  |
| `"week"`  | Last 7 days    |
| `"month"` | Last 30 days   |
| `"year"`  | Last 365 days  |

### `logging_level`

| Value        | Description                  |
| ------------ | ---------------------------- |
| `"disabled"` | No logging (default)         |
| `"debug"`    | All messages including debug |
| `"info"`     | Info, warnings, and errors   |
| `"warning"`  | Warnings and errors only     |
| `"error"`    | Errors only                  |
| `"critical"` | Critical/fatal errors only   |

---

## Exceptions

| Exception                          | Description                                    |
| ---------------------------------- | ---------------------------------------------- |
| `PerplexityError`                  | Base exception for all library errors          |
| `HTTPError`                        | HTTP error with status code and response body  |
| `AuthenticationError`              | Session token is invalid or expired (HTTP 403) |
| `RateLimitError`                   | Rate limit exceeded (HTTP 429)                 |
| `FileUploadError`                  | File upload to Perplexity's S3 failed          |
| `FileValidationError`              | File validation failed (size, type, not found) |
| `ResearchClarifyingQuestionsError` | Research mode requires clarifying questions    |
| `ResponseParsingError`             | API response could not be parsed               |
| `StreamingError`                   | Error during streaming response                |

```python
from perplexity_webui_scraper import (
    AuthenticationError,
    PerplexityError,
    ResearchClarifyingQuestionsError,
)

try:
    conversation.ask("Analyze recent market trends", model="perplexity/best")
except ResearchClarifyingQuestionsError as e:
    print("Needs clarification:", e.questions)
except AuthenticationError:
    print("Token expired — refresh your session token")
except PerplexityError as e:
    print(f"Library error: {e}")
```

---

## OpenAI-Compatible API

Install with the `api` extra:

```bash
uv add "perplexity-webui-scraper[api]"
```

### `perplexity-webui-scraper api`

Starts the server. No token is configured at startup — authentication is done **per-request** via `Authorization: Bearer`, exactly like the real OpenAI API.

| Option        | Short | Default     | Description                                                         |
| ------------- | ----- | ----------- | ------------------------------------------------------------------- |
| `--host`      | `-H`  | `127.0.0.1` | Bind address                                                        |
| `--port`      | `-p`  | `8000`      | Port to listen on                                                   |
| `--reload`    |       | `False`     | Enable auto-reload (dev mode)                                       |
| `--log-level` |       | `info`      | Uvicorn log level (`debug`, `info`, `warning`, `error`, `critical`) |

```bash
# Minimal — binds to localhost:8000
perplexity-webui-scraper api

# Expose on the network
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

### Running via Container (Podman / Docker)

The REST API is published as a multi-arch image on GHCR for `linux/amd64` and `linux/arm64`.

```bash
# Pull a release image
docker pull ghcr.io/henrique-coder/perplexity-webui-scraper:latest

# Run the server (exposed on port 8000)
docker run -d -p 8000:8000 --name perp-api ghcr.io/henrique-coder/perplexity-webui-scraper:latest
```

For local development, use the provided `Containerfile`:

```bash
podman build -t perplexity-api .
podman run -d -p 8000:8000 --name perp-api perplexity-api
```

### Authentication

Pass your Perplexity session token as the Bearer token in every request — clients are cached by token server-side so no session overhead on repeated calls:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello!"}]}'
```

Returns `HTTP 401` if the header is missing or malformed.

### Endpoints

| Method | Path                   | Description                                 |
| ------ | ---------------------- | ------------------------------------------- |
| `GET`  | `/v1/models`           | List all available models                   |
| `POST` | `/v1/chat/completions` | Chat completion (streaming + non-streaming) |
| `GET`  | `/docs`                | Interactive Swagger UI                      |
| `GET`  | `/redoc`               | ReDoc API documentation                     |

### `POST /v1/chat/completions`

**Request body:**

| Field      | Type   | Required | Description                                                        |
| ---------- | ------ | -------- | ------------------------------------------------------------------ |
| `model`    | `str`  | yes      | Any model ID from `/v1/models` (e.g. `"perplexity/best"`)          |
| `messages` | `list` | yes      | List of `{role, content}` messages (`system`, `user`, `assistant`) |
| `stream`   | `bool` | no       | Enable SSE streaming (default: `false`)                            |

> Any extra OpenAI fields (`temperature`, `top_p`, `n`, `max_tokens`, etc.) are accepted for client compatibility but silently ignored.

**Non-streaming response:**

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "perplexity/best",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "..." },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
}
```

**Streaming** (`stream: true`) uses Server-Sent Events, one `data: {...}` JSON chunk per event, ending with `data: [DONE]`.

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

### Passing Optional Arguments

You can pass Perplexity-specific configurations (like `search_focus`, `citation_mode`, or `coordinates`) through the `extra_body` dictionary natively via the OpenAI SDK. The API intercepts the `"perplexity"` block.

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="YOUR_SESSION_TOKEN")

response = client.chat.completions.create(
    model="google/gemini-3.1-pro-thinking-low",
    messages=[{"role": "user", "content": "Analyze these recent academic papers"}],
    extra_body={
        "perplexity": {
            "source_focus": "academic",
            "time_range": "year",
            "citation_mode": "markdown",
            "save_to_library": True
        }
    }
)

print(response.choices[0].message.content)
```

With `curl`, simply append `"perplexity"` to the base JSON payload:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "perplexity/best",
    "messages": [{"role": "user", "content": "Technology news"}],
    "perplexity": {
      "search_focus": "web",
      "source_focus": ["social", "academic"],
      "time_range": "week"
    }
  }'
```

### Posting to a Perplexity Space

Set `space_uuid` in the `perplexity` block to route the thread into a specific Space (collection).
The UUID is different from the URL slug — see [ConversationConfig](#conversationconfig) for how to obtain it.

```python
response = client.chat.completions.create(
    model="perplexity/best",
    messages=[{"role": "user", "content": "Research notes for project X"}],
    extra_body={
        "perplexity": {
            "space_uuid": "12345678-1234-1234-1234-123456789abc"
        }
    }
)
```

### Multimodal Uploads / Images

The REST API fully implements OpenAI's Vision API standard. This means **any compatible chatbot frontend** (like Open WebUI, LibreChat, Chatbox, or AnythingLLM) will work out-of-the-box. When users upload files in these generic UIs, the chatbot automatically encodes the file to a base64 Data URI and sends it to our API as an `image_url` part.

Base64-encoded Data URIs are automatically extracted and uploaded securely to Perplexity before querying the model.

**Example with OpenAI Python SDK:**

```python
import base64
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="YOUR_SESSION_TOKEN")

# Read an image and encode it to base64
with open("document.pdf", "rb") as file:
    pdf_b64 = base64.b64encode(file.read()).decode("utf-8")

response = client.chat.completions.create(
    model="perplexity/best",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this document?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:application/pdf;base64,{pdf_b64}"}
                }
            ]
        }
    ]
)

print(response.choices[0].message.content)
```

**Example with cURL:**

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "perplexity/best",
    "messages": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "What is in this image?" },
          {
            "type": "image_url",
            "image_url": { "url": "data:image/jpeg;base64,/9j/4AAQSkZJR..." }
          }
        ]
      }
    ]
  }'
```
