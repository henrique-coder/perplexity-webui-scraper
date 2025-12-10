"""Configuration classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .enums import CitationMode, SearchFocus, SourceFocus, TimeRange


if TYPE_CHECKING:
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
    """HTTP client settings."""

    timeout: int = 1800
    impersonate: str = "chrome"
