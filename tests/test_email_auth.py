"""Tests for the Perplexity email authentication protocol."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from curl_cffi.requests.exceptions import HTTPError
from orjson import dumps, loads
from pytest import raises

from perplexity_webui_scraper._internal.constants import API_BASE_URL, SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper._internal.exceptions import AuthRequestError
from perplexity_webui_scraper.auth.email import (
    authenticate,
    follow_callback,
    get_session_credential,
    validate_otp_input,
    verify_totp,
)
from perplexity_webui_scraper.auth.requests import raise_for_auth_status
from perplexity_webui_scraper.auth.session_token import pack_session_token, resolve_session_token


_SESSION_UUID = "123e4567-e89b-42d3-a456-426614174000"
_SECOND_SESSION_UUID = "223e4567-e89b-42d3-a456-426614174000"
_SESSION_JWE = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
_SESSION_COOKIE_NAME = f"{SESSION_COOKIE_PREFIX}{_SESSION_UUID}"
_SECOND_SESSION_COOKIE_NAME = f"{SESSION_COOKIE_PREFIX}{_SECOND_SESSION_UUID}"
_TRUSTED_ORIGIN = API_BASE_URL.rstrip("/")


class AuthStatusError(Exception):
    def __init__(self, response: Any) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response = response


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        *,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._data = data or {}
        self.content = dumps(self._data)

    def json(self) -> dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AuthStatusError(self)

    @property
    def response(self) -> FakeResponse:
        return self


def test_validate_otp_input_accepts_six_ascii_digits_and_rejects_other_strings() -> None:
    email = "person@example.test"

    assert validate_otp_input("950515", email) is True
    assert validate_otp_input("000000", email) is True

    for value in ("", "saas", "95051", "9505157", "95a515", "٩٥٠٥١٥"):
        assert validate_otp_input(value, email) is False


def test_validate_otp_input_accepts_only_same_account_perplexity_callback_links() -> None:
    email = "person@example.test"
    valid_link = f"{_TRUSTED_ORIGIN}/api/auth/callback/email?" + urlencode(
        {
            "callbackUrl": f"{_TRUSTED_ORIGIN}/?login-source=floatingSignup",
            "email": email,
            "token": "950515",
            "source": "email",
        }
    )

    assert validate_otp_input(valid_link, email) is True
    assert validate_otp_input(f"@url:`{valid_link}`", email) is True

    for value in (
        "https://www.google.com/",
        "@url:`https://www.google.com/`",
        valid_link.replace(
            _TRUSTED_ORIGIN.removeprefix("https://"), f"{_TRUSTED_ORIGIN.removeprefix('https://')}.evil.test"
        ),
        valid_link.replace("https://", "http://"),
        valid_link.replace("/api/auth/callback/email", "/other"),
        valid_link.replace("person%40example.test", "other%40example.test"),
        valid_link.replace("token=950515", "token=95051"),
    ):
        assert validate_otp_input(value, email) is False


def test_follow_callback_rejects_untrusted_initial_and_redirect_urls_before_request() -> None:
    session = Mock()

    with raises(ValueError, match="Perplexity origin"):
        follow_callback(session, "https://user@www.perplexity.ai/callback")

    session.get.assert_not_called()

    for rejected_url in (
        "https://attacker.example/capture",
        f"{_TRUSTED_ORIGIN}:444/callback",
    ):
        session.get.reset_mock()
        session.get.return_value = FakeResponse(302, headers={"Location": rejected_url})
        with raises(ValueError, match="Perplexity origin"):
            follow_callback(session, f"{_TRUSTED_ORIGIN}/callback")
        session.get.assert_called_once_with(f"{_TRUSTED_ORIGIN}/callback", allow_redirects=False)


def test_follow_callback_follows_same_origin_redirect_chain() -> None:
    session = Mock()
    session.get.side_effect = [
        FakeResponse(302, headers={"Location": "/first"}),
        FakeResponse(307, headers={"Location": "/second"}),
        FakeResponse(303, headers={"Location": "/final"}),
        FakeResponse(200),
    ]

    assert follow_callback(session, f"{_TRUSTED_ORIGIN}/callback") is None
    assert [call.args[0] for call in session.get.call_args_list] == [
        f"{_TRUSTED_ORIGIN}/callback",
        f"{_TRUSTED_ORIGIN}/first",
        f"{_TRUSTED_ORIGIN}/second",
        f"{_TRUSTED_ORIGIN}/final",
    ]
    assert all(call.kwargs["allow_redirects"] is False for call in session.get.call_args_list)


def test_follow_callback_resolves_relative_location_against_current_url() -> None:
    session = Mock()
    session.get.side_effect = [
        FakeResponse(302, headers={"Location": "next"}),
        FakeResponse(200),
    ]

    assert follow_callback(session, f"{_TRUSTED_ORIGIN}/auth/callback") is None

    assert session.get.call_args_list[1].args[0] == f"{_TRUSTED_ORIGIN}/auth/next"


def test_follow_callback_resolves_totp_challenge_from_current_url() -> None:
    session = Mock()
    session.get.return_value = FakeResponse(
        302,
        headers={"Location": "auth/totp-challenge?token=challenge"},
    )

    assert follow_callback(session, f"{_TRUSTED_ORIGIN}/auth/callback") == "challenge"
    session.get.assert_called_once_with(f"{_TRUSTED_ORIGIN}/auth/callback", allow_redirects=False)


def test_follow_callback_rejects_redirect_chain_over_limit() -> None:
    session = Mock()
    session.get.side_effect = [FakeResponse(302, headers={"Location": f"/hop-{index + 1}"}) for index in range(12)]

    with raises(ValueError, match="redirect limit"):
        follow_callback(session, f"{_TRUSTED_ORIGIN}/callback")

    assert session.get.call_count == 11


def test_authenticate_reprompts_after_invalid_otp_without_resending_email() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    response_values = iter(
        [
            FakeResponse(data={"error": "invalid_otp"}),
            FakeResponse(data={"redirect": "/callback"}),
        ]
    )
    session.post.side_effect = lambda *_args, **_kwargs: next(response_values)
    session.get.return_value = FakeResponse(200)
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        credential = authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
        )

    assert credential == pack_session_token(f"{_SESSION_COOKIE_NAME}={_SESSION_JWE}")
    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 2


def test_authenticate_reprompts_after_redirect_error_without_resending_email() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [
        FakeResponse(data={"redirect": "/?error=Verification"}),
        FakeResponse(data={"redirect": "/callback"}),
    ]
    session.get.return_value = FakeResponse(200)
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
        )

    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 2


def test_authenticate_reprompts_on_malformed_otp_without_submitting_it() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.return_value = FakeResponse(data={"redirect": "/callback"})
    session.get.return_value = FakeResponse(200)
    codes = iter(["not-a-code", "123456"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 1
    assert loads(session.post.call_args.kwargs["data"])["otp"] == "123456"


def test_authenticate_rejects_malformed_codes_and_foreign_links_before_requests() -> None:
    session = Mock()
    account_email = "person@example.test"
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [
        FakeResponse(data={"error": "invalid_otp"}),
        FakeResponse(data={"redirect": "/callback"}),
    ]
    session.get.return_value = FakeResponse(200)
    invalid_inputs = [
        "",
        "saas",
        "12345",
        "1234567",
        "@url:`https://www.google.com/`",
        f"{_TRUSTED_ORIGIN}.evil.test/api/auth/callback/email?email=person%40example.test&token=950515",
        f"http://{_TRUSTED_ORIGIN.removeprefix('https://')}/api/auth/callback/email?email=person%40example.test&token=950515",
        f"{_TRUSTED_ORIGIN}/other?email=person%40example.test&token=950515",
        f"{_TRUSTED_ORIGIN}/api/auth/callback/email?email=other%40example.test&token=950515",
        (
            f"{_TRUSTED_ORIGIN}/api/auth/callback/email?"
            "callbackUrl=https%3A%2F%2Fattacker.example%2F%3Flogin-source%3DfloatingSignup"
            "&email=person%40example.test&token=950515"
        ),
    ]
    codes = iter([*invalid_inputs, "000000", "123456"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            account_email,
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected[: len(invalid_inputs)] == [True] * len(invalid_inputs)
    assert rejected[-1] is True
    send_otp.assert_called_once()
    assert session.post.call_count == 2
    assert [loads(call.kwargs["data"])["otp"] for call in session.post.call_args_list] == ["000000", "123456"]


def test_authenticate_accepts_perplexity_magic_link_with_additional_query_parameters() -> None:
    session = Mock()
    account_email = "person@example.test"
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.get.return_value = FakeResponse(200)
    raw_magic_link = f"{_TRUSTED_ORIGIN}/api/auth/callback/email?" + urlencode(
        {
            "callbackUrl": f"{_TRUSTED_ORIGIN}/?login-source=floatingSignup",
            "email": account_email,
            "token": "950515",
            "source": "email",
        }
    )
    magic_link = f"@url:`{raw_magic_link}`"

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        credential = authenticate(account_email, lambda: magic_link, lambda: "000000")

    assert credential == pack_session_token(f"{_SESSION_COOKIE_NAME}={_SESSION_JWE}")
    send_otp.assert_called_once()
    session.post.assert_not_called()
    session.get.assert_called_once_with(raw_magic_link, allow_redirects=False)


def test_authenticate_reprompts_when_callback_reports_invalid_otp() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [
        FakeResponse(data={"redirect": "/callback"}),
        FakeResponse(data={"redirect": "/callback"}),
    ]
    session.get.side_effect = [
        FakeResponse(302, headers={"Location": "/?error=Verification"}),
        FakeResponse(200),
    ]
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 2
    assert session.get.call_count == 2


def test_authenticate_reprompts_when_magic_link_callback_returns_http_400() -> None:
    class EmptyBodyResponse(FakeResponse):
        content = b""

        def __init__(self) -> None:
            super().__init__(400)
            self.content = b""

        def json(self) -> dict[str, Any]:
            raise ValueError("Response body is empty")

    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.get.side_effect = [
        HTTPError("HTTP Error 400:", response=EmptyBodyResponse()),
        FakeResponse(200),
    ]
    session.post.return_value = FakeResponse(data={"redirect": "/callback"})
    link = f"{_TRUSTED_ORIGIN}/api/auth/callback/email?" + urlencode(
        {
            "callbackUrl": f"{_TRUSTED_ORIGIN}/?login-source=floatingSignup",
            "email": "person@example.test",
            "token": "950515",
        }
    )
    assert validate_otp_input(link, "person@example.test") is True
    codes = iter([link, "123456"])
    rejected: list[bool] = []
    sessions: list[Mock] = []

    def create_session() -> _SessionContext:
        sessions.append(session)
        return _SessionContext(session)

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", side_effect=create_session),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.get.call_count == 2
    assert session.post.call_count == 1
    assert loads(session.post.call_args.kwargs["data"])["otp"] == "123456"
    assert sessions == [session]


def test_authenticate_stays_in_the_same_session_after_multiple_invalid_codes() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [
        FakeResponse(data={"error": "invalid_otp"}),
        FakeResponse(data={"error": "invalid_otp"}),
        FakeResponse(data={"redirect": "/callback"}),
    ]
    session.get.return_value = FakeResponse(200)
    codes = iter(["000000", "111111", "222222"])
    rejected: list[bool] = []
    sessions: list[Mock] = []

    def create_session() -> _SessionContext:
        sessions.append(session)
        return _SessionContext(session)

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", side_effect=create_session),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected == [True, True]
    assert sessions == [session]
    send_otp.assert_called_once()
    assert session.post.call_count == 3
    assert [loads(call.kwargs["data"])["otp"] for call in session.post.call_args_list] == ["000000", "111111", "222222"]


def test_authenticate_reprompts_when_http_400_rejects_email_otp() -> None:
    class EmptyBodyResponse(FakeResponse):
        content = b""

        def __init__(self) -> None:
            super().__init__(400)
            self.content = b""

        def json(self) -> dict[str, Any]:
            raise ValueError("Response body is empty")

    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [
        HTTPError("HTTP Error 400:", response=EmptyBodyResponse()),
        FakeResponse(data={"redirect": "/callback"}),
    ]
    session.get.return_value = FakeResponse(200)
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 2
    assert [loads(call.kwargs["data"])["otp"] for call in session.post.call_args_list] == ["111111", "222222"]


def test_authenticate_reprompts_when_email_otp_json_body_reports_invalid_otp() -> None:
    class InvalidJsonResponse(FakeResponse):
        content = b'{"error":"invalid_otp"}'

        def __init__(self) -> None:
            super().__init__(200)
            self.content = b'{"error":"invalid_otp"}'

        def json(self) -> dict[str, Any]:
            raise ValueError("Invalid JSON response: invalid_otp")

    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [InvalidJsonResponse(), FakeResponse(data={"redirect": "/callback"})]
    session.get.return_value = FakeResponse(200)
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
            on_malformed_otp=lambda: rejected.append(True),
        )

    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 2
    assert [loads(call.kwargs["data"])["otp"] for call in session.post.call_args_list] == ["111111", "222222"]


def test_authenticate_does_not_retry_non_otp_http_400() -> None:
    class BadRequestResponse(FakeResponse):
        content = b'{"error":"csrf_invalid"}'

        def __init__(self) -> None:
            super().__init__(400, data={"error": "csrf_invalid"})

    session = Mock()
    session.post.side_effect = HTTPError("HTTP Error 400:", response=BadRequestResponse())
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
        raises(HTTPError),
    ):
        authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
        )

    assert rejected == []
    send_otp.assert_called_once()
    assert session.post.call_count == 1


def test_get_session_credential_returns_uuid_cookie_when_legacy_cookie_also_exists() -> None:
    session = Mock()
    session.cookies = {
        "__Secure-next-auth.session-token": "legacy-value",
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }

    raw = f"{_SESSION_COOKIE_NAME}={_SESSION_JWE}"
    assert get_session_credential(session) == pack_session_token(raw)


def test_authenticate_returns_compact_credential_from_verified_cookie() -> None:
    session = Mock()
    session.cookies = {_SESSION_COOKIE_NAME: _SESSION_JWE}
    session.post.return_value = FakeResponse(data={"redirect": "/callback"})
    session.get.return_value = FakeResponse(200)

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp"),
    ):
        compact = authenticate("person@example.test", lambda: "123456", lambda: "000000")

    resolved = resolve_session_token(compact)
    assert compact.startswith("wsk_")
    assert resolved.uuid == _SESSION_UUID
    assert resolved.cookie_value == _SESSION_JWE


def test_get_session_credential_selects_last_active_account_and_rejects_ambiguity() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        _SECOND_SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SECOND_SESSION_UUID,
    }

    assert get_session_credential(session) == (pack_session_token(f"{_SECOND_SESSION_COOKIE_NAME}={_SESSION_JWE}"))

    del session.cookies["__Host-pplx-last-active-account"]
    with raises(ValueError, match="ambiguous"):
        get_session_credential(session)


def test_verify_totp_retries_invalid_http_and_json_responses() -> None:
    session = Mock()
    session.post.side_effect = [
        AuthRequestError(401, "invalid_code", invalid_code=True),
        FakeResponse(data={"error": "invalid_code"}),
        FakeResponse(data={}),
    ]
    codes = iter(["111111", "222222", "333333"])
    rejected: list[bool] = []

    verify_totp(
        session,
        "challenge-token",
        lambda: next(codes),
        on_invalid_code=lambda: rejected.append(True),
    )

    assert session.post.call_count == 3
    assert rejected == [True, True]


def test_verify_totp_reprompts_after_empty_http_error_body() -> None:
    class EmptyBodyResponse(FakeResponse):
        content = b""

        def __init__(self) -> None:
            super().__init__(400)
            self.content = b""

        def json(self) -> dict[str, Any]:
            raise ValueError("Response body is empty")

    session = Mock()
    session.post.side_effect = [
        AuthRequestError(400, invalid_code=True),
        FakeResponse(data={}),
    ]
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    verify_totp(
        session,
        "challenge-token",
        lambda: next(codes),
        on_invalid_code=lambda: rejected.append(True),
    )

    assert session.post.call_count == 2
    assert rejected == [True]
    assert loads(session.post.call_args_list[1].kwargs["data"])["code"] == "222222"


def test_verify_totp_does_not_retry_non_code_authorization_error() -> None:
    session = Mock()
    session.post.side_effect = [FakeResponse(401, data={"error": "forbidden"})]
    prompt = Mock(return_value="123456")

    with raises(ValueError, match="HTTP 401"):
        verify_totp(session, "challenge-token", prompt)

    assert prompt.call_count == 1
    assert session.post.call_count == 1


def test_verify_totp_reprompts_on_invalid_format_before_request() -> None:
    session = Mock()
    codes = iter(["bad-format", "123456"])
    rejected: list[bool] = []
    session.post.return_value = FakeResponse(data={})

    verify_totp(
        session,
        "challenge-token",
        lambda: next(codes),
        on_invalid_code=lambda: rejected.append(True),
    )

    assert session.post.call_count == 1
    assert rejected == [True]


def test_verify_totp_rejects_failed_redirect_response() -> None:
    session = Mock()
    session.post.return_value = FakeResponse(302, headers={"Location": "/signed-in"})
    session.get.return_value = FakeResponse(401)

    with raises(AuthRequestError, match="HTTP 401"):
        verify_totp(session, "challenge-token", lambda: "123456")


def test_auth_status_error_hides_upstream_response_body() -> None:
    sensitive_detail = "synthetic-auth-body-marker"
    response = FakeResponse(401, data={"error": sensitive_detail})

    with raises(AuthRequestError) as exc_info:
        raise_for_auth_status(response)

    assert sensitive_detail not in str(exc_info.value)
    assert sensitive_detail not in repr(exc_info.value)


def test_verify_totp_follows_relative_multi_hop_redirect_after_empty_see_other() -> None:
    session = Mock()
    response = Mock(status_code=303, headers={"Location": "/auth/callback"})
    response.json.side_effect = ValueError("empty redirect body")
    session.post.return_value = response
    session.get.side_effect = [
        FakeResponse(303, headers={"Location": "signed-in"}),
        FakeResponse(204),
    ]

    verify_totp(session, "challenge-token", lambda: "123456")

    assert [call.args[0] for call in session.get.call_args_list] == [
        f"{_TRUSTED_ORIGIN}/auth/callback",
        f"{_TRUSTED_ORIGIN}/auth/signed-in",
    ]
    assert all(call.kwargs["allow_redirects"] is False for call in session.get.call_args_list)


def test_verify_totp_rejects_error_in_callback_redirect_chain() -> None:
    session = Mock()
    session.post.return_value = FakeResponse(302, headers={"Location": "/signed-in"})
    session.get.side_effect = [
        FakeResponse(302, headers={"Location": "/next"}),
        FakeResponse(302, headers={"Location": "/?error=Verification"}),
    ]

    with raises(ValueError, match="invalid or expired"):
        verify_totp(session, "challenge-token", lambda: "123456")

    assert session.get.call_count == 2


def test_authenticate_reprompts_when_http_400_response_goes_through_auth_status_check() -> None:
    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.post.side_effect = [
        FakeResponse(400, data={"error": "invalid_otp"}),
        FakeResponse(data={"redirect": "/callback"}),
    ]
    session.get.return_value = FakeResponse(200)
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        compact = authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
        )

    assert compact.startswith("wsk_")
    assert rejected == [True]
    send_otp.assert_called_once()
    assert session.post.call_count == 2


def test_authenticate_reprompts_when_magic_link_callback_returns_http_400_response() -> None:
    class EmptyBodyResponse(FakeResponse):
        def __init__(self) -> None:
            super().__init__(400)
            self.content = b""

    session = Mock()
    session.cookies = {
        _SESSION_COOKIE_NAME: _SESSION_JWE,
        "__Host-pplx-last-active-account": _SESSION_UUID,
    }
    session.get.side_effect = [EmptyBodyResponse(), FakeResponse(200)]
    session.post.return_value = FakeResponse(data={"redirect": "/callback"})
    link = f"{_TRUSTED_ORIGIN}/api/auth/callback/email?" + urlencode(
        {
            "callbackUrl": f"{_TRUSTED_ORIGIN}/?login-source=floatingSignup",
            "email": "person@example.test",
            "token": "950515",
        }
    )
    codes = iter([link, "123456"])
    rejected: list[bool] = []

    with (
        patch("perplexity_webui_scraper.auth.email.create_session", return_value=_SessionContext(session)),
        patch("perplexity_webui_scraper.auth.email.fetch_csrf", return_value="csrf"),
        patch("perplexity_webui_scraper.auth.email.send_otp") as send_otp,
    ):
        compact = authenticate(
            "person@example.test",
            lambda: next(codes),
            lambda: "000000",
            on_invalid_otp=lambda: rejected.append(True),
        )

    assert compact.startswith("wsk_")
    assert rejected == [True]
    send_otp.assert_called_once()


def test_verify_totp_reprompts_on_invalid_totp_http_400_response() -> None:
    session = Mock()
    session.post.side_effect = [
        FakeResponse(400, data={"error": "invalid_totp"}),
        FakeResponse(data={}),
    ]
    codes = iter(["111111", "222222"])
    rejected: list[bool] = []

    verify_totp(
        session,
        "challenge-token",
        lambda: next(codes),
        on_invalid_code=lambda: rejected.append(True),
    )

    assert session.post.call_count == 2
    assert rejected == [True]


class _SessionContext:
    def __init__(self, session: Any) -> None:
        self._session = session

    def __enter__(self) -> Any:
        return self._session

    def __exit__(self, *_args: object) -> None:
        return None
