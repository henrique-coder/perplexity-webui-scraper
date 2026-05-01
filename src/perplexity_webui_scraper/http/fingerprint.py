"""Browser fingerprint profiles for curl-cffi impersonation.

The ``BROWSER_PROFILES`` tuple lists all valid ``BrowserTypeLiteral`` values
that are suitable for fingerprint rotation.  ``get_random_browser_profile()``
selects one at random for each retry attempt, making session rotation
unpredictable to bot-detection heuristics.
"""

from __future__ import annotations

from random import choice
from typing import TYPE_CHECKING, Final


if TYPE_CHECKING:
    from curl_cffi.requests import BrowserTypeLiteral


BROWSER_PROFILES: Final[tuple[BrowserTypeLiteral, ...]] = (
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
)
"""All browser profiles eligible for fingerprint rotation."""


def get_random_browser_profile() -> BrowserTypeLiteral:
    """Return a randomly selected browser profile from ``BROWSER_PROFILES``.

    Returns:
        A ``BrowserTypeLiteral`` value compatible with curl-cffi's
        ``Session(impersonate=...)``.
    """
    return choice(BROWSER_PROFILES)  # type: ignore[return-value]
