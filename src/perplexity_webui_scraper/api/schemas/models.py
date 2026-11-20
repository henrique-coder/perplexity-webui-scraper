"""Model listing schemas for the public API."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel


class ModelCatalogMetadata(BaseModel):
    """Perplexity-specific availability metadata for a catalog model."""

    min_tier: Literal["free", "pro", "max", "unknown"]
    is_official: bool
    status: Literal["available", "unknown", "unavailable"]
    last_tested_at: datetime | None


class ModelObject(BaseModel):
    """One model entry in the ``GET /v1/models`` response."""

    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "perplexity"
    perplexity: ModelCatalogMetadata


class ModelList(BaseModel):
    """Response for ``GET /v1/models``."""

    object: Literal["list"] = "list"
    data: list[ModelObject]


__all__ = ["ModelCatalogMetadata", "ModelList", "ModelObject"]
