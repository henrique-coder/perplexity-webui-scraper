"""GET /v1/models route."""

from __future__ import annotations

from asyncio import to_thread
from logging import getLogger
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from orjson import dumps

from perplexity_webui_scraper._internal.exceptions import AuthenticationError, PerplexityError, RateLimitError
from perplexity_webui_scraper.api.auth import account_tier_cache, client_pool, resolve_upstream_token
from perplexity_webui_scraper.api.schemas.models import ModelCatalogMetadata, ModelList, ModelObject
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from perplexity_webui_scraper.core.account import AccountTier
    from perplexity_webui_scraper.models.types import Model


_logger = getLogger("uvicorn.error")
router = APIRouter()


async def _resolve_account_tier(token: str) -> AccountTier:
    """Resolve and cache the account tier for *token* with a 10-minute TTL."""
    cached_tier = account_tier_cache.get(token)

    if cached_tier is not None:
        return cached_tier

    client = client_pool.get_or_create(token)

    try:
        profile = await to_thread(client.get_account_profile)
    except AuthenticationError:
        _logger.warning("Rejected API request (401): upstream Perplexity rejected session credential")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Perplexity session credential.",
        ) from None
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Upstream Perplexity rate limit exceeded.",
        ) from None
    except PerplexityError:
        raise HTTPException(
            status_code=502,
            detail="Unable to verify account tier with Perplexity.",
        ) from None

    tier = profile.account_tier
    account_tier_cache.set(token, tier)

    return tier


def _is_model_visible_for_tier(model: Model, account_tier: AccountTier) -> bool:
    """Return whether *model* should be exposed to an account with *account_tier*."""
    if model.status == "unavailable":
        return False

    if account_tier in ("free", "unknown"):
        return model.min_tier == "free"

    if account_tier == "pro":
        return model.min_tier in ("free", "pro") or model.min_tier is None

    return True


@router.get("/v1/models", response_model=None)
async def list_models(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Response:
    """List Perplexity models accessible to the authenticated account's subscription tier."""
    token = resolve_upstream_token(authorization, x_api_key)
    account_tier = await _resolve_account_tier(token)

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
            if _is_model_visible_for_tier(m, account_tier)
        ]
    )

    return Response(content=dumps(data.model_dump(mode="json")), media_type="application/json")
