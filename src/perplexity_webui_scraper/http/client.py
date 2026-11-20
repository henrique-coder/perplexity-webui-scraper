"""HTTP client wrapping curl-cffi with retry, rate limiting, and error handling.

``HTTPClient`` is the single transport layer for all Perplexity API calls.
It manages a persistent curl-cffi ``Session`` with browser impersonation,
applies rate limiting and exponential-backoff retry, and translates HTTP
error codes into typed exceptions.
"""

from __future__ import annotations

from contextlib import suppress
from math import isfinite
from threading import RLock, local
from time import monotonic
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode
from uuid import uuid4

from curl_cffi.requests import BrowserTypeLiteral, Session
from curl_cffi.requests import Response as CurlResponse
from curl_cffi.requests.cookies import Cookies
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import Timeout as CurlTimeout
from orjson import dumps

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    API_SOURCE,
    API_VERSION,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    ENDPOINT_ASK,
    ENDPOINT_AUTH_SESSION,
    ENDPOINT_SEARCH_INIT,
    ENDPOINT_UPLOAD,
)
from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    HTTPError,
    PerplexityError,
    RateLimitError,
)
from perplexity_webui_scraper._internal.logging import (
    _sanitized_error,
    get_logger,
    log_request,
    log_response,
    log_retry,
)
from perplexity_webui_scraper.auth.cookies import (
    CookieCredential,
    parse_session_cookie_name,
    parse_session_credential,
)
from perplexity_webui_scraper.http.resilience import RateLimiter, RetryConfig, retry_with_backoff


if TYPE_CHECKING:
    from collections.abc import Generator

    from curl_cffi.requests.session import HttpMethod


logger = get_logger(__name__)


