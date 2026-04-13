"""FastAPI application exposing an OpenAI-compatible REST API for Perplexity."""

from __future__ import annotations

from os.path import commonprefix
from time import time
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from perplexity_webui_scraper.config import ClientConfig, ConversationConfig
from perplexity_webui_scraper.core import Conversation, Perplexity
from perplexity_webui_scraper.models import MODELS
from perplexity_webui_scraper.types import Coordinates, FileInput


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from .models import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ErrorDetail,
    ErrorResponse,
    PerplexityExtensions,
    build_models_response,
)


app = FastAPI(
    title="Perplexity WebUI Scraper — OpenAI-compatible API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients cached by token to avoid re-creating on every request.
_clients: dict[str, Perplexity] = {}


def _get_client(authorization: str | None) -> Perplexity:
    """Return a cached (or newly created) Perplexity client for the given token.

    The token is extracted from the ``Authorization: Bearer <token>`` header,
    which is required on every request — exactly like the real OpenAI API.

    Raises:
        HTTPException: 401 if the header is missing or malformed.
    """

    bearer_prefix = "Bearer "

    if not authorization or not authorization.startswith(bearer_prefix):
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing or invalid Authorization header. "
                "Pass your Perplexity session token as: Authorization: Bearer <token>"
            ),
        )

    token = authorization[len(bearer_prefix) :]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Bearer token is empty.",
        )

    if token not in _clients:
        _clients[token] = Perplexity(token, config=ClientConfig())

    return _clients[token]


def _build_query_and_files(request: ChatCompletionRequest) -> tuple[str, list[FileInput]]:
    """Extract the query string and any attached file bytes from the messages.

    System messages are prefixed with ``[System]: `` and prepended; user and
    assistant messages follow in order. Base64-encoded ``image_url`` content
    parts are decoded into ``(bytes, filename, mimetype)`` tuples and collected
    as file attachments for the Perplexity ``ask()`` call.
    """

    parts: list[str] = []
    files: list[FileInput] = []

    for msg in request.messages:
        text = msg.text()

        match msg.role:
            case "system":
                if text:
                    parts.insert(0, f"[System]: {text}")
            case "user" | "assistant":
                if text:
                    parts.append(text)

        # Collect base64-encoded images from multimodal content parts
        files.extend(msg.image_bytes())

    return "\n\n".join(parts), files


def _build_conversation_config(model: str, ext: PerplexityExtensions | None) -> ConversationConfig:
    """Build a ``ConversationConfig`` merging model ID with Perplexity extensions."""

    if ext is None:
        return ConversationConfig(model=model)

    # citation_mode
    citation_mode = "clean"
    if ext.citation_mode:
        citation_mode = ext.citation_mode

    # search_focus
    search_focus = "web"
    if ext.search_focus:
        search_focus = ext.search_focus

    # source_focus
    source_focus = "web"
    if ext.source_focus is not None:
        source_focus = ext.source_focus

    # time_range
    time_range = "all"
    if ext.time_range:
        time_range = ext.time_range

    # coordinates
    coordinates: Coordinates | None = None
    if ext.coordinates is not None:
        coordinates = Coordinates(
            latitude=ext.coordinates.latitude,
            longitude=ext.coordinates.longitude,
        )

    return ConversationConfig(
        model=model,
        citation_mode=citation_mode,
        search_focus=search_focus,
        source_focus=source_focus,
        time_range=time_range,
        save_to_library=ext.save_to_library,
        language=ext.language or "en-US",
        timezone=ext.timezone,
        coordinates=coordinates,
        space_uuid=ext.space_uuid,
    )


@app.get("/v1/models", response_model=None)
async def list_models(
    _authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> JSONResponse:
    """List all available models in OpenAI format."""

    return JSONResponse(content=build_models_response(MODELS).model_dump())


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    raw_request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> JSONResponse | StreamingResponse:
    """Handle a chat completion request (streaming and non-streaming)."""

    try:
        body = await raw_request.json()
        request = ChatCompletionRequest.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if request.model not in MODELS:
        available = ", ".join(f'"{k}"' for k in MODELS)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model {request.model!r}. Available: {available}",
        )

    client = _get_client(authorization)
    query, files = _build_query_and_files(request)
    config = _build_conversation_config(request.model, request.perplexity)
    conversation = client.create_conversation(config)

    if request.stream:
        return StreamingResponse(
            _stream_response(conversation, query, files, request.model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    conversation.ask(query, files=files or None)
    answer = conversation.answer or ""

    return JSONResponse(content=ChatCompletionResponse.build(model=request.model, content=answer).model_dump())


async def _stream_response(
    conversation: object,
    query: str,
    files: list[FileInput],
    model_id: str,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE lines for a streaming chat completion."""

    if not isinstance(conversation, Conversation):
        return

    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time())
    last_content = ""

    # First chunk — role announcement
    yield ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model_id,
        choices=[
            ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(role="assistant"),
            )
        ],
    ).to_sse_line()

    try:
        conversation.ask(query, files=files or None, stream=True)

        for response in conversation:
            current = response.last_chunk or response.answer or ""

            if current and current != last_content:
                common_len = len(commonprefix([last_content, current]))
                delta = current[common_len:]

                if delta:
                    last_content = current

                    yield ChatCompletionChunk(
                        id=completion_id,
                        created=created,
                        model=model_id,
                        choices=[
                            ChatCompletionChunkChoice(
                                delta=ChatCompletionChunkDelta(content=delta),
                            )
                        ],
                    ).to_sse_line()

    except (ConnectionError, BrokenPipeError, OSError):
        # Client disconnected mid-stream — stop gracefully
        return

    # Final chunk — stop signal
    yield ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model_id,
        choices=[
            ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop",
            )
        ],
    ).to_sse_line()

    yield "data: [DONE]\n\n"


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return errors in OpenAI-compatible format."""

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
