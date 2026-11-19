"""OpenAI-compatible chat completion request schemas with Perplexity extensions."""

from __future__ import annotations

from base64 import b64decode
from math import isfinite
from re import fullmatch
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from perplexity_webui_scraper._internal.constants import MAX_FILES


MAX_IMAGE_BYTES = 10 * 1024 * 1024
_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_BASE64_INDEX = {character: index for index, character in enumerate(_BASE64_ALPHABET)}


def _validate_image_data_url(url: str) -> tuple[str, str, str]:
    """Validate an image base64 Data URL before decoding bytes."""
    if not url.startswith("data:"):
        raise ValueError("Image data URL must start with 'data:'.")

    if "," not in url:
        raise ValueError("Image data URL must include a comma separator.")

    header, b64data = url.split(",", 1)
    parts = header[5:].split(";")

    if len(parts) != 2 or parts[1].lower() != "base64":
        raise ValueError("Image data URL must include an explicit ';base64' marker.")

    mimetype = parts[0].lower()
    mime_match = fullmatch(r"image/([a-z0-9]+(?:[.-][a-z0-9]+)*)(?:\+[a-z0-9]+)?", mimetype)

    if mime_match is None:
        raise ValueError("Image data URL must use a valid image MIME type.")

    filename = f"image.{mime_match.group(1)}"

    if not b64data:
        raise ValueError("Image base64 payload must not be empty.")

    max_encoded_chars = ((MAX_IMAGE_BYTES + 2) // 3) * 4

    if len(b64data) > max_encoded_chars:
        raise ValueError("Image base64 payload exceeds the maximum allowed size.")

    if len(b64data) % 4 != 0:
        raise ValueError("Image base64 payload length must be a multiple of 4.")

    padding = 2 if b64data.endswith("==") else (1 if b64data.endswith("=") else 0)
    decoded_size = (len(b64data) // 4) * 3 - padding

    if decoded_size <= 0 or decoded_size > MAX_IMAGE_BYTES:
        raise ValueError("Image decoded size exceeds the maximum allowed size.")

    if fullmatch(r"[A-Za-z0-9+/]+={0,2}", b64data) is None:
        raise ValueError("Image base64 payload contains invalid characters or padding.")

    if padding == 1 and (_BASE64_INDEX[b64data[-2]] & 0b000011) != 0:
        raise ValueError("Image base64 payload has non-canonical padding bits.")

    if padding == 2 and (_BASE64_INDEX[b64data[-3]] & 0b001111) != 0:
        raise ValueError("Image base64 payload has non-canonical padding bits.")

    return b64data, filename, mimetype


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

    @model_validator(mode="after")
    def _validate_image_url(self) -> ContentPartImageUrl:
        url = self.image_url.get("url")

        if not isinstance(url, str) or not url:
            raise ValueError("image_url must include a non-empty 'url' string.")

        if url[:5].lower() == "data:":
            _validate_image_data_url(url)

        return self


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

            if url[:5].lower() != "data:":
                continue

            b64data, filename, mimetype = _validate_image_data_url(url)
            data = b64decode(b64data, validate=True)
            results.append((data, filename, mimetype))

        return results


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
        latitude: Latitude in decimal degrees (-90 through 90). Set with ``longitude``.
        longitude: Longitude in decimal degrees (-180 through 180). Set with ``latitude``.
        space_uuid: UUID of a Perplexity Space to post into.  Use DevTools to
            obtain it from the ``target_collection_uuid`` field of a
            ``perplexity_ask`` request.  The URL slug is **not** the UUID.
        thread_uuid: UUID of an existing conversation thread to continue.
            When provided, the server reuses the cached ``Conversation``
            and sends only the last user message as a follow-up.
        response_format: Hint for the response format.  ``"text"`` (default)
            returns plain text; ``"json_object"`` adds a JSON-output instruction
            to the system prompt. Perplexity has no native structured-output
            mode, so this setting cannot guarantee valid JSON.
        allow_risky_model: Explicitly acknowledge any non-available model status.
        custom_model_mode: Backend mode used with ``model="custom:<identifier>"``.
        research_interaction: Deep Research clarification handling: ``"auto"``
            chooses reasonable assumptions; ``"manual"`` returns the questions.
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
    latitude: Annotated[float, Field(ge=-90, le=90)] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180)] | None = None
    space_uuid: str | None = None
    thread_uuid: str | None = None
    response_format: Literal["text", "json_object"] = "text"
    allow_risky_model: bool = False
    custom_model_mode: Literal["copilot", "search", "research"] = "copilot"
    research_interaction: Literal["auto", "manual"] = "auto"

    @model_validator(mode="before")
    @classmethod
    def _normalize_strings(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Lowercase all string-based enum fields for case-insensitive matching.

        Args:
            values: Raw input dict before field assignment.

        Returns:
            Normalized dict with lowercased enum values.
        """
        if not isinstance(values, dict):
            return values

        for key in (
            "citation_mode",
            "search_focus",
            "time_range",
            "response_format",
            "custom_model_mode",
            "research_interaction",
        ):
            if isinstance(values.get(key), str):
                values[key] = values[key].lower()

        if isinstance(values.get("source_focus"), str):
            values["source_focus"] = values["source_focus"].lower()
        elif isinstance(values.get("source_focus"), list):
            values["source_focus"] = [s.lower() if isinstance(s, str) else s for s in values["source_focus"]]

        return values

    @model_validator(mode="after")
    def _validate_coordinates(self) -> PerplexityExtensions:
        """Require paired, finite latitude and longitude values when provided."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")

        if self.latitude is not None and not isfinite(self.latitude):
            raise ValueError("latitude must be finite")

        if self.longitude is not None and not isfinite(self.longitude):
            raise ValueError("longitude must be finite")

        return self


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Unsupported OpenAI fields such as ``temperature``, ``top_p``, ``n``, and
    ``max_tokens`` are accepted for client compatibility and ignored through
    ``extra="allow"``.

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
                "latitude": -23.5,
                "longitude": -46.6,
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

    @model_validator(mode="after")
    def _validate_attachment_count(self) -> ChatCompletionRequest:
        """Reject requests whose embedded data-URL images exceed the upload cap."""
        image_count = 0

        for message in self.messages:
            if isinstance(message.content, str):
                continue

            for part in message.content:
                if isinstance(part, ContentPartImageUrl) and part.image_url.get("url", "")[:5].lower() == "data:":
                    image_count += 1
                    if image_count > MAX_FILES:
                        raise ValueError(f"Too many image attachments: maximum allowed is {MAX_FILES}.")

        return self
