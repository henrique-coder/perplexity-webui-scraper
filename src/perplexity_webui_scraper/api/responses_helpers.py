"""Translate supported Responses input items into the shared internal request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper.api.schemas.request import (
    ChatCompletionRequest,
    ChatMessage,
    ContentPartImageUrl,
    ContentPartText,
    PerplexityExtensions,
)


if TYPE_CHECKING:
    from perplexity_webui_scraper.api.schemas.responses import ResponsesRequest


def to_chat_completion_request(request: ResponsesRequest) -> ChatCompletionRequest:
    """Convert Responses text/data-image inputs into the common request schema."""
    messages: list[ChatMessage] = []
    if isinstance(request.input, str):
        messages.append(ChatMessage(role="user", content=request.input))
    else:
        for item in request.input:
            if item.get("type", "message") != "message":
                raise ValueError("Only Responses message input items are supported")
            role = item.get("role")
            if role not in {"system", "developer", "user", "assistant"}:
                raise ValueError("Responses input messages must use system, developer, user, or assistant role")
            raw_content = item.get("content", "")
            content = _translate_content(raw_content)
            messages.append(ChatMessage(role="system" if role == "developer" else role, content=content))
    if request.instructions:
        messages.insert(0, ChatMessage(role="system", content=request.instructions))
    extensions = PerplexityExtensions.model_validate(request.perplexity) if request.perplexity is not None else None
    return ChatCompletionRequest(model=request.model, messages=messages, stream=request.stream, perplexity=extensions)


def _translate_content(raw_content: Any) -> str | list[ContentPartText | ContentPartImageUrl]:
    if isinstance(raw_content, str):
        return raw_content
    if not isinstance(raw_content, list):
        raise TypeError("Responses message content must be text or an array of content items")
    translated: list[ContentPartText | ContentPartImageUrl] = []
    for part in raw_content:
        if not isinstance(part, dict):
            raise TypeError("Responses content items must be objects")
        if part.get("type") == "input_text":
            text = part.get("text")
            if not isinstance(text, str):
                raise TypeError("input_text content requires a text string")
            translated.append(ContentPartText(type="text", text=text))
        elif part.get("type") == "input_image":
            image_url = part.get("image_url")
            if not isinstance(image_url, str) or not image_url.startswith("data:"):
                raise ValueError("Only base64 data-URL images are supported; remote image URLs are not fetched")
            translated.append(ContentPartImageUrl(type="image_url", image_url={"url": image_url}))
        else:
            raise ValueError(f"Unsupported Responses content type: {part.get('type')!r}")
    return translated
