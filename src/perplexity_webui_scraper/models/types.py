"""Immutable metadata type for a single AI model."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator


ModelTier: TypeAlias = Literal["free", "pro", "max"]
"""Minimum Perplexity subscription tier required by a model."""

ModelMode: TypeAlias = Literal["copilot", "search", "research"]
"""Internal Perplexity request mode used for a model."""

ModelStatus: TypeAlias = Literal["available", "unknown", "unavailable"]
"""Observed availability state of a model identifier."""

MODEL_STATUS_DESCRIPTIONS: Final[dict[ModelStatus, str]] = {
    "available": "Confirmed to work normally.",
    "unknown": "Current availability has not been confirmed.",
    "unavailable": "Confirmed not to work with the current backend.",
}
"""Canonical human-readable meaning of each model status."""


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
        provider: Provider slug used for catalog grouping.
        is_official: Whether Perplexity currently lists the model in its official WebUI.
        min_tier: Minimum Perplexity subscription, or ``None`` when unknown.
        mode: API request mode sent in the payload (e.g. ``"copilot"``,
            ``"search"``, ``"research"``).
        mode_by_tier: Optional mode overrides selected by account tier.
        status: Observed availability state. Unknown models require explicit
            risk acknowledgement and are the default until a live test is recorded.
        last_tested_at: UTC timestamp of the test that supports the current
            status, or ``None`` when the model has not been tested.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    description: str
    identifier: str
    identifier_by_tier: dict[ModelTier, str] = Field(default_factory=dict)
    tool_name: str
    provider: str
    min_tier: ModelTier | None
    is_official: bool = False
    mode: ModelMode = "copilot"
    mode_by_tier: dict[ModelTier, ModelMode] = Field(default_factory=dict)
    status: ModelStatus = "unknown"
    last_tested_at: datetime | None = None

    @field_validator("last_tested_at")
    @classmethod
    def _require_utc_test_timestamp(cls, value: datetime | None) -> datetime | None:
        """Reject test timestamps that are missing a UTC offset."""
        if value is not None and value.utcoffset() != timedelta(0):
            raise ValueError("last_tested_at must use UTC")

        return value
