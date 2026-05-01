"""Pydantic models for the OpenAI-compatible wire format."""

from __future__ import annotations

from base64 import b64decode
from time import time
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator


if TYPE_CHECKING:
    from perplexity_webui_scraper.models import ModelRegistry


class ContentPartText(BaseModel):
    """A text part within a multimodal message."""

    type: Literal["text"]
    text: str


class ContentPartImageUrl(BaseModel):
    """An image part within a multimodal message (URL or base64 data URI)."""

    type: Literal["image_url"]
    image_url: dict[str, str]  # {"url": "https://..." | "data:image/...;base64,..."}


ContentPart = ContentPartText | ContentPartImageUrl


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant"]
    content: str | list[ContentPart]

    def text(self) -> str:
        """Return the plain-text portion of this message."""
        if isinstance(self.content, str):
            return self.content

        return "\n".join(p.text for p in self.content if isinstance(p, ContentPartText))

    def image_bytes(self) -> list[tuple[bytes, str, str]]:
        """Return a list of ``(data, filename, mimetype)`` tuples for image parts.

        Only ``data:`` URIs (base64-encoded) are supported — external URLs are
        not fetched to avoid unpredictable network calls from the server.
        """
        if isinstance(self.content, str):
            return []

        results: list[tuple[bytes, str, str]] = []

        for part in self.content:
            if not isinstance(part, ContentPartImageUrl):
                continue

            url = part.image_url.get("url", "")

            if not url.startswith("data:"):
                continue

            try:
                header, b64data = url.split(",", 1)
                mimetype = header.split(":")[1].split(";")[0]
                ext = mimetype.split("/")[-1].split("+")[0]  # e.g. "jpeg" from "image/jpeg"
                filename = f"image.{ext}"
                data = b64decode(b64data)
                results.append((data, filename, mimetype))
            except Exception:
                continue

        return results


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request with Perplexity extensions.

    Standard OpenAI fields that Perplexity does not support (``temperature``,
    ``top_p``, ``n``, ``max_tokens``, …) are accepted for drop-in client
    compatibility but silently ignored.

    The ``perplexity`` block exposes all ``ConversationConfig`` knobs:

        {
          "model": "gpt-5.4",
          "messages": [...],
          "perplexity": {
            "citation_mode":   "clean",
            "search_focus":    "web",
            "source_focus":    ["web", "academic"],
            "time_range":      "last_week",
            "save_to_library": false,
            "language":        "pt-BR",
            "timezone":        "America/Sao_Paulo",
            "coordinates":     {"latitude": -23.5, "longitude": -46.6}
          }
        }
    """

    model_config = ConfigDict(extra="allow")

    # Standard OpenAI fields
    model: str
    messages: list[ChatMessage]
    stream: bool = False

    # Perplexity extensions block
    perplexity: PerplexityExtensions | None = None


class PerplexityExtensions(BaseModel):
    """Custom Perplexity configuration passed under the ``perplexity`` key.

    All fields are optional — omitted fields fall back to the server defaults.
    """

    model_config = ConfigDict(extra="ignore")

    citation_mode: Literal["default", "markdown", "clean"] | None = None
    """Citation format: ``clean`` (default), ``markdown``, or ``default``."""

    search_focus: Literal["web", "writing"] | None = None
    """Search type: ``web`` (default) or ``writing``."""

    source_focus: (
        Literal["web", "academic", "social", "finance", "all"]
        | list[Literal["web", "academic", "social", "finance", "all"]]
        | None
    ) = None
    """Source filter: ``web``, ``academic``, ``social``, ``finance``, or a list."""

    time_range: Literal["all", "day", "week", "month", "year"] | None = None
    """Recency filter for search results."""

    save_to_library: bool = False
    """Save the conversation to your Perplexity library."""

    language: str | None = None
    """BCP-47 language tag for the response (e.g. ``"pt-BR"``, ``"en-US"``)."""

    timezone: str | None = None
    """IANA timezone string (e.g. ``"America/Sao_Paulo"``)."""

    coordinates: CoordinatesInput | None = None
    """Geographic location for localised results."""

    space_uuid: str | None = None
    """UUID of the Perplexity Space (collection) to post the thread into.

    How to obtain the Space UUID:
    - **Browser DevTools**: open the Space, make any query, Network tab →
      ``perplexity_ask`` request → copy ``target_collection_uuid``.
    - **Complexity extension**: exposes Space UUIDs directly in the browser UI.

    Note: the URL slug (e.g. ``questions-9emjYx__RDaUatwqW144tQ``) is **not**
    the UUID — they are completely different identifiers.
    """

    thread_uuid: str | None = None
    """UUID of an existing conversation thread to continue.

    When provided, the server reuses the cached ``Conversation`` object and
    sends only the last user message as a follow-up.  The response will
    include the same ``thread_uuid`` in the ``perplexity`` response block.

    If the conversation has expired from the cache (30-minute TTL), the
    server returns a 404 error suggesting the client start a new conversation.
    """

    @model_validator(mode="before")
    @classmethod
    def _normalise_strings(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Lowercase all string fields for case-insensitive matching."""
        if not isinstance(values, dict):
            return values

        for key in ("citation_mode", "search_focus", "time_range"):
            if isinstance(values.get(key), str):
                values[key] = values[key].lower()

        if isinstance(values.get("source_focus"), str):
            values["source_focus"] = values["source_focus"].lower()
        elif isinstance(values.get("source_focus"), list):
            values["source_focus"] = [s.lower() if isinstance(s, str) else s for s in values["source_focus"]]

        return values


