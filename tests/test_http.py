from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime
from threading import Thread
from typing import Any, cast
from unittest.mock import Mock, patch
from warnings import catch_warnings, simplefilter

from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import Timeout as CurlTimeout
from curl_cffi.utils import CurlCffiWarning
from loguru import logger
from orjson import dumps, loads
from pydantic import ValidationError
from pytest import mark, raises

from perplexity_webui_scraper._internal.constants import (
    API_SOURCE,
    API_VERSION,
    ENDPOINT_ASK,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_UPLOAD,
    SESSION_COOKIE_PREFIX,
    SESSION_TOKEN_JWE_HEADER,
)
from perplexity_webui_scraper._internal.exceptions import HTTPError, RateLimitError
from perplexity_webui_scraper._internal.logging import log_error
from perplexity_webui_scraper.http.client import HTTPClient
from perplexity_webui_scraper.http.resilience import RetryConfig, retry_with_backoff


_SESSION_CREDENTIAL = (
    f"{SESSION_COOKIE_PREFIX}123e4567-e89b-42d3-a456-426614174000="
    f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
)
_COMPACT_SESSION_TOKEN = "wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw"


class _HTTPStatusError(Exception):
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        super().__init__(f"HTTP {response.status_code}")


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = "https://www.perplexity.ai/rest/test"
        self.request_method: str | None = None
        self.text = "rate limited" if status_code == 429 else "ok"
        self.headers = headers or {}
        self._json_data = json_data or {}
        self.content = dumps(self._json_data)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _HTTPStatusError(self)

    def json(self) -> dict[str, Any]:
        return self._json_data

    def iter_lines(self) -> list[bytes]:
        return [b"data: {}"]

    def close(self) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.calls = 0
        self.urls: list[str] = []
        self.get_requests: list[dict[str, Any]] = []
        self.post_requests: list[dict[str, Any]] = []
        self.request_methods: list[str] = []

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls += 1
        self.urls.append(url)
        self.get_requests.append({"url": url, **kwargs})

        if url.endswith("/api/auth/session"):
            return _FakeResponse(200, json_data={"user": {"id": "123e4567-e89b-42d3-a456-426614174000"}})

        return _FakeResponse(200)

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls += 1
        self.urls.append(url)
        self.post_requests.append({"url": url, **kwargs})

        if url.endswith("/rest/sse/perplexity_ask"):
            return _FakeResponse(200)
        if url.endswith(ENDPOINT_UPLOAD):
            return _FakeResponse(200)
        return _FakeResponse(429, {"Retry-After": "60"}) if self.calls == 1 else _FakeResponse(200)

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.request_methods.append(method)
        return self.post(url, **kwargs)

    def close(self) -> None:
        return None


def test_http_client_retries_rate_limited_request() -> None:
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    with patch("perplexity_webui_scraper.http.resilience.sleep") as sleep_mock:
        response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2
    sleep_mock.assert_called_once_with(60.0)


def test_retry_with_backoff_honors_bounded_numeric_retry_after() -> None:
    operation_calls = 0
    waits: list[float] = []
    scheduled: list[float] = []

    def operation() -> str:
        nonlocal operation_calls
        operation_calls += 1

        if operation_calls == 1:
            raise RateLimitError(retry_after="120")

        return "ok"

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        result = retry_with_backoff(
            operation,
            RetryConfig(max_retries=1, base_delay=1, max_delay=30, jitter=0),
            on_retry=lambda _attempt, _exception, wait: scheduled.append(wait),
            retryable=(RateLimitError,),
        )

    assert result == "ok"
    assert waits == [30]
    assert scheduled == [30]


def test_retry_with_backoff_honors_http_date_retry_after() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    retry_after = format_datetime(datetime(2026, 1, 1, 12, 0, 20, tzinfo=UTC), usegmt=True)
    waits: list[float] = []
    scheduled: list[float] = []
    operation_calls = 0

    def operation() -> str:
        nonlocal operation_calls
        operation_calls += 1

        if operation_calls == 1:
            raise RateLimitError(retry_after=retry_after)

        return "ok"

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        result = retry_with_backoff(
            operation,
            RetryConfig(max_retries=1, base_delay=1, max_delay=30, jitter=0),
            on_retry=lambda _attempt, _exception, wait: scheduled.append(wait),
            retryable=(RateLimitError,),
            now=now,
        )

    assert result == "ok"
    assert waits == [20]
    assert scheduled == [20]


