"""Shared helpers for building queries and conversation configs from API requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from perplexity_webui_scraper.config.conversation import ConversationConfig


if TYPE_CHECKING:
    from perplexity_webui_scraper.api.schemas.request import ChatCompletionRequest, PerplexityExtensions
    from perplexity_webui_scraper.core.file_types import FileInput


_JSON_SYSTEM_PROMPT = (
    "Respond ONLY with valid JSON. Do not include any prose, explanation, or markdown fences outside the JSON object."
)


def build_query_and_files(request: ChatCompletionRequest) -> tuple[str, list[FileInput]]:
    """Extract query text and image attachments from a validated chat request."""
    parts: list[str] = []
    files: list[FileInput] = []

    if request.perplexity is not None and request.perplexity.response_format == "json_object":
        parts.insert(0, f"[System]: {_JSON_SYSTEM_PROMPT}")

    for message in request.messages:
        text = message.text()
        if message.role == "system":
            if text:
                parts.insert(0, f"[System]: {text}")
        elif text:
            parts.append(text)

        files.extend(message.image_bytes())

    return "\n\n".join(parts), files


def build_conversation_config(model: str, ext: PerplexityExtensions | None) -> ConversationConfig:
    """Build a conversation configuration from the model and optional extensions."""
    if ext is None:
        return ConversationConfig(model=model)

    return ConversationConfig(
        model=model,
        citation_mode=ext.citation_mode or "clean",
        search_focus=ext.search_focus or "web",
        source_focus=ext.source_focus or "web",
        time_range=ext.time_range or "all",
        save_to_library=ext.save_to_library,
        language=ext.language or "en-US",
        timezone=ext.timezone,
        latitude=ext.latitude,
        longitude=ext.longitude,
        space_uuid=ext.space_uuid,
        allow_risky_model=ext.allow_risky_model,
        custom_model_mode=ext.custom_model_mode,
        research_interaction=ext.research_interaction,
    )
