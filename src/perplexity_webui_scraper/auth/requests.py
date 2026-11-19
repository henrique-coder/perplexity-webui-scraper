"""HTTP helpers for Perplexity email authentication."""

from __future__ import annotations

from asyncio import sleep as async_sleep
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from math import ceil
from time import monotonic
from typing import TYPE_CHECKING, Any, Protocol, TypeVar
from urllib.parse import urljoin, urlparse

from orjson import loads
from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from rich.console import Console

from perplexity_webui_scraper._internal.constants import API_BASE_URL
from perplexity_webui_scraper._internal.exceptions import AuthRequestError, RateLimitError


if TYPE_CHECKING:
    from collections.abc import Callable


_T = TypeVar("_T")
console = Console(stderr=True, soft_wrap=True)
_COUNTDOWN_STYLES = Style.from_dict({"instruction": "fg:#E0E0E0", "timer": "fg:ansicyan"})
MANUAL_RETRY_COOLDOWN_SECONDS = 5.0


class AuthResponse(Protocol):
    status_code: int
    headers: dict[str, str]
    content: bytes

    def raise_for_status(self) -> None: ...


def raise_for_auth_status(response: AuthResponse) -> None:
    """Preserve upstream retry guidance on auth endpoint rate limits."""
    try:
        response.raise_for_status()
    except Exception:
        status_code = response.status_code
    else:
        return

    if status_code == 429:
        retry_after = response.headers.get("Retry-After")

        if retry_after is None:
            retry_after = str(parse_retry_after(None))

        raise RateLimitError(retry_after=retry_after)

    error_code: str | None = None

    try:
        data = loads(response.content)
    except Exception:
        data = None

    if isinstance(data, dict) and isinstance(data.get("error"), str):
        error_code = data["error"][:80]

    invalid_code = error_code in {"invalid_code", "invalid_otp", "invalid_totp", "verification"} or (
        status_code == 400 and not response.content
    )

    raise AuthRequestError(status_code, error_code, invalid_code)


def parse_retry_after(value: str | None, fallback_seconds: int = 60, now: datetime | None = None) -> int:
    """Parse a Retry-After seconds/date value, using the fallback when absent or invalid."""
    if value:
        try:
            return max(0, int(value.strip()))
        except ValueError:
            with suppress(TypeError, ValueError, OverflowError):
                retry_at = parsedate_to_datetime(value)

                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                current_time = now or datetime.now(UTC)
                return max(0, int((retry_at - current_time).total_seconds()))

    return max(0, fallback_seconds)


