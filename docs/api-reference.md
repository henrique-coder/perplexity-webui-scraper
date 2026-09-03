# API Reference

## `Perplexity(session_token, config?)`

Create one client per session token and reuse it across conversations.

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

| Method                         | Returns           | Description                                           |
| ------------------------------ | ----------------- | ----------------------------------------------------- |
| `create_conversation(config?)` | `Conversation`    | Create a new conversation                             |
| `get_account_session()`        | `AccountSession`  | Read typed account/session data                       |
| `get_account_settings()`       | `AccountSettings` | Read typed user settings and subscription metadata    |
| `get_account_profile()`        | `AccountProfile`  | Read session data, falling back to settings if needed |
| `close()`                      | `None`            | Close the HTTP session                                |

The client supports a context manager and closes its HTTP session on exit.

---

## Account Profile

`client.get_account_session()` reads Perplexity's `/api/auth/session` endpoint and returns a typed Pydantic object. `client.get_account_settings()` reads `/rest/user/settings`. `client.get_account_profile()` combines both, using settings only when the session response does not expose enough subscription data.

The normalized `account_tier` is one of `free`, `pro`, `max`, or `unknown`.

```python
profile = client.get_account_profile()

print(profile.account_tier)
print(profile.session.user.email if profile.session.user else None)
```

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
| `allow_risky_model` | `bool \| None` | `None` | Acknowledge any non-available model status |
| `custom_model_mode` | `str \| None` | `None` | Mode for `custom:<identifier>` |

Returns `self` (the `Conversation`) for method chaining or streaming iteration.

Before every prompt request, the library performs a fast `/api/auth/session` check and blocks `available` models that require a higher tier than the authenticated account. If the session response is incomplete, it falls back to `/rest/user/settings`. For example, a Pro account receives `ModelAccessError` before an `available` Max-only model is sent to Perplexity. Acknowledged non-available models defer the final entitlement decision to Perplexity, avoiding false local denials caused by stale tier metadata. Free accounts receive `FileAccessError` before file uploads are attempted.

`perplexity/best` adapts to the authenticated account: free accounts use Perplexity's internal `turbo` preference, while Pro/Max accounts use `pplx_pro_upgraded`; both use `copilot` mode.

### Conversation Properties

| Property         | Type                     | Description                      |
| ---------------- | ------------------------ | -------------------------------- |
| `answer`         | `str \| None`            | Full response text               |
| `search_results` | `list[SearchResultItem]` | Source URLs used in the response |
| `uuid`           | `str \| None`            | Conversation backend UUID        |

---

## Models

Models are specified as strings:

```python
ConversationConfig(model="perplexity/best")
conversation.ask("...", model="google/gemini-3.1-pro-thinking-low")
```

Every model has one operational status: `available`, `unknown`, or `unavailable`. Only `available` models can be selected without acknowledgement. `is_official` separately indicates whether the model is listed in Perplexity's official WebUI; it does not imply that the model has been tested. Set `allow_risky_model=True` to explicitly try any non-available status; the backend then makes the final access decision. Custom identifiers default to `unknown` and `is_official=false`.

```python
config = ConversationConfig(
    model="openai/gpt-5.4",
    allow_risky_model=True,
)
conversation = client.create_conversation(config)

custom = ConversationConfig(
    model="custom:gpt57",
    allow_risky_model=True,
    custom_model_mode="copilot",
)
```

The OpenAI-compatible API exposes the same controls inside the `perplexity` request object: `allow_risky_model` and `custom_model_mode`.

<!-- BEGIN GENERATED MODEL CATALOG -->
### Status reference

| Status | Meaning | Runtime behavior |
| --- | --- | --- |
| `available` | Confirmed to work normally. | Normal use; the local minimum-tier check applies. |
| `unknown` | Current availability has not been confirmed. | Requires `allow_risky_model`; this is the default for unverified entries. |
| `unavailable` | Confirmed not to work with the current backend. | Requires `allow_risky_model`; retained for history and expected to fail. |

