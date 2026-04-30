"""Configuration classes."""

from __future__ import annotations

from os import PathLike  # noqa: TC003

from curl_cffi.requests import BrowserTypeLiteral  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from .types import CitationMode, Coordinates, LogLevel, SearchFocus, SourceFocus, TimeRange  # noqa: TC001


class ConversationConfig(BaseModel):
    """Settings for a single conversation thread."""

    model: str | None = Field(
        default=None,
        description='Model ID string (e.g. "openai/gpt-5.4"). None falls back to "perplexity/best" (auto-selection).',
    )
    search_focus: SearchFocus = Field(
        default="web",
        description='"web" for web search, "writing" for a writing-focused, source-free response.',
    )
    source_focus: SourceFocus | list[SourceFocus] = Field(
        default="web",
        description='Source filter(s): "web", "academic", "social", "finance", "all", or a list.',
    )
    time_range: TimeRange = Field(
        default="all",
        description='Recency filter for results: "all", "day", "week", "month", or "year".',
    )
    citation_mode: CitationMode = Field(
        default="clean",
        description='"clean" strips markers, "markdown" converts to links, "default" keeps originals.',
    )
    language: str = Field(
        default="en-US",
        description='BCP-47 language tag for the response (e.g. "pt-BR", "en-US").',
    )
    timezone: str | None = Field(
        default=None,
        description='IANA timezone string (e.g. "America/Sao_Paulo"). None uses server default.',
    )
    coordinates: Coordinates | None = Field(
        default=None,
        description="Geographic coordinates (latitude/longitude) for localised search results.",
    )
    save_to_library: bool = Field(
        default=False,
        description="Save the conversation to your Perplexity library.",
    )
    space_uuid: str | None = Field(
        default=None,
        description=(
            "UUID of the Perplexity Space to post the thread into. "
            "Obtain via DevTools (Network → perplexity_ask → target_collection_uuid) "
            "or the Complexity extension. The URL slug is NOT the UUID."
        ),
    )


class ClientConfig(BaseModel):
    """HTTP client and resilience settings."""

    model_config = ConfigDict(frozen=True)

    timeout: int = Field(
        default=3600,
        description="Request timeout in seconds (default: 1 hour).",
    )
    impersonate: BrowserTypeLiteral = Field(
        default="chrome",
        description='Browser fingerprint to impersonate (e.g. "chrome", "firefox").',
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts on transient errors.",
    )
    retry_base_delay: float = Field(
        default=1.0,
        description="Initial backoff delay in seconds before the first retry.",
    )
    retry_max_delay: float = Field(
        default=60.0,
        description="Maximum backoff delay cap in seconds.",
    )
    retry_jitter: float = Field(
        default=0.5,
        description="Jitter factor (0-1) applied to retry delay randomisation.",
    )
    rotate_fingerprint: bool = Field(
        default=True,
        description="Rotate the browser fingerprint to a new profile on each retry.",
    )
    requests_per_second: float = Field(
        default=0.5,
        description="Rate limit expressed as maximum requests per second.",
    )
    max_init_query_length: int = Field(
        default=2000,
        description="Truncate the search-init query to this length to avoid HTTP 414 errors. Set 0 to disable.",
    )
    logging_level: LogLevel = Field(
        default="disabled",
        description='Log verbosity: "disabled", "debug", "info", "warning", "error", or "critical".',
    )
    log_file: str | PathLike[str] | None = Field(
        default=None,
        description="Write log output to this file path instead of stderr.",
    )
