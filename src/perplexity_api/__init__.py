# Standard modules
from collections.abc import Generator
from enum import Enum
from typing import Any

# Third-party modules
from httpx import Client, Timeout
from orjson import loads
from pydantic import BaseModel


__all__ = [
    "ModelType",
    "Perplexity",
    "SearchFocus",
    "SourceFocus",
    "TimeRange",
]


class ModelBase:
    """Base class for all models"""

    _identifier: str
    _mode: str

    @classmethod
    def get_identifier(cls) -> str:
        return cls._identifier

    @classmethod
    def get_mode(cls) -> str:
        return cls._mode


class ModelType:
    """Available models"""

    class Pro:
        """3x more sources with powerful models, increased limits, and detailed answers"""

        class Best(ModelBase):
            """Selects the best model for each query"""

            _identifier = "pplx_pro"
            _mode = "copilot"

        class Sonar(ModelBase):
            """Perplexity's fast model"""

            _identifier = "experimental"
            _mode = "copilot"

        class Claude37Sonnet(ModelBase):
            """Anthropic's advanced model"""

            _identifier = "claude2"
            _mode = "copilot"

        class GPT41(ModelBase):
            """OpenAI's advanced model"""

            _identifier = "gpt41"
            _mode = "copilot"

        class Gemini25Pro(ModelBase):
            """Google's latest model"""

            _identifier = "gemini2flash"
            _mode = "copilot"

        class Grok3Beta(ModelBase):
            """xAI's latest model"""

            _identifier = "grok"
            _mode = "copilot"

        class Reasoning:
            """Advanced problem solving"""

            class R11776(ModelBase):
                """Perplexity's unbiased reasoning model"""

                _identifier = "r1"
                _mode = "copilot"

            class o4mini(ModelBase):
                """OpenAI's latest reasoning model"""

                _identifier = "o4mini"
                _mode = "copilot"

            class Claude37SonnetThinking(ModelBase):
                """Anthropic's reasoning model"""

                _identifier = "claude37sonnetthinking"
                _mode = "copilot"

    class Research(ModelBase):
        """Advanced analysis on any topic"""

        _identifier = "pplx_alpha"
        _mode = "copilot"


class SearchFocus(Enum):
    """Available search focus"""

    WEB = "internet"
    WRITING = "writing"


class SourceFocus(Enum):
    """Available source focus"""

    WEB = "web"
    ACADEMIC = "scholar"
    SOCIAL = "social"


class TimeRange(Enum):
    """Available time range"""

    ALL = None
    TODAY = "DAY"
    LAST_WEEK = "WEEK"
    LAST_MONTH = "MONTH"
    LAST_YEAR = "YEAR"


class StreamResponse(BaseModel):
    raw: dict[str, Any]
    title: str | None
    answer: str | None
    chunks: list[str]
    last_chunk: str | None
    search_results: list[str]


class AskResponse(BaseModel):
    title: str | None
    answer: str | None
    chunks: list[str]
    search_results: list[str]
    raw_response: dict[str, Any]


