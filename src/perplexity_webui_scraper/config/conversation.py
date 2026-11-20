"""Per-conversation configuration model."""

from __future__ import annotations

from math import isfinite
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class ConversationConfig(BaseModel):
    """Validated settings for one conversation thread.

    Pass supported strings directly; Pydantic validates the values on creation.

    Attributes:
        model: Model ID. Defaults to ``"perplexity/best"`` when omitted.
        search_focus: ``"web"`` searches sources; ``"writing"`` generates without search.
        source_focus: One source or list of ``"web"``, ``"academic"``, ``"social"``, ``"finance"``, ``"all"``.
        time_range: ``"all"``, ``"day"``, ``"week"``, ``"month"``, or ``"year"``.
        citation_mode: ``"default"`` keeps markers, ``"markdown"`` links them, ``"clean"`` removes them.
        language: BCP-47 response language tag.
        timezone: IANA timezone name.
        latitude: Latitude in degrees from -90 through 90. Set it with ``longitude``.
        longitude: Longitude in degrees from -180 through 180. Set it with ``latitude``.
        save_to_library: Save the conversation in the Perplexity library.
        space_uuid: Perplexity Space UUID.
        allow_risky_model: Acknowledge a model whose status is not ``"available"``.
        custom_model_mode: ``"copilot"``, ``"search"``, or ``"research"`` for custom IDs.
        research_interaction: ``"auto"`` answers clarification questions; ``"manual"`` raises them to the caller.
    """

    model: str | None = None
    search_focus: Annotated[
        Literal["web", "writing"],
        Field(description='"web" enables web search; "writing" generates without search.'),
    ] = "web"
    source_focus: (
        Annotated[
            Literal["web", "academic", "social", "finance", "all"],
            Field(description='"web", "academic", "social", "finance", or "all" sources.'),
        ]
        | list[Literal["web", "academic", "social", "finance", "all"]]
    ) = "web"
    time_range: Annotated[
        Literal["all", "day", "week", "month", "year"],
        Field(description='"all", "day", "week", "month", or "year" recency.'),
    ] = "all"
    citation_mode: Annotated[
        Literal["default", "markdown", "clean"],
        Field(description='"default" keeps markers, "markdown" links them, and "clean" removes them.'),
    ] = "clean"
    language: str = "en-US"
    timezone: str | None = None
    latitude: Annotated[float, Field(ge=-90, le=90, description="Latitude in degrees.")] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180, description="Longitude in degrees.")] | None = None
    save_to_library: bool = False
    space_uuid: str | None = None
    allow_risky_model: bool = False
    custom_model_mode: Annotated[
        Literal["copilot", "search", "research"], Field(description="Request mode for a custom model ID.")
    ] = "copilot"
    research_interaction: Annotated[
        Literal["auto", "manual"],
        Field(description='"auto" answers clarification questions; "manual" returns them to the caller.'),
    ] = "auto"

    @model_validator(mode="after")
    def _require_coordinate_pair(self) -> ConversationConfig:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.latitude is not None and not isfinite(self.latitude):
            raise ValueError("latitude must be finite")
        if self.longitude is not None and not isfinite(self.longitude):
            raise ValueError("longitude must be finite")
        return self
