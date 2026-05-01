"""Public data models for Perplexity AI responses.

These models are part of the public API and are re-exported from the
top-level ``perplexity_webui_scraper`` namespace.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from perplexity_webui_scraper._internal.types import Coordinates


__all__ = ["Coordinates", "Response", "SearchResultItem"]


class SearchResultItem(BaseModel):
    """A single web source cited in a Perplexity response.

    Attributes:
        url: Full URL of the source page.  ``None`` if unavailable.
        title: Page or article title.  ``None`` if unavailable.
        snippet: Short excerpt from the source page.  ``None`` if unavailable.
    """

    model_config = ConfigDict(frozen=True)

    url: str | None = None
    title: str | None = None
    snippet: str | None = None


class Response(BaseModel):
    """A single streaming response frame from Perplexity AI.

    Yielded by iterating over a :class:`~perplexity_webui_scraper.Conversation`
    in streaming mode.  The ``answer`` field is ``None`` on intermediate chunks
    and populated only on the final frame.

    Attributes:
        answer: Full, final response text.  ``None`` until the stream completes.
        chunks: All partial response chunks received so far during streaming.
        last_chunk: The most recently received chunk (shortcut to
            ``chunks[-1]``).  ``None`` if no chunks have arrived yet.
        search_results: Web sources cited in the response.
        conversation_uuid: Backend UUID identifying this conversation thread.
            Use this value to continue the conversation via
            ``thread_uuid`` in the API, or for your own bookkeeping.
        raw_data: Raw deserialized JSON payload from the last SSE frame.
            Useful for accessing fields not surfaced by the library.
    """

    answer: str | None = None
    chunks: list[str] = []
    last_chunk: str | None = None
    search_results: list[SearchResultItem] = []
    conversation_uuid: str | None = None
    raw_data: dict[str, Any] = {}

    model_config = ConfigDict(
        # Allow mutable defaults (lists/dicts) per-instance via copy-on-init
        # handled by Pydantic v2's default_factory behaviour for mutable fields.
    )
