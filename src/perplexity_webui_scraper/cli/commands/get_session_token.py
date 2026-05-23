"""get-session-token CLI command — extracts the Perplexity session cookie.

Uses the email → OTP code → redirect-link → cookie extraction flow via curl-cffi.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from curl_cffi.requests import Session
from pyperclip import PyperclipException, copy
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
import typer

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    API_VERSION,
    ENDPOINT_AUTH_CSRF,
    ENDPOINT_AUTH_OTP_REDIRECT,
    ENDPOINT_AUTH_SIGNIN,
    ENDPOINT_AUTH_TOTP_CHALLENGE_VERIFY,
    SESSION_COOKIE_NAME,
)


_DEFAULT_HEADERS: dict[str, str] = {
    "Referer": f"{API_BASE_URL}/",
    "Origin": API_BASE_URL,
}

console = Console(stderr=True, soft_wrap=True)


def _show_header() -> None:
    """Display the welcome header panel."""
    console.print(
        Panel(
            "[bold white]Perplexity WebUI Scraper[/bold white]\n\n"
            "Automatic session token generator via email authentication.\n"
            "[dim]All session data will be cleared on exit.[/dim]",
            title="🔐 Token Generator",
            border_style="cyan",
        )
    )


def _show_exit_message() -> None:
    """Display the security note and wait for the user to press ENTER before clearing the screen."""
    console.print("\n[bold yellow]⚠️ Security Note:[/bold yellow]")
    console.print("Press [bold white]ENTER[/bold white] to clear screen and exit.")
    console.input()


def _prompt_email(provided: str | None) -> str:
    """Prompt for or validate the user's email address."""
    if not provided:
        console.print("\n[bold cyan]Step 1: Email Verification[/bold cyan]")
        email = Prompt.ask("  Enter your Perplexity email", console=console)
    else:
        console.print(f"\n[bold cyan]Step 1: Email Verification[/bold cyan] (using [white]{provided}[/white])")
        email = provided

    email = email.strip()

    if not email or "@" not in email:
        raise ValueError("Invalid email address.")

    return email


def _fetch_csrf(session: Session) -> str:
    """Obtain a CSRF token from Perplexity's auth endpoint."""
    with console.status("[bold green]Initializing secure connection...", spinner="dots"):
        session.get(API_BASE_URL)
        csrf_response = session.get(f"{API_BASE_URL}{ENDPOINT_AUTH_CSRF}")
        csrf_response.raise_for_status()
        csrf_token: str = csrf_response.json().get("csrfToken", "")

        if not csrf_token:
            raise ValueError("Failed to obtain CSRF token.")

    return csrf_token


def _send_otp(session: Session, email: str, csrf_token: str) -> None:
    """Send an OTP email to the given address."""
    with console.status("[bold green]Sending verification code...", spinner="dots"):
        response = session.post(
            f"{API_BASE_URL}{ENDPOINT_AUTH_SIGNIN}?version={API_VERSION}&source=default",
            json={
                "email": email,
                "csrfToken": csrf_token,
                "useNumericOtp": "true",
                "json": "true",
                "callbackUrl": f"{API_BASE_URL}/?login-source=floatingSignup",
            },
        )
        response.raise_for_status()


def _resolve_redirect_url(session: Session, email: str, otp_code: str) -> str:
    """Convert an OTP code or magic link into a redirect URL."""
    if otp_code.startswith("http"):
        return otp_code

    otp_response = session.post(
        f"{API_BASE_URL}{ENDPOINT_AUTH_OTP_REDIRECT}",
        json={
            "email": email,
            "otp": otp_code,
            "redirectUrl": f"{API_BASE_URL}/?login-source=floatingSignup",
            "emailLoginMethod": "web-otp",
        },
    )
    otp_response.raise_for_status()

    redirect_path = otp_response.json().get("redirect", "")

    if not redirect_path:
        raise ValueError("No redirect URL received.")

    return f"{API_BASE_URL}{redirect_path}" if redirect_path.startswith("/") else redirect_path


def _follow_callback(session: Session, redirect_url: str) -> str | None:
    """Follow the callback and return a TOTP challenge token if 2FA is required."""
    callback_resp = session.get(redirect_url, allow_redirects=False)

    if callback_resp.status_code not in (301, 302, 307, 308):
        return None

    location = callback_resp.headers.get("Location", "")

    if "error=" in location:
        raise ValueError("Verification failed. The OTP code may be invalid or expired.")

    if "/auth/totp-challenge" in location:
        parsed = urlparse(location if location.startswith("http") else f"{API_BASE_URL}{location}")
        challenge_token = parse_qs(parsed.query).get("token", [""])[0]

        if not challenge_token:
            raise ValueError("TOTP challenge token not found in redirect.")

        return challenge_token

    # Normal flow — follow the redirect
    follow_url = location if location.startswith("http") else f"{API_BASE_URL}{location}"
    session.get(follow_url)

    return None


