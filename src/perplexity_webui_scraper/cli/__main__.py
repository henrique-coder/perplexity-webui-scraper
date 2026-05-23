"""Unified command entry point: python -m perplexity_webui_scraper.cli."""

from __future__ import annotations

from typing import Annotated

import typer


cli = typer.Typer(
    name="perplexity-webui-scraper",
    help="Perplexity WebUI Scraper command line tools.",
    add_completion=False,
    no_args_is_help=True,
)


@cli.command(name="token")
def token(
    email: Annotated[str | None, typer.Argument(help="Your Perplexity account email.")] = None,
) -> None:
    """Generate a Perplexity session token via email OTP or magic link."""
    from perplexity_webui_scraper.cli.commands.get_session_token import run  # noqa: PLC0415

    run(email)


@cli.command(name="api")
def api(
    host: Annotated[
        str,
        typer.Option("--host", "-H", help="Host address to bind the server to."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to listen on."),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload for development."),
    ] = False,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Uvicorn log level."),
    ] = "info",
) -> None:
    """Start the OpenAI-compatible REST API server."""
    from perplexity_webui_scraper.api.launcher import main as run_api  # noqa: PLC0415

    run_api(host=host, port=port, reload=reload, log_level=log_level)


@cli.command(name="mcp")
def mcp() -> None:
    """Start the MCP server."""
    from perplexity_webui_scraper.mcp.server import main as run_mcp  # noqa: PLC0415

    run_mcp()


def main() -> None:
    """Console script entry point."""
    cli()


if __name__ == "__main__":
    main()
