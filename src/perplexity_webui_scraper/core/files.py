"""File validation and upload logic for Perplexity prompt attachments.

``_FileInfo`` is an internal model describing a single file ready for upload.
``validate_files()`` normalizes supported path and byte inputs into descriptors.
``upload_file()`` performs the two-stage multipart upload and returns its URL.
"""

from __future__ import annotations

from ipaddress import ip_address
from mimetypes import guess_type
from os import PathLike, fspath
from pathlib import Path
from re import fullmatch
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from uuid import uuid4

from curl_cffi import CurlMime
from curl_cffi.requests import Session
from orjson import loads
from pydantic import BaseModel, ConfigDict

from perplexity_webui_scraper._internal.constants import (
    API_SOURCE,
    API_VERSION,
    ENDPOINT_UPLOAD,
    MAX_FILE_SIZE,
    MAX_FILES,
)
from perplexity_webui_scraper._internal.exceptions import (
    FileUploadError,
    FileValidationError,
)


if TYPE_CHECKING:
    from perplexity_webui_scraper.http.client import HTTPClient


class _FileInfo(BaseModel):
    """Internal upload descriptor created by ``validate_files()``.

    Exactly one of ``path`` or ``data`` is set; never both, never neither.

    Attributes:
        filename: Display name sent to Perplexity (used as the S3 object name).
        mimetype: MIME type string (e.g. ``"image/jpeg"``).
        size: File size in bytes.
        is_image: ``True`` when ``mimetype`` starts with ``"image/"``.
        path: Absolute POSIX filesystem path.  Set for path-based inputs;
            bytes are read lazily at upload time.
        data: In-memory bytes.  Set for bytes-based inputs.
    """

    model_config = ConfigDict(frozen=True)

    filename: str
    mimetype: str
    size: int
    is_image: bool
    path: str | None = None
    data: bytes | None = None


_S3_HOST_PATTERN = (
    r"^(?P<bucket>[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)"
    r"\.s3(?:[.-](?P<region>[a-z]{2}(?:-[a-z]+)+-[1-9][0-9]?))?\.amazonaws\.com$"
)
_MIME_TYPE_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9!#$&^_.+-]{0,63}/[a-zA-Z0-9][a-zA-Z0-9!#$&^_.+-]{0,63}"


def _is_allowed_s3_host(hostname: str | None) -> bool:
    """Accept official virtual-hosted AWS S3 bucket endpoints used by WebUI uploads."""
    if not hostname or not hostname.isascii() or len(hostname) > 253 or hostname.endswith("."):
        return False

    if any(character.isspace() or character == "\\" for character in hostname):
        return False

    match = fullmatch(_S3_HOST_PATTERN, hostname.lower())

    if match is None:
        return False

    bucket = match.group("bucket")

    if not 3 <= len(bucket) <= 63:
        return False

    try:
        ip_address(bucket)
    except ValueError:
        return True

    return False


def _public_upload_error(file_path: str, reason: str) -> FileUploadError:
    """Construct an upload error without retaining exception frame locals."""
    exception = FileUploadError(file_path, reason)
    exception.clear_previous_exception_context()
    return exception


def validate_files(files: list[object] | None) -> list[_FileInfo]:
    """Validate and normalize a list of upload inputs.

    Accepts path, bytes, ``(bytes, filename)``, and ``(bytes, filename, mimetype)`` inputs.
    Returns normalized descriptors.

    Duplicate paths are de-duplicated. Empty and oversized inputs are rejected.

    Args:
        files: Raw file inputs from the caller.  ``None`` returns an
            empty list.

    Returns:
        List of validated :class:`_FileInfo` descriptors.

    Raises:
        FileValidationError: If any file fails validation.
    """
    if not files:
        return []

    if len(files) > MAX_FILES:
        raise FileValidationError(
            "<files>",
            f"Too many files: {len(files)}. Maximum allowed is {MAX_FILES}.",
        )

    result: list[_FileInfo] = []
    seen_paths: set[str] = set()

    for item in files:
        match item:
            case bytes() as data:
                _check_bytes_size(data, "<bytes>")
                result.append(
                    _FileInfo(
                        filename="file",
                        mimetype="application/octet-stream",
                        size=len(data),
                        is_image=False,
                        data=data,
                    )
                )

            case (bytes() as data, str() as filename):
                safe_name = _validate_filename(filename)
                _check_bytes_size(data, safe_name)
                guessed, _ = guess_type(safe_name)
                mimetype = guessed or "application/octet-stream"
                result.append(
                    _FileInfo(
                        filename=safe_name,
                        mimetype=mimetype,
                        size=len(data),
                        is_image=mimetype.startswith("image/"),
                        data=data,
                    )
                )

            case (bytes() as data, str() as filename, str() as mimetype):
                safe_name = _validate_filename(filename)
                _check_bytes_size(data, safe_name)
                safe_mimetype = _validate_mimetype(mimetype, safe_name)
                result.append(
                    _FileInfo(
                        filename=safe_name,
                        mimetype=safe_mimetype,
                        size=len(data),
                        is_image=safe_mimetype.startswith("image/"),
                        data=data,
                    )
                )

            case tuple():
                raise FileValidationError(
                    "<tuple>",
                    "Tuple must have 2 or 3 elements: (bytes, filename[, mimetype])",
                )

            case str() | PathLike() as path_input:
                path = Path(fspath(path_input)).resolve()
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
                except (FileNotFoundError, PermissionError):
                    raise FileValidationError(posix, "Cannot access file") from None
                except OSError:
                    raise FileValidationError(posix, "File system error") from None

                if file_size > MAX_FILE_SIZE:
                    raise FileValidationError(
                        posix,
                        f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit: {file_size / (1024 * 1024):.1f} MB",
                    )

                if file_size == 0:
                    raise FileValidationError(posix, "File is empty")

                guessed, _ = guess_type(posix)
                mimetype = guessed or "application/octet-stream"
                result.append(
                    _FileInfo(
                        filename=path.name,
                        mimetype=mimetype,
                        size=file_size,
                        is_image=mimetype.startswith("image/"),
                        path=posix,
                    )
                )

            case _:
                raise FileValidationError(type(item).__name__, "Unsupported file input type")

    return result


