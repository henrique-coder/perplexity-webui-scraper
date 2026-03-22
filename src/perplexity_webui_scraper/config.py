"""Configuration classes."""

from __future__ import annotations

from os import PathLike  # noqa: TC003

from pydantic import BaseModel, ConfigDict

from .types import CitationMode, Coordinates, LogLevel, SearchFocus, SourceFocus, TimeRange  # noqa: TC001


class ConversationConfig(BaseModel):
    """Default settings for a conversation."""

    model: str | None = None
    citation_mode: CitationMode = "clean"
    save_to_library: bool = False
    search_focus: SearchFocus = "web"
    source_focus: SourceFocus | list[SourceFocus] = "web"
    time_range: TimeRange = "all"
    language: str = "en-US"
    timezone: str | None = None
    coordinates: Coordinates | None = None


class ClientConfig(BaseModel):
    """HTTP client settings."""

    model_config = ConfigDict(frozen=True)

    timeout: int = 3600
    impersonate: str = "chrome"
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_jitter: float = 0.5
    requests_per_second: float = 0.5
    rotate_fingerprint: bool = True
    max_init_query_length: int = 2000
    logging_level: LogLevel = "disabled"
    log_file: str | PathLike[str] | None = None
