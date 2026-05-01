"""GET /v1/models route."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from perplexity_webui_scraper.api.schemas.response import ModelList, ModelObject
from perplexity_webui_scraper.models.registry import MODELS


router = APIRouter()


@router.get("/v1/models", response_model=None)
async def list_models() -> JSONResponse:
    """List all available Perplexity models in OpenAI format."""
    data = ModelList(data=[ModelObject(id=m.id) for m in MODELS.list_all()])
    return JSONResponse(content=data.model_dump())
