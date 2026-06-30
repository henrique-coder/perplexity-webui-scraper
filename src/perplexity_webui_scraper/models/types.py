"""Immutable metadata type for a single AI model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


type ModelTier = Literal["free", "pro", "max"]
"""Minimum Perplexity subscription tier required by a model."""

type ModelMode = Literal["copilot", "search", "research"]
"""Internal Perplexity request mode used for a model."""


class Model(BaseModel):
    """Immutable metadata for a single Perplexity AI model.

    Attributes:
        id: Canonical string key used to select this model
            (e.g. ``"perplexity/best"``).
        name: Human-readable display name shown in the UI.
        description: Short description of the model's characteristics.
        identifier: Internal Perplexity model identifier sent in the API payload.
        identifier_by_tier: Optional identifier overrides selected by account tier.
        tool_name: MCP tool name used when registering this model as an MCP tool.
        min_tier: Minimum Perplexity subscription required: ``"pro"`` or ``"max"``.
        mode: API request mode sent in the payload (e.g. ``"copilot"``,
            ``"search"``, ``"research"``).
        mode_by_tier: Optional mode overrides selected by account tier.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    description: str
    identifier: str
    identifier_by_tier: dict[ModelTier, str] = Field(default_factory=dict)
    tool_name: str
    min_tier: ModelTier
    mode: ModelMode = "copilot"
    mode_by_tier: dict[ModelTier, ModelMode] = Field(default_factory=dict)
