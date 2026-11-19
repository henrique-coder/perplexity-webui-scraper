"""Request and response schema exports."""

from __future__ import annotations

from perplexity_webui_scraper.api.schemas.errors import ErrorDetail, ErrorResponse
from perplexity_webui_scraper.api.schemas.models import ModelCatalogMetadata, ModelList, ModelObject
from perplexity_webui_scraper.api.schemas.request import (
    ChatCompletionRequest,
    ChatMessage,
    ContentPart,
    ContentPartImageUrl,
    ContentPartText,
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
    "ErrorDetail",
    "ErrorResponse",
    "ModelCatalogMetadata",
    "ModelList",
    "ModelObject",
    "PerplexityExtensions",
    "PerplexityResponseExtensions",
]
