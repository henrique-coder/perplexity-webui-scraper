"""get-session-token CLI command — extracts the Perplexity session cookie.

Uses the email → OTP code → redirect-link → cookie extraction flow via curl-cffi.
"""

from __future__ import annotations

from typing import Annotated

from curl_cffi.requests import Session
from pyperclip import PyperclipException, copy
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
import typer

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    ENDPOINT_AUTH_CSRF,
    ENDPOINT_AUTH_OTP_REDIRECT,
    ENDPOINT_AUTH_SIGNIN,
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


def run(
    email: Annotated[str | None, typer.Argument(help="Your Perplexity account email.")] = None,
) -> None:
    """Extract your Perplexity session token using email OTP authentication.

    Guides the user through email-based sign-in (OTP or magic link),
    displays the extracted session token, and offers to copy it to the
    clipboard. The screen is cleared on exit for security.
    """
    with console.screen():
        try:
            _show_header()

            if not email:
                console.print("\n[bold cyan]Step 1: Email Verification[/bold cyan]")
                email = Prompt.ask("  Enter your Perplexity email", console=console)
            else:
                console.print(f"\n[bold cyan]Step 1: Email Verification[/bold cyan] (using [white]{email}[/white])")

            email = email.strip()

            if not email or "@" not in email:
                raise ValueError("Invalid email address.")

            with Session(impersonate="chrome", headers=_DEFAULT_HEADERS) as session:
                # Step 1: Obtain CSRF token
                with console.status("[bold green]Initializing secure connection...", spinner="dots"):
                    session.get(API_BASE_URL)
                    csrf_response = session.get(f"{API_BASE_URL}{ENDPOINT_AUTH_CSRF}")
                    csrf_response.raise_for_status()
                    csrf_token: str = csrf_response.json().get("csrfToken", "")

                    if not csrf_token:
                        raise ValueError("Failed to obtain CSRF token.")

                # Step 2: Send OTP email
                with console.status("[bold green]Sending verification code...", spinner="dots"):
                    signin_response = session.post(
                        f"{API_BASE_URL}{ENDPOINT_AUTH_SIGNIN}?version=2.18&source=default",
                        json={
                            "email": email,
                            "csrfToken": csrf_token,
                            "useNumericOtp": "true",
                            "json": "true",
                            "callbackUrl": f"{API_BASE_URL}/?login-source=floatingSignup",
                        },
                    )
                    signin_response.raise_for_status()

                console.print("\n[bold cyan]Step 2: Verification[/bold cyan]")
                console.print("  Check your email for a [bold]6-digit code[/bold] or [bold]magic link[/bold].")

                # Step 3: Prompt user for OTP code
                otp_code = Prompt.ask("  Enter code or paste link", console=console).strip()

                if not otp_code:
                    raise ValueError("OTP code cannot be empty.")

                # Step 4: Convert OTP to redirect URL
                with console.status("[bold green]Validating...", spinner="dots"):
                    if otp_code.startswith("http"):
                        redirect_url = otp_code
                    else:
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

                        redirect_url = (
                            f"{API_BASE_URL}{redirect_path}" if redirect_path.startswith("/") else redirect_path
                        )

                    # Step 5: Follow redirect to set session cookie
                    session.get(redirect_url)

                    # Step 6: Extract session cookie
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

                _show_exit_message()

        except KeyboardInterrupt:
            raise typer.Exit(code=0) from None
        except Exception as error:
            console.print(f"\n[bold red]⛔ Error:[/bold red] {error}")
            console.input("[dim]Press ENTER to exit...[/dim]")
            raise typer.Exit(code=1) from error
