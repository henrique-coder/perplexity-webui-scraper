# Standard modules
from collections.abc import Generator
from enum import Enum
from typing import Any, TypeVar

# Third-party modules
from httpx import Client, Response, Timeout
from orjson import loads


T = TypeVar("T", bound="ModelBase")


class ModelBase:
    """Base class for all models"""

    _identifier: str
    _mode: str

    @classmethod
    def get_identifier(cls: type[T]) -> str:
        return cls._identifier

    @classmethod
    def get_mode(cls: type[T]) -> str:
        return cls._mode


class ModelType:
    """Main class for accessing different model categories and their submodels"""

    class Pro:
        """3x more sources and detailed answers"""

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

    class DeepResearch(ModelBase):
        """In-depth reports on complex topics"""

        _identifier = "pplx_alpha"
        _mode = "copilot"


class SearchFocus(Enum):
    WEB = "internet"
    WRITING = "writing"


class SourceFocus(Enum):
    WEB = "web"
    ACADEMIC = "scholar"
    SOCIAL = "social"


class TimeRange(Enum):
    ALL = None
    TODAY = "DAY"
    LAST_WEEK = "WEEK"
    LAST_MONTH = "MONTH"
    LAST_YEAR = "YEAR"


class Perplexity:
    def __init__(self, session_token: str) -> None:
        self._headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Referer": "https://www.perplexity.ai/",
            "Origin": "https://www.perplexity.ai",
        }
        self._cookies = {"__Secure-next-auth.session-token": session_token}
        self._client = Client(headers=self._headers, cookies=self._cookies, timeout=Timeout(1800, read=None))
        self._backend_uuid: str | None = None

        self.reset_response_data()

    def reset_response_data(self) -> None:
        """Reset all response data attributes"""

        self.title: str | None = None
        self.answer: str | None = None
        self.chunks: list[str] = []
        self.last_chunk: str | None = None
        self.search_results: list[str] = []
        self.raw_response: dict[str, Any] = {}
        self._backend_uuid: str | None = None

    @staticmethod
    def _extract_json_line(line: str | bytes) -> dict[str, Any] | None:
        """Extract JSON data from a line in the response"""

        if isinstance(line, bytes):
            return loads(line[6:]) if line.startswith(b"data: ") else None
        else:
            return loads(line[6:].encode()) if line.startswith("data: ") else None

    def _prepare_json_data(
        self,
        query: str,
        attachment_urls: list[str] | None,
        model: type[ModelBase],
        save_to_library: bool,
        search_focus: SearchFocus,
        source_focus: list[SourceFocus] | SourceFocus,
        time_range: TimeRange,
        language: str,
        timezone: str | None,
        coordinates: tuple[float, float] | None,
    ) -> dict[str, Any]:
        """Prepare the JSON data for the API request"""

        if isinstance(source_focus, SourceFocus):
            sources = [source_focus.value]
        elif isinstance(sources, list):
            sources = [s.value for s in sources]

        return {
            "params": {
                "attachments": attachment_urls or [],
                "language": language,
                "timezone": timezone,
                "client_coordinates": {"location_lat": coordinates[0], "location_lng": coordinates[1], "name": ""}
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
        """Process the data from the API response"""

        if self._backend_uuid is None and "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]

        if "text" in data:
            text_data = loads(data["text"])

            if isinstance(text_data, list):
                for item in text_data:
                    if item["step_type"] == "GENERATE_IMAGE_RESULTS":
                        self._update_response_data(
                            data.get("thread_title", ""), {"answer": item["content"]["image_results"][0]["url"]}
                        )
                    else:
                        if item["step_type"] == "FINAL":
                            self._update_response_data(data.get("thread_title", ""), {"answer": item["content"]["answer"]})

                        break
            elif isinstance(text_data, dict):
                self._update_response_data(data.get("thread_title", ""), text_data)

    def _update_response_data(self, title: str, answer_data: dict[str, Any]) -> None:
        """Update response data attributes from the parsed answer"""

        self.title = title
        self.answer = answer_data.get("answer")
        self.chunks = answer_data.get("chunks", [])
        self.last_chunk = self.chunks[-1] if self.chunks else None
        self.search_results = answer_data.get("web_results", [])
        self.raw_response = answer_data

    def _process_response(self, response: Response, stream: bool = False) -> Generator[dict[str, Any], None, None] | None:
        """Process the API response, either streaming or all at once"""

        if stream:
            return self._stream_generator(response)
        else:
            for line in response.iter_lines():
                data = self._extract_json_line(line)

                if data:
                    self._process_data(data)

                    if data.get("final"):
                        break

            return None

    def _stream_generator(self, response: Response) -> Generator[dict[str, Any], None, None]:
        """Generate streaming data from the API response"""

        for line in response.iter_lines():
            data = self._extract_json_line(line)

            if data:
                self._process_data(data)

                yield data

                if data.get("final"):
                    break

    def ask(
        self,
        query: str,
        attachment_urls: list[str] | None = None,
        model: type[ModelBase] = ModelType.Pro.Best,
        save_to_library: bool = False,
        search_focus: SearchFocus = SearchFocus.WEB,
        source_focus: list[SourceFocus] | SourceFocus = SourceFocus.WEB,
        time_range: TimeRange = TimeRange.ALL,
        language: str = "en-US",
        timezone: str | None = None,
        coordinates: tuple[float, float] | None = None,
        stream: bool = False,
    ) -> Generator[dict[str, Any], None, None] | None:
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
            stream: Whether to stream the response. Defaults to False.

        Returns:
            A generator or None if not streaming.
        """

        # Reset previous response data
        self.reset_response_data()

        # Validate inputs
        if attachment_urls and len(attachment_urls) > 10:
            raise ValueError("Maximum of 10 attachments allowed.")

        # Prepare the JSON data
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

        # Initialize the session with the query
        self._client.get("https://www.perplexity.ai/search/new", params={"q": query})

        # Process the response either streaming or all at once
        if stream:

            def stream_generator() -> Generator[dict[str, Any], None, None]:
                with self._client.stream("POST", "https://www.perplexity.ai/rest/sse/perplexity_ask", json=json_data) as r:
                    r.raise_for_status()

                    for line in r.iter_lines():
                        data = self._extract_json_line(line)
                        if data:
                            self._process_data(data)

                            yield data

                            if data.get("final"):
                                break

            return stream_generator()
        else:
            with self._client.stream("POST", "https://www.perplexity.ai/rest/sse/perplexity_ask", json=json_data) as r:
                r.raise_for_status()

                for line in r.iter_lines():
                    data = self._extract_json_line(line)

                    if data:
                        self._process_data(data)

                        if data.get("final"):
                            break

            return None
