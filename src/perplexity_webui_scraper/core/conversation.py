"""Conversation class — manages query lifecycle and streaming state."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper.core.files import _FileInfo, upload_file, validate_files
from perplexity_webui_scraper.core.parser import parse_sse_line, process_sse_data
from perplexity_webui_scraper.core.payload import build_payload
from perplexity_webui_scraper.core.response import Response, SearchResultItem
from perplexity_webui_scraper.models.registry import MODELS
from perplexity_webui_scraper.models.types import Model  # noqa: TC001


if TYPE_CHECKING:
    from collections.abc import Generator

    from perplexity_webui_scraper._internal.types import CitationMode, FileInput
    from perplexity_webui_scraper.config.conversation import ConversationConfig
    from perplexity_webui_scraper.http.client import HTTPClient


_DEFAULT_MODEL: str = "perplexity/best"


class Conversation:
    """Manage a Perplexity conversation thread with multi-turn and streaming support.

    Create instances via ``client.create_conversation()`` — do not instantiate directly.

    Example:
        ```python
        for response in conversation.ask("Tell me a story", stream=True):
            print(response.last_chunk, end="", flush=True)
        ```

    Attributes:
        answer: The most recent final answer text.
        search_results: Web sources cited in the last response.
        uuid: Conversation UUID returned by Perplexity.
    """

    __slots__ = (
        "_answer",
        "_backend_uuid",
        "_chunks",
        "_citation_mode",
        "_config",
        "_http",
        "_raw_data",
        "_read_write_token",
        "_search_results",
        "_stream_generator",
    )

    def __init__(self, http: HTTPClient, config: ConversationConfig) -> None:
        self._http = http
        self._config = config
        self._citation_mode: CitationMode = config.citation_mode
        self._backend_uuid: str | None = None
        self._read_write_token: str | None = None
        self._answer: str | None = None
        self._chunks: list[str] = []
        self._search_results: list[SearchResultItem] = []
        self._raw_data: dict[str, Any] = {}
        self._stream_generator: Generator[Response, None, None] | None = None

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def answer(self) -> str | None:
        """Most recent final answer text.  ``None`` until a response completes."""
        return self._answer

    @property
    def search_results(self) -> list[SearchResultItem]:
        """Web sources cited in the most recent response."""
        return self._search_results

    @property
    def uuid(self) -> str | None:
        """Backend conversation UUID.  ``None`` before the first query completes."""
        return self._backend_uuid

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ask(
        self,
        query: str,
        model: str | None = None,
        files: list[FileInput] | None = None,
        citation_mode: CitationMode | None = None,
        stream: bool = False,
    ) -> Conversation:
        """Send a query and return ``self`` for chaining or streaming iteration.

        In non-streaming mode, blocks until the response completes.
        In streaming mode, iterate over ``self`` to receive chunks.

        Args:
            query: The prompt text.
            model: Model ID override. Falls back to config or ``"perplexity/best"``.
            files: Optional list of attachments.
            citation_mode: Per-query citation override.
            stream: If ``True``, sets up an internal generator for streaming.

        Returns:
            ``self`` to support method chaining or iteration.
        """
        model_id = model or self._config.model or _DEFAULT_MODEL
        resolved_model = MODELS.resolve(model_id)
        self._citation_mode = citation_mode if citation_mode is not None else self._config.citation_mode

        self._execute(query, resolved_model, files, stream=stream)

        return self

    def __iter__(self) -> Generator[Response, None, None]:
        """Yield streaming response frames.

        Only yields when the conversation was started with ``stream=True``.
        After iteration completes, the internal generator is cleared.

        Yields:
            Incremental Response objects.
        """
        if self._stream_generator is not None:
            yield from self._stream_generator
            self._stream_generator = None

    # ------------------------------------------------------------------
    # Private execution
    # ------------------------------------------------------------------

    def _execute(
        self,
        query: str,
        model: Model,
        files: list[FileInput] | None,
        stream: bool = False,
    ) -> None:
        """Orchestrate file upload, payload construction, and HTTP dispatch."""
        self._reset_state()

        file_urls: list[str] = []

        if files:
            validated: list[_FileInfo] = validate_files(files)

            with ThreadPoolExecutor() as executor:
                file_urls = list(executor.map(lambda f: upload_file(f, self._http), validated))

        payload = build_payload(
            query=query,
            model=model,
            file_urls=file_urls,
            config=self._config,
            backend_uuid=self._backend_uuid,
            read_write_token=self._read_write_token,
        )

        self._http.init_search(query)

        if stream:
            self._stream_generator = self._stream(payload)
        else:
            self._complete(payload)

    def _reset_state(self) -> None:
        """Reset all mutable response state before a new query."""
        self._answer = None
        self._chunks = []
        self._search_results = []
        self._raw_data = {}
        self._stream_generator = None

    def _apply_sse_data(self, data: dict[str, Any]) -> None:
        """Apply a single parsed SSE data chunk to the conversation state.

        Args:
            data: Deserialized SSE data dict (already filtered for ``data:`` prefix).
        """
        if "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]
        if "read_write_token" in data:
            self._read_write_token = data["read_write_token"]

        answer, chunks, updated_results, raw_data = process_sse_data(data, self._search_results, self._citation_mode)

        if updated_results is not self._search_results:
            self._search_results = updated_results

        if answer is not None:
            self._answer = answer

        if chunks:
            self._chunks = chunks

        if raw_data:
            self._raw_data = raw_data

    def _build_response(self) -> Response:
        """Construct a :class:`~perplexity_webui_scraper.Response` snapshot."""
        return Response(
            answer=self._answer,
            chunks=list(self._chunks),
            last_chunk=self._chunks[-1] if self._chunks else None,
            search_results=list(self._search_results),
            conversation_uuid=self._backend_uuid,
            raw_data=dict(self._raw_data),
        )

    def _complete(self, payload: dict[str, Any]) -> None:
        """Run the SSE stream to completion (non-streaming mode)."""
        for line in self._http.stream_ask(payload):
            data = parse_sse_line(line)

            if data:
                self._apply_sse_data(data)

                if data.get("final"):
                    break

    def _stream(self, payload: dict[str, Any]) -> Generator[Response, None, None]:
        """Yield :class:`Response` snapshots for each SSE data frame."""
        for line in self._http.stream_ask(payload):
            data = parse_sse_line(line)

            if data:
                self._apply_sse_data(data)
                yield self._build_response()

                if data.get("final"):
                    break