class HTTPClient:
    """HTTP client with retry, rate limiting, session renewal, and error handling.

    Attributes:
        _session_cookie: Cookie name and value used for authentication.
        _timeout: Request timeout in seconds.
        _impersonate: Current browser fingerprint profile.
        _rotate_fingerprint: Whether to renew the session on retry.
        _max_init_query_length: Max characters for the search-init query.
        _retry_config: Retry behavior configuration.
        _rate_limiter: Optional rate limiter instance.
        _session: Active curl-cffi ``Session``.
    """

    __slots__ = (
        "_account_id",
        "_impersonate",
        "_max_init_query_length",
        "_rate_limiter",
        "_request_metadata",
        "_retry_config",
        "_rotate_fingerprint",
        "_rum_session_id",
        "_session",
        "_session_cookie",
        "_session_lock",
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
        """Initialize the HTTP client.

        Args:
            session_token: The UUID-suffixed Perplexity session-cookie ``name=value`` pair.
            timeout: Request timeout in seconds.
            impersonate: Initial browser fingerprint profile.
            max_retries: Maximum retry attempts on transient errors.
            retry_base_delay: Initial backoff delay in seconds.
            retry_max_delay: Maximum backoff delay cap in seconds.
            retry_jitter: Jitter factor (0-1).
            requests_per_second: Rate limit; ``0`` disables it.
            rotate_fingerprint: Recreate the HTTP session after a retry while retaining its fingerprint.
            max_init_query_length: Truncate init query to this length;
                ``0`` disables truncation.
        """
        self._session_cookie: CookieCredential = parse_session_credential(session_token)
        self._rum_session_id = str(uuid4())
        cookie_metadata = parse_session_cookie_name(self._session_cookie.name)
        self._account_id: str | None = cookie_metadata[1] if cookie_metadata else None

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        if retry_base_delay < 0 or retry_max_delay < 0:
            raise ValueError("retry delays cannot be negative")

        if not isfinite(retry_jitter) or not 0 <= retry_jitter <= 1:
            raise ValueError("retry_jitter must be between zero and one")

        if not isfinite(requests_per_second) or requests_per_second < 0:
            raise ValueError("requests_per_second cannot be negative")

        if max_init_query_length < 0:
            raise ValueError("max_init_query_length cannot be negative")

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
        self._session_lock = RLock()
        self._request_metadata = local()
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
        cookies = Cookies()
        cookies.set(self._session_cookie.name, self._session_cookie.value, secure=True)

        return Session(
            headers=dict(DEFAULT_HEADERS),
            cookies=cookies,
            timeout=self._timeout,
            impersonate=impersonate,  # type: ignore[arg-type]
        )

    def _request_json(
        self,
        method: HttpMethod,
        endpoint: str,
        body: dict[str, Any],
        params: dict[str, Any] | None,
        headers: dict[str, str],
        *,
        stream: bool = False,
    ) -> CurlResponse:
        """Serialize a request body with orjson and send it through curl-cffi."""
        url = f"{API_BASE_URL}{endpoint}"

        with self._session_lock:
            return self._session.request(
                method,
                url,
                params=params,
                data=dumps(body),
                stream=stream,
                headers={"Content-Type": "application/json", **headers},
            )

    def _rotate_session(self) -> None:
        """Replace the current session while retaining its browser fingerprint."""
        if not self._rotate_fingerprint:
            return

        logger.debug("Recreating HTTP session | impersonate={}", self._impersonate)

        with self._session_lock:
            with suppress(Exception):
                self._session.close()

            self._session = self._create_session(self._impersonate)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Apply rate limiting if configured."""
        if self._rate_limiter:
            self._rate_limiter.acquire()

    @property
    def rum_session_id(self) -> str:
        """Return the client-lifetime RUM session identifier."""
        return self._rum_session_id

    def _headers_for_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, str]:
        """Build request-scoped headers observed on current WebUI traffic."""
        url = f"{API_BASE_URL}{endpoint}"

        if params:
            separator = "&" if "?" in url else "?"
            query = urlencode(params)
            url = f"{url}{separator}{query}"

        headers: dict[str, str] = {}
        try_number = getattr(self._request_metadata, "try_number", 1)

        if endpoint == ENDPOINT_AUTH_SESSION:
            headers["X-Perplexity-Request-Endpoint"] = url
            headers["X-Perplexity-Request-Try-Number"] = str(try_number)
            headers["X-Request-Id"] = request_id or str(uuid4())
            headers["X-Perplexity-Request-Reason"] = "getSession"
            headers["X-App-ApiVersion"] = API_VERSION
            headers["X-App-ApiClient"] = API_SOURCE

            if self._account_id:
                headers["X-Pplx-Account"] = self._account_id
                headers["Baggage"] = f"session.id={self._rum_session_id},user.id={self._account_id}"
        elif endpoint == ENDPOINT_UPLOAD:
            headers["X-Perplexity-Request-Endpoint"] = url
            headers["X-Perplexity-Request-Try-Number"] = str(try_number)
            headers["X-Request-Id"] = request_id or str(uuid4())
            headers["X-Perplexity-Request-Reason"] = "ask-input-inner-home"
            headers["X-App-ApiVersion"] = API_VERSION
            headers["X-App-ApiClient"] = API_SOURCE

            if self._account_id:
                headers["X-Pplx-Account"] = self._account_id
        elif endpoint == ENDPOINT_ASK:
            headers["X-Perplexity-Request-Endpoint"] = url
            headers["X-Perplexity-Request-Try-Number"] = str(try_number)
            headers["X-Request-Id"] = request_id or str(uuid4())
            headers["X-Perplexity-Request-Reason"] = "ask-query-state-provider"

        if self._account_id and endpoint == ENDPOINT_ASK:
            headers["X-Pplx-Account"] = self._account_id
            headers["Baggage"] = f"session.id={self._rum_session_id},user.id={self._account_id}"

        return headers

    def _request_json_with_context(
        self,
        method: HttpMethod,
        endpoint: str,
        body: dict[str, Any],
        params: dict[str, Any] | None,
        request_id: str | None = None,
        *,
        stream: bool = False,
    ) -> CurlResponse:
        """Send an orjson-serialized request with standard request context."""
        request_params = params

        if endpoint == ENDPOINT_UPLOAD and request_params is None:
            request_params = {"version": API_VERSION, "source": API_SOURCE}

        request_headers = self._headers_for_request(endpoint, request_params, request_id)

        if endpoint == ENDPOINT_AUTH_SESSION:
            request_headers["X-Perplexity-Request-Reason"] = "getSession"

        if endpoint == ENDPOINT_ASK and isinstance(body.get("params"), dict):
            request_headers["X-Request-Id"] = str(body["params"].get("frontend_uuid") or uuid4())
            request_headers["X-Perplexity-Request-Reason"] = "ask-query-state-provider"

        return self._request_json(method, endpoint, body, request_params, request_headers, stream=stream)

    def _on_retry(self, attempt: int, exception: BaseException, wait: float) -> None:
        """Callback invoked before each retry attempt.

        Args:
            attempt: Current attempt number (1-based).
            exception: The exception that triggered the retry.
            wait: Seconds to wait before the next attempt.
        """
        log_retry(attempt, self._retry_config.max_retries, exception, wait)
        self._request_metadata.try_number = attempt + 1

        if isinstance(exception, RateLimitError):
            return

        self._rotate_session()

    def _reset_request_try_number(self) -> None:
        """Reset upstream request metadata at the start of a new operation."""
        self._request_metadata.try_number = 1

    def _handle_error(self, error: Exception, request_method: str) -> PerplexityError:
        """Translate a raw exception without retaining its upstream details.

        Args:
            error: The original exception from curl-cffi.
            request_method: HTTP method for a bounded diagnostic message.

        Returns:
            A safe typed exception with no raw response or network details.
        """
        response = getattr(error, "response", None)
        status_code: int | None = None
        retry_after: str | None = None

        if response is not None:
            status_code = getattr(response, "status_code", None)
            with suppress(Exception):
                retry_after = response.headers.get("Retry-After")

        match status_code:
            case 403:
                return AuthenticationError()
            case 429:
                return RateLimitError(retry_after=retry_after)
            case _ if status_code is not None:
                return HTTPError(
                    f"{request_method} request failed with HTTP {status_code}.",
                    status_code=status_code,
                )
            case _:
                return PerplexityError(f"{request_method} network request failed.")

    def _raise_for_status(self, response: CurlResponse, request_method: str) -> None:
        """Raise typed project exceptions for non-success HTTP responses."""
        try:
            response.raise_for_status()
        except Exception as error:
            translated_error = self._handle_error(error, request_method)
        except BaseException:
            raise
        else:
            return

        raise translated_error from None

    # ------------------------------------------------------------------
    # Public request methods
    # ------------------------------------------------------------------

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        rate_limited: bool = True,
    ) -> CurlResponse:
        """Make a GET request with retry and rate limiting.

        Args:
            endpoint: Relative path (e.g. ``"/search/new"``).
            params: Optional query parameters.
            rate_limited: Whether to apply the configured request rate limiter.

        Returns:
            The curl-cffi response object.

        Raises:
            AuthenticationError: On HTTP 403.
            RateLimitError: On HTTP 429.
            HTTPError: On other HTTP errors.
            PerplexityError: On network errors.
        """
        if not endpoint.startswith("/"):
            raise ValueError("Authenticated HTTP endpoints must be relative paths")

        url = f"{API_BASE_URL}{endpoint}"
        log_request("GET", url, params=None if endpoint == ENDPOINT_SEARCH_INIT else params)
        self._reset_request_try_number()

        def _do_get() -> CurlResponse:
            if rate_limited:
                self._throttle()

            t0 = monotonic()

            request_params = params

            if endpoint == ENDPOINT_AUTH_SESSION and request_params is None:
                request_params = {"version": API_VERSION, "source": API_SOURCE}

            request_headers = self._headers_for_request(endpoint, request_params)

            with self._session_lock:
                response = self._session.get(url, params=request_params, headers=request_headers)

            log_response("GET", url, response.status_code, elapsed_ms=(monotonic() - t0) * 1000)
            self._raise_for_status(response, "GET")

            return response

        translated_error: PerplexityError | None = None

        try:
            return retry_with_backoff(
                _do_get,
                self._retry_config,
                on_retry=self._on_retry,
                retryable=(RateLimitError, ConnectionError, TimeoutError, CurlConnectionError, CurlTimeout),
            )
        except (RateLimitError, AuthenticationError, HTTPError, PerplexityError):
            raise
        except Exception as error:
            translated_error = self._handle_error(error, "GET")

        if translated_error is None:
            raise RuntimeError("GET request ended without a response or error")

        _sanitized_error(translated_error)
        raise translated_error from None

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> CurlResponse:
        """Make a POST request with retry and rate limiting.

        Args:
            endpoint: Relative endpoint path.
            json: Optional JSON body to serialize and send.
            params: Optional query parameters to include in the request URL.
            stream: If ``True``, keep the response connection open for streaming.

        Returns:
            The curl-cffi response object.

        Raises:
            AuthenticationError: On HTTP 403.
            RateLimitError: On HTTP 429.
            HTTPError: On other HTTP errors.
            PerplexityError: On network errors.
        """
        if not endpoint.startswith("/"):
            raise ValueError("Authenticated HTTP endpoints must be relative paths")

        url = f"{API_BASE_URL}{endpoint}"
        log_request("POST", url, body_size=len(str(json)) if json else 0)
        self._reset_request_try_number()
        request_id = str(uuid4())

        def _do_post() -> CurlResponse:
            self._throttle()
            t0 = monotonic()
            request_params = params

            if endpoint == ENDPOINT_UPLOAD and request_params is None:
                request_params = {"version": API_VERSION, "source": API_SOURCE}

            request_headers = self._headers_for_request(endpoint, request_params)

            if endpoint == ENDPOINT_UPLOAD:
                request_headers["X-Request-Id"] = request_id

            if endpoint == ENDPOINT_AUTH_SESSION:
                request_headers["X-Perplexity-Request-Reason"] = "getSession"

            if endpoint == ENDPOINT_ASK and json and isinstance(json.get("params"), dict):
                request_headers["X-Request-Id"] = str(json["params"].get("frontend_uuid") or uuid4())
                request_headers["X-Perplexity-Request-Reason"] = "ask-query-state-provider"

            if json is None:
                with self._session_lock:
                    response = self._session.post(
                        url,
                        params=request_params,
                        stream=stream,
                        headers=request_headers,
                    )
            elif stream:
                response = self._request_json_with_context(
                    "POST", endpoint, json, request_params, request_id, stream=True
                )
            else:
                response = self._request_json_with_context("POST", endpoint, json, request_params, request_id)

            response_url = url

            if request_params:
                response_url = f"{url}?{urlencode(request_params)}"

            log_response("POST", response_url, response.status_code, elapsed_ms=(monotonic() - t0) * 1000)
            self._raise_for_status(response, "POST")

            return response

        translated_error: PerplexityError | None = None

        try:
            return retry_with_backoff(
                _do_post,
                self._retry_config,
                on_retry=self._on_retry,
                retryable=(RateLimitError, ConnectionError, TimeoutError, CurlConnectionError, CurlTimeout),
            )
        except (RateLimitError, AuthenticationError, HTTPError, PerplexityError):
            raise
        except Exception as error:
            translated_error = self._handle_error(error, "POST")

        if translated_error is None:
            raise RuntimeError("POST request ended without a response or error")

        _sanitized_error(translated_error)
        raise translated_error from None

    def _stream_lines(self, endpoint: str, json: dict[str, Any]) -> Generator[bytes, None, None]:
        """Make a streaming POST and yield raw SSE lines as bytes.

        Args:
            endpoint: Relative endpoint path.
            json: JSON payload.

        Yields:
            Raw bytes lines from the SSE response.
        """
        response = self.post(endpoint, json=json, stream=True)
        stream_error: PerplexityError | None = None

        try:
            yield from response.iter_lines()
        except PerplexityError:
            raise
        except Exception as error:
            stream_error = self._handle_error(error, "POST")
        finally:
            response.close()

        if stream_error is not None:
            _sanitized_error(stream_error)
            raise stream_error

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
        with self._session_lock:
            self._session.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
