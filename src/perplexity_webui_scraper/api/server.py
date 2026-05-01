"""FastAPI application exposing an OpenAI-compatible REST API for Perplexity."""

from __future__ import annotations

from asyncio import Lock
from dataclasses import dataclass, field
from os.path import commonprefix
from time import time
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from perplexity_webui_scraper._internal.types import Coordinates, FileInput
from perplexity_webui_scraper.config import ClientConfig, ConversationConfig
from perplexity_webui_scraper.core import Conversation, Perplexity
from perplexity_webui_scraper.models import MODELS


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
    PerplexityResponseExtensions,
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

# Conversation cache — keyed by (session_token, thread_uuid)

_CONVERSATION_TTL_SECONDS: float = 30 * 60  # 30 minutes


@dataclass
class _CachedConversation:
    """A cached ``Conversation`` with a last-access timestamp for TTL eviction."""

    conversation: Conversation
    last_access: float = field(default_factory=time)


# Cache dict and its async lock.
_conversations: dict[tuple[str, str], _CachedConversation] = {}
_conversations_lock = Lock()


def _evict_stale() -> None:
    """Remove conversation cache entries that have exceeded the TTL.

    Must be called while ``_conversations_lock`` is held.
    """
    now = time()
    stale_keys = [key for key, entry in _conversations.items() if now - entry.last_access > _CONVERSATION_TTL_SECONDS]

    for key in stale_keys:
        del _conversations[key]


# Auth helpers


def _extract_token(authorization: str | None) -> str:
    """Extract the raw session token from the ``Authorization: Bearer`` header.

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

    return token


def _get_client(authorization: str | None) -> Perplexity:
    """Return a cached (or newly created) Perplexity client for the given token."""
    token = _extract_token(authorization)

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
    """Handle a chat completion request (streaming and non-streaming).

    Supports thread continuation: pass ``perplexity.thread_uuid`` to reuse
    a cached conversation.  Omit it to start a new conversation (the
    default, backward-compatible behaviour).
    """
    try:
        body = await raw_request.json()
        request = ChatCompletionRequest.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        MODELS.resolve(request.model)
    except ValueError:
        available = ", ".join(f'"{model.id}"' for model in MODELS.list_all())

        raise HTTPException(
            status_code=400,
            detail=f"Unknown model {request.model!r}. Available: {available}",
        ) from None

    token = _extract_token(authorization)
    client = _get_client(authorization)

    thread_uuid = request.perplexity.thread_uuid if request.perplexity else None

    if thread_uuid:
        # Case A / B: continuation requested
        async with _conversations_lock:
            _evict_stale()
            cached = _conversations.get((token, thread_uuid))

            if cached is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Conversation '{thread_uuid}' not found or expired. "
                        "Start a new conversation by omitting thread_uuid."
                    ),
                )

            cached.last_access = time()
            conversation = cached.conversation

        query = ""
        files: list[FileInput] = []
        found_user_msg = False

        # Collect query and images from the last user message
        for msg in reversed(request.messages):
            if msg.role == "user":
                found_user_msg = True
                query = msg.text()
                files = list(msg.image_bytes())
                break

        if not found_user_msg:
            raise HTTPException(
                status_code=400,
                detail="Thread continuation requires at least one user message.",
            )

        if not query and not files:
            raise HTTPException(
                status_code=400,
                detail="Thread continuation requires the last user message to contain text or images.",
            )

    else:
        # Case C: new conversation
        query, files = _build_query_and_files(request)
        config = _build_conversation_config(request.model, request.perplexity)
        conversation = client.create_conversation(config)

    if request.stream:
        return StreamingResponse(
            _stream_response(conversation, query, files, request.model, token, is_new=thread_uuid is None),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming path
    conversation.ask(query, files=files or None)
    answer = conversation.answer or ""
    conv_uuid = conversation.uuid

    # Cache the conversation after a successful response
    if conv_uuid:
        key = (token, conv_uuid)
        async with _conversations_lock:
            if thread_uuid or key in _conversations:
                # Update existing conversation or recreate it
                cached = _conversations.get(key)
                if cached:
                    cached.conversation = conversation
                    cached.last_access = time()
                else:
                    _conversations[key] = _CachedConversation(conversation=conversation)
            else:
                _conversations[key] = _CachedConversation(conversation=conversation)

            _evict_stale()

    return JSONResponse(
        content=ChatCompletionResponse.build(
            model=request.model,
            content=answer,
            thread_uuid=conv_uuid,
        ).model_dump(exclude_none=True),
    )


async def _stream_response(
    conversation: object,
    query: str,
    files: list[FileInput],
    model_id: str,
    token: str,
    is_new: bool,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE lines for a streaming chat completion.

    Args:
        conversation: The ``Conversation`` object to query.
        query: The user query text.
        files: File attachments for the query.
        model_id: Model identifier for the response envelope.
        token: Session token used as part of the conversation cache key.
        is_new: ``True`` when this is a brand-new conversation that should
            be cached after the stream completes.
    """
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

    # Cache the conversation now that we have the UUID from the response.
    conv_uuid = conversation.uuid

    if conv_uuid:
        key = (token, conv_uuid)
        async with _conversations_lock:
            if is_new or key not in _conversations:
                _conversations[key] = _CachedConversation(conversation=conversation)
            else:
                _conversations[key].conversation = conversation
                _conversations[key].last_access = time()

            _evict_stale()

    # Build the perplexity response extension for the final chunk.
    pplx_ext = PerplexityResponseExtensions(thread_uuid=conv_uuid) if conv_uuid else None

    # Final chunk — stop signal with thread_uuid
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
        perplexity=pplx_ext,
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
