"""Unified CLI dispatcher; feature commands are provided by optional extras."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Annotated, Any

from typer import Exit, Option, Typer, echo


if TYPE_CHECKING:
    from collections.abc import Callable


_COMMANDS: dict[str, tuple[str, str, str]] = {
    "token": ("perplexity_webui_scraper.cli.commands.get_session_token", "run", "token"),
    "api": ("perplexity_webui_scraper.api.launcher", "main", "api"),
    "mcp": ("perplexity_webui_scraper.mcp.server", "main", "mcp"),
}

_OPTIONAL_MODULES: dict[str, set[str]] = {
    "token": {"typer", "rich", "pyperclip"},
    "api": {"typer", "fastapi", "rich", "uvicorn"},
    "mcp": {"fastmcp"},
}

cli = Typer(
    name="perplexity-webui-scraper",
    help="Perplexity WebUI Scraper optional commands.",
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _load_command(command_name: str) -> tuple[Callable[..., Any], str]:
    """Load a command implementation and identify its public extra if unavailable."""
    module_name, symbol, extra = _COMMANDS[command_name]
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name in _OPTIONAL_MODULES[extra]:
            raise SystemExit(f"Install perplexity-webui-scraper[{extra}] to use the {command_name} command") from error
        raise
    return getattr(module, symbol), extra


@cli.command(name="token", context_settings={"help_option_names": ["-h", "--help"]})
def token(
    email: Annotated[str | None, Option("-e", "--email", help="Perplexity account email.")] = None,
) -> None:
    """Generate a Perplexity session token through email authentication."""
    try:
        token_app, _ = _load_command("token")
    except SystemExit as error:
        echo(str(error), err=True)
        raise Exit(code=1) from error
    token_app(email)


@cli.command(
    name="api",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def api(
    host: Annotated[str, Option("--host", "-H", help="Host address to bind the server to.")] = "127.0.0.1",
    port: Annotated[int, Option("--port", "-p", help="Port to listen on.")] = 8000,
    reload: Annotated[bool, Option("--reload", help="Enable auto-reload for development.")] = False,
    log_level: Annotated[str, Option("--log-level", help="Uvicorn log level.")] = "info",
    session_token: Annotated[
        str | None,
        Option("--session-token", envvar="PERPLEXITY_SESSION_TOKEN", help="Optional server-default Perplexity token."),
    ] = None,
    api_key: Annotated[
        str | None,
        Option("--api-key", envvar="PERPLEXITY_API_KEY", help="Gateway key required on each request."),
    ] = None,
) -> None:
    """Start the OpenAI-compatible REST API server."""
    try:
        api_main, _ = _load_command("api")
    except SystemExit as error:
        echo(str(error), err=True)
        raise Exit(code=1) from error
    api_main(
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        default_session_token=session_token,
        gateway_api_key=api_key,
    )


@cli.command(name="mcp", context_settings={"help_option_names": ["-h", "--help"]})
def mcp() -> None:
    """Start the MCP server."""
    try:
        mcp_command, _ = _load_command("mcp")
    except SystemExit as error:
        echo(str(error), err=True)
        raise Exit(code=1) from error
    mcp_command()


def main() -> None:
    """Run the Typer command-line application."""
    cli()
