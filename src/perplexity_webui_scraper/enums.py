"""Enums for Perplexity WebUI Scraper configuration options."""

from __future__ import annotations

from enum import Enum


class CitationMode(str, Enum):
    """
    Citation formatting modes for response text.

    Controls how citation markers (e.g., [1], [2]) are formatted in the response.
    """

    DEFAULT = "default"
    """Keep original Perplexity citation format (e.g., 'This is a citation[1]')."""

    MARKDOWN = "markdown"
    """Convert citations to markdown links (e.g., 'This is a citation[1](https://example.com)')."""

    CLEAN = "clean"
    """Remove all citation markers (e.g., 'This is a citation')."""


class SearchFocus(str, Enum):
    """
    Search focus types that control the type of search performed.

    Determines whether to search the web or focus on writing tasks.
    """

    WEB = "internet"
    """Search the web for information. Best for factual queries and research."""

    WRITING = "writing"
    """Focus on writing tasks. Best for creative writing, editing, and text generation."""


class SourceFocus(str, Enum):
    """
    Source focus types that control which sources to prioritize.

    Can be combined (e.g., [SourceFocus.WEB, SourceFocus.ACADEMIC]) for multi-source searches.
    """

    WEB = "web"
    """Search across the entire internet. General web search."""

    ACADEMIC = "scholar"
    """Search academic papers and scholarly articles (Google Scholar, etc.)."""

    SOCIAL = "social"
    """Search social media for discussions and opinions (Reddit, Twitter, etc.)."""

    FINANCE = "edgar"
    """Search SEC EDGAR filings for financial and corporate documents."""


class TimeRange(str, Enum):
    """
    Time range filters for search results.

    Controls how recent the sources should be.
    """

    ALL = ""
    """Include sources from all time. No time restriction."""

    TODAY = "DAY"
    """Include only sources from today (last 24 hours)."""

    LAST_WEEK = "WEEK"
    """Include sources from the last 7 days."""

    LAST_MONTH = "MONTH"
    """Include sources from the last 30 days."""

    LAST_YEAR = "YEAR"
    """Include sources from the last 365 days."""


class LogLevel(str, Enum):
    """
    Logging level configuration.

    Controls the verbosity of logging output. DISABLED is the default.
    """

    DISABLED = "DISABLED"
    """Completely disable all logging output. This is the default."""

    DEBUG = "DEBUG"
    """Show all messages including internal debug information."""

    INFO = "INFO"
    """Show informational messages, warnings, and errors."""

    WARNING = "WARNING"
    """Show only warnings and errors."""

    ERROR = "ERROR"
    """Show only error messages."""

    CRITICAL = "CRITICAL"
    """Show only critical/fatal errors."""
