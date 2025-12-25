"""MCP server implementation using FastMCP."""

from __future__ import annotations

from os import environ
from typing import Literal

from fastmcp import FastMCP

from perplexity_webui_scraper.config import ClientConfig, ConversationConfig
from perplexity_webui_scraper.core import Perplexity
from perplexity_webui_scraper.enums import CitationMode, SearchFocus, SourceFocus
from perplexity_webui_scraper.models import Models


# Create FastMCP server
mcp = FastMCP(
    "perplexity-webui-scraper-mcp",
    instructions=(
        "Search the web with Perplexity AI using the full range of premium models. "
        "Unlike the official Perplexity API, this tool provides access to GPT-5.2, Claude 4.5, "
        "Gemini 3, Grok 4.1, and other cutting-edge models with reasoning capabilities. "
        "Use for real-time web research, academic searches, financial data, and current events. "
        "Supports multiple source types: web, academic papers, social media, and SEC filings."
    ),
)

# Model name mapping to Model objects
MODEL_MAP = {
    "best": Models.BEST,
    "research": Models.RESEARCH,
    "labs": Models.LABS,
    "sonar": Models.SONAR,
    "gpt52": Models.GPT_52,
    "gpt52_thinking": Models.GPT_52_THINKING,
    "claude_opus": Models.CLAUDE_45_OPUS,
    "claude_opus_thinking": Models.CLAUDE_45_OPUS_THINKING,
    "claude_sonnet": Models.CLAUDE_45_SONNET,
    "claude_sonnet_thinking": Models.CLAUDE_45_SONNET_THINKING,
    "gemini_pro": Models.GEMINI_3_PRO,
    "gemini_flash": Models.GEMINI_3_FLASH,
    "gemini_flash_thinking": Models.GEMINI_3_FLASH_THINKING,
    "grok": Models.GROK_41,
    "grok_thinking": Models.GROK_41_THINKING,
    "kimi_thinking": Models.KIMI_K2_THINKING,
}

ModelName = Literal[
    "best",
    "research",
    "labs",
    "sonar",
    "gpt52",
    "gpt52_thinking",
    "claude_opus",
    "claude_opus_thinking",
    "claude_sonnet",
    "claude_sonnet_thinking",
    "gemini_pro",
    "gemini_flash",
    "gemini_flash_thinking",
    "grok",
    "grok_thinking",
    "kimi_thinking",
]

# Source focus mapping
SOURCE_FOCUS_MAP = {
    "web": [SourceFocus.WEB],
    "academic": [SourceFocus.ACADEMIC],
    "social": [SourceFocus.SOCIAL],
    "finance": [SourceFocus.FINANCE],
    "all": [SourceFocus.WEB, SourceFocus.ACADEMIC, SourceFocus.SOCIAL],
}

SourceFocusName = Literal["web", "academic", "social", "finance", "all"]

# Client singleton
_client: Perplexity | None = None


def _get_client() -> Perplexity:
    """
    Get or create Perplexity client.
    """

    global _client  # noqa: PLW0603
    if _client is None:
        token = environ.get("PERPLEXITY_SESSION_TOKEN", "")

        if not token:
            raise ValueError(
                "PERPLEXITY_SESSION_TOKEN environment variable is required. "
                "Set it with: export PERPLEXITY_SESSION_TOKEN='your_token_here'"
            )
        _client = Perplexity(token, config=ClientConfig())

    return _client


@mcp.tool
def perplexity_ask(
    query: str,
    model: ModelName = "best",
    source_focus: SourceFocusName = "web",
) -> str:
    """
    Ask a question and get AI-generated answers with real-time data from the internet.

    Returns up-to-date information from web sources. Use for factual queries, research,
    current events, news, library versions, documentation, or any question requiring
    the latest information.

    Args:
        query: The question to ask.
        model: AI model to use.
        source_focus: Type of sources to prioritize (web, academic, social, finance, all).

    Returns:
        AI-generated answer with inline citations and a Citations section.
    """

    client = _get_client()
    selected_model = MODEL_MAP.get(model, Models.BEST)
    sources = SOURCE_FOCUS_MAP.get(source_focus, [SourceFocus.WEB])

    try:
        conversation = client.create_conversation(
            ConversationConfig(
                model=selected_model,
                citation_mode=CitationMode.DEFAULT,
                search_focus=SearchFocus.WEB,
                source_focus=sources,
            )
        )

        conversation.ask(query)
        answer = conversation.answer or "No answer received"

        # Build response with Perplexity-style citations
        response_parts = [answer]

        if conversation.search_results:
            response_parts.append("\n\nCitations:")

            for i, result in enumerate(conversation.search_results, 1):
                url = result.url or ""
                response_parts.append(f"\n[{i}]: {url}")

        return "".join(response_parts)
    except Exception as error:
        return f"Error: {error!s}"


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
