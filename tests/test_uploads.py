from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING, Any, cast

from orjson import dumps
from pytest import MonkeyPatch, mark, raises

from perplexity_webui_scraper._internal.constants import API_SOURCE, API_VERSION
from perplexity_webui_scraper._internal.exceptions import FileUploadError, FileValidationError
from perplexity_webui_scraper.core.files import _FileInfo, upload_file, validate_files


if TYPE_CHECKING:
    from pathlib import Path

    from perplexity_webui_scraper.http.client import HTTPClient


class _RequestResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self.content = dumps(data)


class _UploadResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")


class _Mime:
    def __init__(self) -> None:
        self.parts: list[dict[str, Any]] = []
        self.closed = False

    def addpart(self, **kwargs: Any) -> None:
        self.parts.append(kwargs)

    def close(self) -> None:
        self.closed = True


class _S3Session:
    def __init__(self, response: _UploadResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __enter__(self) -> _S3Session:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, *, multipart: _Mime, allow_redirects: bool = True) -> _UploadResponse:
        self.calls.append({"url": url, "multipart": multipart, "allow_redirects": allow_redirects})

        if self.error is not None:
            raise self.error

        assert self.response is not None
        return self.response


class _HTTP:
    def __init__(self, response: _RequestResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(self, endpoint: str, *, json: dict[str, Any], params: dict[str, Any] | None = None) -> _RequestResponse:
        self.calls.append({"endpoint": endpoint, "json": json, "params": params})
        return self.response


def test_upload_file_uses_presigned_s3_fields_without_account_headers(monkeypatch: MonkeyPatch) -> None:
    fields = {
        "key": "uploads/file.jpg",
        "Content-Type": "image/jpeg",
        "X-Amz-Security-Token": "temporary-upload-token",
        "policy": "signed-policy",
    }
    request_response = _RequestResponse(
        {
            "results": {
                "file-id": {
                    "s3_bucket_url": "https://bucket.s3.amazonaws.com/",
                    "s3_object_url": "https://bucket.s3.amazonaws.com/uploads/file.jpg",
                    "fields": fields,
                }
            }
        }
    )
    http = _HTTP(request_response)
    s3_session = _S3Session(_UploadResponse(204))
    mime = _Mime()
    monkeypatch.setattr("perplexity_webui_scraper.core.files.uuid4", lambda: "file-id")
    monkeypatch.setattr("perplexity_webui_scraper.core.files.CurlMime", lambda: mime)
    monkeypatch.setattr("perplexity_webui_scraper.core.files.Session", lambda: s3_session)
    file_info = _FileInfo(filename="file.jpg", mimetype="image/jpeg", size=3, is_image=True, data=b"jpg")

    result = upload_file(file_info, cast("HTTPClient", http))

    assert result == "https://bucket.s3.amazonaws.com/uploads/file.jpg"
    assert http.calls[0]["json"]["files"]["file-id"]["force_image"] is True
    assert http.calls[0]["params"] == {"version": API_VERSION, "source": API_SOURCE}
    assert mime.parts[-1]["data"] == b"jpg"
    assert [(part["name"], part.get("content_type")) for part in mime.parts] == [
        ("key", None),
        ("Content-Type", None),
        ("X-Amz-Security-Token", None),
        ("policy", None),
        ("file", "image/jpeg"),
    ]
    assert mime.closed
    assert s3_session.calls[0]["url"] == "https://bucket.s3.amazonaws.com/"
    assert s3_session.calls[0]["allow_redirects"] is False


def test_upload_file_reports_presigned_post_failure(monkeypatch: MonkeyPatch) -> None:
    fields = {"key": "uploads/file.jpg", "policy": "signed-policy"}
    response = _RequestResponse(
        {
            "results": {
                "file-id": {
                    "s3_bucket_url": "https://bucket.s3.amazonaws.com/",
                    "s3_object_url": "https://bucket.s3.amazonaws.com/uploads/file.jpg",
                    "fields": fields,
                }
            }
        }
    )
    http = _HTTP(response)
    sensitive_response_text = "synthetic-upstream-detail-must-not-leak"
    s3_session = _S3Session(_UploadResponse(403, sensitive_response_text))
    monkeypatch.setattr("perplexity_webui_scraper.core.files.uuid4", lambda: "file-id")
    monkeypatch.setattr("perplexity_webui_scraper.core.files.CurlMime", _Mime)
    monkeypatch.setattr("perplexity_webui_scraper.core.files.Session", lambda: s3_session)
    file_info = _FileInfo(filename="file.jpg", mimetype="image/jpeg", size=3, is_image=True, data=b"jpg")

    with raises(FileUploadError, match="S3 upload failed with status 403") as exc_info:
        upload_file(file_info, cast("HTTPClient", http))

    assert sensitive_response_text not in str(exc_info.value)


def test_upload_file_sanitizes_upstream_exception_and_cause(monkeypatch: MonkeyPatch) -> None:
    fields = {"key": "uploads/file.jpg", "policy": "signed-policy"}
    response = _RequestResponse(
        {
            "results": {
                "file-id": {
                    "s3_bucket_url": "https://bucket.s3.amazonaws.com/",
                    "s3_object_url": "https://bucket.s3.amazonaws.com/uploads/file.jpg",
                    "fields": fields,
                }
            }
        }
    )
    http = _HTTP(response)
    sensitive_detail = "synthetic-signed-url-marker"
    s3_session = _S3Session(error=RuntimeError(sensitive_detail))
    monkeypatch.setattr("perplexity_webui_scraper.core.files.uuid4", lambda: "file-id")
    monkeypatch.setattr("perplexity_webui_scraper.core.files.CurlMime", _Mime)
    monkeypatch.setattr("perplexity_webui_scraper.core.files.Session", lambda: s3_session)
    file_info = _FileInfo(filename="file.jpg", mimetype="image/jpeg", size=3, is_image=True, data=b"jpg")

    with raises(FileUploadError) as exc_info:
        upload_file(file_info, cast("HTTPClient", http))

    assert sensitive_detail not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert sensitive_detail not in repr(exc_info.value)


@mark.parametrize(
    "host",
    [
        "bucket.s3.amazonaws.com",
        "bucket.s3.us-east-1.amazonaws.com",
        "bucket.s3.us-west-2.amazonaws.com",
        "my-bucket.s3.eu-central-1.amazonaws.com",
        "bucket.s3-eu-west-1.amazonaws.com",
        "bucket.s3.us-gov-west-1.amazonaws.com",
    ],
)
def test_upload_file_accepts_documented_regional_s3_hosts(monkeypatch: MonkeyPatch, host: str) -> None:
    response = _RequestResponse(
        {
            "results": {
                "file-id": {
                    "s3_bucket_url": f"https://{host}/",
                    "s3_object_url": f"https://{host}/uploads/file.jpg",
                    "fields": {"key": "uploads/file.jpg"},
                }
            }
        }
    )
    http = _HTTP(response)
    s3_session = _S3Session(_UploadResponse(204))
    monkeypatch.setattr("perplexity_webui_scraper.core.files.uuid4", lambda: "file-id")
    monkeypatch.setattr("perplexity_webui_scraper.core.files.CurlMime", _Mime)
    monkeypatch.setattr("perplexity_webui_scraper.core.files.Session", lambda: s3_session)
    file_info = _FileInfo(filename="file.jpg", mimetype="image/jpeg", size=3, is_image=True, data=b"jpg")

    result = upload_file(file_info, cast("HTTPClient", http))

    assert result == f"https://{host}/uploads/file.jpg"
    assert s3_session.calls[0]["url"] == f"https://{host}/"


@mark.parametrize(
    ("bucket_url", "object_url"),
    [
        ("http://bucket.s3.amazonaws.com/", "http://bucket.s3.amazonaws.com/key"),
        ("https://bucket.s3.amazonaws.com/", "https://attacker.example/key"),
        ("https://user@bucket.s3.amazonaws.com/", "https://bucket.s3.amazonaws.com/key"),
        ("https://bucket.s3.amazonaws.com/", "https://user@bucket.s3.amazonaws.com/key"),
        ("https://bucket.s3.amazonaws.com/", "https://bucket.s3.amazonaws.com/key?signature=secret"),
        ("https://attacker.example/", "https://attacker.example/key"),
        ("https://attacker.com\\.s3.amazonaws.com/", "https://attacker.com\\.s3.amazonaws.com/key"),
        ("https://.s3.amazonaws.com/", "https://.s3.amazonaws.com/key"),
        ("https://..s3.amazonaws.com/", "https://..s3.amazonaws.com/key"),
        ("https://ab.s3.amazonaws.com/", "https://ab.s3.amazonaws.com/key"),
        ("https://127.0.0.1.s3.amazonaws.com/", "https://127.0.0.1.s3.amazonaws.com/key"),
        ("https://bucket.s3.amazonaws.com:8443/", "https://bucket.s3.amazonaws.com:8443/key"),
        ("https://bucket.s3.amazonaws.com:443/", "https://bucket.s3.amazonaws.com/key"),
        ("https://bucket.s3.evil.amazonaws.com/", "https://bucket.s3.evil.amazonaws.com/key"),
        ("https://bucket.s3.amazonaws.com.evil.com/", "https://bucket.s3.amazonaws.com.evil.com/key"),
        ("https://bucket.s3.amazonaws.com./", "https://bucket.s3.amazonaws.com./key"),
        ("https://s3.amazonaws.com/bucket", "https://s3.amazonaws.com/bucket/key"),
    ],
)
def test_upload_file_rejects_untrusted_or_inconsistent_presigned_urls(
    monkeypatch: MonkeyPatch,
    bucket_url: str,
    object_url: str,
) -> None:
    response = _RequestResponse(
        {"results": {"file-id": {"s3_bucket_url": bucket_url, "s3_object_url": object_url, "fields": {"key": "key"}}}}
    )
    http = _HTTP(response)
    s3_session = _S3Session(_UploadResponse(204))
    monkeypatch.setattr("perplexity_webui_scraper.core.files.uuid4", lambda: "file-id")
    monkeypatch.setattr("perplexity_webui_scraper.core.files.Session", lambda: s3_session)
    file_info = _FileInfo(filename="file.jpg", mimetype="image/jpeg", size=3, is_image=True, data=b"jpg")

    with raises(FileUploadError, match="Invalid pre-signed S3 upload URL"):
        upload_file(file_info, cast("HTTPClient", http))

    assert not s3_session.calls


class _CustomPath(PathLike[str]):
    def __init__(self, target: Path) -> None:
        self._target = target

    def __fspath__(self) -> str:
        return str(self._target)


def test_validate_files_accepts_custom_pathlike_and_rejects_bad_tuples_without_leaking_bytes(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    validated = validate_files([_CustomPath(sample)])

    assert len(validated) == 1
    assert validated[0].filename == "sample.txt"

    with raises(FileValidationError, match="Invalid filename"):
        validate_files([(b"data", "../evil.txt")])

    with raises(FileValidationError, match="Invalid MIME type"):
        validate_files([(b"data", "safe.txt", "text/plain\r\nInjected: yes")])

    secret_bytes = b"SECRET_BINARY_PAYLOAD"
    with raises(FileValidationError) as exc_info:
        validate_files([(secret_bytes,)])

    assert "SECRET_BINARY_PAYLOAD" not in str(exc_info.value)
