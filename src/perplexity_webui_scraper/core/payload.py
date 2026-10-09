"""SSE payload construction for Perplexity API requests.

``build_payload()`` assembles the full JSON body sent to the
``/rest/sse/perplexity_ask`` endpoint.  All source/search/time mapping
tables live here as module-level constants so they are defined exactly once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final
from uuid import uuid4

from perplexity_webui_scraper._internal.constants import (
    API_VERSION,
    PROMPT_SOURCE,
    SEND_BACK_TEXT,
    USE_SCHEMATIZED_API,
)


if TYPE_CHECKING:
    from perplexity_webui_scraper.config.conversation import ConversationConfig
    from perplexity_webui_scraper.models.types import Model


# ---------------------------------------------------------------------------
# Mapping tables shared with the MCP tools.
# ---------------------------------------------------------------------------

SOURCE_MAP: Final[dict[str, str]] = {
    "web": "web",
    "academic": "scholar",
    "social": "social",
    "finance": "edgar",
    "all": "web",
}
"""Maps ``SourceFocus`` literals to Perplexity's internal source identifiers."""

TIME_MAP: Final[dict[str, str]] = {
    "all": "",
    "day": "DAY",
    "week": "WEEK",
    "month": "MONTH",
    "year": "YEAR",
}
"""Maps ``TimeRange`` literals to Perplexity's recency filter identifiers."""


def build_payload(
    query: str,
    model: Model,
    file_urls: list[str],
    config: ConversationConfig,
    backend_uuid: str | None,
    read_write_token: str | None,
) -> dict[str, Any]:
    """Build the JSON payload for a Perplexity SSE ask request.

    Args:
        query: The user's prompt text.
        model: Resolved :class:`~perplexity_webui_scraper.models.types.Model`.
        file_urls: List of S3 object URLs for attached files.
        config: Active :class:`~perplexity_webui_scraper.config.conversation.ConversationConfig`.
        backend_uuid: Conversation backend UUID from a previous response.
            ``None`` for the first query in a thread.
        read_write_token: Read-write token from the previous SSE response.
            ``None`` for the first query.

    Returns:
        Dict with ``"params"`` and ``"query_str"`` keys, ready for JSON
        serialization.
    """
    raw_sources = config.source_focus if isinstance(config.source_focus, list) else [config.source_focus]
    sources = ["web", "scholar"] if raw_sources == ["all"] else [SOURCE_MAP.get(s, "web") for s in raw_sources]

    client_coordinates: dict[str, Any] | None = None

    if config.coordinates is not None:
        client_coordinates = {
            "location_lat": config.coordinates.latitude,
            "location_lng": config.coordinates.longitude,
            "name": "",
        }

    frontend_uuid = str(uuid4())

    params: dict[str, Any] = {
        "attachments": file_urls,
        "language": config.language,
        "timezone": config.timezone,
        "client_coordinates": client_coordinates,
        "sources": sources,
        "frontend_uuid": frontend_uuid,
        "model_preference": model.identifier,
        "mode": model.mode,
        "search_focus": "internet",
        "skip_search_enabled": config.search_focus == "writing",
        "search_recency_filter": TIME_MAP.get(config.time_range, "") or None,
        "is_incognito": not config.save_to_library,
        "use_schematized_api": USE_SCHEMATIZED_API,
        "local_search_enabled": config.coordinates is not None,
        "prompt_source": PROMPT_SOURCE,
        "query_source": "home",
        "send_back_text_in_streaming_api": SEND_BACK_TEXT,
        "version": API_VERSION,
    }

    if backend_uuid is None:
        params["frontend_context_uuid"] = str(uuid4())

    # Space requests override incognito mode.

    if config.space_uuid:
        params["target_collection_uuid"] = config.space_uuid
        params["target_thread_access_level"] = 1
        params["query_source"] = "collection"
        params["is_incognito"] = False

    # Follow-up / continuation support

    if backend_uuid is not None:
        params["last_backend_uuid"] = backend_uuid
        params["query_source"] = "followup"
        params["followup_source"] = "link"

        if read_write_token:
            params["read_write_token"] = read_write_token

    return {"params": params, "query_str": query}