class Perplexity:
    """Client for interacting with Perplexity AI Web API"""

    def __init__(self, session_token: str) -> None:
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Referer": "https://www.perplexity.ai/",
            "Origin": "https://www.perplexity.ai",
        }
        self._cookies = {"__Secure-next-auth.session-token": session_token}
        self._client = Client(headers=self._headers, cookies=self._cookies, timeout=Timeout(1800, read=None))
        self.reset_response_data()

    def reset_response_data(self) -> None:
        self.title: str | None = None
        self.answer: str | None = None
        self.chunks: list[str] = []
        self.last_chunk: str | None = None
        self.search_results: list[str] = []
        self.raw_response: dict[str, Any] = {}
        self._backend_uuid: str | None = None

    @staticmethod
    def _extract_json_line(line: str | bytes) -> dict[str, Any] | None:
        if isinstance(line, bytes):
            return loads(line[6:]) if line.startswith(b"data: ") else None
        else:
            return loads(line[6:]) if line.startswith("data: ") else None

    def _prepare_json_data(
        self,
        query: str,
        attachment_urls: list[str] | None,
        model: type[ModelBase],
        save_to_library: bool,
        search_focus: SearchFocus,
        source_focus: SourceFocus | list[SourceFocus],
        time_range: TimeRange,
        language: str,
        timezone: str | None,
        coordinates: tuple[float, float] | None,
    ) -> dict[str, Any]:
        sources = [source_focus.value] if isinstance(source_focus, SourceFocus) else [s.value for s in source_focus]

        return {
            "params": {
                "attachments": attachment_urls or [],
                "language": language,
                "timezone": timezone,
                "client_coordinates": {
                    "location_lat": coordinates[0],
                    "location_lng": coordinates[1],
                    "name": "",
                }
                if coordinates
                else None,
                "sources": sources,
                "model_preference": model.get_identifier(),
                "mode": model.get_mode(),
                "search_focus": search_focus.value,
                "search_recency_filter": time_range.value,
                "is_incognito": not save_to_library,
                "use_schematized_api": True,
                "local_search_enabled": True,
                "prompt_source": "user",
                "send_back_text_in_streaming_api": True,
                "version": "2.18",
            },
            "query_str": query,
        }

    def _process_data(self, data: dict[str, Any]) -> None:
        if self._backend_uuid is None and "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]

        if "text" in data:
            text_data = loads(data["text"])

            if isinstance(text_data, list):
                for item in text_data:
                    if item.get("step_type") == "FINAL":
                        self._update_response_data(data.get("thread_title", ""), {"answer": item["content"]["answer"]})
                        break
            elif isinstance(text_data, dict):
                self._update_response_data(data.get("thread_title", ""), text_data)

    def _update_response_data(self, title: str, answer_data: dict[str, Any]) -> None:
        self.title = title
        self.answer = answer_data.get("answer")
        self.chunks = answer_data.get("chunks", [])
        self.last_chunk = self.chunks[-1] if self.chunks else None
        self.search_results = answer_data.get("web_results", [])
        self.raw_response = answer_data

    class _AskCall:
        def __init__(self, parent: "Perplexity", json_data: dict[str, Any]) -> None:
            self._parent = parent
            self._json_data = json_data

        def stream(self) -> Generator[StreamResponse, None, None]:
            """
            Stream response data in real-time

            Yields:
                StreamResponse
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
                            raw=data,
                            title=self._parent.title,
                            answer=self._parent.answer,
                            chunks=list(self._parent.chunks),
                            last_chunk=self._parent.last_chunk,
                            search_results=list(self._parent.search_results),
                        )

                        if data.get("final"):
                            break

        def run(self) -> AskResponse:
            """
            Run the ask request and return the response data

            Returns:
                AskResponse
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
                raw_response=self._parent.raw_response,
            )

    def ask(
        self,
        query: str,
        attachment_urls: list[str] | None = None,
        model: type[ModelBase] = ModelType.Pro.Best,
        save_to_library: bool = False,
        search_focus: SearchFocus = SearchFocus.WEB,
        source_focus: SourceFocus | list[SourceFocus] = SourceFocus.WEB,
        time_range: TimeRange = TimeRange.ALL,
        language: str = "en-US",
        timezone: str | None = None,
        coordinates: tuple[float, float] | None = None,
    ) -> "_AskCall":
        """
        Send a query to Perplexity AI and get a response.

        Args:
            query: The question or prompt to send.
            attachment_urls: Optional list of URLs to attach (max 10). Defaults to None.
            model: The model to use for the response. Defaults to ModelType.Pro.Best.
            save_to_library: Whether to save this query to your library. Defaults to False.
            search_focus: Search focus type. Defaults to SearchFocus.WEB.
            source_focus: Source focus type. Defaults to SourceFocus.WEB.
            time_range: Time range for search results. Defaults to TimeRange.ALL.
            language: Language code. (e.g., "en-US"). Defaults to "en-US".
            timezone: Timezone code (e.g., "America/New_York"). Defaults to None.
            coordinates: Location coordinates (latitude, longitude). Defaults to None.

        Returns:
            _AskCall object, which can be used to retrieve the response directly or stream it.
        """

        if attachment_urls and len(attachment_urls) > 10:
            raise ValueError("Maximum of 10 attachments allowed.")

        json_data = self._prepare_json_data(
            query,
            attachment_urls,
            model,
            save_to_library,
            search_focus,
            source_focus,
            time_range,
            language,
            timezone,
            coordinates,
        )

        return Perplexity._AskCall(self, json_data)
