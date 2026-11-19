"""Authentication helpers for the API server.

``extract_token()`` validates the ``Authorization`` header containing a session-cookie pair.
``ClientPool`` maintains a per-credential cache of ``Perplexity`` client instances
to avoid recreating HTTP sessions on every request.
"""

from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256
from hmac import compare_digest
from logging import getLogger
from os import environ
from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING

from fastapi import HTTPException

from perplexity_webui_scraper import Perplexity
from perplexity_webui_scraper._internal.constants import AUTH_BEARER_PREFIX
from perplexity_webui_scraper._internal.exceptions import SessionTokenError
from perplexity_webui_scraper.auth.cookies import parse_session_credential, serialize_session_credential
from perplexity_webui_scraper.config.client import ClientConfig


if TYPE_CHECKING:
    from perplexity_webui_scraper.core.account import AccountTier


_logger = getLogger("uvicorn.error")
_BEARER_SCHEME = AUTH_BEARER_PREFIX.strip().casefold()
_MISSING_AUTH_DETAIL = (
    "Missing or invalid Authorization header. "
    "Pass the full account-scoped cookie pair as: "
    "Authorization: Bearer __Secure-pplx.session.<account UUID>=value"
)


def _canonical_session_token(token: str) -> str:
    """Normalize raw and compact credentials to one canonical cookie pair."""
    return serialize_session_credential(parse_session_credential(token))


def _parse_bearer_header(authorization: str | None) -> tuple[bool, str]:
    """Parse a Bearer header case-insensitively without mutating the token."""
    if not authorization:
        return False, ""

    stripped = authorization.strip()

    if not stripped:
        return False, ""

    parts = stripped.split(None, 1)

    if parts[0].casefold() != _BEARER_SCHEME:
        return False, ""

    if len(parts) == 1:
        return True, ""

    return True, parts[1].strip()


def _validate_default_token(default_session_token: str) -> str:
    """Validate and canonicalize the configured server-default credential."""
    try:
        return _canonical_session_token(default_session_token)
    except SessionTokenError:
        raise HTTPException(status_code=503, detail="Server default credentials are invalid.") from None


def extract_token(authorization: str | None) -> str:
    """Extract and validate a Perplexity credential from Authorization.

    Args:
        authorization: Raw value of the ``Authorization`` header.

    Returns:
        The canonical account-scoped session-cookie pair.

    Raises:
        HTTPException: 401 if the header is missing, not ``Bearer``, empty, or malformed.
    """
    is_bearer, token = _parse_bearer_header(authorization)

    if not is_bearer:
        _logger.warning("Rejected API request (401): missing or invalid Authorization header")
        raise HTTPException(status_code=401, detail=_MISSING_AUTH_DETAIL)

    if not token:
        _logger.warning("Rejected API request (401): empty Bearer token")
        raise HTTPException(status_code=401, detail="Bearer token is empty.")

    try:
        return _canonical_session_token(token)
    except SessionTokenError:
        _logger.warning("Rejected API request (401): malformed Perplexity session credential")
        raise HTTPException(status_code=401, detail="Invalid Perplexity session credential.") from None


def resolve_session_token(
    authorization: str | None,
    api_key: str | None,
    default_session_token: str | None,
    configured_api_key: str | None,
) -> str:
    """Authenticate a request and resolve its upstream Perplexity credential.

    When the server has a configured upstream token, a separate gateway key is
    mandatory on every request via ``X-API-Key`` or ``Authorization: Bearer``.
    Combined with a valid ``X-API-Key``, ``Authorization: Bearer`` supplies a
    caller-specific Perplexity credential that overrides the server default.
    """
    if default_session_token and not configured_api_key:
        raise HTTPException(status_code=503, detail="Server default credentials are misconfigured.")

    if configured_api_key:
        if api_key:
            if not compare_digest(api_key, configured_api_key):
                _logger.warning("Rejected API request (401): invalid gateway API key in X-API-Key")
                raise HTTPException(status_code=401, detail="Missing or invalid gateway API key.")

            if authorization:
                return extract_token(authorization)

            if default_session_token:
                return _validate_default_token(default_session_token)

            _logger.warning("Rejected API request (401): missing upstream Perplexity credential")
            raise HTTPException(status_code=401, detail=_MISSING_AUTH_DETAIL)

        is_bearer, bearer_value = _parse_bearer_header(authorization)

        if is_bearer and bearer_value and compare_digest(bearer_value, configured_api_key):
            if default_session_token:
                return _validate_default_token(default_session_token)

            _logger.warning("Rejected API request (401): missing upstream Perplexity credential")
            raise HTTPException(status_code=401, detail=_MISSING_AUTH_DETAIL)

        _logger.warning("Rejected API request (401): missing or invalid gateway API key")
        raise HTTPException(status_code=401, detail="Missing or invalid gateway API key.")

    if authorization:
        return extract_token(authorization)

    if api_key:
        try:
            return _canonical_session_token(api_key.strip())
        except SessionTokenError:
            _logger.warning("Rejected API request (401): malformed Perplexity session credential in X-API-Key")
            raise HTTPException(status_code=401, detail="Invalid Perplexity session credential.") from None

    _logger.warning("Rejected API request (401): missing Authorization or X-API-Key header")
    raise HTTPException(status_code=401, detail=_MISSING_AUTH_DETAIL) from None


def resolve_upstream_token(authorization: str | None, x_api_key: str | None) -> str:
    """Require gateway auth when configured, then resolve caller or server-default token."""
    return resolve_session_token(
        authorization,
        x_api_key,
        environ.get("PERPLEXITY_SESSION_TOKEN"),
        environ.get("PERPLEXITY_API_KEY"),
    )


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


class AccountTierCache:
    """Bounded, per-credential in-memory TTL cache for resolved account tiers."""

    def __init__(self, max_entries: int = 128, ttl_seconds: float = 10 * 60) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least one")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        self._entries: OrderedDict[str, tuple[AccountTier, float]] = OrderedDict()
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()

    @staticmethod
    def _key(token: str) -> str:
        """Hash canonical credentials so raw session tokens are never stored as cache keys."""
        canonical = _canonical_session_token(token)

        return sha256(canonical.encode("utf-8")).hexdigest()

    def _evict_stale(self, now: float) -> None:
        """Remove cached tier entries whose TTL has elapsed."""
        stale_keys = [key for key, (_tier, stored_at) in self._entries.items() if now - stored_at > self._ttl_seconds]

        for key in stale_keys:
            self._entries.pop(key)

    def get(self, token: str) -> AccountTier | None:
        """Return a non-expired cached account tier, or ``None`` on cache miss."""
        key = self._key(token)

        with self._lock:
            now = monotonic()
            self._evict_stale(now)
            cached = self._entries.get(key)

            if cached is None:
                return None

            self._entries.move_to_end(key)

            return cached[0]

    def set(self, token: str, tier: AccountTier) -> None:
        """Cache *tier* for *token* for the configured TTL."""
        key = self._key(token)

        with self._lock:
            now = monotonic()
            self._evict_stale(now)
            self._entries[key] = (tier, now)
            self._entries.move_to_end(key)

            if len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached account tiers."""
        with self._lock:
            self._entries.clear()


client_pool = ClientPool()
account_tier_cache = AccountTierCache()
