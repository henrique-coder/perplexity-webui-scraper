"""Typer CLI for the OpenAI-compatible Perplexity API server."""

from __future__ import annotations

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
) -> None:
    """Start the OpenAI-compatible API server.

    Authentication is done per-request via the Authorization: Bearer header.
    Pass your Perplexity session token as the API key in every request.
    """
    info = Text.assemble(
        ("🌐  URL:   ", "bold cyan"),
        (f"http://{host}:{port}\n", "white"),
        ("📖  Docs:  ", "bold cyan"),
        (f"http://{host}:{port}/docs\n", "white"),
        ("📘  ReDoc: ", "bold cyan"),
        (f"http://{host}:{port}/redoc\n", "white"),
        ("🔑  Auth:  ", "bold cyan"),
        ("Authorization: Bearer <your_session_token>", "dim white"),
    )
    console.print(Panel(info, title="[bold green]Perplexity API Server[/bold green]", expand=False))

    uvicorn_run(
        "perplexity_webui_scraper.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )
