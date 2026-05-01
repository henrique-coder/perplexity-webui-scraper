"""OpenAI-compatible API server package."""

from __future__ import annotations

from perplexity_webui_scraper.api.app import create_app


__all__: list[str] = ["create_app"]
