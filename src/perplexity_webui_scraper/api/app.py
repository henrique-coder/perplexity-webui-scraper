"""FastAPI application factory for the Perplexity OpenAI-compatible API server."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from orjson import dumps

from perplexity_webui_scraper import __version__
from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    FileAccessError,
    FileUploadError,
    FileValidationError,
    ModelAccessError,
    ModelStatusError,
    PerplexityError,
    RateLimitError,
    ResearchClarifyingQuestionsError,
    SessionTokenError,
)
from perplexity_webui_scraper.api.routes.completions import router as completions_router
from perplexity_webui_scraper.api.routes.models import router as models_router
from perplexity_webui_scraper.api.schemas.errors import ErrorDetail, ErrorResponse


if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


_logger = getLogger("uvicorn.error")
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
        return _error_response(str(exc.detail), str(exc.status_code), exc.status_code)

    @application.exception_handler(SessionTokenError)
    async def _session_token_exception_handler(
        _request: Request,
        _exc: SessionTokenError,
    ) -> Response:
        """Reject malformed session credentials in OpenAI-compatible format."""
        return _error_response("Invalid Perplexity session credential.", "invalid_session_credential", 401)

    @application.exception_handler(AuthenticationError)
    async def _authentication_exception_handler(
        _request: Request,
        _exc: AuthenticationError,
    ) -> Response:
        """Return upstream authentication failures in OpenAI-compatible format."""
        _logger.warning("Rejected API request (401): upstream Perplexity rejected session credential")

        return _error_response(
            "Invalid or expired Perplexity session credential.",
            "upstream_authentication_failed",
            401,
        )

    @application.exception_handler(RateLimitError)
    async def _rate_limit_exception_handler(
        _request: Request,
        _exc: RateLimitError,
    ) -> Response:
        """Return upstream rate-limit rejections in OpenAI-compatible format."""
        return _error_response(
            "Upstream Perplexity rate limit exceeded.",
            "rate_limit_exceeded",
            429,
            error_type="rate_limit_error",
        )

    @application.exception_handler(ModelAccessError)
    async def _model_access_exception_handler(
        _request: Request,
        exc: ModelAccessError,
    ) -> Response:
        """Return model-tier denials in OpenAI-compatible format."""
        return _error_response(str(exc), "model_access_denied", 403)

    @application.exception_handler(FileAccessError)
    async def _file_access_exception_handler(
        _request: Request,
        exc: FileAccessError,
    ) -> Response:
        """Return file-attachment denials in OpenAI-compatible format."""
        return _error_response(str(exc), "file_access_denied", 403)

    @application.exception_handler(FileValidationError)
    async def _file_validation_exception_handler(
        _request: Request,
        exc: FileValidationError,
    ) -> Response:
        """Return local attachment validation errors in OpenAI-compatible format."""
        return _error_response(str(exc), "file_validation_failed", 400)

    @application.exception_handler(FileUploadError)
    async def _file_upload_exception_handler(
        _request: Request,
        _exc: FileUploadError,
    ) -> Response:
        """Return upstream attachment upload errors without leaking details."""
        return _error_response(
            "File upload to Perplexity failed.",
            "file_upload_failed",
            502,
            error_type="server_error",
        )

    @application.exception_handler(ResearchClarifyingQuestionsError)
    async def _clarifying_questions_exception_handler(
        _request: Request,
        exc: ResearchClarifyingQuestionsError,
    ) -> Response:
        """Return research clarification prompts in OpenAI-compatible format."""
        return _error_response(str(exc), "research_clarification_required", 400)

    @application.exception_handler(ModelStatusError)
    async def _model_status_exception_handler(
        _request: Request,
        exc: ModelStatusError,
    ) -> Response:
        """Require explicit acknowledgement before risky model use."""
        return _error_response(str(exc), "model_status_confirmation_required", 400)

    @application.exception_handler(PerplexityError)
    async def _perplexity_exception_handler(
        _request: Request,
        exc: PerplexityError,
    ) -> Response:
        """Return unexpected upstream library errors without leaking details."""
        _logger.warning("Upstream API error: %s", type(exc).__name__)

        return _error_response(
            "Upstream Perplexity request failed.",
            "upstream_error",
            502,
            error_type="server_error",
        )

    @application.exception_handler(Exception)
    async def _unhandled_exception_handler(
        _request: Request,
        exc: Exception,
    ) -> Response:
        """Return unexpected server errors in OpenAI-compatible JSON format."""
        _logger.error("Unhandled API error: %s", type(exc).__name__)

        return _error_response(
            "Internal server error.",
            "internal_error",
            500,
            error_type="server_error",
        )

    return application


#: Module-level ASGI application for Uvicorn and ASGI server imports:
#: ``uvicorn perplexity_webui_scraper.api.app:app``
app: FastAPI = create_app()


def _error_response(
    message: str,
    code: str,
    status_code: int,
    error_type: str = "invalid_request_error",
) -> Response:
    """Serialize an OpenAI-compatible error envelope to JSON bytes."""
    payload = ErrorResponse(
        error=ErrorDetail(
            message=message,
            type=error_type,
            code=code,
        )
    ).model_dump()

    return _json_response(payload, status_code=status_code)


def _json_response(content: Any, status_code: int = 200) -> Response:
    """Serialize JSON directly to UTF-8 bytes with orjson."""
    return Response(content=dumps(content), status_code=status_code, media_type="application/json")
