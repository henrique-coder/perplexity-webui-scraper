from __future__ import annotations

from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper.mcp.tools import register_all_tools


if TYPE_CHECKING:
    from collections.abc import Callable

    from perplexity_webui_scraper.core.client import Perplexity


def _unused_client() -> Perplexity:
    raise AssertionError("MCP client factory must not be called during registration")


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: list[tuple[str, str, Callable[..., Any]]] = []

    def tool(self, *, name: str, description: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.tools.append((name, description, function))
            return function

        return decorator


def test_mcp_registers_catalog_and_custom_tools_with_statuses() -> None:
    mcp = _FakeMCP()
    register_all_tools(mcp, _unused_client)

    assert len(mcp.tools) == 76
    by_name = {name: description for name, description, _function in mcp.tools}
    assert by_name["pplx_best"].startswith("[UNKNOWN]")
    assert by_name["pplx_gpt54"].startswith("[UNKNOWN]")
    assert by_name["pplx_gpt4o"].startswith("[UNKNOWN]")
    assert by_name["pplx_grok45"].startswith("[UNKNOWN]")
    assert by_name["pplx_grok45_think"].startswith("[UNKNOWN]")
    assert by_name["pplx_custom"].startswith("[UNKNOWN]")
