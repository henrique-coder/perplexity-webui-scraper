"""Configuration classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .enums import CitationMode, LogLevel, SearchFocus, SourceFocus, TimeRange


if TYPE_CHECKING:
    from pathlib import Path

    from .models import Model
    from .types import Coordinates


@dataclass(slots=True)
class ConversationConfig:
    """Default settings for a conversation. Can be overridden per message."""

    model: Model | None = None
    citation_mode: CitationMode = CitationMode.CLEAN
    save_to_library: bool = False
    search_focus: SearchFocus = SearchFocus.WEB
    source_focus: SourceFocus | list[SourceFocus] = SourceFocus.WEB
    time_range: TimeRange = TimeRange.ALL
    language: str = "en-US"
    timezone: str | None = None
    coordinates: Coordinates | None = None


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """
    HTTP client settings.

    Attributes:
        timeout: Request timeout in seconds.
        impersonate: Browser to impersonate (e.g., "chrome", "edge", "safari").
        max_retries: Maximum retry attempts for failed requests.
        retry_base_delay: Initial delay in seconds before first retry.
        retry_max_delay: Maximum delay between retries.
        retry_jitter: Random jitter factor (0-1) to add to delays.
        requests_per_second: Rate limit for requests (0 to disable).
        rotate_fingerprint: Whether to rotate browser fingerprint on retries.
        logging_level: Logging verbosity level. Default is DISABLED.
        log_file: Optional file path for persistent logging. If set, logs go to file only.
                  If None, logs go to console. All logs are appended.
    """

    timeout: int = 3600
    impersonate: str = "chrome"
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_jitter: float = 0.5
    requests_per_second: float = 0.5
    rotate_fingerprint: bool = True
    logging_level: LogLevel = LogLevel.DISABLED
    log_file: str | Path | None = None