def format_retry_countdown(
    remaining_seconds: float,
    retry_at: datetime,
    manual_retry_cooldown: float = 0,
) -> FormattedText:
    """Format the countdown instruction and server-directed retry time."""
    total_seconds = ceil(max(0, remaining_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    retry_time = retry_at.strftime("%H:%M:%S %Z").strip()
    if manual_retry_cooldown > 0:
        cooldown_seconds = ceil(manual_retry_cooldown)
        cooldown_minutes, cooldown_seconds = divmod(cooldown_seconds, 60)
        return FormattedText(
            [
                ("class:instruction", "Wait for automatic retry  |  Ctrl+C: cancel  |  "),
                (
                    "class:timer",
                    (
                        f"Next attempt in {minutes:02d}:{seconds:02d}  |  "
                        f"Enter available in {cooldown_minutes:02d}:{cooldown_seconds:02d}"
                    ),
                ),
            ]
        )

    return FormattedText(
        [
            ("class:instruction", "Enter: retry now  |  Ctrl+C: cancel  |  "),
            ("class:timer", f"Next attempt in {minutes:02d}:{seconds:02d}  ({retry_time})"),
        ]
    )


def wait_for_rate_limit_retry(
    retry_after: str | None,
    retry_at: datetime | None = None,
    input_stream: Any = None,
    output_stream: Any = None,
    *,
    manual_retry_available_after: float = 0,
) -> bool:
    """Wait for the server delay; throttle manual retries and allow Ctrl+C."""
    if retry_at is None:
        retry_at = datetime.now().astimezone() + timedelta(seconds=parse_retry_after(retry_after))

    deadline = monotonic() + max(0.0, (retry_at - datetime.now().astimezone()).total_seconds())

    def countdown() -> FormattedText:
        return format_retry_countdown(
            deadline - monotonic(),
            retry_at,
            manual_retry_available_after - monotonic(),
        )

    bindings = KeyBindings()
    retry_now_requested = False

    def handle_retry_now(event: Any) -> None:
        nonlocal retry_now_requested
        if monotonic() < manual_retry_available_after:
            return
        retry_now_requested = True
        event.app.exit(result=None)

    @bindings.add("enter", eager=True)
    def retry_now_on_enter(event: Any) -> None:
        handle_retry_now(event)

    @bindings.add("c-m", eager=True)
    def retry_now_on_carriage_return(event: Any) -> None:
        handle_retry_now(event)

    @bindings.add("c-c", eager=True)
    def cancel_retry(event: Any) -> None:
        event.app.exit(exception=KeyboardInterrupt())

    application: Application[None] = Application(
        layout=Layout(Window(FormattedTextControl(countdown), height=1)),
        key_bindings=bindings,
        style=_COUNTDOWN_STYLES,
        input=input_stream,
        output=output_stream,
        refresh_interval=0.1,
        erase_when_done=True,
    )

    async def finish_after_deadline() -> None:
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                application.exit(result=None)
                return
            await async_sleep(min(remaining, 0.1))
            application.invalidate()

    def start_countdown() -> None:
        application.create_background_task(finish_after_deadline())

    application.run(pre_run=start_countdown)
    return retry_now_requested


def log_rate_limit_retry(label: str, retry_after: str | None) -> datetime:
    """Log one rejected request and return its scheduled retry time."""
    event = f"{label} rejected (HTTP 429)."
    console.log(f"[#FF8A80]{event}[/#FF8A80]", log_locals=False)
    return datetime.now().astimezone() + timedelta(seconds=parse_retry_after(retry_after))


def call_with_rate_limit_retry(operation: Callable[[], _T], label: str = "Request") -> _T:
    """Retry an auth operation after a server-directed rate-limit wait."""
    manual_retry_available_after = 0.0
    while True:
        try:
            return operation()
        except RateLimitError as error:
            retry_at = log_rate_limit_retry(label, error.retry_after)
            retry_now = wait_for_rate_limit_retry(
                error.retry_after,
                retry_at,
                manual_retry_available_after=manual_retry_available_after,
            )
            manual_retry_available_after = monotonic() + MANUAL_RETRY_COOLDOWN_SECONDS if retry_now else 0.0


def request_with_rate_limit_retry(
    request: Callable[[], AuthResponse],
    label: str = "Request",
    status_message: str | None = None,
) -> AuthResponse:
    """Perform a request, wait and retry on HTTP 429, then return the response."""
    manual_retry_available_after = 0.0
    while True:
        if status_message:
            with console.status(f"[#E0E0E0]{status_message}[/#E0E0E0]", spinner="dots", spinner_style="#B0BEC5"):
                response = request()
        else:
            response = request()

        try:
            raise_for_auth_status(response)
        except RateLimitError as error:
            retry_at = log_rate_limit_retry(label, error.retry_after)
            retry_now = wait_for_rate_limit_retry(
                error.retry_after,
                retry_at,
                manual_retry_available_after=manual_retry_available_after,
            )
            manual_retry_available_after = monotonic() + MANUAL_RETRY_COOLDOWN_SECONDS if retry_now else 0.0
            continue
        return response


def redirect_url(path_or_url: str, base_url: str | None = None) -> str:
    """Resolve a callback URL and require HTTPS on Perplexity's origin."""
    target_url = urljoin(base_url or f"{API_BASE_URL}/", path_or_url)
    parsed = urlparse(target_url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Authentication redirect is not on the Perplexity origin.") from error
    expected_origin = urlparse(API_BASE_URL)
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected_origin.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ValueError("Authentication redirect is not on the Perplexity origin.")
    return target_url


def validate_auth_response(response: AuthResponse) -> None:
    """Raise the upstream HTTP error, preserving auth rate-limit guidance."""
    raise_for_auth_status(response)


__all__ = [
    "AuthResponse",
    "call_with_rate_limit_retry",
    "console",
    "format_retry_countdown",
    "log_rate_limit_retry",
    "parse_retry_after",
    "raise_for_auth_status",
    "redirect_url",
    "request_with_rate_limit_retry",
    "validate_auth_response",
    "wait_for_rate_limit_retry",
]
