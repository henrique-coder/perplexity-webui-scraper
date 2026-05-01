"""File validation and upload logic for Perplexity prompt attachments.

``_FileInfo`` is an internal model describing a single file ready for upload.
``validate_files()`` normalises all accepted ``FileInput`` forms into a list
of ``_FileInfo`` objects.  ``upload_file()`` performs the two-phase S3
multipart upload and returns the public object URL.
"""

from __future__ import annotations

from mimetypes import guess_type
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from curl_cffi import CurlMime
from curl_cffi.requests import Session
from pydantic import BaseModel, ConfigDict

from perplexity_webui_scraper._internal.constants import (
    ENDPOINT_UPLOAD,
    MAX_FILE_SIZE,
    MAX_FILES,
)
from perplexity_webui_scraper._internal.exceptions import (
    FileUploadError,
    FileValidationError,
)


if TYPE_CHECKING:
    from perplexity_webui_scraper._internal.types import FileInput
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


def validate_files(files: list[FileInput] | None) -> list[_FileInfo]:
    """Validate and normalise a list of ``FileInput`` values.

    Accepts all forms of :attr:`~perplexity_webui_scraper._internal.types.FileInput`
    and returns a list of :class:`_FileInfo` objects ready for upload.

    Duplicate paths are silently de-duplicated.  Empty files and files
    exceeding the size limit are rejected immediately.

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
            repr(files[0]),
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
                _check_bytes_size(data, filename)
                guessed, _ = guess_type(filename)
                mimetype = guessed or "application/octet-stream"
                result.append(
                    _FileInfo(
                        filename=filename,
                        mimetype=mimetype,
                        size=len(data),
                        is_image=mimetype.startswith("image/"),
                        data=data,
                    )
                )

            case (bytes() as data, str() as filename, str() as mimetype):
                _check_bytes_size(data, filename)
                result.append(
                    _FileInfo(
                        filename=filename,
                        mimetype=mimetype,
                        size=len(data),
                        is_image=mimetype.startswith("image/"),
                        data=data,
                    )
                )

            case tuple():
                raise FileValidationError(
                    repr(item),
                    "Tuple must have 2 or 3 elements: (bytes, filename[, mimetype])",
                )

            case str() | Path() as path_input:  # type: ignore[misc]
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
                        f"File exceeds 50 MB limit: {file_size / (1024 * 1024):.1f} MB",
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
                raise FileValidationError(repr(item), "Unsupported file input type")

    return result


def upload_file(file_info: _FileInfo, http: HTTPClient) -> str:
    """Upload a single file to Perplexity's S3 bucket in two phases.

    Phase 1: Request a pre-signed S3 upload URL from Perplexity.
    Phase 2: POST the file data to S3 as a multipart form using
    ``CurlMime`` (curl's native multipart, avoiding Python's multipart encoder).

    Args:
        file_info: The validated :class:`_FileInfo` descriptor.
        http: Active :class:`~perplexity_webui_scraper.http.client.HTTPClient`.

    Returns:
        The public S3 object URL for use as an attachment reference.

    Raises:
        FileUploadError: If the upload fails at either phase.
    """
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

    try:
        response = http.post(ENDPOINT_UPLOAD, json=request_body)
        response_data = response.json()
        result = response_data.get("results", {}).get(file_uuid, {})

        s3_bucket_url: str | None = result.get("s3_bucket_url")
        s3_object_url: str | None = result.get("s3_object_url")
        fields: dict[str, str] = result.get("fields", {})

        if not s3_object_url:
            raise FileUploadError(display_name, "No upload URL returned")
        if not s3_bucket_url or not fields:
            raise FileUploadError(display_name, "Missing S3 upload credentials")

        file_content = file_info.data if file_info.data is not None else Path(str(file_info.path)).read_bytes()

        mime = CurlMime()

        for field_name, field_value in fields.items():
            mime.addpart(name=field_name, data=field_value.encode("utf-8"))

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


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


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
            f"Data exceeds 50 MB limit: {size / (1024 * 1024):.1f} MB",
        )