def test_retry_after_exceeds_maximum_delay_is_capped() -> None:
    waits: list[float] = []
    operation_calls = 0

    def operation() -> str:
        nonlocal operation_calls
        operation_calls += 1

        if operation_calls == 1:
            raise RateLimitError(retry_after="999999999999999999999999999999")

        return "ok"

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        result = retry_with_backoff(
            operation,
            RetryConfig(max_retries=1, base_delay=1, max_delay=30, jitter=0),
            retryable=(RateLimitError,),
        )

    assert result == "ok"
    assert waits == [30]


def test_http_client_honors_retry_after_header_value() -> None:
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)
    waits: list[float] = []

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2
    assert waits == [60]


def test_http_client_does_not_rotate_session_for_explicit_retry_after() -> None:
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    waits: list[float] = []
    with (
        patch("perplexity_webui_scraper.http.client.HTTPClient._rotate_session") as rotate_session,
        patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append),
    ):
        response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2
    rotate_session.assert_not_called()
    assert waits == [60]


def test_http_client_exposes_server_retry_after_header() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    with raises(RateLimitError) as exc_info:
        client.post("/rest/test", json={"query": "hello"})

    assert exc_info.value.retry_after == "60"
    assert "Retry-After: 60" not in str(exc_info.value)


@mark.parametrize(
    ("retry_after", "expected_wait"),
    [("60", 60.0)],
)
def test_http_client_waits_once_for_retry_after(retry_after: str, expected_wait: float) -> None:
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=2,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    responses = iter([429, 200])

    def post(url: str, **kwargs: Any) -> _FakeResponse:
        status = next(responses)
        response = _FakeResponse(status, {"Retry-After": retry_after} if status == 429 else None)
        fake_session.calls += 1
        fake_session.urls.append(url)
        fake_session.post_requests.append({"url": url, **kwargs})
        return response

    fake_session.post = post  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)
    waits: list[float] = []

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2
    assert waits == [expected_wait]


def test_http_client_uses_backoff_when_retry_after_is_invalid() -> None:
    retry_after = "invalid"
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=2,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    responses = iter([429, 200])

    def post(url: str, **kwargs: Any) -> _FakeResponse:
        status = next(responses)
        response = _FakeResponse(status, {"Retry-After": retry_after} if status == 429 else None)
        fake_session.calls += 1
        fake_session.urls.append(url)
        fake_session.post_requests.append({"url": url, **kwargs})
        return response

    fake_session.post = post  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)
    waits: list[float] = []

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        response = client.post("/rest/test", json={"query": "hello"})

    assert response.status_code == 200
    assert fake_session.calls == 2
    assert waits == [2]


def test_rate_limit_error_does_not_expose_untrusted_upstream_error_code() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    response = _FakeResponse(
        429,
        {"Retry-After": "60"},
        json_data={"error_code": "upstream-private-marker"},
    )
    fake_session.post = lambda url, **kwargs: response  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)

    with raises(RateLimitError) as exc_info:
        client.post("/rest/test", json={"query": "hello"})

    assert exc_info.value.retry_after == "60"
    assert "upstream-private-marker" not in str(exc_info.value)


def test_http_client_sanitizes_upstream_http_errors() -> None:
    sensitive_detail = "synthetic-upstream-marker"
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    response = _FakeResponse(500)
    response.text = sensitive_detail

    def raise_sensitive_error() -> None:
        raise _HTTPStatusError(response) from RuntimeError(sensitive_detail)

    response.raise_for_status = raise_sensitive_error
    fake_session.post = lambda url, **kwargs: response  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)

    with raises(HTTPError) as exc_info:
        client.post("/rest/test", json={"query": "hello"})

    error = exc_info.value
    assert sensitive_detail not in str(error)
    assert sensitive_detail not in repr(error)
    assert not hasattr(error, "url")
    assert not hasattr(error, "response_body")
    assert error.__cause__ is None
    assert error.__context__ is None


