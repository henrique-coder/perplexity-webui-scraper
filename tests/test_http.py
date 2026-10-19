from __future__ import annotations

from typing import Any, cast
from warnings import catch_warnings, simplefilter

from curl_cffi.utils import CurlCffiWarning
from pydantic import ValidationError
from pytest import raises

from perplexity_webui_scraper.http.client import HTTPClient
from perplexity_webui_scraper.http.resilience import RetryConfig


class _HTTPStatusError(Exception):
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        super().__init__(f"HTTP {response.status_code}")


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.url = "https://www.perplexity.ai/rest/test"
        self.text = "rate limited" if status_code == 429 else "ok"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _HTTPStatusError(self)


class _FakeSession:
    def __init__(self) -> None:
        self.calls = 0
        self.urls: list[str] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        self.calls += 1
        self.urls.append(url)

        return _FakeResponse(200)

    def post(self, url: str, json: dict[str, Any] | None = None, stream: bool = False) -> _FakeResponse:
        self.calls += 1
        self.urls.append(url)

        return _FakeResponse(429 if self.calls == 1 else 200)

    def close(self) -> None:
        return None


def test_http_client_retries_translated_rate_limit_error() -> None:
    client = HTTPClient(
        "token",
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2


def test_http_get_can_skip_rate_limiter() -> None:
    client = HTTPClient(
        "token",
        max_retries=0,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=1,
    )
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)
    client._rate_limiter = cast("Any", None)

    response = client.get("/api/auth/session", rate_limited=False)

    assert response.status_code == 200
    assert fake_session.calls == 1


def test_http_client_rejects_absolute_url_before_sending_session_cookie() -> None:
    client = HTTPClient("token", max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    with raises(ValueError, match="relative paths"):
        client.get("https://attacker.example/collect")

    assert fake_session.calls == 0
    assert fake_session.urls == []


def test_session_cookie_is_marked_secure_without_warning() -> None:
    with catch_warnings(record=True) as recorded:
        simplefilter("always")
        client = HTTPClient("token", requests_per_second=0)

    assert not any(issubclass(item.category, CurlCffiWarning) for item in recorded)
    cookie = next(cookie for cookie in client._session.cookies.jar if cookie.name == "__Secure-next-auth.session-token")
    assert cookie.secure
    client.close()


def test_retry_config_rejects_negative_retries() -> None:
    with raises(ValidationError, match="max_retries cannot be negative"):
        RetryConfig(max_retries=-1)


def test_http_client_rejects_invalid_jitter() -> None:
    with raises(ValueError, match="retry_jitter"):
        HTTPClient("token", retry_jitter=1.1)
