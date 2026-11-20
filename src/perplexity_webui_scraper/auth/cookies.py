"""Parse Perplexity session-cookie names and credentials."""

from __future__ import annotations

from re import fullmatch
from typing import TYPE_CHECKING, NamedTuple, Protocol

from perplexity_webui_scraper._internal.constants import SESSION_COOKIE_PREFIX
from perplexity_webui_scraper._internal.exceptions import CredentialError
from perplexity_webui_scraper.auth.session_token import resolve_session_token


if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


_UUID_PATTERN = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


class CookieCredential(NamedTuple):
    """Cookie name and value required to construct an authenticated session."""

    name: str
    value: str


class _CookieJar(Protocol):
    def items(self) -> Iterator[tuple[str, str]]: ...


def parse_session_cookie_name(name: str) -> tuple[str, str | None] | None:
    """Return the supported base name and UUID suffix for a session cookie."""
    if not name.startswith(SESSION_COOKIE_PREFIX):
        return None

    account_id = name.removeprefix(SESSION_COOKIE_PREFIX)
    if fullmatch(_UUID_PATTERN, account_id):
        return SESSION_COOKIE_PREFIX.removesuffix("."), account_id

    return None


def extract_session_cookie(
    cookies: Mapping[str, str] | _CookieJar,
    active_account_id: str | None = None,
) -> CookieCredential | None:
    """Find the session cookie in a cookie jar without exposing its value."""
    cookie_items = list(cookies.items())
    candidates = [
        CookieCredential(name, value)
        for name, value in cookie_items
        if parse_session_cookie_name(name) is not None and value
    ]

    if not candidates:
        return None

    if active_account_id is not None:
        active_cookie_name = f"{SESSION_COOKIE_PREFIX}{active_account_id}"
        active_candidates = [item for item in candidates if item.name == active_cookie_name]

        if len(active_candidates) == 1:
            return active_candidates[0]
        if not active_candidates:
            raise CredentialError("The active Perplexity account has no matching session cookie.")
        raise CredentialError("Multiple UUID-suffixed Perplexity session cookies are ambiguous.")

    account_id_cookies = [value for name, value in cookie_items if name == "__Host-pplx-last-active-account"]
    if len(account_id_cookies) == 1:
        if not fullmatch(_UUID_PATTERN, account_id_cookies[0]):
            raise CredentialError("The active Perplexity account identifier is invalid.")

        active_cookie_name = f"{SESSION_COOKIE_PREFIX}{account_id_cookies[0]}"
        active_candidates = [item for item in candidates if item.name == active_cookie_name]

        if len(active_candidates) == 1:
            return active_candidates[0]
        if not active_candidates:
            raise CredentialError("The active Perplexity account has no matching session cookie.")
        raise CredentialError("Multiple UUID-suffixed Perplexity session cookies are ambiguous.")

    if len(candidates) == 1:
        return candidates[0]

    raise CredentialError("Multiple UUID-suffixed Perplexity session cookies are ambiguous.")


def parse_session_credential(value: str) -> CookieCredential:
    """Resolve a raw cookie pair or compact token to one canonical cookie pair."""
    credentials = resolve_session_token(value)
    return CookieCredential(f"{SESSION_COOKIE_PREFIX}{credentials.uuid}", credentials.cookie_value)


def serialize_session_credential(credential: CookieCredential) -> str:
    """Serialize a UUID-suffixed session cookie name and value unchanged."""
    if parse_session_cookie_name(credential.name) is None or not credential.value:
        raise CredentialError("Expected a UUID-suffixed Perplexity session cookie.")

    return f"{credential.name}={credential.value}"


__all__ = [
    "CookieCredential",
    "extract_session_cookie",
    "parse_session_cookie_name",
    "parse_session_credential",
    "serialize_session_credential",
]
