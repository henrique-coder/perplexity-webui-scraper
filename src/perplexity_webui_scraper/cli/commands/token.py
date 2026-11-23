"""Typer command for email-based Perplexity session authentication."""

from __future__ import annotations

from contextlib import nullcontext, suppress
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
from perplexity_webui_scraper.auth.session_token import pack_session_token, resolve_session_token


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


def _print_error(label: str, error: BaseException) -> None:
    """Print a sanitized error line without markup interpretation or blank details."""
    detail = str(error) or type(error).__name__
    console.print(f"[bold red]{label}[/bold red] ", end="")
    console.print(detail, markup=False, highlight=False)


def _wait_for_enter(message: str) -> None:
    """Wait for ENTER in interactive terminals without failing on Ctrl+C or EOF."""
    if not sys_stdin_is_tty():
        return

    with suppress(KeyboardInterrupt, EOFError):
        console.input(message)


def _offer_clipboard_copy(credential: str) -> None:
    """Ask before copying a credential to the system clipboard."""
    if not Confirm.ask("Copy credential to clipboard?", default=False, console=console):
        return

    try:
        copy(credential)
    except PyperclipException as error:
        _print_error("Could not copy to clipboard:", error)
    else:
        console.print("[bold green]Credential copied to clipboard.[/bold green]")


def _prompt_email(provided: str | None) -> str:
    """Prompt for an email address and reject empty or malformed input."""
    if provided is not None:
        email = provided.strip()

        if not email or "@" not in email:
            raise ValueError("Invalid email address.")

        return email

    while True:
        email = Prompt.ask("Perplexity account email", console=console).strip()

        if email and "@" in email:
            return email

        console.print("[bold yellow]Enter a valid email address.[/bold yellow]")


def _prompt_totp() -> str:
    """Prompt for a six-digit authenticator-app code."""
    console.print("\n[bold cyan]Two-factor authentication[/bold cyan]")
    console.print("Enter the code from your authenticator app.")

    return Prompt.ask("TOTP code", console=console)


def _prompt_otp(email: str) -> str:
    """Prompt until the user provides a valid code or magic link."""
    while True:
        value = Prompt.ask(
            "Enter the 6-digit code or paste the magic link",
            console=console,
        ).strip()

        if validate_otp_input(value, email):
            return value

        console.print(
            "[bold yellow]Invalid format. Enter six digits or an HTTPS Perplexity "
            "email link for this account.[/bold yellow]"
        )


def _run_transform(value: str | None, *, deconvert: bool, interactive: bool = True) -> None:
    """Apply a credential transform, prompting again when TTY input is invalid."""
    screen_context = console.screen(hide_cursor=False) if sys_stdin_is_tty() else nullcontext()

    try:
        with screen_context:
            _run_transform_value(value, deconvert=deconvert, interactive=interactive)
    except KeyboardInterrupt:
        raise Exit(code=0) from None
    except EOFError:
        console.print("[bold red]Input closed; no credential was processed.[/bold red]")
        raise Exit(code=1) from None


def _run_transform_value(value: str | None, *, deconvert: bool, interactive: bool) -> None:
    """Transform and display a credential inside the selected terminal context."""
    prompt_text = "Paste a raw cookie or wsk_ token"

    if value is None:
        _show_header(conversion=True)

    while True:
        entered = value if value is not None else Prompt.ask(prompt_text, console=console, password=True)

        try:
            credentials = resolve_session_token(entered)
        except (SessionTokenError, ValueError) as error:
            if value is not None or not (interactive and sys_stdin_is_tty()):
                _print_error("Invalid credential:", error)
                raise Exit(code=1) from error

            _print_error("Invalid session credential:", error)
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
    _offer_clipboard_copy(result)
    _wait_for_enter("[bold cyan]Press ENTER to clear the screen and exit...[/bold cyan]")


def run_transform_command(value: str | None, *, deconvert: bool, interactive: bool) -> None:
    """Run the shared conversion workflow from either CLI operation."""
    _run_transform(value, deconvert=deconvert, interactive=interactive)


def run_command(email: str | None = None) -> None:
    """Authenticate via email/TOTP and emit a compact wsk_ session token."""
    screen_context = console.screen(hide_cursor=False) if sys_stdin_is_tty() else nullcontext()

    try:
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
                _offer_clipboard_copy(credential)
                console.print(
                    "\n[bold yellow]Keep this credential private; it grants access to your account.[/bold yellow]"
                )
                _wait_for_enter("[bold cyan]Press ENTER to clear the screen and exit...[/bold cyan]")
            except (Exit, KeyboardInterrupt, EOFError):
                raise
            except Exception as error:
                _print_error("\nAuthentication failed:", error)
                _wait_for_enter("[bold cyan]Press ENTER to exit...[/bold cyan]")
                raise Exit(code=1) from error
    except KeyboardInterrupt:
        raise Exit(code=0) from None
    except EOFError:
        console.print("[bold red]Authentication cancelled: input closed.[/bold red]")
        raise Exit(code=1) from None


__all__ = ["run_command", "run_transform_command"]
