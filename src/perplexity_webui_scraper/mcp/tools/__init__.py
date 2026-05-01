"""MCP tools package — registers per-model ask tools onto a FastMCP instance."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from typing import Any

from perplexity_webui_scraper._internal.types import SearchFocus, SourceFocus, TimeRange  # noqa: TC001
from perplexity_webui_scraper.core.client import Perplexity  # noqa: TC001
from perplexity_webui_scraper.mcp.tools.ask import _ask
from perplexity_webui_scraper.models.registry import MODELS


def register_all_tools(mcp: Any, get_client: Callable[[], Perplexity]) -> None:
    """Register one MCP tool per model onto *mcp*.

    Each tool is named ``{model.tool_name}`` and delegates to :func:`_ask`
    with the corresponding :class:`~perplexity_webui_scraper.models.types.Model`
    pre-bound.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server instance.
        get_client: Zero-argument callable returning the active
            :class:`~perplexity_webui_scraper.Perplexity` client.
    """
    for model in MODELS.list_all():
        _register_model_tool(mcp, model.tool_name, model.id, model.name, model.description, get_client)


def _register_model_tool(
    mcp: Any,
    tool_name: str,
    model_id: str,
    model_name: str,
    model_description: str,
    get_client: Callable[[], Perplexity],
) -> None:
    """Register a single model tool onto the MCP server.

    Args:
        mcp: FastMCP instance.
        tool_name: The tool name (snake_case).
        model_id: Canonical model ID for client lookup.
        model_name: Human-readable model name for the tool description.
        model_description: Short model description for the tool description.
        get_client: Callable returning the active Perplexity client.
    """
    resolved_model = MODELS.resolve(model_id)

    @mcp.tool(name=tool_name, description=f"[{model_name}] {model_description}")
    def _tool(
        query: str,
        search_focus: SearchFocus = "web",
        source_focus: SourceFocus = "web",
        time_range: TimeRange = "all",
        language: str = "en-US",
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> dict[str, Any]:
        """Search Perplexity AI and return the answer with citations.

        Args:
            query: The search query or question.
            search_focus: ``"web"`` (default) or ``"writing"`` (no sources).
            source_focus: Source filter: ``"web"``, ``"academic"``,
                ``"social"``, ``"finance"``, or ``"all"``.
            time_range: Recency filter: ``"all"``, ``"day"``, ``"week"``,
                ``"month"``, or ``"year"``.
            language: BCP-47 response language tag (e.g. ``"en-US"``).
            latitude: Optional latitude for location-aware results.
            longitude: Optional longitude for location-aware results.

        Returns:
            Dict with ``answer``, ``search_results``, and ``conversation_uuid``.
        """
        return _ask(
            client=get_client(),
            model=resolved_model,
            query=query,
            search_focus=search_focus,
            source_focus=source_focus,
            time_range=time_range,
            language=language,
            latitude=latitude,
            longitude=longitude,
        )
