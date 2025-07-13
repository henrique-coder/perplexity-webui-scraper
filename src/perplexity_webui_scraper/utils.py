# Standard modules
from collections.abc import Generator
from enum import Enum
from re import Match
from re import compile as re_compile
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


class CitationMode(Enum):
    """
    Available citation modes

    Attributes:
        DEFAULT: Use default Perplexity citation format (e.g., "`This is a citation[1]`")
        MARKDOWN: Replace citations with markdown links (e.g., "`This is a citation[1](https://example.com)`")
        CLEAN: Remove all citations (e.g., "`This is a citation`")
    """

    DEFAULT = "default"
    MARKDOWN = "markdown"
    CLEAN = "clean"


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
        WEB: Search across the entire internet
        ACADEMIC: Search academic papers
        SOCIAL: Discussions and opinions
        FINANCE: Search SEC filings
    """

    WEB = "web"
    ACADEMIC = "scholar"
    SOCIAL = "social"
    FINANCE = "edgar"


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


class AskCall:
    def __init__(self, parent, json_data: dict[str, Any]) -> None:
        self._parent = parent
        self._json_data = json_data

    def run(self) -> AskResponse:
        """
        Run the ask request and return the response data

        Returns:
            AskResponse object containing the response data.
        """

        self._parent.reset_response_data()
        self._parent._client.get("https://www.perplexity.ai/search/new", params={"q": self._json_data["query_str"]})

        with self._parent._client.stream(
            "POST", "https://www.perplexity.ai/rest/sse/perplexity_ask", json=self._json_data
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                data = self._parent._extract_json_line(line)

                if data:
                    self._parent._process_data(data)

                    if data.get("final"):
                        break

        return AskResponse(
            title=self._parent.title,
            answer=self._parent.answer,
            chunks=list(self._parent.chunks),
            search_results=list(self._parent.search_results),
            raw_data=self._parent.raw_data,
        )

    def stream(self) -> Generator[StreamResponse]:
        """
        Stream response data in real-time

        Yields:
            StreamResponse object containing the streamed data.
        """

        self._parent.reset_response_data()
        self._parent._client.get("https://www.perplexity.ai/search/new", params={"q": self._json_data["query_str"]})

        with self._parent._client.stream(
            "POST", "https://www.perplexity.ai/rest/sse/perplexity_ask", json=self._json_data
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                data = self._parent._extract_json_line(line)

                if data:
                    self._parent._process_data(data)

                    yield StreamResponse(
                        title=self._parent.title,
                        answer=self._parent.answer,
                        chunks=list(self._parent.chunks),
                        last_chunk=self._parent.last_chunk,
                        search_results=list(self._parent.search_results),
                        raw_data=data,
                    )

                    if data.get("final"):
                        break


def format_citations(citation_mode: CitationMode, text: str, search_results: list) -> str:
    if citation_mode.value == "default" or not text:
        return text

    def citation_replacer(match: Match[str]) -> str:
        num = match.group(1)

        if not num.isdigit():
            return match.group(0)

        idx = int(num) - 1

        if 0 <= idx < len(search_results):
            url = getattr(search_results[idx], "url", "") or ""

            if citation_mode.value == "markdown" and url:
                return f"[{num}]({url})"
            elif citation_mode.value == "clean":
                return ""
            else:
                return match.group(0)
        else:
            return match.group(0)

    return re_compile(r"\[(\d{1,2})\](?![\d\w])").sub(citation_replacer, text)