def test_http_client_sanitizes_error_logged_by_public_logging_helper() -> None:
    sensitive_detail = "synthetic-log-marker"
    output: list[str] = []
    handler_id = logger.add(output.append, format="{message}", level="ERROR")

    try:
        log_error(HTTPError(sensitive_detail, status_code=500))
    finally:
        logger.remove(handler_id)

    assert sensitive_detail not in "".join(output)


def test_http_client_sanitizes_network_error_messages() -> None:
    sensitive_detail = "synthetic-network-marker"
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()

    def raise_network_error(url: str, **kwargs: Any) -> _FakeResponse:
        raise ConnectionError(sensitive_detail)

    fake_session.post = raise_network_error  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)

    with raises(Exception) as exc_info:
        client.post("/rest/test", json={"query": "hello"})

    error = exc_info.value
    assert sensitive_detail not in str(error)
    assert sensitive_detail not in repr(error)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_http_client_attaches_request_metadata_and_account_context() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    client.get("/api/auth/session", rate_limited=False)
    request_id = "frontend-request-id"
    payload = {"params": {"frontend_uuid": request_id}, "query_str": "hello"}
    list(client.stream_ask(payload))

    session_request = fake_session.get_requests[0]
    assert session_request["params"] == {"version": API_VERSION, "source": API_SOURCE}
    session_headers = session_request["headers"]
    assert session_headers["X-Perplexity-Request-Reason"] == "getSession"
    assert session_headers["X-Request-Id"]
    assert session_headers["X-Pplx-Account"] == "123e4567-e89b-42d3-a456-426614174000"
    assert session_headers["X-Perplexity-Request-Endpoint"].endswith(
        f"{ENDPOINT_AUTH_SESSION}?version={API_VERSION}&source={API_SOURCE}"
    )
    assert session_headers["X-App-ApiVersion"] == API_VERSION
    assert session_headers["X-App-ApiClient"] == API_SOURCE
    assert session_headers["X-Perplexity-Request-Try-Number"] == "1"

    ask_request = fake_session.post_requests[0]
    ask_headers = ask_request["headers"]
    assert ask_headers["X-Perplexity-Request-Reason"] == "ask-query-state-provider"
    assert ask_headers["X-Perplexity-Request-Endpoint"].endswith(ENDPOINT_ASK)
    assert ask_headers["X-Request-Id"] == request_id
    assert ask_headers["X-Pplx-Account"] == "123e4567-e89b-42d3-a456-426614174000"
    assert f"session.id={client.rum_session_id}" in ask_headers["Baggage"]
    assert "user.id=123e4567-e89b-42d3-a456-426614174000" in ask_headers["Baggage"]


def test_http_client_scopes_webui_request_metadata_to_captured_endpoints() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    client.get("/rest/user/settings", rate_limited=False)

    assert "X-Perplexity-Request-Reason" not in fake_session.get_requests[0]["headers"]
    assert "X-Perplexity-Request-Endpoint" not in fake_session.get_requests[0]["headers"]


@mark.parametrize(
    ("method", "endpoint"),
    [("get", "/api/auth/session"), ("post", ENDPOINT_UPLOAD)],
)
def test_http_retry_metadata_reports_actual_attempt_number(method: str, endpoint: str) -> None:
    class RetryTrackingSession:
        def __init__(self) -> None:
            self.attempt_headers: list[dict[str, str]] = []
            self.status_codes = iter([429, 200, 200])

        def _respond(self, headers: dict[str, str]) -> _FakeResponse:
            self.attempt_headers.append(headers)
            return _FakeResponse(next(self.status_codes), {"Retry-After": "0"})

        def get(self, _url: str, *, headers: dict[str, str], **_kwargs: Any) -> _FakeResponse:
            return self._respond(headers)

        def request(self, _method: str, _url: str, *, headers: dict[str, str], **_kwargs: Any) -> _FakeResponse:
            return self._respond(headers)

    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        requests_per_second=0,
        rotate_fingerprint=False,
    )
    fake_session = RetryTrackingSession()
    client._session = cast("Any", fake_session)

    if method == "get":
        response = client.get(endpoint, rate_limited=False)
    else:
        response = client.post(endpoint, json={"files": {}})

    assert response.status_code == 200
    if method == "get":
        client.get(endpoint, rate_limited=False)
    else:
        client.post(endpoint, json={"files": {}})
    assert [headers["X-Perplexity-Request-Try-Number"] for headers in fake_session.attempt_headers] == ["1", "2", "1"]


