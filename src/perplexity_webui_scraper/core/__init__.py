"""Core package — re-exports Perplexity and Conversation."""

from __future__ import annotations

from perplexity_webui_scraper.core.client import Perplexity
from perplexity_webui_scraper.core.conversation import Conversation


__all__: list[str] = ["Conversation", "Perplexity"]
