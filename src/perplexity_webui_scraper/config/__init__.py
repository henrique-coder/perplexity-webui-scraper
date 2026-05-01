"""Configuration package — re-exports ClientConfig and ConversationConfig."""

from __future__ import annotations

from perplexity_webui_scraper.config.client import ClientConfig
from perplexity_webui_scraper.config.conversation import ConversationConfig


__all__: list[str] = ["ClientConfig", "ConversationConfig"]
