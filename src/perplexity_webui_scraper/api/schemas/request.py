"""OpenAI-compatible chat completion request schemas with Perplexity extensions."""

from __future__ import annotations

from base64 import b64decode
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class ContentPartText(BaseModel):
    """A plain-text content part within a multimodal message.

    Attributes:
        type: Always ``"text"``.
        text: The text content.
    """

    type: Literal["text"]
    text: str


class ContentPartImageUrl(BaseModel):
    """An image content part within a multimodal message.

    Supports both external URLs and base64 data URIs.  Only ``data:`` URIs
    are decoded server-side; external URLs are ignored (to avoid unpredictable
    network calls from the server).

    Attributes:
        type: Always ``"image_url"``.
        image_url: Dict with a ``"url"`` key containing the image URL or
            ``data:<mime>;base64,<data>`` string.
    """

    type: Literal["image_url"]
    image_url: dict[str, str]


ContentPart = ContentPartText | ContentPartImageUrl
"""Union of all supported content part types."""


class ChatMessage(BaseModel):
    """A single message in a conversation.

    Attributes:
        role: Message author: ``"system"``, ``"user"``, or ``"assistant"``.
        content: Either a plain string or a list of :data:`ContentPart` objects
            for multimodal messages.
    """

    role: Literal["system", "user", "assistant"]
    content: str | list[ContentPart]

    def text(self) -> str:
        """Return the plain-text portion of this message.

        For multimodal messages, concatenates all ``ContentPartText`` blocks
        with newlines.

        Returns:
            Plain-text string.
        """
        if isinstance(self.content, str):
            return self.content

        return "\n".join(p.text for p in self.content if isinstance(p, ContentPartText))

    def image_bytes(self) -> list[tuple[bytes, str, str]]:
        """Return decoded base64 image parts as ``(data, filename, mimetype)`` tuples.

        Only ``data:`` URIs are decoded.  External image URLs are silently
        skipped to avoid server-side network calls.

        Returns:
            List of ``(bytes, filename, mimetype)`` tuples.
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
                ext = mimetype.split("/")[-1].split("+")[0]
                filename = f"image.{ext}"
                data = b64decode(b64data)
                results.append((data, filename, mimetype))
            except Exception:
                continue

        return results


class CoordinatesInput(BaseModel):
    """Latitude/longitude pair for the ``perplexity.coordinates`` field.

    Attributes:
        latitude: Latitude in decimal degrees (-90 to +90).
        longitude: Longitude in decimal degrees (-180 to +180).
    """

    latitude: float
    longitude: float


class PerplexityExtensions(BaseModel):
    """Perplexity-specific configuration passed under the ``perplexity`` key.

    All fields are optional; omitted fields fall back to server defaults.
    Pass this block inside ``ChatCompletionRequest.perplexity``.

    Attributes:
        citation_mode: Citation rendering: ``"clean"`` (default), ``"markdown"``,
            or ``"default"`` (keep markers as-is).
        search_focus: ``"web"`` (default) enables sources; ``"writing"`` disables
            them for purely generative responses.
        source_focus: Source category filter.  Accepts a single value or list:
            ``"web"``, ``"academic"``, ``"social"``, ``"finance"``, ``"all"``.
        time_range: Recency filter: ``"all"``, ``"day"``, ``"week"``,
            ``"month"``, or ``"year"``.
        save_to_library: Save conversation to Perplexity library.
        language: BCP-47 language tag (e.g. ``"pt-BR"``).
        timezone: IANA timezone string (e.g. ``"America/Sao_Paulo"``).
        coordinates: Geographic coordinates for localised results.
        space_uuid: UUID of a Perplexity Space to post into.  Use DevTools to
            obtain it from the ``target_collection_uuid`` field of a
            ``perplexity_ask`` request.  The URL slug is **not** the UUID.
        thread_uuid: UUID of an existing conversation thread to continue.
            When provided, the server reuses the cached ``Conversation``
            and sends only the last user message as a follow-up.
        response_format: Hint for the response format.  ``"text"`` (default)
            returns plain text; ``"json_object"`` adds a JSON-output instruction
            to the system prompt.  Note: Perplexity has no native structured
            output support — this is a best-effort prompt injection.
    """

    model_config = ConfigDict(extra="ignore")

    citation_mode: Literal["default", "markdown", "clean"] | None = None
    search_focus: Literal["web", "writing"] | None = None
    source_focus: (
        Literal["web", "academic", "social", "finance", "all"]
        | list[Literal["web", "academic", "social", "finance", "all"]]
        | None
    ) = None
    time_range: Literal["all", "day", "week", "month", "year"] | None = None
    save_to_library: bool = False
    language: str | None = None
    timezone: str | None = None
    coordinates: CoordinatesInput | None = None
    space_uuid: str | None = None
    thread_uuid: str | None = None
    response_format: Literal["text", "json_object"] = "text"

    @model_validator(mode="before")
    @classmethod
    def _normalise_strings(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Lowercase all string-based enum fields for case-insensitive matching.

        Args:
            values: Raw input dict before field assignment.

        Returns:
            Normalised dict with lowercased enum values.
        """
        if not isinstance(values, dict):
            return values

        for key in ("citation_mode", "search_focus", "time_range", "response_format"):
            if isinstance(values.get(key), str):
                values[key] = values[key].lower()

        if isinstance(values.get("source_focus"), str):
            values["source_focus"] = values["source_focus"].lower()
        elif isinstance(values.get("source_focus"), list):
            values["source_focus"] = [s.lower() if isinstance(s, str) else s for s in values["source_focus"]]

        return values


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Standard OpenAI fields that Perplexity does not support (``temperature``,
    ``top_p``, ``n``, ``max_tokens``, …) are accepted for drop-in client
    compatibility but silently ignored via ``extra="allow"``.

    The optional ``perplexity`` block exposes all Perplexity-specific settings::

        {
            "model": "perplexity/best",
            "messages": [...],
            "perplexity": {
                "citation_mode": "clean",
                "search_focus": "web",
                "source_focus": ["web", "academic"],
                "time_range": "week",
                "save_to_library": false,
                "language": "pt-BR",
                "timezone": "America/Sao_Paulo",
                "coordinates": {"latitude": -23.5, "longitude": -46.6},
                "response_format": "json_object",
            },
        }

    Attributes:
        model: Model ID (e.g. ``"perplexity/best"``).
        messages: Conversation messages.
        stream: Enable SSE streaming.
        perplexity: Optional Perplexity-specific configuration block.
    """

    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    perplexity: PerplexityExtensions | None = None
