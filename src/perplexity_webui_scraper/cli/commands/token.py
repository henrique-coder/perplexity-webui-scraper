"""Typer command for email-based Perplexity session authentication."""

from __future__ import annotations

from contextlib import nullcontext
from sys import stdin

from pyperclip import PyperclipException, copy
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from typer import Exit

from perplexity_webui_scraper._internal.constants import SESSION_COOKIE_PREFIX
from perplexity_webui_scraper._internal.exceptions import SessionTokenError
from perplexity_webui_scraper.auth.cookies import CookieCredential, serialize_session_credential
from perplexity_webui_scraper.auth.email import authenticate, validate_otp_input
from perplexity_webui_scraper.auth.session_token import (
    pack_session_token,
    resolve_session_token,
    unpack_session_token,
)


console = Console(stderr=True, soft_wrap=True, color_system="standard")


def sys_stdin_is_tty() -> bool:
    """Return whether an invalid CLI argument can be corrected interactively."""
    return stdin.isatty()


def _show_header(*, conversion: bool = False) -> None:
    """Display a compact description of the active token workflow."""
    if conversion:
        title = "Credential conversion"
        body = (
            "[bold white]Perplexity WebUI Scraper[/bold white]\n\n"
            "Validate or convert Perplexity session credentials offline."
        )
    else:
        title = "Session sign-in"
        body = (
            "[bold white]Perplexity WebUI Scraper[/bold white]\n\n"
            "Sign in with your Perplexity email to generate a compact wsk_ session token."
        )

    console.print(Panel(body, title=title, border_style="cyan", expand=False))


def _prompt_email(provided: str | None) -> str:
    """Prompt for an email address and reject empty or malformed input."""
    email = provided.strip() if provided else Prompt.ask("Perplexity account email", console=console).strip()
    if not email or "@" not in email:
        raise ValueError("Invalid email address.")
    return email


def _prompt_totp() -> str:
    """Prompt for a six-digit authenticator-app code without echoing it."""
    console.print("\n[bold cyan]Two-factor authentication[/bold cyan]")
    console.print("Enter the code from your authenticator app.")
    return Prompt.ask("TOTP code", console=console, password=True)


def _prompt_otp(email: str) -> str:
    """Prompt until the user provides a code or magic link without echoing it."""
    while True:
        value = Prompt.ask(
            "Enter the 6-digit code or paste the magic link",
            console=console,
            password=True,
        ).strip()
        if validate_otp_input(value, email):
            return value
        console.print(
            "[bold yellow]Invalid format. Enter six digits or an HTTPS Perplexity "
            "email link for this account.[/bold yellow]"
        )


def _run_transform(value: str | None, *, deconvert: bool, interactive: bool = True) -> None:
    """Apply a credential transform, prompting again when TTY input is invalid."""
    if sys_stdin_is_tty():
        with console.screen(hide_cursor=False):
            _run_transform_value(value, deconvert=deconvert, interactive=interactive)
        return

    _run_transform_value(value, deconvert=deconvert, interactive=interactive)


def _run_transform_value(value: str | None, *, deconvert: bool, interactive: bool) -> None:
    """Transform and display a credential inside the selected terminal context."""
    prompt_text = "Paste a compact wsk_ token" if deconvert else "Paste a raw cookie or wsk_ token"
    if value is None:
        _show_header(conversion=True)

    while True:
        try:
            entered = value if value is not None else Prompt.ask(prompt_text, console=console, password=True)
        except KeyboardInterrupt:
            raise Exit(code=0) from None
        except EOFError:
            raise Exit(code=1) from None

        try:
            credentials = unpack_session_token(entered) if deconvert else resolve_session_token(entered)
        except (SessionTokenError, ValueError) as error:
            if value is not None or not (interactive and sys_stdin_is_tty()):
                console.print("[bold red]Invalid credential:[/bold red] ", end="")
                console.print(str(error), markup=False, highlight=False)
                raise Exit(code=1) from error

            error_text = "Invalid compact token" if deconvert else "Invalid session credential"
            console.print(f"[bold red]{error_text}:[/bold red] ", end="")
            console.print(str(error), markup=False, highlight=False)
            continue

        raw_cookie = serialize_session_credential(
            CookieCredential(name=f"{SESSION_COOKIE_PREFIX}{credentials.uuid}", value=credentials.cookie_value)
        )
        compact = pack_session_token(raw_cookie)
        result = raw_cookie if deconvert else compact
        label = "Raw session cookie" if deconvert else "Compact session token"
        _show_transform_result(result, label)
        return


