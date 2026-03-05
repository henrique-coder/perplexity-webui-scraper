"""HTTP client wrapper."""

from __future__ import annotations

from contextlib import suppress
from time import monotonic
from typing import TYPE_CHECKING, Any

from curl_cffi.requests import Response as CurlResponse
from curl_cffi.requests import Session

from .constants import API_BASE_URL, DEFAULT_HEADERS, ENDPOINT_ASK, ENDPOINT_SEARCH_INIT, SESSION_COOKIE_NAME
from .exceptions import AuthenticationError, HTTPError, PerplexityError, RateLimitError
from .limits import DEFAULT_TIMEOUT
from .logging import get_logger, log_request, log_response, log_retry
from .resilience import RateLimiter, RetryConfig, create_retry_decorator, get_random_browser_profile


if TYPE_CHECKING:
    from collections.abc import Generator

    from tenacity import RetryCallState


logger = get_logger(__name__)


class HTTPClient:
    """HTTP client with retry, rate limiting, and error handling."""

    __slots__ = (
        "_impersonate",
        "_max_init_query_length",
        "_rate_limiter",
        "_retry_config",
        "_rotate_fingerprint",
        "_session",
        "_session_token",
        "_timeout",
    )

    def __init__(
        self,
        session_token: str,
        timeout: int = DEFAULT_TIMEOUT,
        impersonate: str = "chrome",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 60.0,
        retry_jitter: float = 0.5,
        requests_per_second: float = 0.5,
        rotate_fingerprint: bool = True,
        max_init_query_length: int = 2000,
    ) -> None:
        self._session_token = session_token
        self._timeout = timeout
        self._impersonate = impersonate
        self._rotate_fingerprint = rotate_fingerprint
        self._max_init_query_length = max_init_query_length

        self._retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
            jitter=retry_jitter,
        )

        self._rate_limiter: RateLimiter | None = None
        if requests_per_second > 0:
            self._rate_limiter = RateLimiter(requests_per_second=requests_per_second)

        self._session = self._create_session(impersonate)
        logger.debug(f"HTTPClient initialized | impersonate={impersonate}")

    def _create_session(self, impersonate: str) -> Session:
        """Create a new HTTP session."""

        headers: dict[str, str] = {
            **DEFAULT_HEADERS,
            "Referer": f"{API_BASE_URL}/",
            "Origin": API_BASE_URL,
        }
        cookies: dict[str, str] = {SESSION_COOKIE_NAME: self._session_token}

        return Session(
            headers=headers,
            cookies=cookies,
            timeout=self._timeout,
            impersonate=impersonate,
        )

    def _rotate_session(self) -> None:
        """Rotate browser fingerprint."""

        if self._rotate_fingerprint:
            new_profile = get_random_browser_profile()
            logger.debug(f"Rotating fingerprint | old={self._impersonate} new={new_profile}")

            with suppress(Exception):
                self._session.close()

            self._impersonate = new_profile
            self._session = self._create_session(new_profile)

    def _on_retry(self, retry_state: RetryCallState) -> None:
        """Callback before each retry attempt."""

        attempt = retry_state.attempt_number
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        wait_time = retry_state.next_action.sleep if retry_state.next_action else 0

        log_retry(attempt, self._retry_config.max_retries, exception, wait_time)

        if self._rotate_fingerprint:
            self._rotate_session()

    def _handle_error(self, error: Exception, context: str = "") -> None:
        """Handle HTTP errors and raise appropriate exceptions."""

        status_code = None
        response_body = None
        url = None
        response = getattr(error, "response", None)

        if response is not None:
            status_code = getattr(response, "status_code", None)
            url = getattr(response, "url", None)
            try:
                response_body = response.text if hasattr(response, "text") else None
            except Exception:
                response_body = None

        if status_code == 403:
            raise AuthenticationError() from error
        elif status_code == 429:
            raise RateLimitError() from error
        elif status_code is not None:
            raise HTTPError(
                f"{context}HTTP {status_code}: {error!s}",
                status_code=status_code,
                url=str(url) if url else None,
                response_body=response_body,
            ) from error
        else:
            raise PerplexityError(f"{context}{error!s}") from error

    def _throttle(self) -> None:
        """Apply rate limiting."""

        if self._rate_limiter:
            self._rate_limiter.acquire()

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> CurlResponse:
        """Make a GET request with retry and rate limiting."""

        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint
        log_request("GET", url, params=params)

        retryable_exceptions = (RateLimitError, ConnectionError, TimeoutError)

        @create_retry_decorator(self._retry_config, retryable_exceptions, self._on_retry)
        def _do_get() -> CurlResponse:
            self._throttle()
            request_start = monotonic()

            try:
                response = self._session.get(url, params=params)
                elapsed_ms = (monotonic() - request_start) * 1000
                log_response("GET", url, response.status_code, elapsed_ms=elapsed_ms)

                response.raise_for_status()
                return response
            except Exception as error:
                if isinstance(error, RateLimitError):
                    raise
                self._handle_error(error, f"GET {endpoint}: ")
                raise error

        return _do_get()

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> CurlResponse:
        """Make a POST request with retry and rate limiting."""

        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint
        log_request("POST", url, body_size=len(str(json)) if json else 0)

        retryable_exceptions = (RateLimitError, ConnectionError, TimeoutError)

        @create_retry_decorator(self._retry_config, retryable_exceptions, self._on_retry)
        def _do_post() -> CurlResponse:
            self._throttle()
            request_start = monotonic()

            try:
                response = self._session.post(url, json=json, stream=stream)
                elapsed_ms = (monotonic() - request_start) * 1000
                log_response("POST", url, response.status_code, elapsed_ms=elapsed_ms)

                response.raise_for_status()
                return response
            except Exception as error:
                if isinstance(error, RateLimitError):
                    raise error
                self._handle_error(error, f"POST {endpoint}: ")
                raise error

        return _do_post()

    def stream_lines(self, endpoint: str, json: dict[str, Any]) -> Generator[bytes, None, None]:
        """Make a streaming POST request and yield lines."""

        response = self.post(endpoint, json=json, stream=True)

        try:
            yield from response.iter_lines()
        finally:
            response.close()

    def init_search(self, query: str) -> None:
        """Initialize a search session (required before prompts).

        The query is sent as a GET parameter. Very long queries can exceed
        server URI limits (HTTP 414). When ``max_init_query_length`` is set
        (default 2000), the query is truncated to stay within safe limits.
        Set to ``0`` to disable truncation.
        """

        if self._max_init_query_length and len(query) > self._max_init_query_length:
            query = query[: self._max_init_query_length]

        self.get(ENDPOINT_SEARCH_INIT, params={"q": query})

    def stream_ask(self, payload: dict[str, Any]) -> Generator[bytes, None, None]:
        """Stream a prompt request to the ask endpoint."""

        yield from self.stream_lines(ENDPOINT_ASK, json=payload)

    def close(self) -> None:
        """Close the HTTP session."""

        self._session.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
