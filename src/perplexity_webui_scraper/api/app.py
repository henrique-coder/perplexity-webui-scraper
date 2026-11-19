"""FastAPI application factory for the Perplexity OpenAI-compatible API server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from orjson import dumps

from perplexity_webui_scraper import __version__
from perplexity_webui_scraper._internal.exceptions import (
    FileAccessError,
    ModelAccessError,
    ModelStatusError,
)
from perplexity_webui_scraper.api.routes.completions import router as completions_router
from perplexity_webui_scraper.api.routes.models import router as models_router
from perplexity_webui_scraper.api.schemas.errors import ErrorDetail, ErrorResponse


if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


_MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024


class _RequestBodyLimitMiddleware:
    """Reject oversized API request bodies before JSON parsing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce a bounded body size for chat completion requests."""
        if scope["type"] != "http" or scope["path"] != "/v1/chat/completions":
            await self.app(scope, receive, send)

            return

        headers = dict(scope["headers"])
        content_length = headers.get(b"content-length")

        if content_length is not None:
            try:
                if int(content_length) > _MAX_REQUEST_BODY_BYTES:
                    response = _json_response({"detail": "Request body exceeds 10 MiB limit"}, status_code=413)
                    await response(scope, receive, send)

                    return
            except ValueError:
                response = _json_response({"detail": "Invalid Content-Length header"}, status_code=400)
                await response(scope, receive, send)

                return

        body = bytearray()

        while True:
            message = await receive()

            if message["type"] == "http.disconnect":
                return

            chunk = message.get("body", b"")

            if len(body) + len(chunk) > _MAX_REQUEST_BODY_BYTES:
                response = _json_response({"detail": "Request body exceeds 10 MiB limit"}, status_code=413)
                await response(scope, receive, send)

                return

            body.extend(chunk)

            if not message.get("more_body", False):
                break

        replayed = False

        async def receive_body() -> Any:
            nonlocal replayed

            if not replayed:
                replayed = True

                return {"type": "http.request", "body": bytes(body), "more_body": False}

            return await receive()

        await self.app(scope, receive_body, send)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    The application includes:

    - ``GET /v1/models`` and ``POST /v1/chat/completions`` routes.
    - OpenAI-compatible error objects for HTTP exceptions.

    Returns:
        Configured :class:`fastapi.FastAPI` instance.
    """
    application = FastAPI(
        title="Perplexity WebUI Scraper: OpenAI-compatible API",
        description=(
            "OpenAI Chat Completions backed by Perplexity's WebUI. "
            "Pass the Perplexity session token as **Authorization: Bearer <token>**."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.add_middleware(_RequestBodyLimitMiddleware)

    application.include_router(models_router)
    application.include_router(completions_router)

    @application.exception_handler(HTTPException)
    async def _http_exception_handler(
        _request: Request,
        exc: HTTPException,
    ) -> Response:
        """Return all HTTP errors in OpenAI-compatible format."""
        return _json_response(
            ErrorResponse(
                error=ErrorDetail(
                    message=str(exc.detail),
                    type="invalid_request_error",
                    code=str(exc.status_code),
                )
            ).model_dump(),
            status_code=exc.status_code,
        )

    @application.exception_handler(ModelAccessError)
    async def _model_access_exception_handler(
        _request: Request,
        exc: ModelAccessError,
    ) -> Response:
        """Return model-tier denials in OpenAI-compatible format."""
        return _json_response(
            ErrorResponse(
                error=ErrorDetail(
                    message=str(exc),
                    type="invalid_request_error",
                    code="model_access_denied",
                )
            ).model_dump(),
            status_code=403,
        )

    @application.exception_handler(FileAccessError)
    async def _file_access_exception_handler(
        _request: Request,
        exc: FileAccessError,
    ) -> Response:
        """Return file-attachment denials in OpenAI-compatible format."""
        return _json_response(
            ErrorResponse(
                error=ErrorDetail(
                    message=str(exc),
                    type="invalid_request_error",
                    code="file_access_denied",
                )
            ).model_dump(),
            status_code=403,
        )

    @application.exception_handler(ModelStatusError)
    async def _model_status_exception_handler(
        _request: Request,
        exc: ModelStatusError,
    ) -> Response:
        """Require explicit acknowledgement before risky model use."""
        return _json_response(
            ErrorResponse(
                error=ErrorDetail(
                    message=str(exc),
                    type="invalid_request_error",
                    code="model_status_confirmation_required",
                )
            ).model_dump(),
            status_code=400,
        )

    return application


#: Module-level ASGI application for Uvicorn and ASGI server imports:
#: ``uvicorn perplexity_webui_scraper.api.app:app``
app: FastAPI = create_app()


def _json_response(content: Any, status_code: int = 200) -> Response:
    """Serialize JSON directly to UTF-8 bytes with orjson."""
    return Response(content=dumps(content), status_code=status_code, media_type="application/json")