### Model catalog

| Model ID | Internal identifier | Provider | Official | Min. tier | Status | Last tested (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| `perplexity/best` | `turbo` | perplexity | `true` | free | `available` | 2026-09-03T11:22:43.678013Z |
| `perplexity/deep-research` | `pplx_alpha` | perplexity | `true` | pro | `available` | 2026-09-03T11:22:48.144988Z |
| `perplexity/sonar-2` | `experimental` | perplexity | `true` | pro | `available` | 2026-09-03T11:22:53.057021Z |
| `openai/gpt-5.6-terra` | `gpt56_terra` | openai | `true` | pro | `available` | 2026-09-03T11:23:01.577429Z |
| `openai/gpt-5.6-terra-thinking` | `gpt56_terra_thinking` | openai | `true` | pro | `available` | 2026-09-03T11:23:06.785982Z |
| `openai/gpt-5.6-sol` | `gpt56_sol` | openai | `true` | max | `available` | 2026-09-03T11:23:12.792318Z |
| `openai/gpt-5.6-sol-thinking` | `gpt56_sol_thinking` | openai | `true` | max | `available` | 2026-09-03T11:23:22.916886Z |
| `google/gemini-3.7-flash` | `gemini37flash` | google | `true` | pro | `available` | 2026-09-03T11:23:27.912685Z |
| `google/gemini-3.7-flash-thinking` | `gemini37flashthinking` | google | `true` | pro | `available` | 2026-09-03T11:23:36.095351Z |
| `anthropic/claude-sonnet-5` | `claude50sonnet` | anthropic | `true` | pro | `available` | 2026-09-03T11:23:43.226216Z |
| `anthropic/claude-sonnet-5-thinking` | `claude50sonnetthinking` | anthropic | `true` | pro | `available` | 2026-09-03T11:23:48.300702Z |
| `anthropic/claude-opus-5` | `claude50opus` | anthropic | `true` | max | `available` | 2026-09-03T11:23:54.080456Z |
| `anthropic/claude-opus-5-thinking` | `claude50opusthinking` | anthropic | `true` | max | `available` | 2026-09-03T11:23:59.927595Z |
| `moonshot/kimi-k3-thinking` | `kimik3thinking` | moonshot | `true` | pro | `available` | 2026-09-03T11:24:05.152887Z |
| `z-ai/glm-5.3` | `glm_5_3_thinking` | z-ai | `true` | pro | `available` | 2026-09-03T11:24:10.277289Z |
| `x-ai/grok-4.6` | `grok46low` | x-ai | `true` | pro | `available` | 2026-09-03T11:24:18.025718Z |
| `x-ai/grok-4.6-thinking` | `grok46medium` | x-ai | `true` | pro | `available` | 2026-09-03T11:24:22.485161Z |
| `nvidia/nemotron-3-ultra-thinking` | `nv_nemotron_3_ultra` | nvidia | `true` | pro | `available` | 2026-09-03T11:24:27.794997Z |
| `z-ai/glm-5.2` | `glm_5_2` | z-ai | `false` | pro | `available` | 2026-09-03T11:24:33.746485Z |
| `google/gemini-3.1-pro-thinking-high` | `gemini31pro_high` | google | `false` | pro | `available` | 2026-09-03T11:24:38.686210Z |
| `x-ai/grok-4.5` | `grok45low` | x-ai | `false` | pro | `available` | 2026-09-03T11:24:46.743380Z |
| `x-ai/grok-4.5-thinking` | `grok45medium` | x-ai | `false` | pro | `available` | 2026-09-03T11:24:52.864031Z |
| `anthropic/claude-opus-4.8` | `claude48opus` | anthropic | `false` | max | `available` | 2026-09-03T11:24:58.547866Z |
| `anthropic/claude-opus-4.8-thinking` | `claude48opusthinking` | anthropic | `false` | max | `available` | 2026-09-03T11:25:05.792719Z |
| `google/gemini-3.1-pro-thinking-low` | `gemini31pro_low` | google | `false` | pro | `available` | 2026-09-03T11:25:09.143634Z |
| `moonshot/kimi-k2.6-instant` | `kimik26instant` | moonshot | `false` | pro | `available` | 2026-09-03T11:25:13.951836Z |
| `moonshot/kimi-k2.6-thinking` | `kimik26thinking` | moonshot | `false` | pro | `available` | 2026-09-03T11:25:17.239309Z |
| `nvidia/nemotron-3-super-thinking` | `nv_nemotron_3_super` | nvidia | `false` | pro | `available` | 2026-09-03T11:25:21.372519Z |
| `openai/gpt-5.4` | `gpt54` | openai | `false` | pro | `available` | 2026-09-03T11:25:25.350995Z |
| `openai/gpt-5.4-thinking` | `gpt54_thinking` | openai | `false` | pro | `available` | 2026-09-03T11:25:29.370161Z |
| `openai/gpt-5.5-thinking` | `gpt55_thinking` | openai | `false` | max | `available` | 2026-09-03T11:25:35.124946Z |
| `anthropic/claude-opus-4.7` | `claude47opus` | anthropic | `false` | max | `available` | 2026-09-03T11:25:39.603900Z |
| `anthropic/claude-opus-4.7-thinking` | `claude47opusthinking` | anthropic | `false` | max | `available` | 2026-09-03T11:25:45.697471Z |
| `anthropic/claude-sonnet-4.6` | `claude46sonnet` | anthropic | `false` | pro | `available` | 2026-09-03T11:25:51.982932Z |
| `anthropic/claude-sonnet-4.6-thinking` | `claude46sonnetthinking` | anthropic | `false` | pro | `available` | 2026-09-03T11:25:55.342187Z |
| `openai/gpt4o` | `gpt4o` | openai | `false` | unknown | `available` | 2026-09-03T11:25:59.837844Z |
| `openai/gpt41` | `gpt41` | openai | `false` | unknown | `available` | 2026-09-03T11:26:03.279349Z |
| `openai/gpt5` | `gpt5` | openai | `false` | unknown | `available` | 2026-09-03T11:26:07.351477Z |
| `openai/gpt5-thinking` | `gpt5_thinking` | openai | `false` | unknown | `available` | 2026-09-03T11:26:11.502969Z |
| `openai/gpt51` | `gpt51` | openai | `false` | unknown | `available` | 2026-09-03T11:26:15.652342Z |
| `openai/gpt51-thinking` | `gpt51_thinking` | openai | `false` | unknown | `available` | 2026-09-03T11:26:19.383352Z |
| `openai/gpt51-low-thinking` | `gpt51_low_thinking` | openai | `false` | unknown | `available` | 2026-09-03T11:26:23.558056Z |
| `openai/gpt5-mini` | `gpt5_mini` | openai | `false` | unknown | `available` | 2026-09-03T11:26:27.310469Z |
| `openai/gpt5-nano` | `gpt5_nano` | openai | `false` | unknown | `available` | 2026-09-03T11:26:31.525358Z |
| `openai/gpt5-pro` | `gpt5_pro` | openai | `false` | unknown | `available` | 2026-09-03T11:26:37.316463Z |
| `openai/gpt52` | `gpt52` | openai | `false` | unknown | `available` | 2026-09-03T11:26:40.764900Z |
| `openai/gpt52-thinking` | `gpt52_thinking` | openai | `false` | unknown | `available` | 2026-09-03T11:26:45.042526Z |
| `openai/gpt52-pro` | `gpt52_pro` | openai | `false` | unknown | `available` | 2026-09-03T11:26:52.724936Z |
| `openai/gpt55` | `gpt55` | openai | `false` | unknown | `available` | 2026-09-03T11:27:00.976672Z |
| `anthropic/claude2` | `claude2` | anthropic | `false` | unknown | `available` | 2026-09-03T11:27:04.448034Z |
| `anthropic/claude37sonnetthinking` | `claude37sonnetthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:27:08.523621Z |
| `anthropic/claude40sonnetthinking` | `claude40sonnetthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:27:12.773211Z |
| `google/gemini25pro` | `gemini25pro` | google | `false` | unknown | `available` | 2026-09-03T11:27:16.685627Z |
| `google/gemini30pro` | `gemini30pro` | google | `false` | unknown | `available` | 2026-09-03T11:27:20.524726Z |
| `google/gemini30flash` | `gemini30flash` | google | `false` | unknown | `available` | 2026-09-03T11:27:24.341624Z |
| `google/gemini30flash-high` | `gemini30flash_high` | google | `false` | unknown | `available` | 2026-09-03T11:27:28.377231Z |
| `google/gemini35flash` | `gemini35flash` | google | `false` | unknown | `available` | 2026-09-03T11:27:32.510070Z |
| `google/gemini35flash-medium` | `gemini35flash_medium` | google | `false` | unknown | `available` | 2026-09-03T11:27:36.844582Z |
| `google/gemini35flash-high` | `gemini35flash_high` | google | `false` | unknown | `available` | 2026-09-03T11:27:40.358426Z |
| `x-ai/grok` | `grok` | x-ai | `false` | unknown | `available` | 2026-09-03T11:27:44.432190Z |
| `anthropic/claude40opus` | `claude40opus` | anthropic | `false` | unknown | `available` | 2026-09-03T11:27:48.335559Z |
| `anthropic/claude40opusthinking` | `claude40opusthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:27:54.319641Z |
| `anthropic/claude41opus` | `claude41opus` | anthropic | `false` | unknown | `available` | 2026-09-03T11:27:59.327141Z |
| `anthropic/claude41opusthinking` | `claude41opusthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:04.308568Z |
| `anthropic/claude45opus` | `claude45opus` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:11.398179Z |
| `anthropic/claude45opusthinking` | `claude45opusthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:16.934832Z |
| `anthropic/claude46opus` | `claude46opus` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:22.379165Z |
| `anthropic/claude46opusthinking` | `claude46opusthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:27.184108Z |
| `anthropic/claude45sonnet` | `claude45sonnet` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:30.536377Z |
| `anthropic/claude45sonnetthinking` | `claude45sonnetthinking` | anthropic | `false` | unknown | `available` | 2026-09-03T11:28:34.776512Z |
| `anthropic/claude45haiku` | `claude45haiku` | anthropic | `false` | unknown | `unavailable` | 2026-09-03T11:29:42.990929Z |
| `anthropic/claude45haikuthinking` | `claude45haikuthinking` | anthropic | `false` | unknown | `unavailable` | 2026-09-03T11:29:46.808308Z |
| `moonshot/kimik2thinking` | `kimik2thinking` | moonshot | `false` | unknown | `available` | 2026-09-03T11:28:46.934524Z |
| `moonshot/kimik25thinking` | `kimik25thinking` | moonshot | `false` | unknown | `available` | 2026-09-03T11:28:50.952534Z |
| `x-ai/grok4` | `grok4` | x-ai | `false` | unknown | `available` | 2026-09-03T11:28:54.587374Z |
| `x-ai/grok4nonthinking` | `grok4nonthinking` | x-ai | `false` | unknown | `available` | 2026-09-03T11:28:58.503272Z |
| `x-ai/grok41reasoning` | `grok41reasoning` | x-ai | `false` | unknown | `available` | 2026-09-03T11:29:02.678239Z |
| `x-ai/grok41nonreasoning` | `grok41nonreasoning` | x-ai | `false` | unknown | `available` | 2026-09-03T11:29:07.564332Z |
| `openai/o4mini` | `o4mini` | openai | `false` | unknown | `available` | 2026-09-03T11:29:10.930610Z |
| `openai/o3pro` | `o3pro` | openai | `false` | unknown | `available` | 2026-09-03T11:29:16.844157Z |

<!-- END GENERATED MODEL CATALOG -->

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
| `allow_risky_model` | `bool` | `False` | Acknowledge any non-available model status |
| `custom_model_mode` | `Literal["copilot", "search", "research"]` | `"copilot"` | Mode for `custom:<identifier>` |
| `research_interaction` | `Literal["auto", "manual"]` | `"auto"` | Deep Research clarification handling |

The Space URL slug, such as `questions-abcdef123456`, is not its UUID. Submit a query inside the Space, inspect the `perplexity_ask` request in the browser Network panel, and copy `target_collection_uuid` from its JSON payload.

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
    print("Token expired; refresh your session token")
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

Starts the server without a configured token. Each request supplies a Perplexity session token through `Authorization: Bearer`.

| Option        | Short | Default     | Description                                                         |
| ------------- | ----- | ----------- | ------------------------------------------------------------------- |
| `--host`      | `-H`  | `127.0.0.1` | Bind address                                                        |
| `--port`      | `-p`  | `8000`      | Port to listen on                                                   |
| `--reload`    |       | `False`     | Enable auto-reload (dev mode)                                       |
| `--log-level` |       | `info`      | Uvicorn log level (`debug`, `info`, `warning`, `error`, `critical`) |

```bash
# Bind to localhost:8000
perplexity-webui-scraper api

# Expose on the network
perplexity-webui-scraper api --host 0.0.0.0 --port 8080
```

### Running via Container (Podman)

The REST API is published as a multi-arch image on GHCR for `linux/amd64` and `linux/arm64`.

```bash
# Pull a release image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:latest

# Run the server (exposed on port 8000)
podman run -d -p 8000:8000 --name perp-api ghcr.io/henrique-coder/perplexity-webui-scraper:latest
```

For local development, use the provided container files:

```bash
# Containerfile: installs the `api` extra, exposes port 8000, and starts the REST server.
podman build -t perplexity-api -f Containerfile .
podman run --rm -p 8000:8000 --name perp-api perplexity-api

# Containerfile.mcp: installs the `mcp` extra and starts the stdio MCP server.
podman build -t perplexity-mcp -f Containerfile.mcp .
podman run --rm -e PERPLEXITY_SESSION_TOKEN=your_token perplexity-mcp
```

### Authentication

Pass your Perplexity session token as the Bearer token in every request. The server caches clients by token and reuses their sessions:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello!"}]}'
```

Returns `HTTP 401` if the header is missing or malformed.

### Endpoints

| Method | Path                   | Description                                 |
| ------ | ---------------------- | ------------------------------------------- |
| `GET`  | `/v1/models`           | List registered models                      |
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

Pass Perplexity-specific settings such as `search_focus`, `citation_mode`, or `coordinates` through the OpenAI SDK's `extra_body` dictionary. The API reads them from the `"perplexity"` block.

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
            "save_to_library": True,
        }
    },
)

print(response.choices[0].message.content)
```

With `curl`, add `"perplexity"` to the JSON payload:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_SESSION_TOKEN" \
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
The UUID is different from the URL slug. See [ConversationConfig](#conversationconfig) for how to obtain it.

```python
response = client.chat.completions.create(
    model="perplexity/best",
    messages=[{"role": "user", "content": "Research notes for project X"}],
    extra_body={"perplexity": {"space_uuid": "12345678-1234-1234-1234-123456789abc"}},
)
```

### Multimodal uploads

The REST API accepts OpenAI-style message content containing `text` parts and base64 Data URLs in `image_url` parts. It does not implement remote image URLs or every OpenAI Vision input form.

The server decodes each Data URL and uploads the resulting file to Perplexity before sending the prompt.

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
                {"type": "image_url", "image_url": {"url": f"data:application/pdf;base64,{pdf_b64}"}},
            ],
        }
    ],
)

print(response.choices[0].message.content)
```

**Example with cURL:**

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_SESSION_TOKEN" \
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
