"""Email-based Perplexity sign-in flow shared by CLI adapters."""

from __future__ import annotations

from functools import partial
from re import fullmatch
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from curl_cffi.requests import Session
from orjson import dumps, loads

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    API_VERSION,
    ENDPOINT_AUTH_CSRF,
    ENDPOINT_AUTH_OTP_REDIRECT,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_AUTH_TOTP_CHALLENGE_VERIFY,
)
from perplexity_webui_scraper._internal.exceptions import AuthRequestError, RateLimitError
from perplexity_webui_scraper.auth.cookies import extract_session_cookie, serialize_session_credential
from perplexity_webui_scraper.auth.requests import redirect_url, request_with_rate_limit_retry
from perplexity_webui_scraper.auth.session_token import pack_session_token


if TYPE_CHECKING:
    from collections.abc import Callable


_DEFAULT_HEADERS: dict[str, str] = {"Referer": f"{API_BASE_URL}/", "Origin": API_BASE_URL}
_MAX_CALLBACK_REDIRECTS = 10
_INVALID_TOTP_ERRORS = frozenset({"invalid_code", "invalid_totp", "invalid_otp"})
_OTP_PATTERN = r"[0-9]{6}"
_EMAIL_CALLBACK_PATH = "/api/auth/callback/email"
_INVALID_EMAIL_OTP_MESSAGE = "Verification failed. The OTP code may be invalid or expired."


def create_session() -> Session:
    """Create an impersonated WebUI session for email authentication."""
    return Session(impersonate="chrome", headers=_DEFAULT_HEADERS)


def _post_json(session: Session, url: str, payload: dict[str, Any]) -> Any:
    """Send an orjson-serialized JSON body through curl-cffi."""
    return session.post(
        url,
        data=dumps(payload),
        headers={"Content-Type": "application/json"},
    )


def fetch_csrf(session: Session) -> str:
    """Initialize the auth session and return its CSRF token."""
    request_with_rate_limit_retry(lambda: session.get(API_BASE_URL), "Connection initialization request")
    response = request_with_rate_limit_retry(
        lambda: session.get(f"{API_BASE_URL}{ENDPOINT_AUTH_CSRF}"),
        "CSRF initialization request",
        "Fetching CSRF token...",
    )
    csrf_token = loads(response.content).get("csrfToken", "")

    if not csrf_token:
        raise ValueError("Failed to obtain CSRF token.")
    return csrf_token


def send_otp(session: Session, email: str, csrf_token: str) -> None:
    """Request an email verification code."""
    request_with_rate_limit_retry(
        lambda: _post_json(
            session,
            f"{API_BASE_URL}{ENDPOINT_AUTH_SIGNIN}?version={API_VERSION}&source=default",
            {
                "email": email,
                "csrfToken": csrf_token,
                "useNumericOtp": "true",
                "json": "true",
                "callbackUrl": f"{API_BASE_URL}/?login-source=floatingSignup",
            },
        ),
        "Verification email request",
        "Sending verification code...",
    )


def validate_otp_input(value: str, email: str) -> bool:
    """Accept only a six-digit ASCII code or a valid same-account magic link."""
    if fullmatch(_OTP_PATTERN, value):
        return True

    value = _unwrap_magic_link(value)
    parsed = urlparse(value)
    expected = urlparse(API_BASE_URL)
    try:
        port = parsed.port
    except ValueError:
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    callback_url_values = query.get("callbackUrl", [])

    if len(callback_url_values) != 1:
        return False
    callback_url = urlparse(callback_url_values[0])
    try:
        callback_port = callback_url.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == expected.hostname
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and parsed.path == _EMAIL_CALLBACK_PATH
        and fullmatch(_OTP_PATTERN, query.get("token", [""])[0]) is not None
        and query.get("email", [""])[0].casefold() == email.casefold()
        and all(len(query.get(name, [])) == 1 for name in ("token", "email"))
        and callback_url.scheme == "https"
        and callback_url.hostname == expected.hostname
        and callback_url.path in ("", "/")
        and callback_url.query != ""
        and callback_port in (None, 443)
        and callback_url.username is None
        and callback_url.password is None
    )


def _unwrap_magic_link(value: str) -> str:
    if value.startswith("@url:`") and value.endswith("`"):
        return value[6:-1]
    return value


def _parse_magic_link(value: str, email: str) -> str | None:
    """Validate and normalize a Perplexity email callback link."""
    if fullmatch(_OTP_PATTERN, value) or not validate_otp_input(value, email):
        return None

    return _unwrap_magic_link(value)


