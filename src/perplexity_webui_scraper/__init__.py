# Standard modules
from collections.abc import Generator
from typing import Any

# Third-party modules
from httpx import Client, Timeout
from orjson import loads
from pydantic import BaseModel

# Local modules
from .models import ModelBase, ModelType
from .utils import SearchFocus, SourceFocus, TimeRange


__all__ = [
    "ModelType",
    "Perplexity",
    "SearchFocus",
    "SourceFocus",
    "TimeRange",
]


class StreamResponse(BaseModel):
    title: str | None
    answer: str | None
    chunks: list[str]
    last_chunk: str | None
    search_results: list[str]
    raw_data: dict[str, Any]


class AskResponse(BaseModel):
    title: str | None
    answer: str | None
    chunks: list[str]
    search_results: list[str]
    raw_data: dict[str, Any]


class Perplexity:
    """Client for interacting with Perplexity AI WebUI"""

    def __init__(self, session_token: str) -> None:
        """
        Initialize the Perplexity client.

        Args:
            session_token: The session token (`__Secure-next-auth.session-token` cookie) to use for authentication.
        """

        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Referer": "https://www.perplexity.ai/",
            "Origin": "https://www.perplexity.ai",
            "Accept": "text/event-stream",
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1",
            "TE": "trailers",
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
        self.conversation_uuid: str | None = None
        self.raw_data: dict[str, Any] = {}

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
        if self.conversation_uuid is None and "backend_uuid" in data:
            self.conversation_uuid = data["backend_uuid"]

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
        self.raw_data = answer_data

    class AskCall:
        def __init__(self, parent: "Perplexity", json_data: dict[str, Any]) -> None:
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
    ) -> AskCall:
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
            AskCall object, which can be used to retrieve the response directly or stream it.
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

        return Perplexity.AskCall(self, json_data)
