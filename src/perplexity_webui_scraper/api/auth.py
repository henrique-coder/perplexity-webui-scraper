"""Authentication helpers for the API server.

``extract_token()`` validates the ``Authorization: Bearer`` header.
``ClientPool`` maintains a per-token cache of ``Perplexity`` client instances
to avoid recreating HTTP sessions on every request.
"""

from __future__ import annotations

from fastapi import HTTPException

from perplexity_webui_scraper import Perplexity
from perplexity_webui_scraper._internal.constants import AUTH_BEARER_PREFIX
from perplexity_webui_scraper.config.client import ClientConfig


def extract_token(authorization: str | None) -> str:
    """Extract the raw session token from the ``Authorization: Bearer`` header.

    Args:
        authorization: Raw value of the ``Authorization`` header.

    Returns:
        The session token string (everything after ``"Bearer "``).

    Raises:
        HTTPException: 401 if the header is missing, not ``Bearer``, or empty.
    """
    if not authorization or not authorization.startswith(AUTH_BEARER_PREFIX):
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing or invalid Authorization header. "
                "Pass your Perplexity session token as: "
                "Authorization: Bearer <token>"
            ),
        )

    token = authorization[len(AUTH_BEARER_PREFIX) :]

    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is empty.")

    return token


class ClientPool:
    """Per-token cache of :class:`~perplexity_webui_scraper.Perplexity` client instances.

    Avoids recreating the curl-cffi session (and its rate limiter) on every
    API request.  Clients are keyed by their session token and never evicted
    — tokens are long-lived relative to server uptime.

    Usage::

        pool = ClientPool()
        client = pool.get_or_create("my-session-token")
    """

    def __init__(self) -> None:
        self._clients: dict[str, Perplexity] = {}

    def get_or_create(self, token: str) -> Perplexity:
        """Return an existing or newly created client for *token*.

        Args:
            token: The Perplexity session token.

        Returns:
            A :class:`~perplexity_webui_scraper.Perplexity` instance.
        """
        if token not in self._clients:
            self._clients[token] = Perplexity(token, config=ClientConfig())

        return self._clients[token]
