"""Authentication helpers for the API server.

``extract_token()`` validates the ``Authorization`` header containing a session-cookie pair.
``ClientPool`` maintains a per-credential cache of ``Perplexity`` client instances
to avoid recreating HTTP sessions on every request.
"""

from __future__ import annotations

from collections import OrderedDict
from hmac import compare_digest
from threading import Lock
from time import monotonic

from fastapi import HTTPException

from perplexity_webui_scraper import Perplexity
from perplexity_webui_scraper._internal.constants import AUTH_BEARER_PREFIX
from perplexity_webui_scraper._internal.exceptions import SessionTokenError
from perplexity_webui_scraper.auth.cookies import parse_session_credential, serialize_session_credential
from perplexity_webui_scraper.config.client import ClientConfig


def _canonical_session_token(token: str) -> str:
    """Normalize raw and compact credentials to one canonical cookie pair."""
    return serialize_session_credential(parse_session_credential(token))


def extract_token(authorization: str | None) -> str:
    """Extract the UUID-suffixed cookie pair from Authorization.

    Args:
        authorization: Raw value of the ``Authorization`` header.

    Returns:
        The full account-scoped cookie pair (everything after ``"Bearer "``).

    Raises:
        HTTPException: 401 if the header is missing, not ``Bearer``, or empty.
    """
    if not authorization or not authorization.startswith(AUTH_BEARER_PREFIX):
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing or invalid Authorization header. "
                "Pass the full account-scoped cookie pair as: "
                "Authorization: Bearer __Secure-pplx.session.<account UUID>=value"
            ),
        )

    token = authorization[len(AUTH_BEARER_PREFIX) :]

    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is empty.")

    try:
        return serialize_session_credential(parse_session_credential(token))
    except SessionTokenError:
        raise HTTPException(status_code=401, detail="Invalid Perplexity session credential.") from None


def resolve_session_token(
    authorization: str | None,
    api_key: str | None,
    default_session_token: str | None,
    configured_api_key: str | None,
) -> str:
    """Authenticate a gateway request and resolve its upstream Perplexity credential.

    When the server has a configured upstream token, a separate gateway key is
    mandatory on every request. A caller may optionally supply its own
    account-scoped session-cookie pair to override the configured credential.
    """
    if default_session_token and not configured_api_key:
        raise HTTPException(status_code=503, detail="Server default credentials are misconfigured.")

    if configured_api_key and not compare_digest(api_key or "", configured_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid gateway API key.")

    if authorization:
        return extract_token(authorization)

    if default_session_token:
        try:
            return serialize_session_credential(parse_session_credential(default_session_token))
        except SessionTokenError:
            raise HTTPException(status_code=503, detail="Server default credentials are invalid.") from None

    raise HTTPException(
        status_code=401,
        detail=(
            "Missing or invalid Authorization header. Pass the full account-scoped cookie pair as: "
            "Authorization: Bearer __Secure-pplx.session.<account UUID>=value"
        ),
    ) from None


class ClientPool:
    """Per-credential cache of :class:`~perplexity_webui_scraper.Perplexity` client instances.

    Avoids recreating the curl-cffi session and rate limiter for every API
    request. Clients are keyed by session-cookie pair and remain cached for the
    lifetime of the process.

    Usage::

        pool = ClientPool()
        client = pool.get_or_create("__Secure-pplx.session.<account UUID>=value")
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
        """Remove and close client references that have been idle beyond TTL."""
        stale_tokens = [
            token for token, (_client, last_access) in self._clients.items() if now - last_access > self._ttl_seconds
        ]

        for token in stale_tokens:
            stale_client, _last_access = self._clients.pop(token)
            stale_client.close()

    def get_or_create(self, token: str) -> Perplexity:
        """Return an existing or newly created client for *token*.

        Args:
            token: The Perplexity session token.

        Returns:
            A :class:`~perplexity_webui_scraper.Perplexity` instance.
        """
        canonical_token = _canonical_session_token(token)
        with self._lock:
            now = monotonic()
            self._evict_stale(now)
            cached = self._clients.get(canonical_token)

            if cached is not None:
                self._clients.move_to_end(canonical_token)
                self._clients[canonical_token] = (cached[0], now)

                return cached[0]

            client = Perplexity(canonical_token, config=ClientConfig())
            self._clients[canonical_token] = (client, now)

            if len(self._clients) > self._max_clients:
                _evicted_token, (evicted_client, _last_access) = self._clients.popitem(last=False)
                evicted_client.close()

            return client
