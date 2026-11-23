"""Unified CLI dispatcher; feature commands are provided by optional extras."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Annotated, Any

from typer import Context, Exit, Option, Typer, echo


if TYPE_CHECKING:
    from collections.abc import Callable


_COMMANDS: dict[str, tuple[str, str, str]] = {
    "token": ("perplexity_webui_scraper.cli.commands.token", "run_command", "token"),
    "api": ("perplexity_webui_scraper.api.launcher", "main", "api"),
    "mcp": ("perplexity_webui_scraper.mcp.server", "main", "mcp"),
}
_OPTIONAL_MODULES: dict[str, set[str]] = {
    "token": {"typer", "rich", "pyperclip", "prompt_toolkit"},
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

_token_cli = Typer(
    name="token",
    help="Generate, convert, or restore Perplexity session credentials.",
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
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


@_token_cli.callback()
def token(
    context: Context,
    email: Annotated[str | None, Option("-e", "--email", help="Perplexity account email.")] = None,
) -> None:
    """Generate, convert, or restore Perplexity session credentials."""
    operation = context.invoked_subcommand

    if operation:
        if email is not None:
            echo("The --email option cannot be combined with convert or deconvert.", err=True)
            raise Exit(code=2)

        return

    try:
        token_command, _ = _load_command("token")
    except SystemExit as error:
        echo(str(error), err=True)
        raise Exit(code=1) from error

    token_command(email)


@_token_cli.command(
    name="convert",
    context_settings={
        "help_option_names": ["-h", "--help"],
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def token_convert(context: Context) -> None:
    """Convert a raw cookie or wsk_ token to the compact wsk_ format."""
    if context.args:
        echo(
            "Passing credentials as command-line arguments is not supported. "
            "Run the command without arguments to use the masked prompt.",
            err=True,
        )
        raise Exit(code=2)

    try:
        transform = _load_token_transform()
    except SystemExit as error:
        echo(str(error), err=True)
        raise Exit(code=1) from error

    transform(None, deconvert=False, interactive=True)


@_token_cli.command(
    name="deconvert",
    context_settings={
        "help_option_names": ["-h", "--help"],
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def token_deconvert(context: Context) -> None:
    """Restore a raw session-cookie pair from a wsk_ token or raw cookie."""
    if context.args:
        echo(
            "Passing credentials as command-line arguments is not supported. "
            "Run the command without arguments to use the masked prompt.",
            err=True,
        )
        raise Exit(code=2)

    try:
        transform = _load_token_transform()
    except SystemExit as error:
        echo(str(error), err=True)
        raise Exit(code=1) from error

    transform(None, deconvert=True, interactive=True)


cli.add_typer(_token_cli, name="token", context_settings={"help_option_names": ["-h", "--help"]})
_token_group_info = next(group for group in cli.registered_groups if group.typer_instance is _token_cli)
_token_group_info.invoke_without_command = True
_token_group_info.no_args_is_help = False


def _load_token_transform() -> Callable[..., Any]:
    """Load the shared credential transform from the optional token command."""
    module_name, _, _ = _COMMANDS["token"]

    try:
        module = import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name in _OPTIONAL_MODULES["token"]:
            raise SystemExit("Install perplexity-webui-scraper[token] to use token conversion") from error

        raise

    return module.run_transform_command


@cli.command(name="api", context_settings={"help_option_names": ["-h", "--help"]})
def api(
    host: Annotated[str, Option("--host", "-H", help="Host address to bind the server to.")] = "127.0.0.1",
    port: Annotated[int, Option("--port", "-p", help="Port to listen on.")] = 8000,
    reload: Annotated[bool, Option("--reload", help="Enable auto-reload for development.")] = False,
    log_level: Annotated[str, Option("--log-level", help="Uvicorn log level.")] = "info",
    session_token: Annotated[
        str | None,
        Option(
            "--session-token",
            envvar="PERPLEXITY_SESSION_TOKEN",
            help=(
                "Optional server-default Perplexity token (compact wsk_ or raw cookie). "
                "Runs without a password unless --api-key is also set."
            ),
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        Option(
            "--api-key",
            envvar="PERPLEXITY_API_KEY",
            help="Optional custom Bearer API key required on every request when --session-token is set.",
        ),
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