def _invalid_email_otp(error: Exception) -> bool:
    if isinstance(error, AuthRequestError):
        return error.invalid_code and error.status_code in (400, 401)

    response = getattr(error, "response", None)

    if response is None or response.status_code not in (400, 401):
        return False
    try:
        data = loads(response.content)
    except Exception:
        data = None
    if isinstance(data, dict):
        error_code = data.get("error")
        return error_code in ("invalid_code", "invalid_otp", "verification")
    return response.status_code == 400 and not getattr(response, "content", b"")


def _is_invalid_email_otp_error(error: Exception) -> bool:
    return _invalid_email_otp(error) or (isinstance(error, ValueError) and _INVALID_EMAIL_OTP_MESSAGE in str(error))


def resolve_redirect_url(session: Session, email: str, otp_code: str) -> str:
    """Exchange a six-digit OTP code for a same-origin callback redirect URL."""
    if not fullmatch(_OTP_PATTERN, otp_code):
        raise ValueError("Enter a 6-digit code or a valid Perplexity email sign-in link.")

    response = request_with_rate_limit_retry(
        lambda: _post_json(
            session,
            f"{API_BASE_URL}{ENDPOINT_AUTH_OTP_REDIRECT}",
            {
                "email": email,
                "otp": otp_code,
                "redirectUrl": f"{API_BASE_URL}/?login-source=floatingSignup",
                "emailLoginMethod": "web-otp",
            },
        ),
        "Verification code request",
        "Validating verification code...",
    )
    try:
        data = loads(response.content)
    except Exception:
        body = getattr(response, "content", b"")

        try:
            body_text = body.decode("utf-8").lower() if isinstance(body, bytes) else str(body).lower()
        except UnicodeDecodeError:
            body_text = ""

        if response.status_code == 200 and "invalid_otp" in body_text:
            raise ValueError(_INVALID_EMAIL_OTP_MESSAGE) from None
        raise
    if data.get("error"):
        raise ValueError(_INVALID_EMAIL_OTP_MESSAGE)

    target = data.get("redirect", "")
    if not isinstance(target, str) or not target:
        raise ValueError("No redirect URL received.")

    resolved = redirect_url(target)
    if parse_qs(urlparse(resolved).query).get("error"):
        raise ValueError(_INVALID_EMAIL_OTP_MESSAGE)
    return resolved


def _totp_challenge(location: str, base_url: str = API_BASE_URL) -> str:
    parsed = urlparse(redirect_url(location, base_url=base_url))
    token = parse_qs(parsed.query).get("token", [""])[0]
    if not token:
        raise ValueError("TOTP challenge token not found in redirect.")
    return token


def follow_callback(session: Session, callback_url: str) -> str | None:
    """Complete callback redirects and return a TOTP challenge token if required."""
    target = redirect_url(callback_url)
    for hop in range(_MAX_CALLBACK_REDIRECTS + 1):
        response = request_with_rate_limit_retry(partial(session.get, target, allow_redirects=False))
        if response.status_code in (200, 204):
            return None
        if response.status_code not in (301, 302, 303, 307, 308):
            raise ValueError(f"Unexpected authentication callback status: {response.status_code}.")

        location = response.headers.get("Location")
        if not location:
            raise ValueError("Authentication callback redirect did not include a Location header.")
        next_url = redirect_url(location, base_url=target)
        if parse_qs(urlparse(next_url).query).get("error"):
            raise ValueError(_INVALID_EMAIL_OTP_MESSAGE)
        if "/auth/totp-challenge" in urlparse(next_url).path:
            return _totp_challenge(location, base_url=target)
        if hop == _MAX_CALLBACK_REDIRECTS:
            raise ValueError("Authentication callback exceeded the redirect limit.")
        target = next_url

    raise ValueError("Authentication callback exceeded the redirect limit.")


def _submit_totp_verification(
    session: Session,
    verify_url: str,
    challenge_token: str,
    code: str,
    on_invalid_code: Callable[[], object] | None,
) -> Any | None:
    """Submit one TOTP verification code; return ``None`` when rejected as invalid."""
    try:
        return request_with_rate_limit_retry(
            partial(_post_json, session, verify_url, {"token": challenge_token, "code": code}),
            "TOTP verification request",
            "Verifying TOTP...",
        )
    except Exception as error:
        if not isinstance(error, AuthRequestError):
            raise TypeError("TOTP verification request failed.") from None

        if error.invalid_code and error.status_code in (400, 401):
            if on_invalid_code is not None:
                on_invalid_code()

            return None

        raise ValueError(f"TOTP verification request failed with HTTP {error.status_code}.") from None


