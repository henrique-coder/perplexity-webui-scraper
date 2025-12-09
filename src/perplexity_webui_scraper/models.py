"""AI model definitions for Perplexity WebUI Scraper."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Model:
    """AI model configuration.

    Attributes:
        identifier: Model identifier used by the API.
        mode: Model execution mode. Default: "copilot".
    """

    identifier: str
    mode: str = "copilot"


class Models:
    """Available AI models with their configurations.

    All models use the "copilot" mode which enables web search.
    """

    LABS = Model(identifier="pplx_beta")
    """Create projects from scratch (turn your ideas into completed docs, slides, dashboards, and more)."""

    RESEARCH = Model(identifier="pplx_alpha")
    """Deep research on any topic (in-depth reports with more sources, charts, and advanced reasoning)."""

    BEST = Model(identifier="pplx_pro")
    """Automatically selects the best model based on the query. Recommended for most use cases."""

    SONAR = Model(identifier="experimental")
    """Perplexity's fast model. Good for quick queries."""

    GPT_51 = Model(identifier="gpt51")
    """OpenAI's latest model (GPT-5.1)."""

    GPT_51_THINKING = Model(identifier="gpt51_thinking")
    """OpenAI's latest model with extended reasoning capabilities."""

    CLAUDE_45_SONNET = Model(identifier="claude45sonnet")
    """Anthropic's Claude 4.5 Sonnet model."""

    CLAUDE_45_SONNET_THINKING = Model(identifier="claude45sonnetthinking")
    """Anthropic's Claude 4.5 Sonnet with extended reasoning capabilities."""

    GEMINI_3_PRO_THINKING = Model(identifier="gemini30pro")
    """Google's Gemini 3.0 Pro with reasoning capabilities."""

    GROK_41 = Model(identifier="grok41nonreasoning")
    """xAI's Grok 4.1 model."""

    KIMI_K2_THINKING = Model(identifier="kimik2thinking")
    """Moonshot AI's Kimi K2 reasoning model (hosted in the US)."""
