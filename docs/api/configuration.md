# Configuration

Configuration classes are validated with Pydantic on instantiation.

## `ClientConfig`

Immutable transport, retry, rate-limiting, and logging configuration passed to `Perplexity(session_token, config=ClientConfig(...))`.

```python
from perplexity_webui_scraper import ClientConfig

config = ClientConfig(
    timeout=3600,
    max_retries=3,
    requests_per_second=0.5,
    logging_level="info",
)
```

| Field                   | Type                                                                   | Default      | Description                                                       |
| ----------------------- | ---------------------------------------------------------------------- | ------------ | ----------------------------------------------------------------- |
| `timeout`               | `int`                                                                  | `3600`       | Request timeout in seconds.                                       |
| `impersonate`           | `BrowserTypeLiteral`                                                   | `"chrome"`   | Browser TLS/HTTP fingerprint profile used by `curl-cffi`.         |
| `max_retries`           | `int`                                                                  | `3`          | Maximum retry attempts on transient network or rate-limit errors. |
| `retry_base_delay`      | `float`                                                                | `1.0`        | Initial exponential backoff delay in seconds.                     |
| `retry_max_delay`       | `float`                                                                | `60.0`       | Maximum retry delay in seconds.                                   |
| `retry_jitter`          | `float`                                                                | `0.5`        | Randomized jitter factor between `0.0` and `1.0`.                 |
| `rotate_fingerprint`    | `bool`                                                                 | `True`       | Recreate the HTTP session after a retry.                          |
| `requests_per_second`   | `float`                                                                | `0.5`        | Maximum request rate (`0` disables client-side throttling).       |
| `max_init_query_length` | `int`                                                                  | `2000`       | Maximum search-init query length (`0` disables truncation).       |
| `logging_level`         | `Literal["disabled", "debug", "info", "warning", "error", "critical"]` | `"disabled"` | Library log verbosity (`"disabled"` suppresses library logs).     |
| `log_file`              | `str \| PathLike[str] \| None`                                         | `None`       | Optional file path to append logs to instead of `stderr`.         |

## `ConversationConfig`

Per-thread settings passed to `client.create_conversation(ConversationConfig(...))`.

```python
from perplexity_webui_scraper import ConversationConfig

config = ConversationConfig(
    model="perplexity/best",
    citation_mode="markdown",
    search_focus="web",
    source_focus=["web", "academic"],
    time_range="month",
    language="en-US",
)
```

| Field                  | Type                                             | Default     | Description                                                                                                 |
| ---------------------- | ------------------------------------------------ | ----------- | ----------------------------------------------------------------------------------------------------------- |
| `model`                | `str \| None`                                    | `None`      | Model ID string (defaults to `"perplexity/best"` when `None`).                                              |
| `search_focus`         | `Literal["web", "writing"]`                      | `"web"`     | `"web"` enables web search and citations; `"writing"` generates without web search.                         |
| `source_focus`         | `SourceFocus \| list[SourceFocus]`               | `"web"`     | One or more of `"web"`, `"academic"`, `"social"`, `"finance"`, or `"all"`.                                  |
| `time_range`           | `Literal["all", "day", "week", "month", "year"]` | `"all"`     | Recency filter for web search results.                                                                      |
| `citation_mode`        | `Literal["default", "markdown", "clean"]`        | `"clean"`   | `"default"` keeps `[1]` markers, `"markdown"` links them, and `"clean"` removes them.                       |
| `language`             | `str`                                            | `"en-US"`   | BCP-47 response language tag (e.g. `"en-US"`, `"pt-BR"`).                                                   |
| `timezone`             | `str \| None`                                    | `None`      | Optional IANA timezone identifier (e.g. `"America/Sao_Paulo"`).                                             |
| `latitude`             | `float \| None`                                  | `None`      | Latitude in degrees (`-90` to `90`). Must be provided together with `longitude`.                            |
| `longitude`            | `float \| None`                                  | `None`      | Longitude in degrees (`-180` to `180`). Must be provided together with `latitude`.                          |
| `save_to_library`      | `bool`                                           | `False`     | Save the conversation thread to the Perplexity account library.                                             |
| `space_uuid`           | `str \| None`                                    | `None`      | Target Perplexity Space UUID (`target_collection_uuid`).                                                    |
| `allow_risky_model`    | `bool`                                           | `False`     | Acknowledge models with `"unknown"` or `"unavailable"` status.                                              |
| `custom_model_mode`    | `Literal["copilot", "search", "research"]`       | `"copilot"` | Request mode used when `model` is a `custom:<identifier>` string.                                           |
| `research_interaction` | `Literal["auto", "manual"]`                      | `"auto"`    | `"auto"` answers Deep Research clarification prompts; `"manual"` raises `ResearchClarifyingQuestionsError`. |

## Location values

`ConversationConfig` and the API extension accept `latitude` and `longitude` as separate fields. Set both or neither. Latitude ranges from -90 through 90 degrees; longitude ranges from -180 through 180 degrees.

In a REST API request, the object is nested under the `perplexity` key:

```json
{ "perplexity": { "latitude": -23.5, "longitude": -46.6 } }
```
