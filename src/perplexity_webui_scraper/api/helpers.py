"""Shared helpers for building queries and conversation configs from API requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.response import Coordinates


if TYPE_CHECKING:
    from perplexity_webui_scraper._internal.types import FileInput
    from perplexity_webui_scraper.api.schemas.request import (
        ChatCompletionRequest,
        PerplexityExtensions,
    )

_JSON_SYSTEM_PROMPT = (
    "Respond ONLY with valid JSON. Do not include any prose, explanation, or markdown fences outside the JSON object."
)


def build_query_and_files(
    request: ChatCompletionRequest,
) -> tuple[str, list[FileInput]]:
    """Extract the query string and file attachments from message history.

    System messages are prepended with ``[System]: `` prefix.  User and
    assistant messages follow in order.  Base64 ``image_url`` parts are
    decoded into ``(bytes, filename, mimetype)`` tuples.

    When ``perplexity.response_format == "json_object"``, a JSON-output
    instruction is injected as the leading system message.

    Args:
        request: Validated :class:`ChatCompletionRequest`.

    Returns:
        ``(query_text, files)`` tuple.
    """
    parts: list[str] = []
    files: list[FileInput] = []

    if request.perplexity is not None and request.perplexity.response_format == "json_object":
        parts.insert(0, f"[System]: {_JSON_SYSTEM_PROMPT}")

    for msg in request.messages:
        text = msg.text()

        match msg.role:
            case "system":
                if text:
                    parts.insert(0, f"[System]: {text}")
            case "user" | "assistant":
                if text:
                    parts.append(text)

        files.extend(msg.image_bytes())

    return "\n\n".join(parts), files


def build_conversation_config(
    model: str,
    ext: PerplexityExtensions | None,
) -> ConversationConfig:
    """Build a :class:`ConversationConfig` from a model ID and Perplexity extensions.

    Args:
        model: Model ID from the request.
        ext: Optional :class:`PerplexityExtensions` block.

    Returns:
        Fully populated :class:`ConversationConfig`.
    """
    if ext is None:
        return ConversationConfig(model=model)

    coordinates: Coordinates | None = None

    if ext.coordinates is not None:
        coordinates = Coordinates(
            latitude=ext.coordinates.latitude,
            longitude=ext.coordinates.longitude,
        )

    return ConversationConfig(
        model=model,
        citation_mode=ext.citation_mode or "clean",
        search_focus=ext.search_focus or "web",
        source_focus=ext.source_focus or "web",
        time_range=ext.time_range or "all",
        save_to_library=ext.save_to_library,
        language=ext.language or "en-US",
        timezone=ext.timezone,
        coordinates=coordinates,
        space_uuid=ext.space_uuid,
    )
