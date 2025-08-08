# Standard modules
from re import match
from typing import Any

# Third-party modules
from httpx import Client, Timeout
from orjson import loads

# Local modules
from .models import ModelBase, ModelType
from .utils import AskCall, CitationMode, SearchFocus, SearchResultItem, SourceFocus, TimeRange, format_citations


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
        self._citation_mode = CitationMode.DEFAULT
        self.reset_response_data()

    def reset_response_data(self) -> None:
        self.title = None
        self.answer = None
        self.chunks = []
        self.last_chunk = None
        self.search_results = []
        self.conversation_uuid = None
        self.raw_data = {}

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
        model: ModelBase,
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
                "model_preference": model._get_identifier(),
                "mode": model._get_mode(),
                "search_focus": search_focus.value,
                "search_recency_filter": time_range.value,
                "is_incognito": not save_to_library,
                "use_schematized_api": False,
                "local_search_enabled": True,
                "prompt_source": "user",
                "send_back_text_in_streaming_api": True,
                "version": "2.18",
            },
            "query_str": query,
        }

    def _process_data(
        self,
        data: dict[str, Any],
    ) -> None:
        if self.conversation_uuid is None and "backend_uuid" in data:
            self.conversation_uuid = data["backend_uuid"]

        if "text" in data:
            json_data = loads(data["text"])
            answer_data = {}

            if isinstance(json_data, list):
                for item in json_data:
                    if item.get("step_type") == "FINAL":
                        raw_content = item.get("content", {})
                        answer_content = raw_content.get("answer")

                        if isinstance(answer_content, str) and match(r"^\{.*\}$", answer_content):
                            answer_data = loads(answer_content)
                        else:
                            answer_data = raw_content

                        self._update_response_data(data.get("thread_title"), answer_data)
                        break
            elif isinstance(json_data, dict):
                self._update_response_data(data.get("thread_title"), json_data)

    def _update_response_data(
        self,
        title: str | None,
        answer_data: dict[str, Any],
    ) -> None:
        self.title = title
        self.search_results = [
            SearchResultItem(title=r.get("name"), snippet=r.get("snippet"), url=r.get("url"))
            for r in answer_data.get("web_results", [])
            if isinstance(r, dict)
        ]
        self.answer = format_citations(self._citation_mode, answer_data.get("answer"), self.search_results)
        self.chunks = answer_data.get("chunks", [])
        self.last_chunk = self.chunks[-1] if self.chunks else None
        self.raw_data = answer_data

    def ask(
        self,
        query: str,
        citation_mode: CitationMode = CitationMode.CLEAN,
        # attachment_urls: list[str] | None = None,
        model: ModelBase = ModelType.Best,
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
            citation_mode: The citation mode to use. Defaults to CitationMode.CLEAN.
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

        self._citation_mode = citation_mode

        # attachment_urls: Optional list of URLs to attach (max 10). Defaults to None.
        # if attachment_urls and len(attachment_urls) > 10:
        #     raise ValueError("Maximum of 10 attachments allowed.")

        json_data = self._prepare_json_data(
            query,
            [],  # attachment_urls,
            model,
            save_to_library,
            search_focus,
            source_focus,
            time_range,
            language,
            timezone,
            coordinates,
        )

        return AskCall(self, json_data)
