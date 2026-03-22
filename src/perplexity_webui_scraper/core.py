"""Core client implementation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from mimetypes import guess_type
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from curl_cffi import CurlMime
from curl_cffi.requests import Session
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
    MAX_FILE_SIZE,
    MAX_FILES,
    PROMPT_SOURCE,
    SEND_BACK_TEXT,
    USE_SCHEMATIZED_API,
)
from .exceptions import FileUploadError, FileValidationError, ResearchClarifyingQuestionsError, ResponseParsingError
from .http import HTTPClient
from .logging import configure_logging, get_logger
from .models import Model, _resolve_model
from .types import CitationMode, FileInput, Response, SearchResultItem, _FileInfo


logger = get_logger(__name__)

_DEFAULT_MODEL: str = "best"


class Perplexity:
    """Web scraper for Perplexity AI conversations."""

    __slots__ = ("_http",)

    def __init__(self, session_token: str, config: ClientConfig | None = None) -> None:
        """Initialize with session token."""

        if not session_token or not session_token.strip():
            raise ValueError("session_token cannot be empty")

        cfg = config or ClientConfig()
        configure_logging(level=cfg.logging_level, log_file=cfg.log_file)

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
            max_init_query_length=cfg.max_init_query_length,
        )

        logger.info("Perplexity client initialized")

    def create_conversation(self, config: ConversationConfig | None = None) -> Conversation:
        """Create a new conversation."""

        return Conversation(self._http, config or ConversationConfig())

    def close(self) -> None:
        """Close the client."""

        self._http.close()

    def __enter__(self) -> Perplexity:
        return self

    def __exit__(self, *args: object) -> None:
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
        self._http = http
        self._config = config
        self._citation_mode: CitationMode = "default"
        self._backend_uuid: str | None = None
        self._read_write_token: str | None = None
        self._title: str | None = None
        self._answer: str | None = None
        self._chunks: list[str] = []
        self._search_results: list[SearchResultItem] = []
        self._raw_data: dict[str, Any] = {}
        self._stream_generator: Generator[Response, None, None] | None = None

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
        model: str | None = None,
        files: list[FileInput] | None = None,
        citation_mode: CitationMode | None = None,
        stream: bool = False,
    ) -> Conversation:
        """Ask a question. Returns self for method chaining or streaming iteration."""

        model_id = model or self._config.model or _DEFAULT_MODEL
        effective_model = _resolve_model(model_id)
        effective_citation = citation_mode if citation_mode is not None else self._config.citation_mode
        self._citation_mode = effective_citation

        self._execute(query, effective_model, files, stream=stream)

        return self

    def _execute(
        self,
        query: str,
        model: Model,
        files: list[FileInput] | None,
        stream: bool = False,
    ) -> None:
        """Execute a query."""

        self._reset_response_state()

        file_urls: list[str] = []

        if files:
            validated = self._validate_files(files)

            with ThreadPoolExecutor() as executor:
                file_urls = list(executor.map(self._upload_file, validated))

        payload = self._build_payload(query, model, file_urls)
        self._http.init_search(query)

        if stream:
            self._stream_generator = self._stream(payload)
        else:
            self._complete(payload)

    def _reset_response_state(self) -> None:
        self._title = None
        self._answer = None
        self._chunks = []
        self._search_results = []
        self._raw_data = {}
        self._stream_generator = None

    def _validate_files(self, files: list[FileInput] | None) -> list[_FileInfo]:
        if not files:
            return []

        if len(files) > MAX_FILES:
            raise FileValidationError(
                repr(files[0]),
                f"Too many files: {len(files)}. Maximum allowed is {MAX_FILES}.",
            )

        result: list[_FileInfo] = []
        seen_paths: set[str] = set()

        for item in files:
            match item:
                case bytes() as data:
                    filename = "file"
                    mimetype = "application/octet-stream"
                    size = len(data)

                    if size == 0:
                        raise FileValidationError("<bytes>", "Bytes data is empty")
                    if size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            "<bytes>",
                            f"Data exceeds 50MB limit: {size / (1024 * 1024):.1f}MB",
                        )

                    result.append(_FileInfo(filename=filename, size=size, mimetype=mimetype, is_image=False, data=data))

                case (bytes() as data, str() as filename):
                    guessed, _ = guess_type(filename)
                    mimetype = guessed or "application/octet-stream"
                    size = len(data)

                    if size == 0:
                        raise FileValidationError(filename, "Bytes data is empty")
                    if size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            filename,
                            f"Data exceeds 50MB limit: {size / (1024 * 1024):.1f}MB",
                        )

                    result.append(
                        _FileInfo(
                            filename=filename,
                            size=size,
                            mimetype=mimetype,
                            is_image=mimetype.startswith("image/"),
                            data=data,
                        )
                    )

                case (bytes() as data, str() as filename, str() as mimetype):
                    size = len(data)

                    if size == 0:
                        raise FileValidationError(filename, "Bytes data is empty")
                    if size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            filename,
                            f"Data exceeds 50MB limit: {size / (1024 * 1024):.1f}MB",
                        )

                    result.append(
                        _FileInfo(
                            filename=filename,
                            size=size,
                            mimetype=mimetype,
                            is_image=mimetype.startswith("image/"),
                            data=data,
                        )
                    )

                case tuple():
                    raise FileValidationError(
                        repr(item),
                        "Tuple must have 2 or 3 elements: (bytes, filename[, mimetype])",
                    )

                case str() | PathLike() as path_input:
                    path = Path(path_input).resolve()
                    posix = path.as_posix()

                    if posix in seen_paths:
                        continue

                    seen_paths.add(posix)

                    if not path.exists():
                        raise FileValidationError(posix, "File not found")
                    if not path.is_file():
                        raise FileValidationError(posix, "Path is not a file")

                    try:
                        file_size = path.stat().st_size
                    except (FileNotFoundError, PermissionError) as error:
                        raise FileValidationError(posix, f"Cannot access file: {error}") from error
                    except OSError as error:
                        raise FileValidationError(posix, f"File system error: {error}") from error

                    if file_size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            posix,
                            f"File exceeds 50MB limit: {file_size / (1024 * 1024):.1f}MB",
                        )
                    if file_size == 0:
                        raise FileValidationError(posix, "File is empty")

                    guessed, _ = guess_type(posix)
                    mimetype = guessed or "application/octet-stream"

                    result.append(
                        _FileInfo(
                            filename=path.name,
                            size=file_size,
                            mimetype=mimetype,
                            is_image=mimetype.startswith("image/"),
                            path=posix,
                        )
                    )

                case _:
                    raise FileValidationError(repr(item), "Unsupported file input type")

        return result

    def _upload_file(self, file_info: _FileInfo) -> str:
        file_uuid = str(uuid4())
        display_name = file_info.filename

        json_data = {
            "files": {
                file_uuid: {
                    "filename": display_name,
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
            result = response_data.get("results", {}).get(file_uuid, {})

            s3_bucket_url = result.get("s3_bucket_url")
            s3_object_url = result.get("s3_object_url")
            fields = result.get("fields", {})

            if not s3_object_url:
                raise FileUploadError(display_name, "No upload URL returned")
            if not s3_bucket_url or not fields:
                raise FileUploadError(display_name, "Missing S3 upload credentials")

            file_content = file_info.data if file_info.data is not None else Path(str(file_info.path)).read_bytes()

            mime = CurlMime()

            for field_name, field_value in fields.items():
                mime.addpart(name=field_name, data=field_value)

            mime.addpart(
                name="file",
                content_type=file_info.mimetype,
                filename=display_name,
                data=file_content,
            )

            with Session() as s3_session:
                upload_response = s3_session.post(s3_bucket_url, multipart=mime)

            mime.close()

            if upload_response.status_code not in (200, 201, 204):
                raise FileUploadError(
                    display_name,
                    f"S3 upload failed with status {upload_response.status_code}: {upload_response.text}",
                )

        except FileUploadError:
            raise
        except Exception as error:
            raise FileUploadError(display_name, str(error)) from error

        return s3_object_url

    def _build_payload(
        self,
        query: str,
        model: Model,
        file_urls: list[str],
    ) -> dict[str, Any]:
        cfg = self._config

        _source_map = {
            "web": "web",
            "academic": "scholar",
            "social": "social",
            "finance": "edgar",
            "all": "web",
        }
        _search_map = {
            "web": "internet",
            "writing": "writing",
        }
        _time_map = {
            "all": "",
            "day": "DAY",
            "week": "WEEK",
            "month": "MONTH",
            "year": "YEAR",
        }

        raw_sources = cfg.source_focus if isinstance(cfg.source_focus, list) else [cfg.source_focus]
        sources = [_source_map.get(s, "web") for s in raw_sources]

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
            "search_focus": _search_map.get(cfg.search_focus, "internet"),
            "search_recency_filter": _time_map.get(cfg.time_range, "") or None,
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
        if not text or self._citation_mode == "default":
            return text

        def replacer(m: Match[str]) -> str:
            num = m.group(1)

            if not num.isdigit():
                return m.group(0)

            if self._citation_mode == "clean":
                return ""

            idx = int(num) - 1

            if 0 <= idx < len(self._search_results):
                url = self._search_results[idx].url or ""

                if self._citation_mode == "markdown" and url:
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

        if "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]
        if "read_write_token" in data:
            self._read_write_token = data["read_write_token"]
        if data.get("thread_title"):
            self._title = data["thread_title"]
        if "text" not in data and "blocks" not in data:
            return
        if data.get("status") == "FAILED":
            raise ResponseParsingError(
                f"Query processing failed: {data.get('text', 'Unknown error')}",
                raw_data=str(data),
            )

        try:
            json_data = loads(data["text"])
        except KeyError as error:
            raise ValueError("Missing 'text' field in data") from error
        except JSONDecodeError:
            json_data = data.copy()
            json_data["answer"] = data.get("text")

        answer_data: dict[str, Any] = {}

        if isinstance(json_data, list):
            for item in json_data:
                step_type = item.get("step_type")

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

                    title = data.get("thread_title") or answer_data.get("thread_title")
                    self._update_state(title, answer_data)

                    break

        elif isinstance(json_data, dict):
            title = data.get("thread_title") or json_data.get("thread_title")
            self._update_state(title, json_data)

        else:
            raise ResponseParsingError(
                "Unexpected JSON structure in 'text' field",
                raw_data=str(json_data),
            )

    def _extract_clarifying_questions(self, item: dict[str, Any]) -> list[str]:
        """Extract clarifying questions from a RESEARCH_CLARIFYING_QUESTIONS step."""

        questions: list[str] = []
        content = item.get("content", {})

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
        if title is not None:
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