def _show_transform_result(result: str, label: str) -> None:
    """Show a generated credential after clearing prior input and request clipboard consent."""
    if sys_stdin_is_tty():
        console.clear()
    console.print("[green]Validated session credential.[/green]")
    console.print(f"\n[bold white]{label}:[/bold white]")
    console.print(result, markup=False, highlight=False, soft_wrap=True)
    console.print("\n[bold yellow]Keep this credential private; it grants access to your account.[/bold yellow]")
    if Confirm.ask("Copy credential to clipboard?", default=False, console=console):
        try:
            copy(result)
        except PyperclipException as error:
            console.print("[bold red]Could not copy to clipboard:[/bold red] ", end="")
            console.print(str(error), markup=False, highlight=False)
        else:
            console.print("[bold green]Credential copied to clipboard.[/bold green]")
    if sys_stdin_is_tty():
        console.input("[bold cyan]Press ENTER to clear the screen and exit...[/bold cyan]")


def run_transform_command(value: str | None, *, deconvert: bool, interactive: bool) -> None:
    """Run the shared conversion workflow from either CLI operation."""
    _run_transform(value, deconvert=deconvert, interactive=interactive)


def run_command(email: str | None = None) -> None:
    """Authenticate via email/TOTP and emit a compact wsk_ session token."""
    screen_context = console.screen(hide_cursor=False) if sys_stdin_is_tty() else nullcontext()

    with screen_context:
        try:
            _show_header()
            resolved_email = _prompt_email(email)
            console.print("\n[bold cyan]Step 1: Email verification[/bold cyan]")
            console.print("A verification code will be sent to your email.")

            credential = authenticate(
                resolved_email,
                prompt_otp=lambda: _prompt_otp(resolved_email),
                prompt_totp=_prompt_totp,
                on_otp_submitted=lambda: console.print("[dim]Verifying email sign-in...[/dim]"),
                on_malformed_otp=lambda: console.print(
                    "[bold yellow]Invalid format. Enter six digits or an HTTPS Perplexity email link "
                    "for this account.[/bold yellow]"
                ),
                on_invalid_otp=lambda: console.print(
                    "[bold red]Code or link rejected. Enter a fresh one; no new email was sent.[/bold red]"
                ),
                on_invalid_totp=lambda: console.print("[red]TOTP code rejected. Enter a new code.[/red]"),
            )

            console.print("[green]Compact session token generated.[/green]")
            console.print("\n[bold white]Account session credential:[/bold white]")
            console.print(credential, style="green", markup=False, highlight=False, soft_wrap=True)

            if Confirm.ask("Copy credential to clipboard?", default=False, console=console):
                try:
                    copy(credential)
                except PyperclipException as error:
                    console.print("[bold red]Could not copy to clipboard:[/bold red] ", end="")
                    console.print(str(error), markup=False, highlight=False)
                else:
                    console.print("[bold green]Credential copied to clipboard.[/bold green]")

            console.print(
                "\n[bold yellow]Keep this credential private; it grants access to your account.[/bold yellow]"
            )

            if sys_stdin_is_tty():
                console.input("[bold cyan]Press ENTER to clear the screen and exit...[/bold cyan]")
        except Exit:
            raise
        except KeyboardInterrupt:
            raise Exit(code=0) from None
        except Exception as error:
            console.print("\n[bold red]Authentication failed:[/bold red] ", end="")
            console.print(str(error), markup=False, highlight=False)

            if sys_stdin_is_tty():
                console.input("[bold cyan]Press ENTER to exit...[/bold cyan]")

            raise Exit(code=1) from error


__all__ = ["run_command", "run_transform_command"]
