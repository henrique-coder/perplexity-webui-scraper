"""get-session-token CLI command — extracts the Perplexity session cookie.

Uses the email → OTP code → redirect-link → cookie extraction flow via
curl-cffi (no Playwright/browser automation required).
"""

from __future__ import annotations

from time import sleep
from typing import Annotated

from curl_cffi.requests import Session
import typer

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    ENDPOINT_AUTH_CSRF,
    ENDPOINT_AUTH_OTP_REDIRECT,
    ENDPOINT_AUTH_SIGNIN,
    SESSION_COOKIE_NAME,
)


_DEFAULT_HEADERS: dict[str, str] = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": f"{API_BASE_URL}/",
    "Origin": API_BASE_URL,
}


def run(
    email: Annotated[str | None, typer.Argument(help="Your Perplexity account email.")] = None,
) -> None:
    """Extract your Perplexity session token using email OTP authentication.

    If email is not provided as an argument, you will be prompted interactively.
    The session token is printed to stdout so it can be piped or exported::

        export PERPLEXITY_SESSION_TOKEN=$(get-perplexity-session-token you@example.com)
    """
    if email is None:
        email = typer.prompt("Enter your Perplexity account email")

    email = email.strip()

    if not email or "@" not in email:
        typer.echo("Error: invalid email address.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"→ Sending OTP to {email} …", err=True)

    with Session(impersonate="chrome", headers=_DEFAULT_HEADERS) as session:
        # Step 1: Obtain CSRF token
        try:
            csrf_response = session.get(f"{API_BASE_URL}{ENDPOINT_AUTH_CSRF}")
            csrf_response.raise_for_status()
            csrf_token: str = csrf_response.json().get("csrfToken", "")
        except Exception as exc:
            typer.echo(f"Error: failed to fetch CSRF token: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if not csrf_token:
            typer.echo("Error: could not obtain CSRF token.", err=True)
            raise typer.Exit(code=1)

        # Step 2: Send OTP email
        try:
            signin_response = session.post(
                f"{API_BASE_URL}{ENDPOINT_AUTH_SIGNIN}",
                data={
                    "email": email,
                    "csrfToken": csrf_token,
                    "callbackUrl": f"{API_BASE_URL}/",
                    "json": "true",
                },
            )
            signin_response.raise_for_status()
        except Exception as exc:
            typer.echo(f"Error: failed to initiate sign-in: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        typer.echo("→ OTP email sent. Check your inbox.", err=True)

        # Step 3: Prompt user for OTP code
        otp_code: str = typer.prompt("Enter the 6-digit OTP code from your email").strip()

        if not otp_code:
            typer.echo("Error: OTP code cannot be empty.", err=True)
            raise typer.Exit(code=1)

        # Step 4: Convert OTP to redirect URL
        typer.echo("→ Verifying OTP …", err=True)

        try:
            otp_response = session.get(
                f"{API_BASE_URL}{ENDPOINT_AUTH_OTP_REDIRECT}",
                params={"email": email, "token": otp_code},
            )
            otp_response.raise_for_status()
            redirect_url: str = otp_response.json().get("url", "")
        except Exception as exc:
            typer.echo(f"Error: OTP verification failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if not redirect_url:
            typer.echo("Error: OTP verification returned no redirect URL.", err=True)
            raise typer.Exit(code=1)

        # Step 5: Follow redirect to set session cookie
        typer.echo("→ Completing authentication …", err=True)

        try:
            sleep(1)  # brief pause to let the session cookie propagate
            session.get(redirect_url, allow_redirects=True)
        except Exception as exc:
            typer.echo(f"Warning: redirect failed, but cookie may still be set: {exc}", err=True)

        # Step 6: Extract session cookie
        session_token: str | None = session.cookies.get(SESSION_COOKIE_NAME)

        if not session_token:
            typer.echo(
                f"Error: session cookie '{SESSION_COOKIE_NAME}' not found. "
                "The OTP may have expired or been entered incorrectly.",
                err=True,
            )
            raise typer.Exit(code=1)

    # Output only the token to stdout for shell capture
    typer.echo(session_token)

    typer.echo(
        "\n✓ Session token extracted successfully.\n"
        "  Store it as an environment variable:\n\n"
        f"    export PERPLEXITY_SESSION_TOKEN={session_token!r}",
        err=True,
    )
