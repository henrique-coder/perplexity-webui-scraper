"""Unified command entry point: python -m perplexity_webui_scraper.cli."""

from __future__ import annotations

from typing import Annotated

from typer import Argument, Context, Option, Typer


cli = Typer(
    name="perplexity-webui-scraper",
    help="Perplexity WebUI Scraper command line tools.",
    add_completion=False,
    no_args_is_help=True,
)

chat_app = Typer(
    name="chat",
    help="Chat with Perplexity AI directly from the terminal.",
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"allow_interspersed_args": True},
)


@chat_app.callback(invoke_without_command=True)
def chat(
    ctx: Context,
    query: Annotated[
        str | None,
        Argument(help="The initial question to ask Perplexity AI (optional)."),
    ] = None,
    model: Annotated[
        str | None,
        Argument(help="Model ID (e.g. 'perplexity/best')."),
    ] = None,
    search_focus: Annotated[
        str,
        Option("--search-focus", "-sf", help="Search mode: 'web' or 'writing'."),
    ] = "web",
    source_focus: Annotated[
        str,
        Option("--source-focus", "-SF", help="Source filter: 'web', 'academic', 'social', 'finance', 'all'."),
    ] = "web",
    time_range: Annotated[
        str,
        Option("--time-range", "-tr", help="Recency filter: 'all', 'day', 'week', 'month', 'year'."),
    ] = "all",
    citation_mode: Annotated[
        str,
        Option("--citation-mode", "-cm", help="Citation style: 'default', 'markdown', 'clean'."),
    ] = "clean",
    language: Annotated[
        str,
        Option("--language", "-l", help="Response language (BCP-47 tag, e.g. 'en-US', 'pt-BR')."),
    ] = "en-US",
    files: Annotated[
        list[str] | None,
        Option("--file", "-f", help="File attachment paths (repeatable)."),
    ] = None,
    timezone: Annotated[
        str | None,
        Option("--timezone", "-tz", help="IANA timezone string for localization (e.g., 'America/Sao_Paulo')."),
    ] = None,
    latitude: Annotated[
        float | None,
        Option("--latitude", "-lat", help="Latitude for location-aware results."),
    ] = None,
    longitude: Annotated[
        float | None,
        Option("--longitude", "-lon", help="Longitude for location-aware results."),
    ] = None,
    space_uuid: Annotated[
        str | None,
        Option("--space", "-s", help="UUID of a Perplexity Space (collection) to post into."),
    ] = None,
    save: Annotated[
        bool,
        Option("--save/--no-save", help="Save conversation to your Perplexity library."),
    ] = False,
    copy: Annotated[
        bool,
        Option("--copy", "-cp", help="Copy the final answer to clipboard."),
    ] = False,
    raw: Annotated[
        bool,
        Option("--raw", "-r", help="Plain text output without Rich formatting."),
    ] = False,
    token: Annotated[
        str | None,
        Option("--token", "-t", help="Session token override (skips saved token)."),
    ] = None,
) -> None:
    """Ask Perplexity AI a question with real-time streaming."""
    if ctx.invoked_subcommand is not None:
        return

    if query == "setup" and model is None:
        from perplexity_webui_scraper.cli.commands.chat import setup as run_setup  # noqa: PLC0415

        run_setup()
        return

    # Start REPL or single query if query is provided

    from perplexity_webui_scraper.cli.commands.chat import run as run_chat  # noqa: PLC0415

    run_chat(
        query=query,
        model=model,
        search_focus=search_focus,
        source_focus=source_focus,
        time_range=time_range,
        citation_mode=citation_mode,
        language=language,
        files=files,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        space_uuid=space_uuid,
        save=save,
        copy=copy,
        raw=raw,
        token=token,
    )


@chat_app.command()
def setup() -> None:
    """Interactive setup wizard — configure token and default model."""
    from perplexity_webui_scraper.cli.commands.chat import setup as run_setup  # noqa: PLC0415

    run_setup()


cli.add_typer(chat_app)


@cli.command(name="token")
def token(
    email: Annotated[str | None, Argument(help="Your Perplexity account email.")] = None,
) -> None:
    """Generate a Perplexity session token via email OTP or magic link."""
    from perplexity_webui_scraper.cli.commands.get_session_token import run  # noqa: PLC0415

    run(email)


@cli.command(name="api")
def api(
    host: Annotated[
        str,
        Option("--host", "-H", help="Host address to bind the server to."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        Option("--port", "-p", help="Port to listen on."),
    ] = 8000,
    reload: Annotated[
        bool,
        Option("--reload", help="Enable auto-reload for development."),
    ] = False,
    log_level: Annotated[
        str,
        Option("--log-level", help="Uvicorn log level."),
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
