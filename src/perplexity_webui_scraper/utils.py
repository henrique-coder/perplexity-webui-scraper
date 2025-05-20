# Standard modules
from enum import Enum
from typing import Any

# Third-party modules
from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    title: str | None = None
    snippet: str | None = None
    url: str | None = None


class StreamResponse(BaseModel):
    title: str | None = None
    answer: str | None = None
    chunks: list[str] = Field(default_factory=list)
    last_chunk: str | None
    search_results: list[SearchResultItem] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class AskResponse(BaseModel):
    title: str | None = None
    answer: str | None = None
    chunks: list[str] = Field(default_factory=list)
    search_results: list[SearchResultItem] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class SearchFocus(Enum):
    """
    Available search focus

    Attributes:
        WEB: Search the web
        WRITING: Search for writing
    """

    WEB = "internet"
    WRITING = "writing"


class SourceFocus(Enum):
    """
    Available source focus

    Attributes:
        WEB: Search the web
        ACADEMIC: Search academic sources
        SOCIAL: Search social media
    """

    WEB = "web"
    ACADEMIC = "scholar"
    SOCIAL = "social"


class TimeRange(Enum):
    """
    Available time range

    Attributes:
        ALL: Include sources from all time
        TODAY: Include sources from today
        LAST_WEEK: Include sources from the last week
        LAST_MONTH: Include sources from the last month
        LAST_YEAR: Include sources from the last year
    """

    ALL = None
    TODAY = "DAY"
    LAST_WEEK = "WEEK"
    LAST_MONTH = "MONTH"
    LAST_YEAR = "YEAR"