def test_http_upload_request_matches_webui_request_context() -> None:
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)
    params = {"version": API_VERSION, "source": API_SOURCE}
    payload = {"files": {"id": {"filename": "image.png", "file_size": 123}}}

    response = client.post(ENDPOINT_UPLOAD, json=payload, params=params)

    request = fake_session.post_requests[0]
    assert fake_session.request_methods == ["POST"]
    assert loads(request["data"]) == payload
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["params"] == params
    headers = request["headers"]
    assert headers["X-Perplexity-Request-Endpoint"].endswith(
        f"{ENDPOINT_UPLOAD}?version={API_VERSION}&source={API_SOURCE}"
    )
    assert headers["X-Perplexity-Request-Reason"] == "ask-input-inner-home"
    assert headers["X-Perplexity-Request-Try-Number"] == "1"
    assert headers["X-Request-Id"]
    assert headers["X-App-ApiVersion"] == API_VERSION
    assert headers["X-App-ApiClient"] == API_SOURCE
    assert headers["X-Pplx-Account"] == account_id
    assert response.status_code == 200


def test_http_get_can_skip_rate_limiter() -> None:
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=0,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=1,
    )
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)
    rate_limiter = Mock()
    client._rate_limiter = rate_limiter

    response = client.get("/api/auth/session", rate_limited=False)

    assert response.status_code == 200
    assert fake_session.calls == 1
    rate_limiter.acquire.assert_not_called()


def test_http_client_rejects_absolute_url_without_leaking_session_cookie() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    with raises(ValueError, match="relative paths"):
        client.get("https://attacker.example/collect")

    assert fake_session.calls == 0
    assert fake_session.urls == []


def test_session_cookie_is_marked_secure_without_warning() -> None:
    with catch_warnings(record=True) as recorded:
        simplefilter("always")
        client = HTTPClient(_SESSION_CREDENTIAL, requests_per_second=0)

    assert not any(issubclass(item.category, CurlCffiWarning) for item in recorded)
    cookie = next(cookie for cookie in client._session.cookies.jar if cookie.name.startswith("__Secure-pplx.session."))
    assert cookie.secure
    client.close()


def test_http_client_installs_uuid_cookie_pair_with_account_id() -> None:
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    cookie_value = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    credential = f"__Secure-pplx.session.{account_id}={cookie_value}"
    client = HTTPClient(credential, requests_per_second=0)

    cookie = next(item for item in client._session.cookies.jar if item.name.startswith("__Secure-pplx.session."))
    assert cookie.name == f"__Secure-pplx.session.{account_id}"
    assert cookie.value == cookie_value
    assert cookie.secure
    assert client._account_id == account_id
    client.close()


def test_http_client_installs_same_cookie_for_raw_and_compact_credentials() -> None:
    raw_client = HTTPClient(_SESSION_CREDENTIAL, requests_per_second=0)
    compact_client = HTTPClient(_COMPACT_SESSION_TOKEN, requests_per_second=0)
    try:
        raw_cookie = next(iter(raw_client._session.cookies.jar))
        compact_cookie = next(iter(compact_client._session.cookies.jar))

        assert (compact_cookie.name, compact_cookie.value, compact_cookie.secure) == (
            raw_cookie.name,
            raw_cookie.value,
            raw_cookie.secure,
        )
        assert compact_client._account_id == raw_client._account_id
    finally:
        raw_client.close()
        compact_client.close()


def test_http_client_uses_cookie_account_id_for_ask_without_session_lookup() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    list(client.stream_ask({"params": {"frontend_uuid": "request-id"}, "query_str": "hello"}))

    request = fake_session.post_requests[0]
    assert request["headers"]["X-Pplx-Account"] == "123e4567-e89b-42d3-a456-426614174000"
    assert "user.id=123e4567-e89b-42d3-a456-426614174000" in request["headers"]["Baggage"]