class CoordinatesInput(BaseModel):
    """Latitude/longitude pair for the ``perplexity.coordinates`` field."""

    latitude: float
    longitude: float


class PerplexityResponseExtensions(BaseModel):
    """Perplexity-specific metadata included in API responses.

    Returned under the ``perplexity`` key alongside standard OpenAI fields.
    """

    thread_uuid: str
    """UUID of the conversation thread.  Use this value in subsequent requests
    to continue the same conversation."""


class ChatCompletionMessage(BaseModel):
    """Message in a completion choice."""

    role: Literal["assistant"] = "assistant"
    content: str | None = None


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Literal["stop"] | None = "stop"


class ChatCompletionUsage(BaseModel):
    """Token usage statistics (approximated to zero — not tracked by the scraper)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible non-streaming chat completion response."""

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
        """Build a response from a model ID, answer text, and optional thread UUID."""
        pplx = PerplexityResponseExtensions(thread_uuid=thread_uuid) if thread_uuid else None

        return cls(
            id=f"chatcmpl-{uuid4().hex}",
            created=int(time()),
            model=model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content=content),
                )
            ],
            perplexity=pplx,
        )


class ChatCompletionChunkDelta(BaseModel):
    """Delta content for a streaming chunk."""

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """A single choice in a streaming chunk."""

    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Literal["stop"] | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible SSE streaming chunk."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]
    perplexity: PerplexityResponseExtensions | None = None

    def to_sse_line(self) -> str:
        """Serialize to a Server-Sent Events data line."""
        return f"data: {self.model_dump_json(exclude_none=True)}\n\n"


class ModelObject(BaseModel):
    """A single model entry in the /v1/models list."""

    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "perplexity"


class ModelList(BaseModel):
    """Response for GET /v1/models."""

    object: Literal["list"] = "list"
    data: list[ModelObject]


class ErrorDetail(BaseModel):
    """Inner error payload."""

    message: str
    type: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI-compatible error envelope."""

    error: ErrorDetail


def build_models_response(registry: ModelRegistry) -> ModelList:
    """Build a ModelList from the MODELS registry."""
    return ModelList(
        data=[ModelObject(id=model.id) for model in registry.list_all()],
    )
