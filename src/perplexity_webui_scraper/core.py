from mimetypes import guess_type
from os import PathLike
from pathlib import Path
from re import match
from typing import Any
from uuid import uuid4

from curl_cffi.requests import Session
from orjson import loads

from .models import Model, Models
from .utils import (
    CitationMode,
    ModeValue,
    PromptCall,
    SearchFocus,
    SearchResultItem,
    SourceFocus,
    TimeRange,
    format_citations,
)


class Perplexity:
    """Client for interacting with Perplexity AI WebUI"""

    def __init__(self, session_token: str) -> None:
        """
        Initialize the Perplexity client.

        Args:
            session_token: The session token (`__Secure-next-auth.session-token` cookie) to use for authentication.

        Raises:
            ValueError: If session_token is empty or None
        """

        if not session_token or not session_token.strip():
            raise ValueError("session_token cannot be empty or None")

        self._headers: dict[str, str] = {
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json",
            "Referer": "https://www.perplexity.ai/",
            "Origin": "https://www.perplexity.ai",
        }
        self._cookies: dict[str, str] = {"__Secure-next-auth.session-token": session_token}
        self._client: Session = Session(headers=self._headers, cookies=self._cookies, timeout=1800, impersonate="chrome")
        self._citation_mode: CitationMode
        self.reset_response_data()

        self._max_files: int = 30
        self._max_file_size: int = 50 * 1024 * 1024

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

    def validate_files(self, files: str | PathLike | list[str | PathLike] | None) -> list[dict[str, str | int | bool]]:
        if files is None:
            files = []
        elif isinstance(files, (str, PathLike)):
            files = [Path(files).resolve().as_posix()] if files else []
        elif isinstance(files, list):
            files = list(
                dict.fromkeys(Path(item).resolve().as_posix() for item in files if item and isinstance(item, (str, PathLike)))
            )
        else:
            files = []

        if len(files) > self._max_files:
            raise ValueError(f"Too many files: {len(files)}. Maximum allowed is {self._max_files} files.")

        result = []

        for file_path in files:
            try:
                path_obj = Path(file_path)

                if not path_obj.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                if not path_obj.is_file():
                    raise ValueError(f"Path is not a file: {file_path}")

                file_size = path_obj.stat().st_size

                if file_size > self._max_file_size:
                    size_mb = file_size / (1024 * 1024)

                    raise ValueError(f"File '{file_path}' exceeds 50MB limit: {size_mb:.1f}MB")

                if file_size == 0:
                    raise ValueError(f"File is empty: {file_path}")

                mimetype, _ = guess_type(file_path)
                mimetype = mimetype or "application/octet-stream"

                result.append({
                    "path": file_path,
                    "size": file_size,
                    "mimetype": mimetype,
                    "is_image": mimetype.startswith("image/"),
                })
            except (FileNotFoundError, PermissionError) as e:
                raise ValueError(f"Cannot access file '{file_path}': {str(e)}") from e
            except OSError as e:
                raise ValueError(f"File system error for '{file_path}': {str(e)}") from e
            except Exception as e:
                raise ValueError(f"Unexpected error processing file '{file_path}': {str(e)}") from e

        return result

    def upload_file(self, file_data: dict[str, str | int | bool]) -> str:
        try:
            file_uuid = str(uuid4())

            json_data = {
                "files": {
                    file_uuid: {
                        "filename": file_data["path"],
                        "content_type": file_data["mimetype"],
                        "source": "default",
                        "file_size": file_data["size"],
                        "force_image": file_data["is_image"],
                    }
                }
            }

            response = self._client.post(
                "https://www.perplexity.ai/rest/uploads/batch_create_upload_urls",
                json=json_data,
            )

            response.raise_for_status()

            response_data = response.json()
            upload_url = response_data.get("results", {}).get(file_uuid, {}).get("s3_object_url")

            if not upload_url:
                raise ValueError(f"Upload failed for '{file_data['path']}': No upload URL returned from server")

            return upload_url
        except Exception as e:
            if hasattr(e, "response") and hasattr(e.response, "status_code"):
                status_code = e.response.status_code

                if status_code == 403:
                    raise ValueError(
                        f"Upload failed for '{file_data['path']}': Access forbidden (403). "
                        "Your session token may be invalid or expired. Please obtain a new session token."
                    ) from e
                elif status_code == 429:
                    raise ValueError(
                        f"Upload failed for '{file_data['path']}': Rate limit exceeded (429). "
                        "Please wait a moment before trying again."
                    ) from e
                else:
                    raise ValueError(f"Upload failed for '{file_data['path']}': HTTP {status_code} - {str(e)}") from e
            else:
                raise ValueError(f"Upload failed for '{file_data['path']}': {str(e)}") from e

    def _prepare_json_data(
        self,
        query: str,
        files: str | PathLike | list[str | PathLike] | None,
        model: Model,
        save_to_library: bool,
        search_focus: ModeValue,
        source_focus: ModeValue | list[ModeValue],
        time_range: ModeValue,
        language: str,
        timezone: str | None,
        coordinates: tuple[float, float] | None,
    ) -> dict[str, Any]:
        validated_files = self.validate_files(files)
        file_urls = []

        if validated_files:
            for file_data in validated_files:
                try:
                    upload_url = self.upload_file(file_data)
                    file_urls.append(upload_url)
                except ValueError as e:
                    raise ValueError(f"File upload error: {str(e)}") from e

        sources = [source_focus.value] if not isinstance(source_focus, list) else [s.value for s in source_focus]

        return {
            "params": {
                "attachments": file_urls,
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
                "model_preference": model.identifier,
                "mode": model.mode,
                "search_focus": search_focus.value,
                "search_recency_filter": time_range.value if time_range.value else None,
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

    def prompt(
        self,
        query: str,
        files: str | PathLike | list[str | PathLike] | None = None,
        citation_mode: ModeValue = CitationMode.DEFAULT,
        model: Model = Models.BEST,
        save_to_library: bool = False,
        search_focus: ModeValue = SearchFocus.WEB,
        source_focus: ModeValue | list[ModeValue] = SourceFocus.WEB,
        time_range: ModeValue = TimeRange.ALL,
        language: str = "en-US",
        timezone: str | None = None,
        coordinates: tuple[float, float] | None = None,
    ) -> PromptCall:
        """
        Configure a prompt to send to Perplexity AI.

        Args:
            query: The question or prompt to send.
            files: File path(s) to attach. Single path or list. Max 30 files, 50MB each. Defaults to None.
            citation_mode: Citation format. Use CitationMode.DEFAULT, .MARKDOWN, or .CLEAN. Defaults to CitationMode.DEFAULT.
            model: AI model to use. Defaults to Models.BEST.
            save_to_library: Whether to save this query to your library. Defaults to False.
            search_focus: Search focus. Use SearchFocus.WEB or .WRITING. Defaults to SearchFocus.WEB.
            source_focus: Source type(s). Use SourceFocus.WEB, .ACADEMIC, .SOCIAL, or .FINANCE. Defaults to SourceFocus.WEB.
            time_range: Time filter. Use TimeRange.ALL, .TODAY, .LAST_WEEK, .LAST_MONTH, or .LAST_YEAR. Defaults to TimeRange.ALL.
            language: Language code (e.g., "en-US"). Defaults to "en-US".
            timezone: Timezone code (e.g., "America/New_York"). Defaults to None.
            coordinates: Location coordinates (latitude, longitude). Defaults to None.

        Returns:
            PromptCall object with .run(stream=False) method.

        Examples:
            # Blocking mode (waits for complete response)
            response = client.prompt("What is AI?", citation_mode=CitationMode.MARKDOWN).run()
            print(response.answer)

            # Streaming mode (real-time updates)
            for chunk in client.prompt("What is AI?").run(stream=True):
                print(chunk.answer, end="", flush=True)
        """

        self._citation_mode = citation_mode

        json_data = self._prepare_json_data(
            query,
            files,
            model,
            save_to_library,
            search_focus,
            source_focus,
            time_range,
            language,
            timezone,
            coordinates,
        )

        return PromptCall(self, json_data)
