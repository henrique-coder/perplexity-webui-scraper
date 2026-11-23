"""Offline tests for raw and compact Perplexity session credentials."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import blake2s, shake_128
from urllib.parse import quote
from uuid import UUID

from pytest import mark, raises

from perplexity_webui_scraper._internal.exceptions import (
    CompactTokenAlignmentError,
    CompactTokenChecksumError,
    CompactTokenFormatError,
    CompactTokenTruncatedError,
    CredentialError,
    EmbeddedUUIDError,
    PerplexityError,
    RawCookieFormatError,
    SessionTokenError,
    UnsupportedTokenVersionError,
)
from perplexity_webui_scraper.auth.cookies import CookieCredential, parse_session_credential
from perplexity_webui_scraper.auth.session_token import (
    SessionCredentials,
    pack_session_token,
    resolve_session_token,
    unpack_session_token,
    validate_raw_cookie,
)


STATIC_HEADER = "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0"
assert urlsafe_b64decode(STATIC_HEADER + "=" * (-len(STATIC_HEADER) % 4)) == b'{"alg":"dir","enc":"A256GCM"}'
SYNTHETIC_UUID = str(UUID("123e4567-e89b-42d3-a456-426614174000"))


def _b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _synthetic_raw(uuid_text: str = SYNTHETIC_UUID) -> str:
    iv = bytes(range(12))
    ciphertext = b"synthetic-ciphertext"
    tag = bytes(range(16, 32))
    return f"__Secure-pplx.session.{uuid_text}={STATIC_HEADER}..{_b64url(iv)}.{_b64url(ciphertext)}.{_b64url(tag)}"


def _make_compact(payload: bytes, version: int = 1, sentinel: bool = True) -> str:
    version_byte = (0b1000 if sentinel else 0) | (version & 0b0111)
    digest = blake2s(payload, digest_size=2, person=b"pplx-v1" + bytes([version])).digest()
    checksum = int.from_bytes(digest, "big") & 0xFFF
    header = ((version_byte << 12) | checksum).to_bytes(2, "big")
    mask = shake_128(header + b"pplx-shake-v1").digest(len(payload))
    return "wsk_" + _base62(int.from_bytes(header + bytes(a ^ b for a, b in zip(payload, mask, strict=True)), "big"))


def _base62(number: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return alphabet[0]
    encoded = ""
    while number:
        number, remainder = divmod(number, 62)
        encoded = alphabet[remainder] + encoded
    return encoded


def test_raw_cookie_validates_and_round_trips_through_compact_token() -> None:
    raw = _synthetic_raw()
    expected = SessionCredentials(uuid=SYNTHETIC_UUID, cookie_value=raw.split("=", 1)[1])

    assert validate_raw_cookie(raw) == expected
    assert parse_session_credential(raw) == CookieCredential(
        name=f"__Secure-pplx.session.{SYNTHETIC_UUID}",
        value=expected.cookie_value,
    )
    compact = pack_session_token(raw)
    assert compact.startswith("wsk_")
    assert unpack_session_token(compact) == expected
    assert resolve_session_token(compact) == expected


def test_raw_cookie_accepts_optional_prefix_and_normalizes_quoted_url_encoded_input() -> None:
    raw = _synthetic_raw().removeprefix("__Secure-pplx.session.")
    assert validate_raw_cookie(raw) == SessionCredentials(uuid=SYNTHETIC_UUID, cookie_value=raw.split("=", 1)[1])
    assert parse_session_credential(raw) == CookieCredential(
        name=f"__Secure-pplx.session.{SYNTHETIC_UUID}",
        value=raw.split("=", 1)[1],
    )
    quoted = quote(f'"{_synthetic_raw()}"', safe="")
    assert validate_raw_cookie(quoted) == validate_raw_cookie(_synthetic_raw())
    assert resolve_session_token(quoted) == validate_raw_cookie(_synthetic_raw())


@mark.parametrize(
    "raw",
    [
        "",
        "not-a-cookie",
        f"__Secure-pplx.session.{SYNTHETIC_UUID}=not-a-jwe",
        _synthetic_raw("123e4567-e89b-12d3-a456-426614174000"),
        _synthetic_raw().replace("..", "."),
        _synthetic_raw().replace("AAECAwQFBgcICQoL", "AAECAwQFBgcICQoL="),
    ],
)
def test_raw_cookie_rejects_malformed_values(raw: str) -> None:
    with raises(RawCookieFormatError, match=r"cookie|JWE|UUID"):
        validate_raw_cookie(raw)


def test_compact_decoder_reports_truncation_alignment_and_format() -> None:
    with raises(CompactTokenTruncatedError):
        unpack_session_token("wsk_1")
    with raises(CompactTokenTruncatedError):
        unpack_session_token("wsk_" + "z" * 60)
    with raises(CompactTokenFormatError):
        unpack_session_token("wsk_0!")


def test_compact_decoder_rejects_noncanonical_base62_spelling() -> None:
    token = pack_session_token(_synthetic_raw())
    with raises(CompactTokenFormatError, match="canonical"):
        unpack_session_token(token[:4] + "0" + token[4:])


def test_compact_decoder_rejects_misaligned_header_from_dropped_body_character() -> None:
    token = "wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw"
    token = token[:-1] + ("A" if token[-1] != "A" else "B")
    with raises(CompactTokenAlignmentError):
        unpack_session_token(token[0:4] + token[5:])


def test_compact_decoder_rejects_sentinel_version_and_checksum() -> None:
    payload = bytes.fromhex(SYNTHETIC_UUID.replace("-", "")) + bytes(range(12)) + bytes(range(16, 32)) + b"x"
    with raises(CompactTokenAlignmentError, match="sentinel"):
        unpack_session_token(_make_compact(payload, sentinel=False))
    with raises(UnsupportedTokenVersionError):
        unpack_session_token(_make_compact(payload, version=2))
    token = pack_session_token(_synthetic_raw())
    chars = list(token)
    chars[-1] = "0" if chars[-1] != "0" else "1"
    with raises(CompactTokenChecksumError):
        unpack_session_token("".join(chars))


def test_compact_decoder_rejects_invalid_embedded_uuid_and_bad_jwe_lengths() -> None:
    invalid_uuid = bytearray(bytes.fromhex(SYNTHETIC_UUID.replace("-", "")))
    invalid_uuid[6] = (invalid_uuid[6] & 0x0F) | 0x30
    payload = bytes(invalid_uuid) + bytes(range(12)) + bytes(range(16, 32)) + b"x"
    with raises(EmbeddedUUIDError):
        unpack_session_token(_make_compact(payload))

    short_payload = bytes.fromhex(SYNTHETIC_UUID.replace("-", "")) + b"x" * 28
    with raises(CompactTokenTruncatedError):
        unpack_session_token(_make_compact(short_payload))


def test_session_credentials_are_immutable() -> None:
    raw = _synthetic_raw()
    credentials = validate_raw_cookie(raw)
    field_name = "uuid"
    with raises(AttributeError, match="cannot assign to field"):
        setattr(credentials, field_name, "changed")


def test_typed_errors_are_value_errors_and_library_errors() -> None:
    for error_type in (
        RawCookieFormatError,
        CredentialError,
        SessionTokenError,
        CompactTokenFormatError,
        CompactTokenTruncatedError,
        CompactTokenAlignmentError,
        UnsupportedTokenVersionError,
        CompactTokenChecksumError,
        EmbeddedUUIDError,
    ):
        assert issubclass(error_type, ValueError)
        assert issubclass(error_type, PerplexityError)


def test_pack_matches_fixed_v1_reference_vector() -> None:
    iv = bytes(range(0x10, 0x1C))
    ciphertext = bytes(range(1, 8))
    tag = bytes(range(0x30, 0x40))
    raw = f"{SYNTHETIC_UUID}={STATIC_HEADER}..{_b64url(iv)}.{_b64url(ciphertext)}.{_b64url(tag)}"

    assert pack_session_token(raw) == "wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw"

    assert unpack_session_token("wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw") == (
        SessionCredentials(
            uuid=SYNTHETIC_UUID,
            cookie_value=f"{STATIC_HEADER}..{_b64url(iv)}.{_b64url(ciphertext)}.{_b64url(tag)}",
        )
    )


def test_raw_cookie_rejects_invalid_base64url_length_as_credential_error() -> None:
    for malformed_iv in ("A", "abcde"):
        raw = f"{SYNTHETIC_UUID}={STATIC_HEADER}..{malformed_iv}.{_b64url(b'cipher')}.{_b64url(bytes(range(16)))}"

        with raises(RawCookieFormatError):
            validate_raw_cookie(raw)


def test_resolve_and_unpack_enforce_single_normalization_and_size_limit() -> None:
    raw = _synthetic_raw()
    double_quoted = f'""{raw}""'
    backslash_wrapped = f"\\{raw}\\"

    with raises(RawCookieFormatError):
        validate_raw_cookie(double_quoted)
    with raises(RawCookieFormatError):
        resolve_session_token(double_quoted)
    with raises(RawCookieFormatError):
        resolve_session_token(backslash_wrapped)
    with raises(CompactTokenFormatError, match="length"):
        unpack_session_token("wsk_" + "A" * 9000)


def test_pack_and_unpack_accept_both_raw_and_compact_tokens() -> None:
    raw = _synthetic_raw()
    compact = pack_session_token(raw)

    assert pack_session_token(compact) == compact
    assert unpack_session_token(raw) == unpack_session_token(compact) == resolve_session_token(raw)
