"""Models package — re-exports ModelRegistry singleton and Model type."""

from __future__ import annotations

from perplexity_webui_scraper.models.registry import MODELS, ModelRegistry
from perplexity_webui_scraper.models.types import Model


__all__: list[str] = ["MODELS", "Model", "ModelRegistry"]
