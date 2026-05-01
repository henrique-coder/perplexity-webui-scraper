"""Immutable metadata type for a single AI model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    """Immutable metadata for a single Perplexity AI model.

    Attributes:
        id: Canonical string key used to select this model
            (e.g. ``"perplexity/best"``).
        name: Human-readable display name shown in the UI.
        description: Short description of the model's characteristics.
        identifier: Internal Perplexity model identifier sent in the API payload.
        tool_name: MCP tool name used when registering this model as an MCP tool.
        min_tier: Minimum Perplexity subscription required: ``"pro"`` or ``"max"``.
        mode: API request mode sent in the payload (e.g. ``"copilot"``,
            ``"search"``, ``"research"``).
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    identifier: str
    tool_name: str
    min_tier: str
    mode: str = "copilot"
