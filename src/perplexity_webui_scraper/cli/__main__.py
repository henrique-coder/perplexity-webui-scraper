"""Entry point: python -m perplexity_webui_scraper.cli."""

from __future__ import annotations

import typer

from perplexity_webui_scraper.cli.commands.get_session_token import run as _get_session_token


cli = typer.Typer(
    name="perplexity-webui-scraper-cli",
    help="CLI tools for Perplexity WebUI Scraper.",
    add_completion=False,
)

cli.command(name="get-session-token")(_get_session_token)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
