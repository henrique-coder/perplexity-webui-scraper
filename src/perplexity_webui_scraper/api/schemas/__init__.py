"""API schemas package — re-exports all request and response schemas."""

from __future__ import annotations

from perplexity_webui_scraper.api.schemas.errors import ErrorDetail, ErrorResponse
from perplexity_webui_scraper.api.schemas.request import (
    ChatCompletionRequest,
    ChatMessage,
    ContentPart,
    ContentPartImageUrl,
    ContentPartText,
    CoordinatesInput,
    PerplexityExtensions,
)
from perplexity_webui_scraper.api.schemas.response import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessage,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ModelList,
    ModelObject,
    PerplexityResponseExtensions,
)


__all__: list[str] = [
    "ChatCompletionChoice",
    "ChatCompletionChunk",
    "ChatCompletionChunkChoice",
    "ChatCompletionChunkDelta",
    "ChatCompletionMessage",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatCompletionUsage",
    "ChatMessage",
    "ContentPart",
    "ContentPartImageUrl",
    "ContentPartText",
    "CoordinatesInput",
    "ErrorDetail",
    "ErrorResponse",
    "ModelList",
    "ModelObject",
    "PerplexityExtensions",
    "PerplexityResponseExtensions",
]
