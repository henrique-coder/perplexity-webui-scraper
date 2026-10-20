"""Typer CLI for launching the OpenAI-compatible Perplexity API server."""

from __future__ import annotations

from os import environ
from typing import Annotated

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typer import Option, Typer
from uvicorn import run as uvicorn_run


console = Console(stderr=True, soft_wrap=True)

app = Typer(
    name="perplexity-webui-scraper-api",
    help="OpenAI-compatible API server powered by Perplexity WebUI Scraper.",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def main(
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
    default_session_token: Annotated[
        str | None,
        Option("--session-token", envvar="PERPLEXITY_SESSION_TOKEN", help="Optional server-default Perplexity token."),
    ] = None,
    gateway_api_key: Annotated[
        str | None,
        Option("--api-key", envvar="PERPLEXITY_API_KEY", help="Gateway key required on each request when configured."),
    ] = None,
) -> None:
    """Start the OpenAI-compatible Perplexity API server.

    Authentication is done per-request via the ``Authorization: Bearer`` header.
    Pass your Perplexity session token as the API key in every request.
    """
    if default_session_token:
        environ["PERPLEXITY_SESSION_TOKEN"] = default_session_token

    if gateway_api_key:
        environ["PERPLEXITY_API_KEY"] = gateway_api_key

    if environ.get("PERPLEXITY_SESSION_TOKEN") and not environ.get("PERPLEXITY_API_KEY"):
        raise ValueError("PERPLEXITY_SESSION_TOKEN requires PERPLEXITY_API_KEY for gateway authentication")

    info = Text.assemble(
        ("🌐  URL:   ", "bold cyan"),
        (f"http://{host}:{port}\n", "white"),
        ("📖  Docs:  ", "bold cyan"),
        (f"http://{host}:{port}/docs\n", "white"),
        ("📘  ReDoc: ", "bold cyan"),
        (f"http://{host}:{port}/redoc\n", "white"),
        ("🔑  Auth:  ", "bold cyan"),
        (
            "X-API-Key + server session token"
            if environ.get("PERPLEXITY_SESSION_TOKEN")
            else "Authorization: Bearer <Perplexity token>",
            "dim white",
        ),
    )
    console.print(Panel(info, title="[bold green]Perplexity API Server[/bold green]", expand=False))

    uvicorn_run(
        "perplexity_webui_scraper.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )
