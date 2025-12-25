"""Core client implementation."""

from __future__ import annotations

from mimetypes import guess_type
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from orjson import JSONDecodeError, loads


if TYPE_CHECKING:
    from collections.abc import Generator
    from re import Match

from .config import ClientConfig, ConversationConfig
from .constants import (
    API_VERSION,
    CITATION_PATTERN,
    ENDPOINT_UPLOAD,
    JSON_OBJECT_PATTERN,
    PROMPT_SOURCE,
    SEND_BACK_TEXT,
    USE_SCHEMATIZED_API,
)
from .enums import CitationMode
from .exceptions import FileUploadError, FileValidationError, ResearchClarifyingQuestionsError, ResponseParsingError
from .http import HTTPClient
from .limits import MAX_FILE_SIZE, MAX_FILES
from .logging import configure_logging, get_logger, log_conversation_created, log_query_sent
from .models import Model, Models
from .types import Response, SearchResultItem, _FileInfo


logger = get_logger(__name__)


class Perplexity:
    """Web scraper for Perplexity AI conversations."""

    __slots__ = ("_http",)

    def __init__(self, session_token: str, config: ClientConfig | None = None) -> None:
        """
        Initialize web scraper with session token.

        Args:
            session_token: Perplexity session cookie (__Secure-next-auth.session-token).
            config: Optional HTTP client configuration.

        Raises:
            ValueError: If session_token is empty or whitespace.
        """

        if not session_token or not session_token.strip():
            raise ValueError("session_token cannot be empty")

        cfg = config or ClientConfig()

        # Configure logging based on config
        configure_logging(level=cfg.logging_level, log_file=cfg.log_file)

        logger.info(
            "Perplexity client initializing | "
            f"session_token_length={len(session_token)} "
            f"logging_level={cfg.logging_level.value} "
            f"log_file={cfg.log_file}"
        )
        logger.debug(
            "Client configuration | "
            f"timeout={cfg.timeout}s "
            f"impersonate={cfg.impersonate} "
            f"max_retries={cfg.max_retries} "
            f"retry_base_delay={cfg.retry_base_delay}s "
            f"retry_max_delay={cfg.retry_max_delay}s "
            f"retry_jitter={cfg.retry_jitter} "
            f"requests_per_second={cfg.requests_per_second} "
            f"rotate_fingerprint={cfg.rotate_fingerprint}"
        )

        self._http = HTTPClient(
            session_token,
            timeout=cfg.timeout,
            impersonate=cfg.impersonate,
            max_retries=cfg.max_retries,
            retry_base_delay=cfg.retry_base_delay,
            retry_max_delay=cfg.retry_max_delay,
            retry_jitter=cfg.retry_jitter,
            requests_per_second=cfg.requests_per_second,
            rotate_fingerprint=cfg.rotate_fingerprint,
        )

        logger.info("Perplexity client initialized successfully")

    def create_conversation(self, config: ConversationConfig | None = None) -> Conversation:
        """Create a new conversation."""

        cfg = config or ConversationConfig()
        logger.debug(
            "Creating conversation | "
            f"model={cfg.model} "
            f"citation_mode={cfg.citation_mode} "
            f"save_to_library={cfg.save_to_library} "
            f"search_focus={cfg.search_focus} "
            f"language={cfg.language}"
        )

        conversation = Conversation(self._http, cfg)

        log_conversation_created(
            f"model={cfg.model}, citation_mode={cfg.citation_mode}, "
            f"search_focus={cfg.search_focus}, language={cfg.language}"
        )
        logger.info("Conversation created successfully")

        return conversation

    def close(self) -> None:
        """Close the client."""

        logger.debug("Closing Perplexity client")
        self._http.close()
        logger.info("Perplexity client closed")

    def __enter__(self) -> Perplexity:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class Conversation:
    """Manage a Perplexity conversation with query and follow-up support."""

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
        "_title",
    )

    def __init__(self, http: HTTPClient, config: ConversationConfig) -> None:
        logger.debug(
            "Conversation.__init__ | "
            f"model={config.model} "
            f"citation_mode={config.citation_mode} "
            f"save_to_library={config.save_to_library} "
            f"search_focus={config.search_focus}"
        )
        self._http = http
        self._config = config
        self._citation_mode = CitationMode.DEFAULT
        self._backend_uuid: str | None = None
        self._read_write_token: str | None = None
        self._title: str | None = None
        self._answer: str | None = None
        self._chunks: list[str] = []
        self._search_results: list[SearchResultItem] = []
        self._raw_data: dict[str, Any] = {}
        self._stream_generator: Generator[Response, None, None] | None = None
        logger.debug("Conversation initialized with empty state")

    @property
    def answer(self) -> str | None:
        """Last response text."""

        return self._answer

    @property
    def title(self) -> str | None:
        """Conversation title."""

        return self._title

    @property
    def search_results(self) -> list[SearchResultItem]:
        """Search results from last response."""

        return self._search_results

    @property
    def uuid(self) -> str | None:
        """Conversation UUID."""

        return self._backend_uuid

    def __iter__(self) -> Generator[Response, None, None]:
        if self._stream_generator is not None:
            yield from self._stream_generator

            self._stream_generator = None

    def ask(
        self,
        query: str,
        model: Model | None = None,
        files: list[str | PathLike] | None = None,
        citation_mode: CitationMode | None = None,
        stream: bool = False,
    ) -> Conversation:
        """Ask a question. Returns self for method chaining or streaming iteration."""

        logger.info(
            "Conversation.ask called | "
            f"query_length={len(query)} "
            f"query_preview={query[:100]}{'...' if len(query) > 100 else ''} "
            f"model={model} "
            f"files_count={len(files) if files else 0} "
            f"citation_mode={citation_mode} "
            f"stream={stream}"
        )

        effective_model = model or self._config.model or Models.BEST
        effective_citation = citation_mode if citation_mode is not None else self._config.citation_mode
        self._citation_mode = effective_citation

        logger.debug(
            f"Effective parameters | effective_model={effective_model} effective_citation={effective_citation}"
        )

        log_query_sent(query, str(effective_model), bool(files))
        self._execute(query, effective_model, files, stream=stream)

        logger.debug("Query execution completed")

        return self

    def _execute(
        self,
        query: str,
        model: Model,
        files: list[str | PathLike] | None,
        stream: bool = False,
    ) -> None:
        """Execute a query."""

        logger.debug(
            f"Executing query | "
            f"query_length={len(query)} "
            f"model={model} "
            f"files_count={len(files) if files else 0} "
            f"stream={stream} "
            f"is_followup={self._backend_uuid is not None}"
        )

        self._reset_response_state()
        logger.debug("Response state reset")

        # Upload files
        file_urls: list[str] = []

        if files:
            logger.debug(f"Validating {len(files)} files")
            validated = self._validate_files(files)
            logger.debug(f"Validated {len(validated)} files, uploading...")
            file_urls = [self._upload_file(f) for f in validated]
            logger.debug(f"Uploaded {len(file_urls)} files successfully")

        payload = self._build_payload(query, model, file_urls)
        logger.debug(
            f"Payload built | payload_keys={list(payload.keys())} params_keys={list(payload.get('params', {}).keys())}"
        )

        logger.debug("Initializing search session")
        self._http.init_search(query)

        if stream:
            logger.debug("Starting streaming mode")
            self._stream_generator = self._stream(payload)
        else:
            logger.debug("Starting complete mode (non-streaming)")
            self._complete(payload)
            logger.debug(
                f"Query completed | "
                f"title={self._title} "
                f"answer_length={len(self._answer) if self._answer else 0} "
                f"chunks_count={len(self._chunks)} "
                f"search_results_count={len(self._search_results)}"
            )

    def _reset_response_state(self) -> None:
        self._title = None
        self._answer = None
        self._chunks = []
        self._search_results = []
        self._raw_data = {}
        self._stream_generator = None

    def _validate_files(self, files: list[str | PathLike] | None) -> list[_FileInfo]:
        if not files:
            return []

        seen: set[str] = set()
        file_list: list[Path] = []

        for item in files:
            if item and isinstance(item, (str, PathLike)):
                path = Path(item).resolve()

                if path.as_posix() not in seen:
                    seen.add(path.as_posix())
                    file_list.append(path)

        if len(file_list) > MAX_FILES:
            raise FileValidationError(
                str(file_list[0]),
                f"Too many files: {len(file_list)}. Maximum allowed is {MAX_FILES}.",
            )

        result: list[_FileInfo] = []

        for path in file_list:
            file_path = path.as_posix()

            try:
                if not path.exists():
                    raise FileValidationError(file_path, "File not found")
                if not path.is_file():
                    raise FileValidationError(file_path, "Path is not a file")

                file_size = path.stat().st_size

                if file_size > MAX_FILE_SIZE:
                    raise FileValidationError(
                        file_path,
                        f"File exceeds 50MB limit: {file_size / (1024 * 1024):.1f}MB",
                    )

                if file_size == 0:
                    raise FileValidationError(file_path, "File is empty")

                mimetype, _ = guess_type(file_path)
                mimetype = mimetype or "application/octet-stream"

                result.append(
                    _FileInfo(
                        path=file_path,
                        size=file_size,
                        mimetype=mimetype,
                        is_image=mimetype.startswith("image/"),
                    )
                )
            except FileValidationError as error:
                raise error
            except (FileNotFoundError, PermissionError) as error:
                raise FileValidationError(file_path, f"Cannot access file: {error}") from error
            except OSError as error:
                raise FileValidationError(file_path, f"File system error: {error}") from error

        return result

    def _upload_file(self, file_info: _FileInfo) -> str:
        file_uuid = str(uuid4())

        json_data = {
            "files": {
                file_uuid: {
                    "filename": file_info.path,
                    "content_type": file_info.mimetype,
                    "source": "default",
                    "file_size": file_info.size,
                    "force_image": file_info.is_image,
                }
            }
        }

        try:
            response = self._http.post(ENDPOINT_UPLOAD, json=json_data)
            response_data = response.json()
            upload_url = response_data.get("results", {}).get(file_uuid, {}).get("s3_object_url")

            if not upload_url:
                raise FileUploadError(file_info.path, "No upload URL returned")

            return upload_url
        except FileUploadError as error:
            raise error
        except Exception as e:
            raise FileUploadError(file_info.path, str(e)) from e

    def _build_payload(
        self,
        query: str,
        model: Model,
        file_urls: list[str],
    ) -> dict[str, Any]:
        cfg = self._config

        sources = (
            [s.value for s in cfg.source_focus] if isinstance(cfg.source_focus, list) else [cfg.source_focus.value]
        )

        client_coordinates = None
        if cfg.coordinates is not None:
            client_coordinates = {
                "location_lat": cfg.coordinates.latitude,
                "location_lng": cfg.coordinates.longitude,
                "name": "",
            }

        params: dict[str, Any] = {
            "attachments": file_urls,
            "language": cfg.language,
            "timezone": cfg.timezone,
            "client_coordinates": client_coordinates,
            "sources": sources,
            "model_preference": model.identifier,
            "mode": model.mode,
            "search_focus": cfg.search_focus.value,
            "search_recency_filter": cfg.time_range.value if cfg.time_range.value else None,
            "is_incognito": not cfg.save_to_library,
            "use_schematized_api": USE_SCHEMATIZED_API,
            "local_search_enabled": cfg.coordinates is not None,
            "prompt_source": PROMPT_SOURCE,
            "send_back_text_in_streaming_api": SEND_BACK_TEXT,
            "version": API_VERSION,
        }

        if self._backend_uuid is not None:
            params["last_backend_uuid"] = self._backend_uuid
            params["query_source"] = "followup"

            if self._read_write_token:
                params["read_write_token"] = self._read_write_token

        return {"params": params, "query_str": query}

    def _format_citations(self, text: str | None) -> str | None:
        if not text or self._citation_mode == CitationMode.DEFAULT:
            return text

        def replacer(m: Match[str]) -> str:
            num = m.group(1)

            if not num.isdigit():
                return m.group(0)

            if self._citation_mode == CitationMode.CLEAN:
                return ""

            idx = int(num) - 1

            if 0 <= idx < len(self._search_results):
                url = self._search_results[idx].url or ""

                if self._citation_mode == CitationMode.MARKDOWN and url:
                    return f"[{num}]({url})"

            return m.group(0)

        return CITATION_PATTERN.sub(replacer, text)

    def _parse_line(self, line: str | bytes) -> dict[str, Any] | None:
        if isinstance(line, bytes) and line.startswith(b"data: "):
            return loads(line[6:])

        if isinstance(line, str) and line.startswith("data: "):
            return loads(line[6:])

        return None

    def _process_data(self, data: dict[str, Any]) -> None:
        """Process SSE data chunk and update conversation state."""

        if self._backend_uuid is None and "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]

        if self._read_write_token is None and "read_write_token" in data:
            self._read_write_token = data["read_write_token"]

        if self._title is None and "thread_title" in data:
            self._title = data["thread_title"]

        if "blocks" in data:
            for block in data["blocks"]:
                if block.get("intended_usage") == "web_results":
                    diff = block.get("diff_block", {})

                    for patch in diff.get("patches", []):
                        if patch.get("op") == "replace" and patch.get("path") == "/web_results":
                            pass

        if "text" not in data and "blocks" not in data:
            return None

        try:
            json_data = loads(data["text"])
        except KeyError as e:
            raise ValueError("Missing 'text' field in data") from e
        except JSONDecodeError as e:
            raise ValueError("Invalid JSON in 'text' field") from e

        answer_data: dict[str, Any] = {}

        if isinstance(json_data, list):
            for item in json_data:
                step_type = item.get("step_type")

                # Handle Research mode clarifying questions
                if step_type == "RESEARCH_CLARIFYING_QUESTIONS":
                    questions = self._extract_clarifying_questions(item)

                    raise ResearchClarifyingQuestionsError(questions)

                if step_type == "FINAL":
                    raw_content = item.get("content", {})
                    answer_content = raw_content.get("answer")

                    if isinstance(answer_content, str) and JSON_OBJECT_PATTERN.match(answer_content):
                        answer_data = loads(answer_content)
                    else:
                        answer_data = raw_content

                    self._update_state(data.get("thread_title"), answer_data)

                    break
        elif isinstance(json_data, dict):
            self._update_state(data.get("thread_title"), json_data)
        else:
            raise ResponseParsingError(
                "Unexpected JSON structure in 'text' field",
                raw_data=str(json_data),
            )

    def _extract_clarifying_questions(self, item: dict[str, Any]) -> list[str]:
        """Extract clarifying questions from a RESEARCH_CLARIFYING_QUESTIONS step."""

        questions: list[str] = []
        content = item.get("content", {})

        # Try different possible structures for questions
        if isinstance(content, dict):
            if "questions" in content:
                raw_questions = content["questions"]

                if isinstance(raw_questions, list):
                    questions = [str(q) for q in raw_questions if q]
            elif "clarifying_questions" in content:
                raw_questions = content["clarifying_questions"]

                if isinstance(raw_questions, list):
                    questions = [str(q) for q in raw_questions if q]
            elif not questions:
                for value in content.values():
                    if isinstance(value, str) and "?" in value:
                        questions.append(value)
        elif isinstance(content, list):
            questions = [str(q) for q in content if q]
        elif isinstance(content, str):
            questions = [content]

        return questions

    def _update_state(self, title: str | None, answer_data: dict[str, Any]) -> None:
        self._title = title

        web_results = answer_data.get("web_results", [])

        if web_results:
            self._search_results = [
                SearchResultItem(
                    title=r.get("name"),
                    snippet=r.get("snippet"),
                    url=r.get("url"),
                )
                for r in web_results
                if isinstance(r, dict)
            ]

        answer_text = answer_data.get("answer")

        if answer_text is not None:
            self._answer = self._format_citations(answer_text)

        chunks = answer_data.get("chunks", [])

        if chunks:
            formatted = [self._format_citations(chunk) for chunk in chunks if chunk is not None]
            self._chunks = [c for c in formatted if c is not None]

        self._raw_data = answer_data

    def _build_response(self) -> Response:
        return Response(
            title=self._title,
            answer=self._answer,
            chunks=list(self._chunks),
            last_chunk=self._chunks[-1] if self._chunks else None,
            search_results=list(self._search_results),
            conversation_uuid=self._backend_uuid,
            raw_data=self._raw_data,
        )

    def _complete(self, payload: dict[str, Any]) -> None:
        for line in self._http.stream_ask(payload):
            data = self._parse_line(line)

            if data:
                self._process_data(data)

                if data.get("final"):
                    break

    def _stream(self, payload: dict[str, Any]) -> Generator[Response, None, None]:
        for line in self._http.stream_ask(payload):
            data = self._parse_line(line)

            if data:
                self._process_data(data)

                yield self._build_response()

                if data.get("final"):
                    break
