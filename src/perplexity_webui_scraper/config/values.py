"""Pydantic-annotated values shared by API and MCP schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field


CitationMode = Annotated[
    Literal["default", "markdown", "clean"],
    Field(description='"default" keeps citation markers, "markdown" links them, and "clean" removes them.'),
]
SearchFocus = Annotated[
    Literal["web", "writing"],
    Field(description='"web" enables web search; "writing" generates without search.'),
]
SourceFocus = Annotated[
    Literal["web", "academic", "social", "finance", "all"],
    Field(description='"web", "academic", "social", "finance", or "all" sources.'),
]
TimeRange = Annotated[
    Literal["all", "day", "week", "month", "year"],
    Field(description='"all", "day", "week", "month", or "year" recency.'),
]
ResearchInteraction = Annotated[
    Literal["auto", "manual"],
    Field(description='"auto" answers Deep Research questions; "manual" returns them to the caller.'),
]
LogLevel = Annotated[
    Literal["disabled", "debug", "info", "warning", "error", "critical"],
    Field(description='"disabled" suppresses library logs; other values select the minimum emitted severity.'),
]
