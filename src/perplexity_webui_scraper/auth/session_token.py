"""Normalize raw Perplexity cookies and encode/decode compact session tokens."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from hashlib import blake2s, shake_128
from re import fullmatch
from urllib.parse import unquote
from uuid import RFC_4122, UUID

from perplexity_webui_scraper._internal.constants import (
    SESSION_COOKIE_PREFIX,
    SESSION_TOKEN_BASE62_ALPHABET,
    SESSION_TOKEN_BLAKE2S_PERSON,
    SESSION_TOKEN_JWE_HEADER,
    SESSION_TOKEN_PREFIX,
    SESSION_TOKEN_SENTINEL,
    SESSION_TOKEN_SHAKE_SALT,
    SESSION_TOKEN_VERSION,
)
from perplexity_webui_scraper._internal.exceptions import (
    CompactTokenAlignmentError,
    CompactTokenChecksumError,
    CompactTokenFormatError,
    CompactTokenTruncatedError,
    EmbeddedUUIDError,
    RawCookieFormatError,
    UnsupportedTokenVersionError,
)


MAX_COMPACT_TOKEN_LENGTH = 8192


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    """Validated account UUID and JWE cookie value used by session setup."""

    uuid: str
    cookie_value: str


def _normalize_input(token_input: str) -> str:
    if not isinstance(token_input, str):
        raise RawCookieFormatError("Session token must be text.")
    normalized = unquote(token_input.strip()).strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in "\"'":
        normalized = normalized[1:-1]
    return normalized


def _uuid_bytes(value: str) -> bytes:
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise RawCookieFormatError("Session cookie account UUID is malformed.") from exc

    if str(parsed) != value.lower() or parsed.version != 4 or parsed.variant != RFC_4122:
        raise RawCookieFormatError("Session cookie account UUID must be an RFC 4122 UUIDv4.")
    return parsed.bytes


def _decode_b64url(segment: str, expected_size: int | None = None) -> bytes:
    if not segment or fullmatch(r"[A-Za-z0-9_-]+", segment) is None:
        raise RawCookieFormatError("JWE Base64URL segment must use the unpadded URL-safe alphabet.")

    try:
        decoded = urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (ValueError, TypeError) as exc:
        raise RawCookieFormatError("JWE Base64URL segment is malformed.") from exc

    if urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != segment:
        raise RawCookieFormatError("Base64URL segment is not canonical.")
    if expected_size is not None and len(decoded) != expected_size:
        raise RawCookieFormatError("Base64URL segment has an invalid decoded size.")
    return decoded


def _encode_b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _parse_jwe(value: str) -> tuple[bytes, bytes, bytes]:
    segments = value.split(".")
    if len(segments) != 5 or segments[0] != SESSION_TOKEN_JWE_HEADER or segments[1] != "":
        raise ValueError("Session cookie must be a direct-encryption A256GCM JWE.")
    iv = _decode_b64url(segments[2], 12)
    ciphertext = _decode_b64url(segments[3])
    tag = _decode_b64url(segments[4], 16)
    return iv, ciphertext, tag


def _validate_raw_cookie_normalized(value: str) -> SessionCredentials:
    """Validate an already normalized raw UUID-suffixed session cookie."""
    if value.startswith(SESSION_COOKIE_PREFIX):
        value = value.removeprefix(SESSION_COOKIE_PREFIX)
    account_uuid, separator, cookie_value = value.partition("=")
    if not separator or not cookie_value:
        raise RawCookieFormatError("Expected an optional session cookie prefix, UUID, and non-empty JWE value.")

    uuid_bytes = _uuid_bytes(account_uuid)
    try:
        _parse_jwe(cookie_value)
    except ValueError as exc:
        raise RawCookieFormatError(str(exc)) from exc
    return SessionCredentials(uuid=str(UUID(bytes=uuid_bytes)), cookie_value=cookie_value)


def validate_raw_cookie(raw_input: str) -> SessionCredentials:
    """Validate a raw UUID-suffixed session cookie and return its components."""
    return _validate_raw_cookie_normalized(_normalize_input(raw_input))


def _base62_encode(number: int) -> str:
    alphabet = SESSION_TOKEN_BASE62_ALPHABET
    if number == 0:
        return alphabet[0]
    result = ""
    while number:
        number, remainder = divmod(number, len(alphabet))
        result = alphabet[remainder] + result
    return result


def _base62_decode(value: str) -> int:
    if not value or any(character not in SESSION_TOKEN_BASE62_ALPHABET for character in value):
        raise CompactTokenFormatError("Compact token contains invalid Base62 characters.")
    number = 0
    for character in value:
        number = number * 62 + SESSION_TOKEN_BASE62_ALPHABET.index(character)
    if _base62_encode(number) != value:
        raise CompactTokenFormatError("Compact token Base62 representation is not canonical.")
    return number


def _base62_decode_bytes(value: str) -> bytes:
    """Decode Base62, preserving the leading-zero bytes of the serialized header."""
    number = _base62_decode(value)
    return number.to_bytes((number.bit_length() + 7) // 8, "big")


def _checksum(payload: bytes, version: int) -> int:
    digest = blake2s(payload, digest_size=2, person=SESSION_TOKEN_BLAKE2S_PERSON + bytes([version])).digest()
    return int.from_bytes(digest, "big") & 0xFFF


def pack_session_token(raw_input: str) -> str:
    """Validate a raw session cookie or compact token and encode it in the compact v1 format."""
    credentials = resolve_session_token(raw_input)
    uuid_bytes = _uuid_bytes(credentials.uuid)
    iv, ciphertext, tag = _parse_jwe(credentials.cookie_value)
    payload = uuid_bytes + iv + tag + ciphertext
    version_nibble = SESSION_TOKEN_SENTINEL | (SESSION_TOKEN_VERSION & 0b0111)
    header_value = (version_nibble << 12) | _checksum(payload, SESSION_TOKEN_VERSION)
    header = header_value.to_bytes(2, "big")
    mask = shake_128(header + SESSION_TOKEN_SHAKE_SALT).digest(len(payload))
    obfuscated = bytes(left ^ right for left, right in zip(payload, mask, strict=True))
    return SESSION_TOKEN_PREFIX + _base62_encode(int.from_bytes(header + obfuscated, "big"))


def _unpack_session_token_normalized(value: str) -> SessionCredentials:
    """Decode and validate an already normalized compact v1 session token."""
    if len(value) > MAX_COMPACT_TOKEN_LENGTH:
        raise CompactTokenFormatError("Compact token exceeds maximum allowed length.")
    if not value.startswith(SESSION_TOKEN_PREFIX):
        raise CompactTokenFormatError("Compact token must start with the wsk_ prefix.")
    encoded = value[len(SESSION_TOKEN_PREFIX) :]
    binary = _base62_decode_bytes(encoded)
    if len(binary) < 2 + 16 + 12 + 16 + 1:
        raise CompactTokenTruncatedError("Compact token is truncated.")
    header = binary[:2]
    header_value = int.from_bytes(header, "big")
    version_nibble = header_value >> 12
    if version_nibble & SESSION_TOKEN_SENTINEL != SESSION_TOKEN_SENTINEL:
        raise CompactTokenAlignmentError(
            "Compact token sentinel check failed; the token may be truncated or misaligned."
        )
    version = version_nibble & 0b0111

    if version != SESSION_TOKEN_VERSION:
        raise UnsupportedTokenVersionError(f"Compact token protocol version {version} is unsupported.")
    obfuscated = binary[2:]
    mask = shake_128(header + SESSION_TOKEN_SHAKE_SALT).digest(len(obfuscated))
    payload = bytes(left ^ right for left, right in zip(obfuscated, mask, strict=True))
    if _checksum(payload, version) != (header_value & 0xFFF):
        raise CompactTokenChecksumError("Compact token checksum does not match its payload.")
    uuid_raw = payload[:16]
    embedded_uuid = UUID(bytes=uuid_raw)

    if embedded_uuid.version != 4 or embedded_uuid.variant != RFC_4122:
        raise EmbeddedUUIDError("Compact token does not contain an RFC 4122 UUIDv4.")
    iv, tag, ciphertext = payload[16:28], payload[28:44], payload[44:]
    cookie_value = (
        f"{SESSION_TOKEN_JWE_HEADER}..{_encode_b64url(iv)}.{_encode_b64url(ciphertext)}.{_encode_b64url(tag)}"
    )
    try:
        _parse_jwe(cookie_value)
    except ValueError as exc:
        raise RawCookieFormatError(f"Embedded JWE structure is invalid: {exc}") from exc
    return SessionCredentials(uuid=str(embedded_uuid), cookie_value=cookie_value)


def unpack_session_token(compact_token: str) -> SessionCredentials:
    """Decode a compact v1 token (or validate a raw cookie pair) into SessionCredentials."""
    return resolve_session_token(compact_token)


def resolve_session_token(token_input: str) -> SessionCredentials:
    """Resolve either compact or raw session credential input."""
    value = _normalize_input(token_input)
    if value.startswith(SESSION_TOKEN_PREFIX):
        return _unpack_session_token_normalized(value)
    return _validate_raw_cookie_normalized(value)
