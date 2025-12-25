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

# Available model names for type hints
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
    """Get or create Perplexity client."""

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

    Args:
        query: The search query or question to ask Perplexity AI.
        model: AI model to use. Options:
            - "best": Automatically selects optimal model (default)
            - "research": Fast and thorough for routine research
            - "labs": Multi-step tasks with advanced troubleshooting
            - "sonar": Perplexity's fast built-in model
            - "gpt52": OpenAI's GPT-5.2
            - "gpt52_thinking": GPT-5.2 with reasoning
            - "claude_opus": Anthropic's Claude Opus 4.5
            - "claude_opus_thinking": Claude Opus with reasoning
            - "claude_sonnet": Anthropic's Claude Sonnet 4.5
            - "claude_sonnet_thinking": Claude Sonnet with reasoning
            - "gemini_pro": Google's Gemini 3 Pro
            - "gemini_flash": Google's Gemini 3 Flash
            - "gemini_flash_thinking": Gemini Flash with reasoning
            - "grok": xAI's Grok 4.1
            - "grok_thinking": Grok with reasoning
            - "kimi_thinking": Moonshot's Kimi K2 with reasoning
        source_focus: Type of sources to prioritize:
            - "web": General web search (default)
            - "academic": Scholarly articles and papers
            - "social": Social media (Reddit, Twitter)
            - "finance": SEC EDGAR financial filings
            - "all": Combine web, academic, and social sources

    Returns:
        AI-generated answer with inline citations [1][2] and a Citations section.
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
        return f"Error searching Perplexity: {error!s}"


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
