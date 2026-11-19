"""All magic constants for the Perplexity internal API.

This is the single source of truth for every URL, endpoint path, header key,
cookie name, numeric limit, and compiled regex pattern used across the project.
No other module may define these values independently.
"""

from __future__ import annotations

from re import Pattern, compile
from typing import Final


# ---------------------------------------------------------------------------
# WebUI request metadata
# ---------------------------------------------------------------------------

API_VERSION: Final[str] = "2.18"
"""Current API version used by Perplexity WebUI."""

API_SOURCE: Final[str] = "default"
"""WebUI API source/client identifier observed in current requests."""

API_BASE_URL: Final[str] = "https://www.perplexity.ai"
"""Base URL for all API requests."""

# ---------------------------------------------------------------------------
# Endpoint paths (relative to API_BASE_URL)
# ---------------------------------------------------------------------------

ENDPOINT_ASK: Final[str] = "/rest/sse/perplexity_ask"
"""SSE endpoint for sending prompts."""

ENDPOINT_SEARCH_INIT: Final[str] = "/search/new"
"""Endpoint to initialize a search session (required before /ask)."""

ENDPOINT_UPLOAD: Final[str] = "/rest/uploads/batch_create_upload_urls"
"""Endpoint for file upload URL generation."""

ENDPOINT_AUTH_CSRF: Final[str] = "/api/auth/csrf"
"""Endpoint to obtain a CSRF token for authentication."""

ENDPOINT_AUTH_SIGNIN: Final[str] = "/api/auth/signin/email"
"""Endpoint to send an email verification code."""

ENDPOINT_AUTH_SESSION: Final[str] = "/api/auth/session"
"""Endpoint to read the authenticated account session."""

ENDPOINT_USER_SETTINGS: Final[str] = "/rest/user/settings"
"""Endpoint to read authenticated user settings and subscription metadata."""

ENDPOINT_AUTH_OTP_REDIRECT: Final[str] = "/api/auth/otp-redirect-link"
"""Endpoint to convert an OTP code into a redirect URL."""

ENDPOINT_AUTH_TOTP_CHALLENGE_VERIFY: Final[str] = "/api/auth/totp/challenge-verify"
"""Endpoint to verify a TOTP code during 2FA challenge."""

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

SESSION_COOKIE_PREFIX: Final[str] = "__Secure-pplx.session."
"""Prefix of Perplexity's account-scoped session-cookie name."""

SESSION_TOKEN_PREFIX: Final[str] = "wsk_"
"""Prefix for compact session tokens."""

SESSION_TOKEN_VERSION: Final[int] = 1
"""Current compact session-token protocol version."""

SESSION_TOKEN_BASE62_ALPHABET: Final[str] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
"""Alphabet used for compact-token integer encoding."""

SESSION_TOKEN_SHAKE_SALT: Final[bytes] = b"pplx-shake-v1"
"""Public domain-separation salt for the v1 SHAKE mask."""

SESSION_TOKEN_BLAKE2S_PERSON: Final[bytes] = b"pplx-v1"
"""BLAKE2s personalization prefix for the compact-token checksum."""

SESSION_TOKEN_SENTINEL: Final[int] = 0b1000
"""Sentinel bit in the high nibble of compact-token headers."""

SESSION_TOKEN_JWE_HEADER: Final[str] = "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0"
"""Encoded protected header for direct A256GCM JWE values."""

AUTH_BEARER_PREFIX: Final[str] = "Bearer "
"""Prefix for Authorization: Bearer header values."""

# ---------------------------------------------------------------------------
# Default HTTP headers (shared across all sessions)
# ---------------------------------------------------------------------------

DEFAULT_HEADERS: Final[dict[str, str]] = {
    "Accept": "text/event-stream, application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "Pragma": "no-cache",
    "Referer": f"{API_BASE_URL}/",
    "Origin": API_BASE_URL,
}
"""Default HTTP headers required by the Perplexity API."""

# ---------------------------------------------------------------------------
# Request payload flags
# ---------------------------------------------------------------------------

SEND_BACK_TEXT: Final[bool] = False
"""Whether to receive full text in each streaming chunk (replace mode)."""

USE_SCHEMATIZED_API: Final[bool] = True
"""Whether to use the current schematized WebUI stream format."""

PROMPT_SOURCE: Final[str] = "user"
"""Source identifier for prompts."""

# ---------------------------------------------------------------------------
# File upload limits
# ---------------------------------------------------------------------------

MAX_FILES: Final[int] = 30
"""Maximum number of files per prompt."""

MAX_FILE_SIZE: Final[int] = 50 * 1024 * 1024
"""Maximum file size in bytes (50 MB)."""

# ---------------------------------------------------------------------------
# HTTP client defaults
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT: Final[int] = 60 * 60
"""Default request timeout in seconds (1 hour)."""

# ---------------------------------------------------------------------------
# Compiled regex patterns (compile once at module level)
# ---------------------------------------------------------------------------

CITATION_PATTERN: Final[Pattern[str]] = compile(r"\[(\d{1,2})\]")
"""Regex pattern for matching citation markers like [1], [2]."""

JSON_OBJECT_PATTERN: Final[Pattern[str]] = compile(r"^\{.*\}$")
"""Pattern to detect JSON object strings (single line)."""
