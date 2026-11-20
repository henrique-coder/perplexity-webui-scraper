from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from perplexity_webui_scraper._internal.constants import SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper.api.auth import ClientPool
from perplexity_webui_scraper.auth.cookies import parse_session_credential
from perplexity_webui_scraper.mcp import server as mcp_server
from perplexity_webui_scraper.mcp.tools import register_all_tools
from perplexity_webui_scraper.models.registry import MODELS


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

    assert len(mcp.tools) == len(MODELS.list_all()) + 1
    by_name = {name: description for name, description, _function in mcp.tools}
    assert by_name["pplx_custom"].startswith("[UNKNOWN]")
    assert all(f"[{model.status.upper()}]" in by_name[model.tool_name] for model in MODELS.list_all())


def test_mcp_client_pool_accepts_compact_and_raw_credentials_as_one_session() -> None:
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    raw = (
        f"{SESSION_COOKIE_PREFIX}{account_id}="
        f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    )
    compact = "wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw"
    client = MagicMock()

    with patch("perplexity_webui_scraper.api.auth.Perplexity", return_value=client) as create_client:
        pool = ClientPool()
        assert pool.get_or_create(raw) is client
        assert pool.get_or_create(compact) is client

    create_client.assert_called_once()
    assert parse_session_credential(raw) == parse_session_credential(compact)


def test_mcp_server_ingress_builds_same_session_from_raw_and_compact_credentials() -> None:
    account_id = "123e4567-e89b-42d3-a456-426614174000"
    raw = (
        f"{SESSION_COOKIE_PREFIX}{account_id}="
        f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    )
    compact = "wsk_1LlYHVDOBjIiT2Z5Re7RX82sRkpZ5DPQbXq7WcWjQyJlxphkNEnW1yoqjF8SLIqNqCvaOJkw"

    for token in (raw, compact):
        with patch.object(mcp_server, "_client", None), patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": token}):
            client = mcp_server._get_client()
            try:
                assert client._http._session_cookie == parse_session_credential(raw)
            finally:
                client.close()
