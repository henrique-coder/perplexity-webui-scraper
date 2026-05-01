"""Shared ask logic and dynamic tool factory for MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.response import Coordinates


if TYPE_CHECKING:
    from perplexity_webui_scraper._internal.types import (
        SearchFocus,
        SourceFocus,
        TimeRange,
    )
    from perplexity_webui_scraper.core.client import Perplexity
    from perplexity_webui_scraper.models.types import Model


def _ask(
    client: Perplexity,
    model: Model,
    query: str,
    search_focus: SearchFocus = "web",
    source_focus: SourceFocus = "web",
    time_range: TimeRange = "all",
    language: str = "en-US",
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    """Execute a single Perplexity query and return a structured result dict.

    Args:
        client: Active :class:`~perplexity_webui_scraper.Perplexity` client.
        model: The resolved :class:`~perplexity_webui_scraper.models.types.Model`.
        query: The user's search query.
        search_focus: ``"web"`` for web search; ``"writing"`` for pure generation.
        source_focus: Source category filter.
        time_range: Recency filter for search results.
        language: BCP-47 response language tag.
        latitude: Optional latitude for localised results.
        longitude: Optional longitude for localised results.

    Returns:
        Dict with ``answer``, ``search_results``, and ``conversation_uuid`` keys.
    """
    coordinates: Coordinates | None = None

    if latitude is not None and longitude is not None:
        coordinates = Coordinates(latitude=latitude, longitude=longitude)

    config = ConversationConfig(
        model=model.id,
        search_focus=search_focus,
        source_focus=source_focus,
        time_range=time_range,
        citation_mode="clean",
        language=language,
        coordinates=coordinates,
    )

    conversation = client.create_conversation(config)
    conversation.ask(query)

    results = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in conversation.search_results]

    return {
        "answer": conversation.answer,
        "search_results": results,
        "conversation_uuid": conversation.uuid,
    }
