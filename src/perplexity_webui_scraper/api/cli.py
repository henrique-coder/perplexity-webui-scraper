"""Typer CLI for the OpenAI-compatible Perplexity API server."""

from __future__ import annotations

from typing import Annotated

import typer


try:
    import uvicorn as _uvicorn  # noqa: F401

    _HAS_UVICORN = True
except ImportError:
    _HAS_UVICORN = False


app = typer.Typer(
    name="perplexity-webui-scraper-api",
    help="OpenAI-compatible API server powered by Perplexity WebUI Scraper.",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(
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
    """Start the OpenAI-compatible API server.

    Authentication is done per-request via the Authorization: Bearer header.
    Pass your Perplexity session token as the API key in every request.
    """

    if not _HAS_UVICORN:
        typer.echo(
            "Error: uvicorn is not installed. Install the 'api' extras:\n\n"
            "  uv sync --extra api\n"
            "  pip install perplexity-webui-scraper[api]",
            err=True,
        )
        raise typer.Exit(code=1)

    import uvicorn  # noqa: PLC0415

    typer.echo(
        f"Starting Perplexity API server at http://{host}:{port}\n"
        f"  Docs:  http://{host}:{port}/docs\n"
        f"  ReDoc: http://{host}:{port}/redoc\n"
        f"  Auth:  Authorization: Bearer <your_session_token>"
    )

    uvicorn.run(
        "perplexity_webui_scraper.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )
