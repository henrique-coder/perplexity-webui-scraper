"""HTTP client wrapper for Perplexity API requests."""

from __future__ import annotations

from contextlib import suppress
from time import monotonic
from typing import TYPE_CHECKING, Any

from curl_cffi.requests import Response as CurlResponse
from curl_cffi.requests import Session

from .constants import API_BASE_URL, DEFAULT_HEADERS, ENDPOINT_ASK, ENDPOINT_SEARCH_INIT, SESSION_COOKIE_NAME
from .exceptions import AuthenticationError, CloudflareBlockError, PerplexityError, RateLimitError
from .limits import DEFAULT_TIMEOUT
from .logging import (
    get_logger,
    log_cloudflare_detected,
    log_error,
    log_fingerprint_rotation,
    log_rate_limit,
    log_request,
    log_response,
    log_retry,
    log_session_created,
)
from .resilience import (
    CLOUDFLARE_MARKERS,
    RateLimiter,
    RetryConfig,
    create_retry_decorator,
    get_random_browser_profile,
    is_cloudflare_challenge,
    is_cloudflare_status,
)


if TYPE_CHECKING:
    from collections.abc import Generator

    from tenacity import RetryCallState

logger = get_logger(__name__)


class HTTPClient:
    """
    HTTP client wrapper with error handling for Perplexity API.

    Provides a unified interface for making HTTP requests with automatic
    error handling, retry mechanisms, rate limiting, and Cloudflare bypass.
    """

    __slots__ = (
        "_impersonate",
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
    ) -> None:
        """Initialize the HTTP client.

        Args:
            session_token: Perplexity session cookie.
            timeout: Request timeout in seconds.
            impersonate: Browser profile to impersonate.
            max_retries: Maximum retry attempts for failed requests.
            retry_base_delay: Initial delay before first retry.
            retry_max_delay: Maximum delay between retries.
            retry_jitter: Random jitter factor for delays.
            requests_per_second: Rate limit (0 to disable).
            rotate_fingerprint: Whether to rotate browser fingerprint on retries.
        """

        logger.debug(
            "Initializing HTTPClient | "
            f"session_token_length={len(session_token)} "
            f"timeout={timeout}s "
            f"impersonate={impersonate} "
            f"max_retries={max_retries} "
            f"retry_base_delay={retry_base_delay}s "
            f"retry_max_delay={retry_max_delay}s "
            f"retry_jitter={retry_jitter} "
            f"requests_per_second={requests_per_second} "
            f"rotate_fingerprint={rotate_fingerprint}"
        )

        self._session_token = session_token
        self._timeout = timeout
        self._impersonate = impersonate
        self._rotate_fingerprint = rotate_fingerprint

        self._retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
            jitter=retry_jitter,
        )

        logger.debug(
            "RetryConfig created | "
            f"max_retries={self._retry_config.max_retries} "
            f"base_delay={self._retry_config.base_delay}s "
            f"max_delay={self._retry_config.max_delay}s "
            f"jitter={self._retry_config.jitter}"
        )

        self._rate_limiter: RateLimiter | None = None

        if requests_per_second > 0:
            self._rate_limiter = RateLimiter(requests_per_second=requests_per_second)
            logger.debug(f"RateLimiter enabled | requests_per_second={requests_per_second}")
        else:
            logger.debug("RateLimiter disabled | requests_per_second=0")

        self._session = self._create_session(impersonate)
        log_session_created(impersonate, timeout)

    def _create_session(self, impersonate: str) -> Session:
        """Create a new HTTP session with the given browser profile."""

        logger.debug(f"Creating new HTTP session | browser_profile={impersonate}")

        headers: dict[str, str] = {
            **DEFAULT_HEADERS,
            "Referer": f"{API_BASE_URL}/",
            "Origin": API_BASE_URL,
        }
        cookies: dict[str, str] = {SESSION_COOKIE_NAME: self._session_token}

        logger.debug(
            f"Session configuration | headers_count={len(headers)} cookies_count={len(cookies)} base_url={API_BASE_URL}"
        )

        session = Session(
            headers=headers,
            cookies=cookies,
            timeout=self._timeout,
            impersonate=impersonate,
        )

        logger.debug(f"HTTP session created successfully | browser_profile={impersonate}")

        return session

    def _rotate_session(self) -> None:
        """Rotate to a new browser fingerprint by recreating the session."""

        if self._rotate_fingerprint:
            old_profile = self._impersonate
            new_profile = get_random_browser_profile()

            logger.debug(f"Rotating browser fingerprint | old={old_profile} new={new_profile}")
            log_fingerprint_rotation(old_profile, new_profile)

            with suppress(Exception):
                self._session.close()
                logger.debug("Previous session closed")

            self._impersonate = new_profile
            self._session = self._create_session(new_profile)

            logger.debug(f"Browser fingerprint rotated successfully | new_profile={new_profile}")

    def _on_retry(self, retry_state: RetryCallState) -> None:
        """Callback executed before each retry attempt."""

        attempt = retry_state.attempt_number
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        wait_time = retry_state.next_action.sleep if retry_state.next_action else 0

        logger.warning(
            f"Retry triggered | "
            f"attempt={attempt}/{self._retry_config.max_retries} "
            f"exception_type={type(exception).__name__ if exception else 'None'} "
            f"exception_message={str(exception) if exception else 'None'} "
            f"wait_seconds={wait_time:.2f}"
        )
        log_retry(attempt, self._retry_config.max_retries, exception, wait_time)

        # Rotate fingerprint on retry to avoid detection
        if self._rotate_fingerprint:
            logger.debug("Rotating fingerprint due to retry")
            self._rotate_session()

    def _check_cloudflare(self, response: CurlResponse) -> None:
        """Check if response is a Cloudflare challenge and raise if so."""

        logger.debug(f"Checking for Cloudflare challenge | status_code={response.status_code}")

        if is_cloudflare_status(response.status_code):
            logger.debug(f"Status code indicates potential Cloudflare block | status_code={response.status_code}")

            try:
                body = response.text
                headers = dict(response.headers) if hasattr(response, "headers") else None

                logger.debug(
                    f"Analyzing response for Cloudflare markers | "
                    f"body_length={len(body)} "
                    f"headers_count={len(headers) if headers else 0}"
                )

                if is_cloudflare_challenge(body, headers):
                    # Find which markers were detected
                    markers_found = [m for m in CLOUDFLARE_MARKERS if m.lower() in body.lower()]
                    logger.warning(
                        f"Cloudflare challenge detected | "
                        f"status_code={response.status_code} "
                        f"markers_found={markers_found}"
                    )
                    log_cloudflare_detected(response.status_code, markers_found)
                    raise CloudflareBlockError()
                else:
                    logger.debug("No Cloudflare markers found in response")
            except CloudflareBlockError as error:
                raise error
            except Exception as error:
                logger.debug(f"Error checking Cloudflare response | error={error}")

    def _handle_error(self, error: Exception, context: str = "") -> None:
        """Handle HTTP errors and raise appropriate custom exceptions.

        Args:
            error: The original exception.
            context: Additional context for the error message.

        Raises:
            AuthenticationError: If status code is 403 (not Cloudflare).
            RateLimitError: If status code is 429.
            CloudflareBlockError: If Cloudflare challenge detected.
            PerplexityError: For other HTTP errors.
        """

        logger.debug(f"Handling error | context={context} error_type={type(error).__name__} error={error}")
        log_error(error, context)

        status_code = None
        response = getattr(error, "response", None)

        if response is not None:
            status_code = getattr(response, "status_code", None)
            logger.debug(f"Error has response | status_code={status_code}")

            # Check for Cloudflare before handling as regular 403
            if is_cloudflare_status(status_code):
                logger.debug(f"Checking if error is Cloudflare challenge | status_code={status_code}")

                try:
                    body = response.text if hasattr(response, "text") else ""
                    headers = dict(response.headers) if hasattr(response, "headers") else None

                    if is_cloudflare_challenge(body, headers):
                        markers_found = [m for m in CLOUDFLARE_MARKERS if m.lower() in body.lower()]
                        logger.warning(
                            f"Cloudflare challenge confirmed in error response | "
                            f"status_code={status_code} "
                            f"markers={markers_found}"
                        )
                        log_cloudflare_detected(status_code, markers_found)
                        raise CloudflareBlockError() from error
                except CloudflareBlockError:
                    raise

        if status_code == 403:
            logger.error(f"Authentication error | status_code=403 context={context}")
            raise AuthenticationError() from error
        elif status_code == 429:
            logger.warning(f"Rate limit exceeded | status_code=429 context={context}")
            raise RateLimitError() from error
        elif status_code is not None:
            logger.error(f"HTTP error | status_code={status_code} context={context} error={error}")
            raise PerplexityError(f"{context}HTTP {status_code}: {error!s}", status_code=status_code) from error
        else:
            logger.error(f"Unknown error | context={context} error={error}")
            raise PerplexityError(f"{context}{error!s}") from error

    def _throttle(self) -> None:
        """Apply rate limiting before making a request."""

        if self._rate_limiter:
            start_time = monotonic()
            logger.debug("Acquiring rate limiter")
            self._rate_limiter.acquire()
            wait_time = monotonic() - start_time

            if wait_time > 0.001:  # Only log if we actually waited
                logger.debug(f"Rate limiter throttled request | wait_seconds={wait_time:.3f}")
                log_rate_limit(wait_time)

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> CurlResponse:
        """Make a GET request with retry and rate limiting.

        Args:
            endpoint: The API endpoint (relative to BASE_URL).
            params: Optional query parameters.

        Returns:
            The response object.

        Raises:
            AuthenticationError: If session token is invalid.
            RateLimitError: If rate limit is exceeded.
            CloudflareBlockError: If Cloudflare blocks the request.
            PerplexityError: For other errors.
        """

        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint

        logger.debug(f"GET request initiated | endpoint={endpoint} url={url} params={params}")
        log_request("GET", url, params=params)

        # Create retry wrapper for this specific call
        retryable_exceptions = (RateLimitError, CloudflareBlockError, ConnectionError, TimeoutError)

        @create_retry_decorator(self._retry_config, retryable_exceptions, self._on_retry)
        def _do_get() -> CurlResponse:
            self._throttle()

            request_start = monotonic()
            logger.debug(f"Executing GET request | url={url}")

            try:
                response = self._session.get(url, params=params)
                elapsed_ms = (monotonic() - request_start) * 1000

                logger.debug(
                    f"GET response received | "
                    f"status_code={response.status_code} "
                    f"elapsed_ms={elapsed_ms:.2f} "
                    f"content_length={len(response.content) if hasattr(response, 'content') else 'unknown'}"
                )
                log_response(
                    "GET",
                    url,
                    response.status_code,
                    elapsed_ms=elapsed_ms,
                    content_length=len(response.content) if hasattr(response, "content") else None,
                )

                self._check_cloudflare(response)
                response.raise_for_status()

                logger.debug(f"GET request successful | endpoint={endpoint}")
                return response
            except Exception as error:
                elapsed_ms = (monotonic() - request_start) * 1000
                logger.debug(
                    f"GET request failed | "
                    f"endpoint={endpoint} "
                    f"elapsed_ms={elapsed_ms:.2f} "
                    f"error_type={type(error).__name__} "
                    f"error={error}"
                )

                if isinstance(error, (CloudflareBlockError, RateLimitError)):
                    raise

                self._handle_error(error, f"GET {endpoint}: ")

                # Never reached but satisfies type checker
                raise error

        return _do_get()

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> CurlResponse:
        """Make a POST request with retry and rate limiting.

        Args:
            endpoint: The API endpoint (relative to BASE_URL).
            json: JSON data to send.
            stream: Whether to stream the response.

        Returns:
            The response object.

        Raises:
            AuthenticationError: If session token is invalid.
            RateLimitError: If rate limit is exceeded.
            CloudflareBlockError: If Cloudflare blocks the request.
            PerplexityError: For other errors.
        """

        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint
        body_size = len(str(json)) if json else 0

        logger.debug(f"POST request initiated | endpoint={endpoint} url={url} stream={stream} body_size={body_size}")
        log_request("POST", url, body_size=body_size)

        retryable_exceptions = (RateLimitError, CloudflareBlockError, ConnectionError, TimeoutError)

        @create_retry_decorator(self._retry_config, retryable_exceptions, self._on_retry)
        def _do_post() -> CurlResponse:
            self._throttle()

            request_start = monotonic()
            logger.debug(f"Executing POST request | url={url} stream={stream}")

            try:
                response = self._session.post(url, json=json, stream=stream)
                elapsed_ms = (monotonic() - request_start) * 1000

                logger.debug(
                    f"POST response received | "
                    f"status_code={response.status_code} "
                    f"elapsed_ms={elapsed_ms:.2f} "
                    f"stream={stream}"
                )
                log_response("POST", url, response.status_code, elapsed_ms=elapsed_ms)

                self._check_cloudflare(response)
                response.raise_for_status()

                logger.debug(f"POST request successful | endpoint={endpoint}")
                return response
            except Exception as error:
                elapsed_ms = (monotonic() - request_start) * 1000
                logger.debug(
                    f"POST request failed | "
                    f"endpoint={endpoint} "
                    f"elapsed_ms={elapsed_ms:.2f} "
                    f"error_type={type(error).__name__} "
                    f"error={error}"
                )

                if isinstance(error, (CloudflareBlockError, RateLimitError)):
                    raise error

                self._handle_error(error, f"POST {endpoint}: ")

                # Never reached but satisfies type checker
                raise error

        return _do_post()

    def stream_lines(self, endpoint: str, json: dict[str, Any]) -> Generator[bytes, None, None]:
        """Make a streaming POST request and yield lines.

        Args:
            endpoint: The API endpoint.
            json: JSON data to send.

        Yields:
            Response lines as bytes.

        Raises:
            AuthenticationError: If session token is invalid.
            RateLimitError: If rate limit is exceeded.
            CloudflareBlockError: If Cloudflare blocks the request.
            PerplexityError: For other errors.
        """

        logger.debug(f"Starting streaming request | endpoint={endpoint}")

        response = self.post(endpoint, json=json, stream=True)
        lines_count = 0

        try:
            logger.debug("Iterating stream lines")

            for line in response.iter_lines():
                lines_count += 1
                yield line

            logger.debug(f"Stream completed | total_lines={lines_count}")
        finally:
            response.close()
            logger.debug(f"Stream response closed | lines_yielded={lines_count}")

    def init_search(self, query: str) -> None:
        """Initialize a search session.

        This is required before making a prompt request.

        Args:
            query: The search query.
        """

        logger.debug(f"Initializing search session | query_length={len(query)} query_preview={query[:50]}...")
        self.get(ENDPOINT_SEARCH_INIT, params={"q": query})
        logger.debug("Search session initialized successfully")

    def stream_ask(self, payload: dict[str, Any]) -> Generator[bytes, None, None]:
        """Stream a prompt request to the ask endpoint.

        Args:
            payload: The request payload.

        Yields:
            Response lines as bytes.
        """

        logger.debug(f"Streaming ask request | payload_keys={list(payload.keys())}")
        yield from self.stream_lines(ENDPOINT_ASK, json=payload)

    def close(self) -> None:
        """Close the HTTP session."""

        logger.debug("Closing HTTP client")
        self._session.close()
        logger.debug("HTTP client closed successfully")

    def __enter__(self) -> HTTPClient:
        logger.debug("Entering HTTPClient context manager")
        return self

    def __exit__(self, *args: Any) -> None:
        logger.debug("Exiting HTTPClient context manager")
        self.close()
