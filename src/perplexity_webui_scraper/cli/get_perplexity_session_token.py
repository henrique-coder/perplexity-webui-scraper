"""CLI utility for secure Perplexity authentication and session extraction."""

from __future__ import annotations

from sys import exit
from typing import NoReturn

from curl_cffi import Session
from orjson import loads
from pyperclip import PyperclipException, copy
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt


BASE_URL: str = "https://www.perplexity.ai"

console = Console(stderr=True, soft_wrap=True)


def _initialize_session() -> tuple[Session, str]:
    """Initialize session and obtain CSRF token.

    Returns:
        A tuple of the initialized session and the CSRF token string.

    Raises:
        ValueError: If the CSRF token cannot be obtained from the API.
    """
    session = Session(impersonate="chrome", headers={"Referer": BASE_URL, "Origin": BASE_URL})

    with console.status("[bold green]Initializing secure connection...", spinner="dots"):
        session.get(BASE_URL)
        csrf_data = loads(session.get(f"{BASE_URL}/api/auth/csrf").content)
        csrf = csrf_data.get("csrfToken")

        if not csrf:
            raise ValueError("Failed to obtain CSRF token.")

    return session, csrf


def _request_verification_code(session: Session, csrf: str, email: str) -> None:
    """Send a verification code to the user's email address.

    Args:
        session: The active curl-cffi session.
        csrf: The CSRF token for the request.
        email: The user's Perplexity account email address.

    Raises:
        ValueError: If the authentication request returns a non-200 status.
    """
    with console.status("[bold green]Sending verification code...", spinner="dots"):
        response = session.post(
            f"{BASE_URL}/api/auth/signin/email?version=2.18&source=default",
            json={
                "email": email,
                "csrfToken": csrf,
                "useNumericOtp": "true",
                "json": "true",
                "callbackUrl": f"{BASE_URL}/?login-source=floatingSignup",
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Authentication request failed: {response.text}")


def _validate_and_get_redirect_url(session: Session, email: str, user_input: str) -> str:
    """Validate the OTP or magic link and return the authentication redirect URL.

    Args:
        session: The active curl-cffi session.
        email: The user's Perplexity account email address.
        user_input: Either a 6-digit OTP code or a magic link URL.

    Returns:
        The full redirect URL to complete authentication.

    Raises:
        ValueError: If the code is invalid or no redirect URL is returned.
    """
    with console.status("[bold green]Validating...", spinner="dots"):
        if user_input.startswith("http"):
            return user_input

        response_otp = session.post(
            f"{BASE_URL}/api/auth/otp-redirect-link",
            json={
                "email": email,
                "otp": user_input,
                "redirectUrl": f"{BASE_URL}/?login-source=floatingSignup",
                "emailLoginMethod": "web-otp",
            },
        )

        if response_otp.status_code != 200:
            raise ValueError("Invalid verification code.")

        redirect_path = loads(response_otp.content).get("redirect")

        if not redirect_path:
            raise ValueError("No redirect URL received.")

        return f"{BASE_URL}{redirect_path}" if redirect_path.startswith("/") else redirect_path


def _extract_session_token(session: Session, redirect_url: str) -> str:
    """Extract the session token from cookies after completing authentication.

    Args:
        session: The active curl-cffi session.
        redirect_url: The full redirect URL returned after OTP/link validation.

    Returns:
        The raw ``__Secure-next-auth.session-token`` cookie value.

    Raises:
        ValueError: If the token cookie is not found after the redirect.
    """
    session.get(redirect_url)
    token = session.cookies.get("__Secure-next-auth.session-token")

    if not token:
        raise ValueError("Authentication successful, but token not found.")

    return token


def _display_and_copy_token(token: str) -> None:
    """Display the token and optionally copy it to the system clipboard.

    Prompts the user with a yes/no question (default: yes). If confirmed,
    copies the token to the clipboard using ``pyperclip``.

    Args:
        token: The raw session token string to display and copy.
    """
    console.print("\n[bold green]✅ Token generated successfully![/bold green]")
    console.print(f"\n[bold white]Your session token:[/bold white]\n[green]{token}[/green]\n")

    if Confirm.ask("Copy token to clipboard?", default=True, console=console):
        try:
            copy(token)
            console.print("[dim]Token copied to clipboard.[/dim]")
        except PyperclipException as error:
            console.print(f"[red]Could not copy to clipboard: {error}[/red]")


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


def get_token() -> NoReturn:
    """Run the full authentication flow inside an ephemeral terminal screen.

    Guides the user through email-based sign-in (OTP or magic link),
    displays the extracted session token, and offers to copy it to the
    clipboard. The screen is cleared on exit for security.
    """
    with console.screen():
        try:
            _show_header()

            session, csrf = _initialize_session()

            console.print("\n[bold cyan]Step 1: Email Verification[/bold cyan]")
            email = Prompt.ask("  Enter your Perplexity email", console=console)
            _request_verification_code(session, csrf, email)

            console.print("\n[bold cyan]Step 2: Verification[/bold cyan]")
            console.print("  Check your email for a [bold]6-digit code[/bold] or [bold]magic link[/bold].")
            user_input = Prompt.ask("  Enter code or paste link", console=console).strip()
            redirect_url = _validate_and_get_redirect_url(session, email, user_input)

            token = _extract_session_token(session, redirect_url)

            _display_and_copy_token(token)

            _show_exit_message()

            exit(0)
        except KeyboardInterrupt:
            exit(0)
        except Exception as error:
            console.print(f"\n[bold red]⛔ Error:[/bold red] {error}")
            console.input("[dim]Press ENTER to exit...[/dim]")
            exit(1)


if __name__ == "__main__":
    get_token()
