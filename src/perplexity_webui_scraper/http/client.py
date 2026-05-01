"""HTTP client wrapping curl-cffi with retry, rate limiting, and error handling.

``HTTPClient`` is the single transport layer for all Perplexity API calls.
It manages a persistent curl-cffi ``Session`` with browser impersonation,
applies rate limiting and exponential-backoff retry, and translates HTTP
error codes into typed exceptions.
"""

from __future__ import annotations

from contextlib import suppress
from time import monotonic
from typing import TYPE_CHECKING, Any

from curl_cffi.requests import Response as CurlResponse
from curl_cffi.requests import Session

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ENDPOINT_ASK,
    ENDPOINT_SEARCH_INIT,
    SESSION_COOKIE_NAME,
)
from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    HTTPError,
    PerplexityError,
    RateLimitError,
)
from perplexity_webui_scraper._internal.logging import (
    get_logger,
    log_request,
    log_response,
    log_retry,
)
from perplexity_webui_scraper.http.fingerprint import get_random_browser_profile
from perplexity_webui_scraper.http.resilience import RateLimiter, RetryConfig, retry_with_backoff


if TYPE_CHECKING:
    from collections.abc import Generator

    from curl_cffi.requests import BrowserTypeLiteral


logger = get_logger(__name__)


class HTTPClient:
    """HTTP client with retry, rate limiting, fingerprint rotation, and error handling.

    Attributes:
        _session_token: The Perplexity session token used for authentication.
        _timeout: Request timeout in seconds.
        _impersonate: Current browser fingerprint profile.
        _rotate_fingerprint: Whether to rotate the profile on retry.
        _max_init_query_length: Max characters for the search-init query.
        _retry_config: Retry behaviour configuration.
        _rate_limiter: Optional rate limiter instance.
        _session: Active curl-cffi ``Session``.
    """

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
        impersonate: BrowserTypeLiteral = "chrome",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 60.0,
        retry_jitter: float = 0.5,
        requests_per_second: float = 0.5,
        rotate_fingerprint: bool = True,
        max_init_query_length: int = 2000,
    ) -> None:
        """Initialise the HTTP client.

        Args:
            session_token: The ``__Secure-next-auth.session-token`` cookie value.
            timeout: Request timeout in seconds.
            impersonate: Initial browser fingerprint profile.
            max_retries: Maximum retry attempts on transient errors.
            retry_base_delay: Initial backoff delay in seconds.
            retry_max_delay: Maximum backoff delay cap in seconds.
            retry_jitter: Jitter factor (0-1).
            requests_per_second: Rate limit; ``0`` disables it.
            rotate_fingerprint: Rotate fingerprint on each retry.
            max_init_query_length: Truncate init query to this length;
                ``0`` disables truncation.
        """
        self._session_token = session_token
        self._timeout = timeout
        self._impersonate: BrowserTypeLiteral = impersonate
        self._rotate_fingerprint = rotate_fingerprint
        self._max_init_query_length = max_init_query_length

        self._retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
            jitter=retry_jitter,
        )

        self._rate_limiter: RateLimiter | None = (
            RateLimiter(requests_per_second=requests_per_second) if requests_per_second > 0 else None
        )

        self._session = self._create_session(impersonate)
        logger.debug("HTTPClient initialized | impersonate={}", impersonate)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _create_session(self, impersonate: BrowserTypeLiteral) -> Session:
        """Create a new curl-cffi session with auth cookie and default headers.

        Args:
            impersonate: Browser profile to impersonate.

        Returns:
            Configured :class:`curl_cffi.requests.Session`.
        """
        return Session(
            headers=dict(DEFAULT_HEADERS),
            cookies={SESSION_COOKIE_NAME: self._session_token},
            timeout=self._timeout,
            impersonate=impersonate,  # type: ignore[arg-type]
        )

    def _rotate_session(self) -> None:
        """Replace the current session with a new random browser fingerprint."""
        if not self._rotate_fingerprint:
            return

        new_profile = get_random_browser_profile()
        logger.debug("Rotating fingerprint | old={} new={}", self._impersonate, new_profile)

        with suppress(Exception):
            self._session.close()

        self._impersonate = new_profile
        self._session = self._create_session(new_profile)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Apply rate limiting if configured."""
        if self._rate_limiter:
            self._rate_limiter.acquire()

    def _on_retry(self, attempt: int, exception: BaseException, wait: float) -> None:
        """Callback invoked before each retry attempt.

        Args:
            attempt: Current attempt number (1-based).
            exception: The exception that triggered the retry.
            wait: Seconds to wait before the next attempt.
        """
        log_retry(attempt, self._retry_config.max_retries, exception, wait)

        if self._rotate_fingerprint:
            self._rotate_session()

    def _handle_error(self, error: Exception, context: str = "") -> None:
        """Translate a raw exception into a typed Perplexity exception.

        Args:
            error: The original exception from curl-cffi.
            context: Optional prefix describing the request context.

        Raises:
            AuthenticationError: On HTTP 403.
            RateLimitError: On HTTP 429.
            HTTPError: On any other HTTP error with a status code.
            PerplexityError: On network-level errors without a status code.
        """
        response = getattr(error, "response", None)
        status_code: int | None = None
        url: str | None = None
        response_body: str | None = None

        if response is not None:
            status_code = getattr(response, "status_code", None)
            url = getattr(response, "url", None)

            with suppress(Exception):
                response_body = response.text if hasattr(response, "text") else None

        match status_code:
            case 403:
                raise AuthenticationError from error
            case 429:
                raise RateLimitError from error
            case _ if status_code is not None:
                raise HTTPError(
                    f"{context}HTTP {status_code}: {error!s}",
                    status_code=status_code,
                    url=str(url) if url else None,
                    response_body=response_body,
                ) from error
            case _:
                raise PerplexityError(f"{context}{error!s}") from error

    # ------------------------------------------------------------------
    # Public request methods
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> CurlResponse:
        """Make a GET request with retry and rate limiting.

        Args:
            endpoint: Relative path (e.g. ``"/search/new"``) or full URL.
            params: Optional query parameters.

        Returns:
            The curl-cffi response object.

        Raises:
            AuthenticationError: On HTTP 403.
            RateLimitError: On HTTP 429.
            HTTPError: On other HTTP errors.
            PerplexityError: On network errors.
        """
        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint
        log_request("GET", url, params=params)

        def _do_get() -> CurlResponse:
            self._throttle()
            t0 = monotonic()
            response = self._session.get(url, params=params)
            log_response("GET", url, response.status_code, elapsed_ms=(monotonic() - t0) * 1000)
            response.raise_for_status()
            return response

        try:
            return retry_with_backoff(
                _do_get,
                self._retry_config,
                on_retry=self._on_retry,
                retryable=(RateLimitError, ConnectionError, TimeoutError),
            )
        except (RateLimitError, AuthenticationError, HTTPError, PerplexityError):
            raise
        except Exception as error:
            self._handle_error(error, f"GET {endpoint}: ")
            raise  # unreachable but satisfies type checker

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> CurlResponse:
        """Make a POST request with retry and rate limiting.

        Args:
            endpoint: Relative path or full URL.
            json: Optional JSON body to serialize and send.
            stream: If ``True``, keep the response connection open for streaming.

        Returns:
            The curl-cffi response object.

        Raises:
            AuthenticationError: On HTTP 403.
            RateLimitError: On HTTP 429.
            HTTPError: On other HTTP errors.
            PerplexityError: On network errors.
        """
        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint
        log_request("POST", url, body_size=len(str(json)) if json else 0)

        def _do_post() -> CurlResponse:
            self._throttle()
            t0 = monotonic()
            response = self._session.post(url, json=json, stream=stream)
            log_response("POST", url, response.status_code, elapsed_ms=(monotonic() - t0) * 1000)
            response.raise_for_status()
            return response

        try:
            return retry_with_backoff(
                _do_post,
                self._retry_config,
                on_retry=self._on_retry,
                retryable=(RateLimitError, ConnectionError, TimeoutError),
            )
        except (RateLimitError, AuthenticationError, HTTPError, PerplexityError):
            raise
        except Exception as error:
            self._handle_error(error, f"POST {endpoint}: ")
            raise  # unreachable but satisfies type checker

    def _stream_lines(self, endpoint: str, json: dict[str, Any]) -> Generator[bytes, None, None]:
        """Make a streaming POST and yield raw SSE lines as bytes.

        Args:
            endpoint: Relative path or full URL.
            json: JSON payload.

        Yields:
            Raw bytes lines from the SSE response.
        """
        response = self.post(endpoint, json=json, stream=True)

        try:
            yield from response.iter_lines()
        finally:
            response.close()

    def init_search(self, query: str) -> None:
        """Initialize a search session (required before each prompt).

        The query is sent as a GET parameter.  Very long queries can exceed
        server URI limits (HTTP 414).  When ``max_init_query_length > 0``,
        the query is truncated to stay within safe limits.

        Args:
            query: The search query string to initialize.
        """
        if self._max_init_query_length and len(query) > self._max_init_query_length:
            query = query[: self._max_init_query_length]

        self.get(ENDPOINT_SEARCH_INIT, params={"q": query})

    def stream_ask(self, payload: dict[str, Any]) -> Generator[bytes, None, None]:
        """Stream a prompt request to the Perplexity SSE ask endpoint.

        Args:
            payload: The fully-constructed request payload (see
                :func:`~perplexity_webui_scraper.core.payload.build_payload`).

        Yields:
            Raw bytes lines from the SSE stream.
        """
        yield from self._stream_lines(ENDPOINT_ASK, json=payload)

    def close(self) -> None:
        """Close the underlying curl-cffi session and release resources."""
        self._session.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