def test_http_client_rejects_legacy_cookie_credential() -> None:
    with raises(ValueError, match=r"UUID|cookie"):
        HTTPClient("__Secure-next-auth.session-token=synthetic-legacy-value", requests_per_second=0)


def test_retry_config_rejects_negative_retries() -> None:
    with raises(ValidationError, match="max_retries cannot be negative"):
        RetryConfig(max_retries=-1)


def test_http_client_rejects_invalid_jitter() -> None:
    with raises(ValueError, match="retry_jitter"):
        HTTPClient(_SESSION_CREDENTIAL, retry_jitter=1.1)


def test_stream_lines_can_advance_across_threads_without_lock_deadlock() -> None:
    class _MultiLineResponse(_FakeResponse):
        def __init__(self) -> None:
            super().__init__(200)
            self.closed = False

        def iter_lines(self) -> Any:
            yield b'data: {"chunk": 1}'
            yield b'data: {"chunk": 2}'

        def close(self) -> None:
            self.closed = True

    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    stream_response = _MultiLineResponse()
    fake_session = _FakeSession()
    fake_session.post = Mock(return_value=stream_response)  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)
    generator = client.stream_ask({"params": {"frontend_uuid": "req"}, "query_str": "hello"})
    results: list[bytes] = []
    errors: list[BaseException] = []

    def read_one() -> None:
        try:
            results.append(next(generator))
        except BaseException as exc:
            errors.append(exc)

    first_thread = Thread(target=read_one)
    second_thread = Thread(target=read_one)
    first_thread.start()
    first_thread.join()
    second_thread.start()
    second_thread.join()
    generator.close()

    assert not errors
    assert results == [b'data: {"chunk": 1}', b'data: {"chunk": 2}']
    assert stream_response.closed
    assert client._session_lock.acquire(blocking=False)
    client._session_lock.release()
    client.close()


@mark.parametrize("error_type", [CurlConnectionError, CurlTimeout])
def test_http_client_retries_curl_connection_and_timeout_errors(error_type: type[Exception]) -> None:
    client = HTTPClient(
        _SESSION_CREDENTIAL,
        max_retries=1,
        retry_base_delay=0,
        retry_jitter=0,
        rotate_fingerprint=False,
        requests_per_second=0,
    )
    fake_session = _FakeSession()
    attempts = 0

    def flaky_get(url: str, **kwargs: Any) -> _FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise error_type("transient network failure")
        return _FakeResponse(200)

    fake_session.get = flaky_get  # type: ignore[method-assign]
    client._session = cast("Any", fake_session)

    with patch("perplexity_webui_scraper.http.resilience.sleep"):
        response = client.get("/search/new")

    assert response.status_code == 200
    assert attempts == 2


def test_retry_with_backoff_honors_zero_and_oversized_retry_after() -> None:
    waits: list[float] = []
    zero_calls = 0
    oversized_calls = 0

    def zero_retry() -> str:
        nonlocal zero_calls
        zero_calls += 1
        if zero_calls == 1:
            raise RateLimitError(retry_after="0")
        return "ok"

    def huge_retry() -> str:
        nonlocal oversized_calls
        oversized_calls += 1
        if oversized_calls == 1:
            raise RateLimitError(retry_after="9" * 5000)
        return "ok"

    with patch("perplexity_webui_scraper.http.resilience.sleep", side_effect=waits.append):
        config = RetryConfig(max_retries=1, base_delay=5.0, max_delay=12.0, jitter=0.0)
        assert retry_with_backoff(zero_retry, config, retryable=(RateLimitError,)) == "ok"
        assert retry_with_backoff(huge_retry, config, retryable=(RateLimitError,)) == "ok"

    assert waits == [0.0, 12.0]


def test_init_search_does_not_pass_query_params_to_debug_log() -> None:
    client = HTTPClient(_SESSION_CREDENTIAL, max_retries=0, requests_per_second=0)
    fake_session = _FakeSession()
    client._session = cast("Any", fake_session)

    with patch("perplexity_webui_scraper.http.client.log_request") as log_request_mock:
        client.init_search("private user prompt")

    assert log_request_mock.call_args.kwargs["params"] is None
