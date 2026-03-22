"""MCP server implementation using FastMCP."""

from __future__ import annotations

from os import environ
from typing import Literal

from fastmcp import FastMCP

from perplexity_webui_scraper.config import ClientConfig, ConversationConfig
from perplexity_webui_scraper.core import Perplexity
from perplexity_webui_scraper.enums import CitationMode, SearchFocus, SourceFocus
from perplexity_webui_scraper.models import MODELS


mcp = FastMCP(
    "perplexity-webui-scraper",
    instructions=(
        "Search the web with Perplexity AI using premium models. "
        "Each tool uses a specific AI model - enable only the ones you need. "
        "All tools support source_focus: web, academic, social, finance, all."
    ),
)

SOURCE_FOCUS_MAP: dict[str, list[SourceFocus]] = {
    "web": [SourceFocus.WEB],
    "academic": [SourceFocus.ACADEMIC],
    "social": [SourceFocus.SOCIAL],
    "finance": [SourceFocus.FINANCE],
    "all": [SourceFocus.WEB, SourceFocus.ACADEMIC, SourceFocus.SOCIAL],
}

SourceFocusName = Literal["web", "academic", "social", "finance", "all"]

_client: Perplexity | None = None


def _get_client() -> Perplexity:
    """Get or create Perplexity client."""

    global _client  # noqa: PLW0603

    if _client is None:
        token = environ.get("PERPLEXITY_SESSION_TOKEN", "")

        if not token:
            msg = (
                "PERPLEXITY_SESSION_TOKEN environment variable is required. "
                "Set it with: export PERPLEXITY_SESSION_TOKEN='your_token_here'"
            )

            raise ValueError(msg)

        _client = Perplexity(token, config=ClientConfig())

    return _client


def _ask(query: str, model_id: str, source_focus: SourceFocusName = "web") -> str:
    """Execute a query with a specific model."""

    client = _get_client()
    sources = SOURCE_FOCUS_MAP.get(source_focus, [SourceFocus.WEB])

    try:
        conversation = client.create_conversation(
            ConversationConfig(
                model=model_id,
                citation_mode=CitationMode.DEFAULT,
                search_focus=SearchFocus.WEB,
                source_focus=sources,
            )
        )

        conversation.ask(query)
    except Exception as error:
        return f"Error: {error!s}"
    else:
        return conversation.answer or "No answer received"


def _create_tool_function(model_id: str) -> None:
    """Dynamically create and register a tool for a model."""

    model = MODELS[model_id]

    @mcp.tool(name=model.tool_name, description=f"{model.name} - {model.description}")
    def tool_fn(query: str, source_focus: SourceFocusName = "web") -> str:
        return _ask(query, model_id, source_focus)


def _register_all_tools() -> None:
    """Register all model tools dynamically."""

    for model_id in MODELS:
        _create_tool_function(model_id)


_register_all_tools()


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
