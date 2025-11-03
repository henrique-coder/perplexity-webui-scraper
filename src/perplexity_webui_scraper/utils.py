# Standard modules
from collections.abc import Generator
from re import Match, compile
from typing import Any

# Third-party modules
from pydantic import BaseModel, Field


class _ModeBase(BaseModel):
    """Base class for mode objects"""

    value: str

    class Config:
        frozen = True


# Type alias for mode values
ModeValue = _ModeBase


class CitationMode:
    """Citation formatting modes"""

    DEFAULT = _ModeBase(value="default")
    """Use default Perplexity citation format (e.g., 'This is a citation[1]')"""

    MARKDOWN = _ModeBase(value="markdown")
    """Replace citations with markdown links (e.g., 'This is a citation[1](https://example.com)')"""

    CLEAN = _ModeBase(value="clean")
    """Remove all citations (e.g., 'This is a citation')"""


class SearchFocus:
    """Search focus types"""

    WEB = _ModeBase(value="internet")
    """Search the web"""

    WRITING = _ModeBase(value="writing")
    """Search for writing"""


class SourceFocus:
    """Source focus types"""

    WEB = _ModeBase(value="web")
    """Search across the entire internet"""

    ACADEMIC = _ModeBase(value="scholar")
    """Search academic papers"""

    SOCIAL = _ModeBase(value="social")
    """Discussions and opinions"""

    FINANCE = _ModeBase(value="edgar")
    """Search SEC filings"""


class TimeRange:
    """Time range filters"""

    ALL = _ModeBase(value="")
    """Include sources from all time"""

    TODAY = _ModeBase(value="DAY")
    """Include sources from today"""

    LAST_WEEK = _ModeBase(value="WEEK")
    """Include sources from the last week"""

    LAST_MONTH = _ModeBase(value="MONTH")
    """Include sources from the last month"""

    LAST_YEAR = _ModeBase(value="YEAR")
    """Include sources from the last year"""


class SearchResultItem(BaseModel):
    """Individual search result item"""

    title: str | None = None
    snippet: str | None = None
    url: str | None = None


class Response(BaseModel):
    """Unified response model for both streaming and complete responses"""

    title: str | None = None
    answer: str | None = None
    chunks: list[str] = Field(default_factory=list)
    last_chunk: str | None = None
    search_results: list[SearchResultItem] = Field(default_factory=list)
    conversation_uuid: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class PromptCall:
    """Configured prompt that can be executed with .ask() method"""

    def __init__(self, parent, json_data: dict[str, Any]) -> None:
        self._parent = parent
        self._json_data = json_data

    def run(self, stream: bool = False) -> Response | Generator[Response, None, None]:
        """
        Execute the prompt request.

        Args:
            stream: If False (default), blocks until complete and returns full Response.
                   If True, returns generator yielding Response objects with incremental updates.

        Returns:
            Response object (if stream=False) or Generator[Response] (if stream=True)

        Raises:
            PermissionError: If session token is invalid (403)
            ConnectionError: If rate limit is exceeded (429)
        """

        if stream:
            return self._stream_response()
        else:
            return self._complete_response()

    def _complete_response(self) -> Response:
        """Execute request and block until complete"""

        self._parent.reset_response_data()

        try:
            self._parent._client.get("https://www.perplexity.ai/search/new", params={"q": self._json_data["query_str"]})
        except Exception as e:
            if hasattr(e, "response") and hasattr(e.response, "status_code"):
                if e.response.status_code == 403:
                    raise PermissionError(
                        "Access forbidden (403). Your session token is invalid or expired. "
                        "Please obtain a new session token from your browser cookies."
                    ) from e
                elif e.response.status_code == 429:
                    raise ConnectionError("Rate limit exceeded (429). Please wait a moment before trying again.") from e

            raise e

        with self._parent._client.stream(
            "POST", "https://www.perplexity.ai/rest/sse/perplexity_ask", json=self._json_data
        ) as response:
            try:
                response.raise_for_status()
            except Exception as e:
                if hasattr(e, "response") and hasattr(e.response, "status_code"):
                    if e.response.status_code == 403:
                        raise PermissionError(
                            "Access forbidden (403). Your session token is invalid or expired. "
                            "Please obtain a new session token from your browser cookies."
                        ) from e
                    elif e.response.status_code == 429:
                        raise ConnectionError("Rate limit exceeded (429). Please wait a moment before trying again.") from e

                raise e

            for line in response.iter_lines():
                data = self._parent._extract_json_line(line)

                if data:
                    self._parent._process_data(data)

                    if data.get("final"):
                        break

        return Response(
            title=self._parent.title,
            answer=self._parent.answer,
            chunks=list(self._parent.chunks),
            last_chunk=self._parent.last_chunk if self._parent.chunks else None,
            search_results=list(self._parent.search_results),
            conversation_uuid=self._parent.conversation_uuid,
            raw_data=self._parent.raw_data,
        )

    def _stream_response(self) -> Generator[Response, None, None]:
        """Stream response data in real-time"""

        self._parent.reset_response_data()

        try:
            self._parent._client.get("https://www.perplexity.ai/search/new", params={"q": self._json_data["query_str"]})
        except Exception as e:
            if hasattr(e, "response") and hasattr(e.response, "status_code"):
                if e.response.status_code == 403:
                    raise PermissionError(
                        "Access forbidden (403). Your session token is invalid or expired. "
                        "Please obtain a new session token from your browser cookies."
                    ) from e
                elif e.response.status_code == 429:
                    raise ConnectionError("Rate limit exceeded (429). Please wait a moment before trying again.") from e

            raise e

        with self._parent._client.stream(
            "POST", "https://www.perplexity.ai/rest/sse/perplexity_ask", json=self._json_data
        ) as response:
            try:
                response.raise_for_status()
            except Exception as e:
                if hasattr(e, "response") and hasattr(e.response, "status_code"):
                    if e.response.status_code == 403:
                        raise PermissionError(
                            "Access forbidden (403). Your session token is invalid or expired. "
                            "Please obtain a new session token from your browser cookies."
                        ) from e
                    elif e.response.status_code == 429:
                        raise ConnectionError("Rate limit exceeded (429). Please wait a moment before trying again.") from e

                raise e

            for line in response.iter_lines():
                data = self._parent._extract_json_line(line)

                if data:
                    self._parent._process_data(data)

                    yield Response(
                        title=self._parent.title,
                        answer=self._parent.answer,
                        chunks=list(self._parent.chunks),
                        last_chunk=self._parent.last_chunk,
                        search_results=list(self._parent.search_results),
                        conversation_uuid=self._parent.conversation_uuid,
                        raw_data=data,
                    )

                    if data.get("final"):
                        break


def citation_replacer(match: Match[str], citation_mode: ModeValue, search_results: list[SearchResultItem]) -> str:
    """Replace citation markers based on mode"""

    num = match.group(1)

    if not num.isdigit():
        return match.group(0)

    idx = int(num) - 1

    if 0 <= idx < len(search_results):
        url = search_results[idx].url or ""

        if citation_mode.value == "markdown" and url:
            return f"[{num}]({url})"
        elif citation_mode.value == "clean":
            return ""

    return match.group(0)


def format_citations(citation_mode: ModeValue, text: str | None, search_results: list[SearchResultItem]) -> str | None:
    """Format citation markers in text based on mode"""

    if not text or citation_mode.value == "default":
        return text

    return compile(r"\[(\d{1,2})\](?![\d\w])").sub(lambda match: citation_replacer(match, citation_mode, search_results), text)
