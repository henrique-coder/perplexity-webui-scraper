"""Response types and data models."""

from __future__ import annotations

from os import PathLike
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


# Type alias for accepted file inputs in ask():
#   - str | PathLike[str]          → local file path
#   - bytes                         → raw bytes (filename defaults to "file", mimetype auto-detected or octet-stream)
#   - tuple[bytes, str]             → (data, filename)         — mimetype guessed from filename
#   - tuple[bytes, str, str]        → (data, filename, mimetype)
FileInput = str | PathLike[str] | bytes | tuple[bytes, str] | tuple[bytes, str, str]


# Type aliases for intuitive string arguments
CitationMode = Literal["default", "markdown", "clean"]
SearchFocus = Literal["web", "writing"]
SourceFocus = Literal["web", "academic", "social", "finance", "all"]
TimeRange = Literal["all", "day", "week", "month", "year"]
LogLevel = Literal["disabled", "debug", "info", "warning", "error", "critical"]


class Coordinates(BaseModel):
    """Geographic coordinates (lat/lng)."""

    model_config = ConfigDict(frozen=True)

    latitude: float
    longitude: float


class SearchResultItem(BaseModel):
    """A single search result."""

    model_config = ConfigDict(frozen=True)

    title: str | None = None
    snippet: str | None = None
    url: str | None = None


class Response(BaseModel):
    """Response from Perplexity AI."""

    title: str | None = None
    answer: str | None = None
    chunks: list[str] = []
    last_chunk: str | None = None
    search_results: list[SearchResultItem] = []
    conversation_uuid: str | None = None
    raw_data: dict[str, Any] = {}


class _FileInfo(BaseModel):
    """Internal file info for uploads.

    Exactly one of ``path`` or ``data`` is set:
    - ``path`` — source filesystem path (bytes read lazily at upload time)
    - ``data`` — in-memory bytes (no filesystem access needed)
    """

    model_config = ConfigDict(frozen=True)

    filename: str
    size: int
    mimetype: str
    is_image: bool
    path: str | None = None
    data: bytes | None = None
