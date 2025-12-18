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
from .exceptions import FileUploadError, FileValidationError
from .http import HTTPClient
from .limits import MAX_FILE_SIZE, MAX_FILES
from .models import Model, Models
from .types import Response, SearchResultItem, _FileInfo


class Perplexity:
    """Web scraper for Perplexity AI conversations."""

    __slots__ = ("_http",)

    def __init__(self, session_token: str, config: ClientConfig | None = None) -> None:
        """Initialize web scraper with session token.

        Args:
            session_token: Perplexity session cookie (__Secure-next-auth.session-token).
            config: Optional HTTP client configuration.

        Raises:
            ValueError: If session_token is empty or whitespace.
        """

        if not session_token or not session_token.strip():
            raise ValueError("session_token cannot be empty")

        cfg = config or ClientConfig()
        self._http = HTTPClient(session_token, timeout=cfg.timeout, impersonate=cfg.impersonate)

    def create_conversation(self, config: ConversationConfig | None = None) -> Conversation:
        """Create a new conversation."""
        return Conversation(self._http, config or ConversationConfig())

    def close(self) -> None:
        """Close the client."""
        self._http.close()

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
        effective_model = model or self._config.model or Models.BEST
        effective_citation = citation_mode if citation_mode is not None else self._config.citation_mode
        self._citation_mode = effective_citation
        self._execute(query, effective_model, files, stream=stream)
        return self

    def _execute(
        self,
        query: str,
        model: Model,
        files: list[str | PathLike] | None,
        stream: bool = False,
    ) -> None:
        """Execute a query."""
        self._reset_response_state()

        # Upload files
        file_urls: list[str] = []
        if files:
            validated = self._validate_files(files)
            file_urls = [self._upload_file(f) for f in validated]

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
            except FileValidationError:
                raise
            except (FileNotFoundError, PermissionError) as e:
                raise FileValidationError(file_path, f"Cannot access file: {e}") from e
            except OSError as e:
                raise FileValidationError(file_path, f"File system error: {e}") from e

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
        except FileUploadError:
            raise
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
        prefix = b"data: " if isinstance(line, bytes) else "data: "
        if (isinstance(line, bytes) and line.startswith(prefix)) or (isinstance(line, str) and line.startswith(prefix)):
            return loads(line[6:])
        return None

    def _process_data(self, data: dict[str, Any]) -> None:
        if self._backend_uuid is None and "backend_uuid" in data:
            self._backend_uuid = data["backend_uuid"]

        if self._read_write_token is None and "read_write_token" in data:
            self._read_write_token = data["read_write_token"]

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
                if item.get("step_type") == "FINAL":
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
            raise ValueError("Unexpected JSON structure in 'text' field")

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
            self._chunks = chunks

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