def _has_unsafe_url_chars(value: str) -> bool:
    """Reject backslashes and ASCII control/whitespace characters in URLs."""
    return any(ord(character) <= 0x20 or ord(character) == 0x7F or character == "\\" for character in value)


def _upload_file_impl(file_info: _FileInfo, http: HTTPClient) -> str:
    file_uuid = str(uuid4())
    display_name = file_info.filename

    request_body: dict[str, Any] = {
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

    safe_object_url: str | None = None

    response = http.post(
        ENDPOINT_UPLOAD,
        json=request_body,
        params={"version": API_VERSION, "source": API_SOURCE},
    )
    response_data = loads(response.content)
    result = response_data.get("results", {}).get(file_uuid, {})

    s3_bucket_url: str | None = result.get("s3_bucket_url")
    s3_object_url = result.get("s3_object_url")
    fields: dict[str, str] = result.get("fields", {})

    if not s3_object_url:
        raise FileUploadError(display_name, "No upload URL returned")

    safe_object_url = str(s3_object_url)

    if not s3_bucket_url or not fields:
        raise FileUploadError(display_name, "Missing S3 upload credentials")

    if _has_unsafe_url_chars(s3_bucket_url) or _has_unsafe_url_chars(safe_object_url):
        raise FileUploadError(display_name, "Invalid pre-signed S3 upload URL")

    upload_url = urlsplit(s3_bucket_url)
    object_url = urlsplit(safe_object_url)

    try:
        upload_port = upload_url.port
        object_port = object_url.port
    except ValueError:
        raise FileUploadError(display_name, "Invalid pre-signed S3 upload URL") from None

    if (
        upload_url.scheme != "https"
        or not upload_url.netloc
        or upload_url.query
        or upload_url.fragment
        or upload_port not in (None, 443)
        or object_url.scheme != "https"
        or not object_url.netloc
        or object_port not in (None, 443)
        or upload_port != object_port
        or upload_url.hostname != object_url.hostname
        or upload_url.username is not None
        or upload_url.password is not None
        or object_url.username is not None
        or object_url.password is not None
        or object_url.query
        or object_url.fragment
        or not _is_allowed_s3_host(upload_url.hostname)
        or not _is_allowed_s3_host(object_url.hostname)
    ):
        raise FileUploadError(display_name, "Invalid pre-signed S3 upload URL")

    if file_info.data is not None:
        file_content = file_info.data
    else:
        with Path(str(file_info.path)).open("rb") as handle:
            file_content = handle.read(MAX_FILE_SIZE + 1)

        if not file_content or len(file_content) > MAX_FILE_SIZE:
            raise FileUploadError(display_name, "File size is invalid or exceeds limit")

    mime = CurlMime()

    try:
        for field_name, field_value in fields.items():
            mime.addpart(name=field_name, data=field_value.encode("utf-8"))

        mime.addpart(
            name="file",
            content_type=file_info.mimetype,
            filename=display_name,
            data=file_content,
        )

        with Session() as s3_session:
            upload_response = s3_session.post(s3_bucket_url, multipart=mime, allow_redirects=False)
    finally:
        mime.close()

    if upload_response.status_code not in (200, 201, 204):
        raise FileUploadError(
            display_name,
            f"S3 upload failed with status {upload_response.status_code}.",
        )

    return safe_object_url


def upload_file(file_info: _FileInfo, http: HTTPClient) -> str:
    """Upload an attachment while suppressing upstream details in failures."""
    failure_reason: str | None = None

    try:
        return _upload_file_impl(file_info, http)
    except FileUploadError as error:
        failure_reason = error.message.removeprefix(f"Upload failed for '{file_info.filename}': ")
    except Exception:
        failure_reason = "Upload request failed; upstream diagnostics were suppressed."

    raise _public_upload_error(file_info.filename, failure_reason)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_filename(filename: str) -> str:
    """Reject empty filenames, path traversal separators, and control characters."""
    if (
        not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in filename)
    ):
        raise FileValidationError("<filename>", "Invalid filename")

    return filename


def _validate_mimetype(mimetype: str, label: str) -> str:
    """Validate an explicit ``type/subtype`` MIME header token."""
    if fullmatch(_MIME_TYPE_PATTERN, mimetype) is None:
        raise FileValidationError(label, "Invalid MIME type")

    return mimetype


def _check_bytes_size(data: bytes, label: str) -> None:
    """Validate that bytes data is non-empty and within the size limit.

    Args:
        data: The raw bytes to check.
        label: Display name used in the error message.

    Raises:
        FileValidationError: If the data is empty or exceeds the size limit.
    """
    size = len(data)

    if size == 0:
        raise FileValidationError(label, "Bytes data is empty")

    if size > MAX_FILE_SIZE:
        raise FileValidationError(
            label,
            f"Data exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit: {size / (1024 * 1024):.1f} MB",
        )
