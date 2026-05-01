"""MCP server package — re-exports run_server."""

from __future__ import annotations

from perplexity_webui_scraper.mcp.server import run_server


__all__: list[str] = ["run_server"]
