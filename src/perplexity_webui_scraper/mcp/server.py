"""FastMCP server instance and client lifecycle management."""

from __future__ import annotations

from os import environ

from fastmcp import FastMCP

from perplexity_webui_scraper import Perplexity
from perplexity_webui_scraper.config.client import ClientConfig
from perplexity_webui_scraper.mcp.tools import register_all_tools


mcp: FastMCP = FastMCP(name="perplexity-webui-scraper")  # type: ignore[type-arg]

_client: Perplexity | None = None


def _get_client() -> Perplexity:
    """Return the singleton Perplexity client, creating it on first call.

    Reads the ``PERPLEXITY_SESSION_TOKEN`` environment variable.

    Returns:
        Active :class:`~perplexity_webui_scraper.Perplexity` instance.

    Raises:
        RuntimeError: If the environment variable is not set.
    """
    global _client  # noqa: PLW0603

    if _client is None:
        token = environ.get("PERPLEXITY_SESSION_TOKEN", "")

        if not token:
            raise RuntimeError(
                "PERPLEXITY_SESSION_TOKEN environment variable is not set. "
                "Set it before starting the MCP server:\n\n"
                "  PERPLEXITY_SESSION_TOKEN=<token> perplexity-webui-scraper mcp"
            )

        _client = Perplexity(token, config=ClientConfig())

    return _client


register_all_tools(mcp, _get_client)


def run_server() -> None:
    """Start the MCP server (blocking).  Call from ``__main__`` only."""
    mcp.run()


def main() -> None:
    """Console script entry point."""
    run_server()
