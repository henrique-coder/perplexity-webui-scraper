"""Per-conversation configuration model."""

from __future__ import annotations

from pydantic import BaseModel

from perplexity_webui_scraper._internal.types import (  # noqa: TC001
    CitationMode,
    Coordinates,
    SearchFocus,
    SourceFocus,
    TimeRange,
)


class ConversationConfig(BaseModel):
    """Settings for a single conversation thread.

    All fields are optional and fall back to sensible defaults. Construct a
    ``ConversationConfig`` and pass it to ``client.create_conversation()``.

    Attributes:
        model: Model ID string (e.g., ``"perplexity/best"``). Defaults to
            ``"perplexity/best"`` (Perplexity auto-selection).
        search_focus: Search mode constraint. ``"web"`` enables live search;
            ``"writing"`` disables external sources for pure generation.
        source_focus: Filter categories for search (e.g., ``"academic"``,
            ``"finance"``, ``"social"``). Accepts a string or list of strings.
        time_range: Recency constraint for web results (e.g., ``"week"``).
            ``"all"`` removes time restrictions.
        citation_mode: Determines how inline citations are returned.
            ``"clean"`` removes them, ``"markdown"`` converts to links.
        language: BCP-47 language tag for the response (e.g., ``"pt-BR"``).
        timezone: IANA timezone string for localization (e.g., ``"America/Sao_Paulo"``).
        coordinates: Geographic location constraints (latitude/longitude).
        save_to_library: If ``True``, saves the thread to your account history.
        space_uuid: UUID of a Perplexity Space (collection) to post into.
    """

    model: str | None = None
    search_focus: SearchFocus = "web"
    source_focus: SourceFocus | list[SourceFocus] = "web"
    time_range: TimeRange = "all"
    citation_mode: CitationMode = "clean"
    language: str = "en-US"
    timezone: str | None = None
    coordinates: Coordinates | None = None
    save_to_library: bool = False
    space_uuid: str | None = None
