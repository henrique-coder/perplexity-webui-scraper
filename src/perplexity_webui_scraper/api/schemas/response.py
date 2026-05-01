"""OpenAI-compatible chat completion response schemas."""

from __future__ import annotations

from time import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel


class ModelObject(BaseModel):
    """A single model entry in the ``GET /v1/models`` response.

    Attributes:
        id: Canonical model ID (e.g. ``"perplexity/best"``).
        object: Always ``"model"``.
        created: Unix timestamp (always ``0`` — not tracked).
        owned_by: Model provider string.
    """

    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "perplexity"


class ModelList(BaseModel):
    """Response for ``GET /v1/models``.

    Attributes:
        object: Always ``"list"``.
        data: List of :class:`ModelObject` entries.
    """

    object: Literal["list"] = "list"
    data: list[ModelObject]


class PerplexityResponseExtensions(BaseModel):
    """Perplexity-specific metadata included in API responses.

    Returned under the ``perplexity`` key alongside standard OpenAI fields.
    Use ``thread_uuid`` in subsequent requests to continue the conversation.

    Attributes:
        thread_uuid: UUID of the conversation thread for follow-up queries.
    """

    thread_uuid: str


class ChatCompletionMessage(BaseModel):
    """Message within a completion choice.

    Attributes:
        role: Always ``"assistant"`` for model responses.
        content: The response text.
    """

    role: Literal["assistant"] = "assistant"
    content: str | None = None


class ChatCompletionChoice(BaseModel):
    """A single completion choice (non-streaming).

    Attributes:
        index: Choice index (always ``0`` — single choice only).
        message: The :class:`ChatCompletionMessage`.
        finish_reason: Stop reason (always ``"stop"``).
    """

    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Literal["stop"] | None = "stop"


class ChatCompletionUsage(BaseModel):
    """Token usage statistics.

    All values are ``0`` — the scraper does not have access to token counts.

    Attributes:
        prompt_tokens: Always ``0``.
        completion_tokens: Always ``0``.
        total_tokens: Always ``0``.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible non-streaming chat completion response.

    Attributes:
        id: Unique completion ID in the format ``"chatcmpl-<hex>"``.
        object: Always ``"chat.completion"``.
        created: Unix timestamp of response creation.
        model: The model ID used.
        choices: List of completion choices (always one element).
        usage: Approximated-to-zero token usage.
        perplexity: Optional Perplexity-specific metadata (thread UUID).
    """

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = ChatCompletionUsage()
    perplexity: PerplexityResponseExtensions | None = None

    @classmethod
    def build(
        cls,
        model: str,
        content: str,
        thread_uuid: str | None = None,
    ) -> ChatCompletionResponse:
        """Build a response from a model ID, answer text, and optional thread UUID.

        Args:
            model: Model ID string used in the request.
            content: The assistant's response text.
            thread_uuid: UUID of the conversation thread (for follow-up support).

        Returns:
            A fully constructed :class:`ChatCompletionResponse`.
        """
        return cls(
            id=f"chatcmpl-{uuid4().hex}",
            created=int(time()),
            model=model,
            choices=[ChatCompletionChoice(message=ChatCompletionMessage(content=content))],
            perplexity=PerplexityResponseExtensions(thread_uuid=thread_uuid) if thread_uuid else None,
        )


class ChatCompletionChunkDelta(BaseModel):
    """Incremental content delta in a streaming chunk.

    Attributes:
        role: Set to ``"assistant"`` on the first chunk; absent thereafter.
        content: Incremental text content for this chunk.
    """

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """A single choice in a streaming chunk.

    Attributes:
        index: Always ``0``.
        delta: The :class:`ChatCompletionChunkDelta` for this chunk.
        finish_reason: ``"stop"`` on the final chunk; ``None`` otherwise.
    """

    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Literal["stop"] | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible SSE streaming chunk.

    Attributes:
        id: Shared completion ID across all chunks in a stream.
        object: Always ``"chat.completion.chunk"``.
        created: Unix timestamp (shared across all chunks in a stream).
        model: Model ID string.
        choices: List of choice deltas (always one element).
        perplexity: Perplexity metadata, present only on the final chunk.
    """

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]
    perplexity: PerplexityResponseExtensions | None = None

    def to_sse_line(self) -> str:
        r"""Serialize this chunk to an SSE ``data:`` line.

        Returns:
            String in the format ``"data: <json>\\n\\n"``.
        """
        return f"data: {self.model_dump_json(exclude_none=True)}\n\n"
