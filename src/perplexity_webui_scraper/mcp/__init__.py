"""
MCP (Model Context Protocol) server for Perplexity WebUI Scraper.

This module provides an MCP server that exposes Perplexity AI search capabilities to AI assistants.
"""

from __future__ import annotations


__all__: list[str] = ["run_server"]


def run_server() -> None:
    """Run the MCP server."""

    from .server import main  # noqa: PLC0415

    main()
