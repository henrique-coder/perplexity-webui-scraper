"""FastAPI application factory for the Perplexity OpenAI-compatible API server."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from perplexity_webui_scraper.api.routes.completions import router as completions_router
from perplexity_webui_scraper.api.routes.models import router as models_router
from perplexity_webui_scraper.api.schemas.errors import ErrorDetail, ErrorResponse


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns a fully configured :class:`fastapi.FastAPI` instance with:

    - CORS middleware (allow all origins — configure in production).
    - ``GET /v1/models`` and ``POST /v1/chat/completions`` routes.
    - OpenAI-compatible error format for all HTTP exceptions.

    Returns:
        Configured :class:`fastapi.FastAPI` instance.
    """
    application = FastAPI(
        title="Perplexity WebUI Scraper — OpenAI-compatible API",
        description=(
            "Drop-in OpenAI-compatible API powered by Perplexity WebUI Scraper. "
            "Pass your Perplexity session token as: **Authorization: Bearer <token>**."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(models_router)
    application.include_router(completions_router)

    @application.exception_handler(HTTPException)
    async def _http_exception_handler(
        _request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """Return all HTTP errors in OpenAI-compatible format."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=str(exc.detail),
                    type="invalid_request_error",
                    code=str(exc.status_code),
                )
            ).model_dump(),
        )

    return application


#: Module-level ``app`` instance for uvicorn compatibility:
#: ``uvicorn perplexity_webui_scraper.api.app:app``
app: FastAPI = create_app()
