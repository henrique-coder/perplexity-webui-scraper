"""POST /v1/chat/completions route — streaming and non-streaming."""

from __future__ import annotations

from os.path import commonprefix
from time import time
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from perplexity_webui_scraper.api.auth import ClientPool, extract_token
from perplexity_webui_scraper.api.conversation_cache import ConversationCache
from perplexity_webui_scraper.api.helpers import build_conversation_config, build_query_and_files
from perplexity_webui_scraper.api.schemas.request import ChatCompletionRequest
from perplexity_webui_scraper.api.schemas.response import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionResponse,
    PerplexityResponseExtensions,
)
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from perplexity_webui_scraper._internal.types import FileInput
    from perplexity_webui_scraper.core.conversation import Conversation


router = APIRouter()

# Shared singletons — injected from app.py via dependency or passed directly.
# Using module-level singletons is acceptable here because the API server is
# a single-process application; the cache is not shared across processes.
_client_pool = ClientPool()
_conversation_cache = ConversationCache()


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    raw_request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> JSONResponse | StreamingResponse:
    """Handle a chat completion request (streaming and non-streaming).

    Supports thread continuation: pass ``perplexity.thread_uuid`` to reuse
    a cached ``Conversation`` and send only the last user message as a
    follow-up.  Omit it to start a new conversation (default behaviour).
    """
    try:
        body = await raw_request.json()
        request = ChatCompletionRequest.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        MODELS.resolve(request.model)
    except ValueError:
        available = ", ".join(f'"{m.id}"' for m in MODELS.list_all())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model {request.model!r}. Available: {available}",
        ) from None

    token = extract_token(authorization)
    client = _client_pool.get_or_create(token)
    thread_uuid = request.perplexity.thread_uuid if request.perplexity else None

    conversation: Conversation

    if thread_uuid:
        async with _conversation_cache.lock:
            cached_conv = _conversation_cache.get(token, thread_uuid)

        if cached_conv is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Conversation '{thread_uuid}' not found or expired. "
                    "Start a new conversation by omitting thread_uuid."
                ),
            )

        conversation = cached_conv
        query = ""
        files: list[FileInput] = []
        found_user = False

        for msg in reversed(request.messages):
            if msg.role == "user":
                found_user = True
                query = msg.text()
                files = list(msg.image_bytes())
                break

        if not found_user:
            raise HTTPException(
                status_code=400,
                detail="Thread continuation requires at least one user message.",
            )

        if not query and not files:
            raise HTTPException(
                status_code=400,
                detail="Last user message must contain text or images.",
            )

    else:
        query, files = build_query_and_files(request)
        config = build_conversation_config(request.model, request.perplexity)
        conversation = client.create_conversation(config)

    if request.stream:
        return StreamingResponse(
            _stream_response(
                conversation,
                query,
                files,
                request.model,
                token,
                is_new=thread_uuid is None,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    conversation.ask(query, files=files or None)
    answer = conversation.answer or ""
    conv_uuid = conversation.uuid

    if conv_uuid:
        async with _conversation_cache.lock:
            _conversation_cache.set(token, conv_uuid, conversation)

    return JSONResponse(
        content=ChatCompletionResponse.build(
            model=request.model,
            content=answer,
            thread_uuid=conv_uuid,
        ).model_dump(exclude_none=True)
    )


async def _stream_response(
    conversation: Conversation,
    query: str,
    files: list[FileInput],
    model_id: str,
    token: str,
    is_new: bool,
) -> AsyncGenerator[str, None]:
    """Yield SSE lines for a streaming chat completion.

    Args:
        conversation: Active ``Conversation`` to query.
        query: User query text.
        files: File attachments.
        model_id: Model identifier for response envelope.
        token: Session token for cache keying.
        is_new: ``True`` when this is a brand-new conversation.
    """
    completion_id = f"chatcmpl-{uuid4().hex}"
    created = int(time())
    last_content = ""

    yield ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model_id,
        choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(role="assistant"))],
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
                        choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(content=delta))],
                    ).to_sse_line()

    except (ConnectionError, BrokenPipeError, OSError):
        return

    conv_uuid = conversation.uuid

    if conv_uuid:
        async with _conversation_cache.lock:
            _conversation_cache.set(token, conv_uuid, conversation)

    pplx_ext = PerplexityResponseExtensions(thread_uuid=conv_uuid) if conv_uuid else None

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