def _verify_totp(session: Session, challenge_token: str) -> None:
    """Prompt for and verify a TOTP code, then follow any post-verification redirect."""
    console.print("\n[bold cyan]Step 3: Two-Factor Authentication[/bold cyan]")
    console.print("  Your account has TOTP enabled. Enter the code from your authenticator app.")

    verify_url = f"{API_BASE_URL}{ENDPOINT_AUTH_TOTP_CHALLENGE_VERIFY}?version={API_VERSION}&source=default"

    while True:
        totp_code = Prompt.ask("  Enter TOTP code", console=console).strip()

        if not totp_code or not totp_code.isdigit() or len(totp_code) != 6:
            console.print("[red]  Invalid format. TOTP code must be a 6-digit number.[/red]")
            continue

        with console.status("[bold green]Verifying TOTP...", spinner="dots"):
            totp_verify_response = session.post(
                verify_url,
                json={"token": challenge_token, "code": totp_code},
            )

            try:
                totp_verify_response.raise_for_status()
            except Exception:
                with suppress(Exception):
                    totp_data = totp_verify_response.json()

                    if "error" in totp_data:
                        console.print(f"[red]  ❌ {totp_data.get('error')}[/red]")
                        continue

                raise

            if totp_verify_response.status_code in (301, 302, 307, 308):
                next_location = totp_verify_response.headers.get("Location", "")

                if next_location:
                    next_url = next_location if next_location.startswith("http") else f"{API_BASE_URL}{next_location}"
                    session.get(next_url)

                break

            totp_data = totp_verify_response.json()

            if "error" in totp_data:
                console.print(f"[red]  ❌ {totp_data.get('error')}[/red]")
                continue

            next_redirect = totp_data.get("redirect", "")

            if next_redirect:
                next_url = f"{API_BASE_URL}{next_redirect}" if next_redirect.startswith("/") else next_redirect
                session.get(next_url)

            break


def _extract_and_present_token(session: Session) -> None:
    """Extract the session cookie, display the token, and offer clipboard copy."""
    session_token = session.cookies.get(SESSION_COOKIE_NAME)

    if not session_token:
        raise ValueError("Authentication successful, but token not found.")

    console.print("\n[bold green]✅ Token generated successfully![/bold green]")
    console.print(f"\n[bold white]Your session token:[/bold white]\n[green]{session_token}[/green]\n")

    if Confirm.ask("Copy token to clipboard?", default=False, console=console):
        try:
            copy(session_token)
            console.print("[dim]Token copied to clipboard.[/dim]")
        except PyperclipException as error:
            console.print(f"[red]Could not copy to clipboard: {error}[/red]")


def run(
    email: Annotated[str | None, typer.Argument(help="Your Perplexity account email.")] = None,
) -> None:
    """Extract your Perplexity session token using email OTP authentication.

    Guides the user through email-based sign-in (OTP or magic link),
    displays the extracted session token, and offers to copy it to the
    clipboard. The screen is cleared on exit for security.
    """
    with console.screen(hide_cursor=False):
        try:
            _show_header()

            email = _prompt_email(email)

            with Session(impersonate="chrome", headers=_DEFAULT_HEADERS) as session:
                csrf_token = _fetch_csrf(session)
                _send_otp(session, email, csrf_token)

                console.print("\n[bold cyan]Step 2: Verification[/bold cyan]")
                console.print("  Check your email for a [bold]6-digit code[/bold] or [bold]magic link[/bold].")

                while True:
                    otp_code = Prompt.ask("  Enter code or paste link", console=console).strip()

                    if not otp_code:
                        console.print("[red]  OTP code cannot be empty.[/red]")
                        continue

                    if not otp_code.startswith("http") and (not otp_code.isdigit() or len(otp_code) != 6):
                        console.print("[red]  Invalid format. Enter a 6-digit code or a valid magic link.[/red]")
                        continue

                    try:
                        with console.status("[bold green]Validating...", spinner="dots"):
                            redirect_url = _resolve_redirect_url(session, email, otp_code)
                            challenge_token = _follow_callback(session, redirect_url)
                        break
                    except ValueError as e:
                        if "Verification failed" in str(e):
                            console.print(f"[red]  ❌ {e}[/red]")
                            console.print(
                                "[yellow]  The previous request was invalidated. Resending a new code...[/yellow]"
                            )
                            _send_otp(session, email, csrf_token)
                            console.print("  Check your email for the [bold]new[/bold] 6-digit code.")
                            continue

                        raise

                if challenge_token:
                    _verify_totp(session, challenge_token)

                _extract_and_present_token(session)
                _show_exit_message()
        except KeyboardInterrupt:
            raise typer.Exit(code=0) from None
        except Exception as error:
            console.print(f"\n[bold red]⛔ Error:[/bold red] {error}")
            console.input("[dim]Press ENTER to exit...[/dim]")

            raise typer.Exit(code=1) from error
