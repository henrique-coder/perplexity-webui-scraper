"""Response types and data models."""

from __future__ import annotations

from os import PathLike
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    """Geographic coordinates (latitude/longitude)."""

    model_config = ConfigDict(frozen=True)

    latitude: float = Field(description="Latitude in decimal degrees (-90 to +90).")
    longitude: float = Field(description="Longitude in decimal degrees (-180 to +180).")


class SearchResultItem(BaseModel):
    """A single search result returned by Perplexity."""

    model_config = ConfigDict(frozen=True)

    url: str | None = Field(default=None, description="Full URL of the source.")
    title: str | None = Field(default=None, description="Page or article title.")
    snippet: str | None = Field(default=None, description="Short excerpt from the source page.")


class Response(BaseModel):
    """Response from Perplexity AI."""

    answer: str | None = Field(default=None, description="Full, final response text. None until complete.")
    chunks: list[str] = Field(default_factory=list, description="Partial response chunks received during streaming.")
    last_chunk: str | None = Field(default=None, description="Most recently received chunk (shortcut to chunks[-1]).")
    search_results: list[SearchResultItem] = Field(
        default_factory=list, description="Web sources cited in the response."
    )
    conversation_uuid: str | None = Field(
        default=None, description="Backend UUID identifying this conversation thread."
    )
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw deserialized response payload.")


class _FileInfo(BaseModel):
    """Internal upload descriptor. Exactly one of ``path`` or ``data`` is set."""

    model_config = ConfigDict(frozen=True)

    filename: str = Field(description="Display name sent to Perplexity.")
    mimetype: str = Field(description='MIME type string (e.g. "image/jpeg").')
    size: int = Field(description="File size in bytes.")
    is_image: bool = Field(description="Whether the file is an image type.")
    path: str | None = Field(
        default=None, description="Absolute filesystem path. Bytes are read lazily at upload time."
    )
    data: bytes | None = Field(default=None, description="In-memory bytes. No filesystem access needed.")
