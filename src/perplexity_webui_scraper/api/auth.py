"""Authentication helpers for the API server.

``extract_token()`` validates the ``Authorization: Bearer`` header.
``ClientPool`` maintains a per-token cache of ``Perplexity`` client instances
to avoid recreating HTTP sessions on every request.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from time import monotonic

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

    Avoids recreating the curl-cffi session and rate limiter for every API
    request. Clients are keyed by session token and remain cached for the
    lifetime of the process.

    Usage::

        pool = ClientPool()
        client = pool.get_or_create("my-session-token")
    """

    def __init__(self, max_clients: int = 128, ttl_seconds: float = 30 * 60) -> None:
        if max_clients < 1:
            raise ValueError("max_clients must be at least one")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        self._clients: OrderedDict[str, tuple[Perplexity, float]] = OrderedDict()
        self._max_clients = max_clients
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()

    def _evict_stale(self, now: float) -> None:
        """Remove client references that have been idle beyond the configured TTL."""
        stale_tokens = [
            token for token, (_client, last_access) in self._clients.items() if now - last_access > self._ttl_seconds
        ]

        for token in stale_tokens:
            self._clients.pop(token)

    def get_or_create(self, token: str) -> Perplexity:
        """Return an existing or newly created client for *token*.

        Args:
            token: The Perplexity session token.

        Returns:
            A :class:`~perplexity_webui_scraper.Perplexity` instance.
        """
        with self._lock:
            now = monotonic()
            self._evict_stale(now)
            cached = self._clients.get(token)

            if cached is not None:
                self._clients.move_to_end(token)
                self._clients[token] = (cached[0], now)

                return cached[0]

            client = Perplexity(token, config=ClientConfig())
            self._clients[token] = (client, now)

            if len(self._clients) > self._max_clients:
                self._clients.popitem(last=False)

            return client

    def touch(self, token: str, client: Perplexity) -> None:
        """Refresh TTL after a request only if *client* remains cached."""
        with self._lock:
            cached = self._clients.get(token)

            if cached is None or cached[0] is not client:
                return

            self._clients[token] = (client, monotonic())
            self._clients.move_to_end(token)
