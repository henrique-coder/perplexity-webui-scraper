"""
Resilience utilities for HTTP requests.

Provides retry mechanisms, rate limiting, and Cloudflare bypass utilities
using the tenacity library for robust retry handling.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import random
from threading import Lock
import time
from typing import TYPE_CHECKING, Any, TypeVar

from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter


if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


# Browser profiles supported by curl_cffi for fingerprint rotation
BROWSER_PROFILES: tuple[str, ...] = (
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

# Cloudflare challenge detection markers
CLOUDFLARE_MARKERS: tuple[str, ...] = (
    "cf-ray",
    "cf-mitigated",
    "__cf_chl_",
    "Checking your browser",
    "Just a moment...",
    "cloudflare",
    "Enable JavaScript and cookies to continue",
    "challenge-platform",
)


@dataclass(slots=True)
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay between retries.
        jitter: Random jitter factor to add to delays (0-1).
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.5


@dataclass
class RateLimiter:
    """Token bucket rate limiter for throttling requests.

    Attributes:
        requests_per_second: Maximum requests allowed per second.
    """

    requests_per_second: float = 0.5
    _last_request: float = field(default=0.0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def acquire(self) -> None:
        """
        Wait until a request can be made within rate limits.
        """

        with self._lock:
            now = time.monotonic()
            min_interval = 1.0 / self.requests_per_second

            if self._last_request > 0:
                elapsed = now - self._last_request
                wait_time = min_interval - elapsed

                if wait_time > 0:
                    time.sleep(wait_time)

            self._last_request = time.monotonic()


def get_random_browser_profile() -> str:
    """Get a random browser profile for fingerprint rotation.

    Returns:
        A browser profile identifier compatible with curl_cffi.
    """

    return random.choice(BROWSER_PROFILES)


def is_cloudflare_challenge(response_text: str, headers: dict[str, Any] | None = None) -> bool:
    """Detect if a response is a Cloudflare challenge page.

    Args:
        response_text: The response body text.
        headers: Optional response headers.

    Returns:
        True if Cloudflare challenge markers are detected.
    """

    text_lower = response_text.lower()

    for marker in CLOUDFLARE_MARKERS:
        if marker.lower() in text_lower:
            return True

    if headers:
        for key in headers:
            key_lower = key.lower()

            if "cf-" in key_lower or "cloudflare" in key_lower:
                return True

    return False


def is_cloudflare_status(status_code: int) -> bool:
    """Check if status code indicates a potential Cloudflare block.

    Args:
        status_code: HTTP status code.

    Returns:
        True if status code is commonly used by Cloudflare challenges.
    """

    return status_code in (403, 503, 520, 521, 522, 523, 524, 525, 526)


def create_retry_decorator(
    config: RetryConfig,
    retryable_exceptions: tuple[type[Exception], ...],
    on_retry: Callable[[RetryCallState], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create a tenacity retry decorator with the given configuration.

    Args:
        config: Retry configuration.
        retryable_exceptions: Tuple of exception types to retry on.
        on_retry: Optional callback to execute on each retry.

    Returns:
        A retry decorator configured with the given settings.
    """

    return retry(
        stop=stop_after_attempt(config.max_retries + 1),
        wait=wait_exponential_jitter(
            initial=config.base_delay,
            max=config.max_delay,
            jitter=config.max_delay * config.jitter,
        ),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=on_retry,
        reraise=True,
    )
