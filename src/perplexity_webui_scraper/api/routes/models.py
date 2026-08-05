"""GET /v1/models route."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from perplexity_webui_scraper.api.schemas.response import ModelCatalogMetadata, ModelList, ModelObject
from perplexity_webui_scraper.models.registry import MODELS


router = APIRouter()


@router.get("/v1/models", response_model=None)
async def list_models() -> JSONResponse:
    """List all available Perplexity models in OpenAI format."""
    data = ModelList(
        data=[
            ModelObject(
                id=m.id,
                owned_by=m.provider,
                perplexity=ModelCatalogMetadata(
                    min_tier=m.min_tier,
                    is_official=m.is_official,
                    status=m.status,
                    last_tested_at=m.last_tested_at,
                ),
            )
            for m in MODELS.list_all()
        ]
    )
    return JSONResponse(content=data.model_dump(mode="json"))