def _parse_totp_response_data(response: Any) -> dict[str, Any]:
    """Decode and validate a JSON TOTP verification response body."""
    try:
        data = loads(response.content)

        if not isinstance(data, dict):
            raise TypeError("Invalid TOTP verification response.")
    except Exception:
        raise ValueError("Failed to parse the TOTP verification response.") from None

    return data


def _follow_totp_redirect(session: Session, verify_url: str, target: str, *, missing_message: str) -> None:
    """Follow a post-TOTP callback redirect and reject any recursive challenge."""
    if not target:
        raise ValueError(missing_message)

    challenge = follow_callback(session, redirect_url(target, base_url=verify_url))

    if challenge:
        raise ValueError("Unexpected TOTP challenge after verification.")


def verify_totp(
    session: Session,
    challenge_token: str,
    prompt: Callable[[], str],
    on_invalid_code: Callable[[], object] | None = None,
) -> None:
    """Prompt for a TOTP code and follow its successful redirect."""
    verify_url = f"{API_BASE_URL}{ENDPOINT_AUTH_TOTP_CHALLENGE_VERIFY}?version={API_VERSION}&source=default"

    while True:
        code = prompt().strip()

        if not fullmatch(_OTP_PATTERN, code):
            if on_invalid_code is not None:
                on_invalid_code()
                continue

            raise ValueError("TOTP code must be a 6-digit number.")

        response = _submit_totp_verification(session, verify_url, challenge_token, code, on_invalid_code)

        if response is None:
            continue

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "")
            _follow_totp_redirect(
                session,
                verify_url,
                location,
                missing_message="TOTP verification redirect did not include a Location header.",
            )

            return

        data = _parse_totp_response_data(response)

        if data.get("error"):
            if data.get("error") not in _INVALID_TOTP_ERRORS:
                raise ValueError("TOTP verification failed.")

            if on_invalid_code is not None:
                on_invalid_code()

            continue

        next_redirect = data.get("redirect", "")

        if next_redirect:
            if not isinstance(next_redirect, str):
                raise ValueError("Invalid post-TOTP redirect.")

            _follow_totp_redirect(
                session,
                verify_url,
                next_redirect,
                missing_message="Invalid post-TOTP redirect.",
            )

        return


def get_session_credential(session: Session) -> str:
    """Return the compact ``wsk_`` token for the active authenticated account."""
    credential = extract_session_cookie(session.cookies)

    if credential is None:
        raise ValueError(
            "The authentication session returned no account-scoped UUID cookie. "
            "Confirm email/TOTP verification completed in the current session."
        )

    return pack_session_token(serialize_session_credential(credential))


def authenticate(
    email: str,
    prompt_otp: Callable[[], str],
    prompt_totp: Callable[[], str],
    on_invalid_otp: Callable[[], object] | None = None,
    on_invalid_totp: Callable[[], object] | None = None,
    on_malformed_otp: Callable[[], object] | None = None,
    on_otp_submitted: Callable[[], object] | None = None,
) -> str:
    """Complete email/TOTP sign-in and return the compact ``wsk_`` session token."""
    with create_session() as session:
        csrf = fetch_csrf(session)
        send_otp(session, email, csrf)

        while True:
            otp = prompt_otp().strip()

            if not validate_otp_input(otp, email):
                if on_malformed_otp is not None:
                    on_malformed_otp()
                continue

            try:
                magic_link = _parse_magic_link(otp, email)

                if on_otp_submitted is not None:
                    on_otp_submitted()

                callback = magic_link if magic_link is not None else resolve_redirect_url(session, email, otp)

                if callback is None:
                    raise ValueError("Invalid Perplexity email sign-in link.")
            except Exception as error:
                if _is_invalid_email_otp_error(error):
                    if on_invalid_otp is not None:
                        on_invalid_otp()
                    continue
                if isinstance(error, (AuthRequestError, RateLimitError)):
                    raise OSError("Authentication request failed.") from None
                raise
            try:
                challenge = follow_callback(session, callback)
            except Exception as error:
                if _is_invalid_email_otp_error(error):
                    if on_invalid_otp is not None:
                        on_invalid_otp()
                    continue
                if isinstance(error, (AuthRequestError, RateLimitError)):
                    raise OSError("Authentication request failed.") from None
                raise
            break
        if challenge:
            verify_totp(session, challenge, prompt_totp, on_invalid_totp)
        return get_session_credential(session)


__all__ = [
    "authenticate",
    "create_session",
    "fetch_csrf",
    "follow_callback",
    "get_session_credential",
    "resolve_redirect_url",
    "send_otp",
    "validate_otp_input",
    "verify_totp",
]
