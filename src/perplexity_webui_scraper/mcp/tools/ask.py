"""Shared ask logic and dynamic tool factory for MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from perplexity_webui_scraper._internal.exceptions import (
    FileAccessError,
    ModelAccessError,
    ModelStatusError,
)
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.client import Perplexity  # noqa: TC001
from perplexity_webui_scraper.models.types import Model  # noqa: TC001


def _ask(
    client: Perplexity,
    model: Model,
    query: str,
    search_focus: Literal["web", "writing"] = "web",
    source_focus: Literal["web", "academic", "social", "finance", "all"] = "web",
    time_range: Literal["all", "day", "week", "month", "year"] = "all",
    language: str = "en-US",
    latitude: float | None = None,
    longitude: float | None = None,
    allow_risky_model: bool = False,
    research_interaction: Literal["auto", "manual"] = "auto",
) -> dict[str, Any]:
    """Execute a single Perplexity query and return a structured result dict.

    Args:
        client: Active :class:`~perplexity_webui_scraper.Perplexity` client.
        model: The resolved :class:`~perplexity_webui_scraper.models.types.Model`.
        query: The user's search query.
        search_focus: ``"web"`` for web search; ``"writing"`` for pure generation.
        source_focus: One or more of ``"web"``, ``"academic"``, ``"social"``, ``"finance"``, or ``"all"``.
        time_range: ``"all"``, ``"day"``, ``"week"``, ``"month"``, or ``"year"``.
        language: BCP-47 response language tag.
        latitude: Optional latitude in degrees, from -90 through 90.
        longitude: Optional longitude in degrees, from -180 through 180. Both coordinates are required together.
        allow_risky_model: Acknowledge any non-available model status.
        research_interaction: ``"auto"`` answers Deep Research questions; ``"manual"`` returns them as an error.

    Returns:
        Dict with ``answer``, ``search_results``, and ``conversation_uuid`` keys.
    """
    config = ConversationConfig(
        model=model.id,
        search_focus=search_focus,
        source_focus=source_focus,
        time_range=time_range,
        citation_mode="clean",
        language=language,
        latitude=latitude,
        longitude=longitude,
        allow_risky_model=allow_risky_model,
        custom_model_mode=model.mode,
        research_interaction=research_interaction,
    )

    conversation = client.create_conversation(config)

    try:
        conversation.ask(query)
    except ModelAccessError as exc:
        return {
            "error": str(exc),
            "error_type": "model_access_denied",
            "model": exc.model_id,
            "required_tier": exc.required_tier,
            "account_tier": exc.account_tier,
        }
    except FileAccessError as exc:
        return {
            "error": str(exc),
            "error_type": "file_access_denied",
            "account_tier": exc.account_tier,
        }
    except ModelStatusError as exc:
        return {
            "error": str(exc),
            "error_type": "model_status_confirmation_required",
            "model": exc.model_id,
            "status": exc.status,
        }

    results = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in conversation.search_results]

    return {
        "answer": conversation.answer,
        "search_results": results,
        "conversation_uuid": conversation.uuid,
    }
