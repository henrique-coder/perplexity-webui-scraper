"""
Response types and data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Coordinates:
    """
    Geographic coordinates (lat/lng).
    """

    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    """
    A single search result.
    """

    title: str | None = None
    snippet: str | None = None
    url: str | None = None


@dataclass(slots=True)
class Response:
    """
    Response from Perplexity AI.
    """

    title: str | None = None
    answer: str | None = None
    chunks: list[str] = field(default_factory=list)
    last_chunk: str | None = None
    search_results: list[SearchResultItem] = field(default_factory=list)
    conversation_uuid: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _FileInfo:
    """
    Internal file info for uploads.
    """

    path: str
    size: int
    mimetype: str
    is_image: bool
