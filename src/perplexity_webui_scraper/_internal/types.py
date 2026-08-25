"""Public type aliases used across the library.

All ``Literal`` type aliases and the ``FileInput`` union type are defined
here as the single source of truth.  They are re-exported through the
top-level ``perplexity_webui_scraper`` namespace.
"""

from __future__ import annotations

from os import PathLike
from typing import Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Coordinates live here to avoid a circular import with core.response.
# ---------------------------------------------------------------------------


class Coordinates(BaseModel):
    """Geographic coordinates for location-aware Perplexity search results.

    Attributes:
        latitude: Latitude in decimal degrees (-90 to +90).
        longitude: Longitude in decimal degrees (-180 to +180).
    """

    model_config = ConfigDict(frozen=True)

    latitude: float
    longitude: float


# ---------------------------------------------------------------------------
# Literal type aliases
# ---------------------------------------------------------------------------

CitationMode = Literal["default", "markdown", "clean"]
"""Controls how citation markers are rendered in the final answer.

- ``"default"``: leave ``[1]``, ``[2]`` … markers as-is.
- ``"markdown"``: convert markers to ``[1](url)`` Markdown links.
- ``"clean"``: strip all citation markers from the text.
"""

ResearchInteraction = Literal["auto", "manual"]
"""Controls how Deep Research clarification prompts are handled."""

SearchFocus = Literal["web", "writing"]
"""Selects the search/generation mode.

- ``"web"``: enable web search and cited sources.
- ``"writing"``: generate a response without sources.
"""

SourceFocus = Literal["web", "academic", "social", "finance", "all"]
"""Filters which source categories Perplexity searches.

- ``"web"``: general web results.
- ``"academic"``: scholarly and academic databases.
- ``"social"``: social media posts and discussions.
- ``"finance"``: SEC EDGAR filings and financial data.
- ``"all"``: combine web, academic, and social.
"""

TimeRange = Literal["all", "day", "week", "month", "year"]
"""Recency filter applied to web search results.

- ``"all"``: no time restriction.
- ``"day"`` / ``"week"`` / ``"month"`` / ``"year"``: restrict to that window.
"""

LogLevel = Literal["disabled", "debug", "info", "warning", "error", "critical"]
"""Log verbosity level.

- ``"disabled"``: no log output (default).
- ``"debug"`` through ``"critical"``: standard severity levels.
"""

# ---------------------------------------------------------------------------
# FileInput union type
# ---------------------------------------------------------------------------

FileInput = str | PathLike[str] | bytes | tuple[bytes, str] | tuple[bytes, str, str]
"""Accepted file inputs for ``Conversation.ask(files=...)``.

- ``str | PathLike[str]``: local filesystem path; read at upload time.
- ``bytes``: raw bytes; filename defaults to ``"file"`` and MIME type is detected.
- ``tuple[bytes, str]``: ``(data, filename)``; MIME type is guessed from the filename.
- ``tuple[bytes, str, str]``: ``(data, filename, mimetype)``.
"""
