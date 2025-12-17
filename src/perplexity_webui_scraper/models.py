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

    RESEARCH = Model(identifier="pplx_alpha")
    """Research - Fast and thorough for routine research"""

    LABS = Model(identifier="pplx_beta")
    """Labs - Multi-step tasks with advanced troubleshooting"""

    BEST = Model(identifier="pplx_pro_upgraded")
    """Best - Automatically selects the most responsive model based on the query"""

    SONAR = Model(identifier="experimental")
    """Sonar - Perplexity's fast model"""

    GPT_52 = Model(identifier="gpt52")
    """GPT-5.2 - OpenAI's latest model"""

    GPT_52_THINKING = Model(identifier="gpt52_thinking")
    """GPT-5.2 Thinking - OpenAI's latest model with thinking"""

    CLAUDE_45_OPUS = Model(identifier="claude45opus")
    """Claude Opus 4.5 - Anthropic's Opus reasoning model"""

    CLAUDE_45_OPUS_THINKING = Model(identifier="claude45opusthinking")
    """Claude Opus 4.5 Thinking - Anthropic's Opus reasoning model with thinking"""

    GEMINI_3_PRO_THINKING = Model(identifier="gemini30pro")
    """Gemini 3 Pro - Google's newest reasoning model"""

    GROK_41 = Model(identifier="grok41nonreasoning")
    """Grok 4.1 - xAI's latest advanced model"""

    GROK_41_THINKING = Model(identifier="grok41reasoning")
    """Grok 4.1 Thinking - xAI's latest reasoning model"""

    KIMI_K2_THINKING = Model(identifier="kimik2thinking")
    """Kimi K2 Thinking - Moonshot AI's latest reasoning model"""

    CLAUDE_45_SONNET = Model(identifier="claude45sonnet")
    """Claude Sonnet 4.5 - Anthropic's newest advanced model"""

    CLAUDE_45_SONNET_THINKING = Model(identifier="claude45sonnetthinking")
    """Claude Sonnet 4.5 Thinking - Anthropic's newest reasoning model"""
