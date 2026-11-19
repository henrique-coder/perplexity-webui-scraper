from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from threading import Timer
from time import monotonic
from unittest.mock import Mock, patch

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pytest import raises

from perplexity_webui_scraper._internal.exceptions import AuthRequestError, RateLimitError
from perplexity_webui_scraper.auth.requests import (
    call_with_rate_limit_retry,
    parse_retry_after,
    raise_for_auth_status,
    wait_for_rate_limit_retry,
)


def test_retry_after_supports_seconds_http_dates_and_fallback() -> None:
    now = datetime.fromtimestamp(0, UTC)
    retry_date = format_datetime(datetime.fromtimestamp(45, UTC), usegmt=True)

    assert parse_retry_after("75", now=now) == 75
    assert parse_retry_after(retry_date, now=now) == 45
    assert parse_retry_after("invalid", fallback_seconds=30, now=now) == 30


def test_raise_for_auth_status_preserves_retry_after_header() -> None:
    response = Mock(status_code=429, headers={"Retry-After": "60"})
    response.raise_for_status.side_effect = RuntimeError("HTTP Error 429")

    with raises(RateLimitError) as exc_info:
        raise_for_auth_status(response)

    assert exc_info.value.retry_after == "60"
    assert "Retry-After: 60" not in str(exc_info.value)


def test_call_with_rate_limit_retry_waits_then_retries_operation() -> None:
    retry_at = datetime.fromtimestamp(0, UTC)
    operation = Mock(side_effect=[RateLimitError(retry_after="60"), "ok"])

    with (
        patch("perplexity_webui_scraper.auth.requests.log_rate_limit_retry", return_value=retry_at) as log_retry,
        patch("perplexity_webui_scraper.auth.requests.wait_for_rate_limit_retry", return_value=False) as wait,
    ):
        result = call_with_rate_limit_retry(operation, "OTP email request")

    assert result == "ok"
    assert operation.call_count == 2
    wait.assert_called_once_with("60", retry_at, manual_retry_available_after=0.0)
    log_retry.assert_called_once_with("OTP email request", "60")


def test_wait_for_rate_limit_retry_returns_when_enter_is_pressed() -> None:
    with create_pipe_input() as input_pipe:
        press_enter = Timer(0.05, input_pipe.send_text, args=("\r",))
        press_enter.start()
        started = monotonic()
        try:
            retry_now = wait_for_rate_limit_retry(
                "60",
                datetime.now().astimezone() + timedelta(seconds=60),
                input_stream=input_pipe,
                output_stream=DummyOutput(),
                manual_retry_available_after=started + 0.01,
            )
        finally:
            press_enter.join()

    assert retry_now is True
    assert monotonic() - started >= 0.05


def test_wait_for_rate_limit_retry_cancels_on_ctrl_c() -> None:
    with create_pipe_input() as input_pipe:
        interrupt = Timer(0.05, input_pipe.send_text, args=("\x03",))
        interrupt.start()
        try:
            with raises(KeyboardInterrupt):
                wait_for_rate_limit_retry(
                    "60",
                    datetime.now().astimezone() + timedelta(seconds=60),
                    input_stream=input_pipe,
                    output_stream=DummyOutput(),
                )
        finally:
            interrupt.join()


def test_call_with_rate_limit_retry_propagates_cancellation_without_retry() -> None:
    operation = Mock(side_effect=RateLimitError(retry_after="60"))

    with (
        patch("perplexity_webui_scraper.auth.requests.wait_for_rate_limit_retry", side_effect=KeyboardInterrupt),
        raises(KeyboardInterrupt),
    ):
        call_with_rate_limit_retry(operation)

    assert operation.call_count == 1


def test_raise_for_auth_status_marks_invalid_totp_as_retryable_code_error() -> None:
    response = Mock(status_code=400, headers={}, content=b'{"error":"invalid_totp"}')
    response.raise_for_status.side_effect = RuntimeError("HTTP Error 400")

    with raises(AuthRequestError) as exc_info:
        raise_for_auth_status(response)

    assert exc_info.value.status_code == 400
    assert exc_info.value.invalid_code is True
