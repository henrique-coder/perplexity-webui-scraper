"""Conversation query lifecycle and streaming state."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper._internal.constants import ENDPOINT_AUTH_SESSION, ENDPOINT_USER_SETTINGS
from perplexity_webui_scraper._internal.exceptions import ResearchClarifyingQuestionsError
from perplexity_webui_scraper.core.account import (
    AccountProfile,
    AccountSession,
    AccountSettings,
    ensure_file_access,
    ensure_model_access,
    model_for_account,
)
from perplexity_webui_scraper.core.files import _FileInfo, upload_file, validate_files
from perplexity_webui_scraper.core.parser import (
    SchematizedStreamState,
    parse_sse_line,
    process_sse_data,
)
from perplexity_webui_scraper.core.payload import build_payload
from perplexity_webui_scraper.core.response import Response, SearchResultItem
from perplexity_webui_scraper.models.registry import MODELS
from perplexity_webui_scraper.models.types import Model  # noqa: TC001


if TYPE_CHECKING:
    from collections.abc import Generator

    from perplexity_webui_scraper._internal.types import CitationMode, FileInput
    from perplexity_webui_scraper.config.conversation import ConversationConfig
    from perplexity_webui_scraper.http.client import HTTPClient
    from perplexity_webui_scraper.models.types import ModelMode


_DEFAULT_MODEL: str = "perplexity/best"


class Conversation:
    """Manage a Perplexity conversation thread with multi-turn and streaming support.

    Create instances through ``client.create_conversation()`` instead of instantiating this class directly.

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
        "_schematized_state",
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
        self._schematized_state = SchematizedStreamState()
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
        allow_risky_model: bool | None = None,
        custom_model_mode: ModelMode | None = None,
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
            allow_risky_model: Per-query acknowledgement for a model whose
                status is not ``"available"``.
            custom_model_mode: Backend mode for a ``custom:<identifier>`` model.

        Returns:
            ``self`` to support method chaining or iteration.
        """
        model_id = model or self._config.model or _DEFAULT_MODEL
        resolved_model = MODELS.resolve_for_use(
            model_id,
            allow_risky_model=(self._config.allow_risky_model if allow_risky_model is None else allow_risky_model),
            custom_model_mode=custom_model_mode or self._config.custom_model_mode,
        )
        resolved_model = self._validate_request_access(resolved_model, has_files=bool(files))
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
            self._stream_generator = self._stream(payload, model)
        else:
            self._complete(payload, model)

    def _validate_request_access(self, model: Model, has_files: bool) -> Model:
        """Ensure the account can use the selected model and attachments."""
        response = self._http.get(ENDPOINT_AUTH_SESSION, rate_limited=False)
        session = AccountSession.model_validate(response.json())
        settings: AccountSettings | None = None

        if session.account_tier == "unknown":
            settings_response = self._http.get(ENDPOINT_USER_SETTINGS, rate_limited=False)
            settings = AccountSettings.model_validate(settings_response.json())

        profile = AccountProfile(session=session, settings=settings)
        account_tier = profile.account_tier
        effective_session = AccountSession.model_validate({"user": {"subscription_tier": account_tier}})

        if model.status == "available":
            ensure_model_access(effective_session, model)

        ensure_file_access(account_tier, has_files)

        return model_for_account(model, account_tier)

    def _reset_state(self) -> None:
        """Reset all mutable response state before a new query."""
        self._reset_response_state()
        self._stream_generator = None

    def _reset_response_state(self) -> None:
        """Reset response fields while retaining conversation continuation tokens."""
        self._answer = None
        self._chunks = []
        self._search_results = []
        self._raw_data = {}
        self._schematized_state = SchematizedStreamState()

    def _apply_sse_data(self, data: dict[str, Any]) -> None:
        """Apply a single parsed SSE data chunk to the conversation state.

        Args:
            data: Deserialized SSE data dict (already filtered for ``data:`` prefix).
        """
        if "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]

        if "read_write_token" in data:
            self._read_write_token = data["read_write_token"]

        answer, chunks, updated_results, raw_data = process_sse_data(
            data,
            self._search_results,
            self._citation_mode,
            self._schematized_state,
        )

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

    def _complete(self, payload: dict[str, Any], model: Model) -> None:
        """Run the SSE stream to completion, retrying clarification automatically."""
        try:
            self._consume(payload)
        except ResearchClarifyingQuestionsError as error:
            if self._config.research_interaction == "manual":
                raise

            self._consume(self._build_research_followup_payload(model, error))

    def _consume(self, payload: dict[str, Any]) -> None:
        """Consume an SSE stream without yielding intermediate responses."""
        for line in self._http.stream_ask(payload):
            data = parse_sse_line(line)

            if data:
                self._apply_sse_data(data)

                if data.get("final"):
                    break

    def _stream(self, payload: dict[str, Any], model: Model) -> Generator[Response, None, None]:
        """Yield response snapshots and retry clarification automatically when configured."""
        try:
            yield from self._stream_payload(payload)
        except ResearchClarifyingQuestionsError as error:
            if self._config.research_interaction == "manual":
                raise

            yield from self._stream_payload(self._build_research_followup_payload(model, error))

    def _stream_payload(self, payload: dict[str, Any]) -> Generator[Response, None, None]:
        """Yield response snapshots for one SSE request."""
        for line in self._http.stream_ask(payload):
            data = parse_sse_line(line)

            if data:
                self._apply_sse_data(data)
                yield self._build_response()

                if data.get("final"):
                    break

    def _build_research_followup_payload(
        self,
        model: Model,
        error: ResearchClarifyingQuestionsError,
    ) -> dict[str, Any]:
        """Build one autonomous follow-up after a Deep Research clarification."""
        questions = "\n".join(f"{index}. {question}" for index, question in enumerate(error.questions, start=1))
        query = (
            "Continue the Deep Research task without asking the user for input. "
            "Answer the clarification questions below by choosing the most "
            "reasonable options from the original context. If ambiguity remains, "
            "state the assumption briefly and proceed with the research.\n\n"
            f"Clarification questions:\n{questions}"
        )

        self._reset_response_state()
        self._http.init_search(query)

        return build_payload(
            query=query,
            model=model,
            file_urls=[],
            config=self._config,
            backend_uuid=self._backend_uuid,
            read_write_token=self._read_write_token,
        )
