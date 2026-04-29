"""Resilience utilities: rate limiting and retry logic."""

from __future__ import annotations

from random import choice
from threading import Lock
from time import monotonic, sleep
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ConfigDict


if TYPE_CHECKING:
    from collections.abc import Callable

    from curl_cffi.requests import BrowserTypeLiteral


T = TypeVar("T")

BROWSER_PROFILES: tuple[BrowserTypeLiteral, ...] = (
    "chrome",
    "chrome110",
    "chrome116",
    "chrome119",
    "chrome120",
    "chrome123",
    "chrome124",
    "chrome131",
    "edge99",
    "edge101",
    "safari15_3",
    "safari15_5",
    "safari17_0",
    "safari17_2_ios",
)


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""

    model_config = ConfigDict(frozen=True)

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.5


class RateLimiter:
    """Token bucket rate limiter."""

    __slots__ = ("_last_request", "_lock", "requests_per_second")

    def __init__(self, requests_per_second: float = 0.5) -> None:
        self.requests_per_second = requests_per_second
        self._last_request: float = 0.0
        self._lock = Lock()

    def acquire(self) -> None:
        """Wait until a request can be made within rate limits."""

        with self._lock:
            now = monotonic()
            min_interval = 1.0 / self.requests_per_second

            if self._last_request > 0:
                elapsed = now - self._last_request
                wait_time = min_interval - elapsed

                if wait_time > 0:
                    sleep(wait_time)

            self._last_request = monotonic()


def get_random_browser_profile() -> BrowserTypeLiteral:
    """Get a random browser profile for fingerprint rotation."""

    return choice(BROWSER_PROFILES)


def retry_with_backoff(
    fn: Callable[[], T],
    config: RetryConfig,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
    retryable: tuple[type[BaseException], ...] = (),
) -> T:
    """Execute *fn* with exponential-backoff retry.

    Args:
        fn: Zero-argument callable to execute.
        config: Retry configuration.
        on_retry: Optional callback invoked before each retry with (attempt, exception, wait_seconds).
        retryable: Exception types that trigger a retry.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception if all attempts are exhausted.
    """

    last_exc: BaseException | None = None
    max_attempts = config.max_retries + 1

    for attempt in range(1, max_attempts + 1):
        exc: BaseException | None = None

        try:
            return fn()
        except BaseException as _exc:
            exc = _exc

        if exc is not None:
            if retryable and not isinstance(exc, retryable):
                raise exc

            last_exc = exc

            if attempt >= max_attempts:
                break

            delay = min(config.base_delay * (2 ** (attempt - 1)), config.max_delay)
            jitter_amount = delay * config.jitter
            wait = max(0.0, delay + jitter_amount * (2 * (monotonic() % 1) - 1))

            if on_retry is not None:
                on_retry(attempt, exc, wait)

    if last_exc is not None:
        raise last_exc

    raise RuntimeError("Retry loop exhausted without raising an exception")
