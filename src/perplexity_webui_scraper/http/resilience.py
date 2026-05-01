"""Retry and rate-limiting utilities for the HTTP layer."""

from __future__ import annotations

from threading import Lock
from time import monotonic, sleep
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ConfigDict


if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")


class RetryConfig(BaseModel):
    """Immutable configuration for exponential-backoff retry behaviour.

    Attributes:
        max_retries: Maximum number of retry attempts after the initial failure.
            Set to ``0`` to disable retries.
        base_delay: Initial backoff delay in seconds before the first retry.
            Doubles with each subsequent attempt (exponential backoff).
        max_delay: Upper cap on the backoff delay in seconds.  Prevents
            excessively long waits on later retry attempts.
        jitter: Jitter factor (0-1).  A fraction of the computed delay is
            added or subtracted randomly to avoid thundering-herd effects.
    """

    model_config = ConfigDict(frozen=True)

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.5


class RateLimiter:
    """Simple token-bucket rate limiter using a threading lock.

    Ensures that no more than ``requests_per_second`` requests are issued
    per second across all threads sharing this limiter instance.

    Attributes:
        requests_per_second: Maximum allowed request rate.
    """

    __slots__ = ("_last_request", "_lock", "requests_per_second")

    def __init__(self, requests_per_second: float = 0.5) -> None:
        self.requests_per_second = requests_per_second
        self._last_request: float = 0.0
        self._lock = Lock()

    def acquire(self) -> None:
        """Block the calling thread until a request slot is available.

        Uses a monotonic clock to compute the minimum interval between
        requests and sleeps if the interval has not elapsed yet.
        """
        with self._lock:
            now = monotonic()
            min_interval = 1.0 / self.requests_per_second

            if self._last_request > 0:
                elapsed = now - self._last_request
                wait_time = min_interval - elapsed

                if wait_time > 0:
                    sleep(wait_time)

            self._last_request = monotonic()


def retry_with_backoff[T](
    fn: Callable[[], T],
    config: RetryConfig,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
    retryable: tuple[type[BaseException], ...] = (),
) -> T:
    """Execute *fn* with exponential-backoff retry.

    Args:
        fn: Zero-argument callable to execute.
        config: :class:`RetryConfig` controlling retry behaviour.
        on_retry: Optional callback invoked **before** each retry with
            ``(attempt, exception, wait_seconds)``.  Use this to rotate
            sessions, log warnings, etc.
        retryable: Tuple of exception types that trigger a retry.  Any
            exception not in this tuple is re-raised immediately without
            retrying.  Pass an empty tuple to retry on any exception.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception raised by *fn* if all attempts are exhausted.
        ``RuntimeError`` if the loop exits unexpectedly without an exception.
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

            sleep(wait)

    if last_exc is not None:
        raise last_exc

    raise RuntimeError("Retry loop exhausted without raising an exception")
