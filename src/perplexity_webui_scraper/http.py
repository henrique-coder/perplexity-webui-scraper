"""HTTP client wrapper for Perplexity API requests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from curl_cffi.requests import Response as CurlResponse
from curl_cffi.requests import Session

from .constants import (
    API_BASE_URL,
    DEFAULT_HEADERS,
    ENDPOINT_ASK,
    ENDPOINT_SEARCH_INIT,
    SESSION_COOKIE_NAME,
)
from .exceptions import AuthenticationError, PerplexityError, RateLimitError
from .limits import DEFAULT_TIMEOUT


class HTTPClient:
    """HTTP client wrapper with error handling for Perplexity API.

    Provides a unified interface for making HTTP requests with automatic
    error handling and response processing.
    """

    __slots__ = ("_session",)

    def __init__(
        self,
        session_token: str,
        timeout: int = DEFAULT_TIMEOUT,
        impersonate: str = "chrome",
    ) -> None:
        """Initialize the HTTP client."""

        headers: dict[str, str] = {
            **DEFAULT_HEADERS,
            "Referer": f"{API_BASE_URL}/",
            "Origin": API_BASE_URL,
        }
        cookies: dict[str, str] = {SESSION_COOKIE_NAME: session_token}
        self._session: Session = Session(
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            impersonate=impersonate,
        )

    def _handle_error(self, error: Exception, context: str = "") -> None:
        """Handle HTTP errors and raise appropriate custom exceptions.

        Args:
            error: The original exception.
            context: Additional context for the error message.

        Raises:
            AuthenticationError: If status code is 403.
            RateLimitError: If status code is 429.
            PerplexityError: For other HTTP errors.
        """

        status_code = None

        if hasattr(error, "response") and error.response is not None:
            status_code = getattr(error.response, "status_code", None)

        if status_code == 403:
            raise AuthenticationError() from error
        elif status_code == 429:
            raise RateLimitError() from error
        elif status_code is not None:
            raise PerplexityError(f"{context}HTTP {status_code}: {str(error)}", status_code=status_code) from error
        else:
            raise PerplexityError(f"{context}{str(error)}") from error

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> CurlResponse:
        """Make a GET request.

        Args:
            endpoint: The API endpoint (relative to BASE_URL).
            params: Optional query parameters.

        Returns:
            The response object.

        Raises:
            AuthenticationError: If session token is invalid.
            RateLimitError: If rate limit is exceeded.
            PerplexityError: For other errors.
        """

        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint

        try:
            response = self._session.get(url, params=params)
            response.raise_for_status()
            return response
        except Exception as e:
            self._handle_error(e, f"GET {endpoint}: ")

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> CurlResponse:
        """Make a POST request.

        Args:
            endpoint: The API endpoint (relative to BASE_URL).
            json: JSON data to send.
            stream: Whether to stream the response.

        Returns:
            The response object.

        Raises:
            AuthenticationError: If session token is invalid.
            RateLimitError: If rate limit is exceeded.
            PerplexityError: For other errors.
        """

        url = f"{API_BASE_URL}{endpoint}" if endpoint.startswith("/") else endpoint

        try:
            response = self._session.post(url, json=json, stream=stream)
            response.raise_for_status()
            return response
        except Exception as e:
            self._handle_error(e, f"POST {endpoint}: ")

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
            PerplexityError: For other errors.
        """

        response = self.post(endpoint, json=json, stream=True)

        try:
            yield from response.iter_lines()
        finally:
            response.close()

    def init_search(self, query: str) -> None:
        """Initialize a search session.

        This is required before making a prompt request.

        Args:
            query: The search query.
        """

        self.get(ENDPOINT_SEARCH_INIT, params={"q": query})

    def stream_ask(self, payload: dict[str, Any]) -> Generator[bytes, None, None]:
        """Stream a prompt request to the ask endpoint.

        Args:
            payload: The request payload.

        Yields:
            Response lines as bytes.
        """

        yield from self.stream_lines(ENDPOINT_ASK, json=payload)

    def close(self) -> None:
        """Close the HTTP session."""

        self._session.close()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
