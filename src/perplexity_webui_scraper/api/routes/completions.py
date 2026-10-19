"""Shared Perplexity execution behind Responses and Chat Completions routes."""

from __future__ import annotations

from asyncio import CancelledError, create_task, shield, to_thread
from functools import partial
from os import environ
from time import time
from typing import TYPE_CHECKING, Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from starlette.concurrency import iterate_in_threadpool

from perplexity_webui_scraper.api.auth import ClientPool, resolve_session_token
from perplexity_webui_scraper.api.conversation_cache import ConversationCache
from perplexity_webui_scraper.api.helpers import build_conversation_config, build_query_and_files
from perplexity_webui_scraper.api.response_cache import ResponseThreadCache
from perplexity_webui_scraper.api.responses_helpers import to_chat_completion_request
from perplexity_webui_scraper.api.responses_stream import chat_stream_to_responses
from perplexity_webui_scraper.api.schemas.request import ChatCompletionRequest, PerplexityExtensions
from perplexity_webui_scraper.api.schemas.response import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionResponse,
    PerplexityResponseExtensions,
)
from perplexity_webui_scraper.api.schemas.responses import ResponsesAPIResponse, ResponsesRequest
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.types import Receive, Scope, Send

    from perplexity_webui_scraper._internal.types import FileInput
    from perplexity_webui_scraper.core.conversation import Conversation


router = APIRouter()


def _common_prefix_length(left: str, right: str) -> int:
    """Return the length of the exact shared prefix of two streamed texts."""
    prefix_length = 0

    for left_char, right_char in zip(left, right, strict=False):
        if left_char != right_char:
            break

        prefix_length += 1

    return prefix_length


class _LockReleasingStreamingResponse(StreamingResponse):
    """Release a cached conversation lock even if response sending fails early."""

    def __init__(self, *args: Any, operation_lock: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._operation_lock = operation_lock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            if self._operation_lock is not None and self._operation_lock.locked():
                self._operation_lock.release()


# Shared clients used by the application routes.
# Using module-level singletons is acceptable here because the API server is
# a single-process application; the cache is not shared across processes.
_client_pool = ClientPool()
_conversation_cache = ConversationCache()
_response_thread_cache = ResponseThreadCache()


async def _run_sync_safely(function: Any) -> Any:
    """Run blocking work in a thread and wait for it to finish on cancellation."""
    task = create_task(to_thread(function))

    try:
        return await shield(task)
    except CancelledError:
        try:
            await task
        finally:
            raise


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    raw_request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
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
        raise HTTPException(status_code=422, detail="Invalid chat completion request body") from exc

    token = _resolve_upstream_token(authorization, x_api_key)

    return await _execute_chat_completion(request, token)


@router.post("/v1/responses", response_model=None)
async def responses(
    raw_request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> JSONResponse | StreamingResponse:
    """Handle supported text and image input in the OpenAI Responses API."""
    try:
        body = await raw_request.json()
        responses_request = ResponsesRequest.model_validate(body)
        request = to_chat_completion_request(responses_request)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid or unsupported Responses API request body") from exc

    token = _resolve_upstream_token(authorization, x_api_key)
    thread_uuid = (
        _response_thread_cache.get(token, responses_request.previous_response_id)
        if responses_request.previous_response_id
        else None
    )
    if responses_request.previous_response_id and thread_uuid is None:
        raise HTTPException(status_code=404, detail="Previous response not found or expired")
    if thread_uuid:
        extensions = request.perplexity or PerplexityExtensions()
        extensions.thread_uuid = thread_uuid
        request.perplexity = extensions

    chat_result = await _execute_chat_completion(request, token)
    if responses_request.stream:
        if not isinstance(chat_result, StreamingResponse):
            raise HTTPException(status_code=500, detail="Streaming response was not initialized")
        return _LockReleasingStreamingResponse(
            chat_stream_to_responses(
                chat_result.body_iterator,
                request.model,
                responses_request.previous_response_id,
                on_thread=lambda response_id, uuid: _response_thread_cache.set(token, response_id, uuid),
            ),
            operation_lock=getattr(chat_result, "_operation_lock", None),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    if not isinstance(chat_result, JSONResponse):
        raise HTTPException(status_code=500, detail="Non-streaming response was not returned")
    completion = ChatCompletionResponse.model_validate_json(bytes(chat_result.body))
    response_id = f"resp_{uuid4().hex}"
    thread_uuid = completion.perplexity.thread_uuid if completion.perplexity else None
    if thread_uuid:
        _response_thread_cache.set(token, response_id, thread_uuid)
    response = ResponsesAPIResponse.build(
        request.model,
        completion.choices[0].message.content or "",
        response_id,
        responses_request.previous_response_id,
    )
    return JSONResponse(content=response.model_dump(exclude_none=True))


def _resolve_upstream_token(authorization: str | None, x_api_key: str | None) -> str:
    """Require gateway auth when configured, then resolve caller/default upstream token."""
    return resolve_session_token(
        authorization,
        x_api_key,
        environ.get("PERPLEXITY_SESSION_TOKEN"),
        environ.get("PERPLEXITY_API_KEY"),
    )


async def _execute_chat_completion(
    request: ChatCompletionRequest,
    token: str,
) -> JSONResponse | StreamingResponse:
    """Run one normalized API request through the shared conversation implementation."""
    _validate_model(request)

    thread_uuid = request.perplexity.thread_uuid if request.perplexity else None

    conversation: Conversation
    cached_entry = None

    if thread_uuid:
        async with _conversation_cache.lock:
            cached_entry = _conversation_cache.get_entry(token, thread_uuid)

        if cached_entry is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Conversation '{thread_uuid}' not found or expired. "
                    "Start a new conversation by omitting thread_uuid."
                ),
            )

        conversation = cached_entry.conversation

        if request.model != cached_entry.model_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Thread uses model {cached_entry.model_id!r}; start a new thread to select a different model."
                ),
            )

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
        client = _client_pool.get_or_create(token)
        query, files = build_query_and_files(request)
        config = build_conversation_config(request.model, request.perplexity)
        conversation = client.create_conversation(config)

    if request.stream:
        if cached_entry is not None:
            await cached_entry.operation_lock.acquire()

        lock_held = cached_entry is not None

        try:
            await _run_sync_safely(partial(conversation.ask, query, files=files or None, stream=True))
        except CancelledError:
            if cached_entry is not None and lock_held:
                cached_entry.operation_lock.release()

            raise
        except Exception:
            if cached_entry is not None and lock_held:
                cached_entry.operation_lock.release()

            raise

        try:
            streaming_response = _LockReleasingStreamingResponse(
                _stream_response(
                    conversation,
                    request.model,
                    token,
                ),
                operation_lock=cached_entry.operation_lock if cached_entry is not None else None,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
            streaming_response._operation_lock = cached_entry.operation_lock if cached_entry is not None else None
        except Exception:
            if cached_entry is not None and lock_held:
                cached_entry.operation_lock.release()

            raise
        else:
            return streaming_response

    if cached_entry is not None:
        await cached_entry.operation_lock.acquire()

    try:
        await _run_sync_safely(partial(conversation.ask, query, files=files or None))
    finally:
        if cached_entry is not None:
            cached_entry.operation_lock.release()

    answer = conversation.answer or ""
    conv_uuid = conversation.uuid

    if conv_uuid:
        async with _conversation_cache.lock:
            _conversation_cache.set(token, conv_uuid, conversation, request.model)

    return JSONResponse(
        content=ChatCompletionResponse.build(
            model=request.model,
            content=answer,
            thread_uuid=conv_uuid,
        ).model_dump(exclude_none=True)
    )


def _validate_model(request: ChatCompletionRequest) -> None:
    """Validate the selected model and translate registry errors to HTTP errors."""
    try:
        ext = request.perplexity
        MODELS.resolve_for_use(
            request.model,
            allow_risky_model=ext.allow_risky_model if ext else False,
            custom_model_mode=ext.custom_model_mode if ext else "copilot",
        )
    except ValueError as exc:
        if request.model.startswith("custom:"):
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        available = ", ".join(f'"{m.id}"' for m in MODELS.list_all())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model {request.model!r}. Available: {available}",
        ) from exc


async def _stream_response(
    conversation: Conversation,
    model_id: str,
    token: str,
) -> AsyncGenerator[str, None]:
    """Yield SSE lines for a streaming chat completion.

    Args:
        conversation: Active streaming ``Conversation`` to iterate.
        model_id: Model identifier for response envelope.
        token: Session token for cache keying.
    """
    async for event in _stream_response_events(conversation, model_id, token):
        yield event


async def _stream_response_events(
    conversation: Conversation,
    model_id: str,
    token: str,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for one active conversation stream."""
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
        async for response in iterate_in_threadpool(iter(conversation)):
            response_chunks = getattr(response, "chunks", None)
            current = response.answer or ""

            if not current and isinstance(response_chunks, list):
                current = "".join(response_chunks)

            if not current:
                current = response.last_chunk or ""

            if current:
                common_len = _common_prefix_length(last_content, current)

                if common_len == len(last_content):
                    delta = current[common_len:]
                    last_content += delta
                elif common_len == len(current):
                    delta = ""
                else:
                    delta = current
                    last_content += delta

                if delta:
                    yield ChatCompletionChunk(
                        id=completion_id,
                        created=created,
                        model=model_id,
                        choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(content=delta))],
                    ).to_sse_line()
    except (ConnectionError, BrokenPipeError, OSError):
        logger.warning("Upstream completion stream ended before completion")
        yield (
            'event: error\ndata: {"error":{"message":"Upstream stream ended before completion",'
            '"type":"server_error","code":"upstream_incomplete"}}\n\n'
        )
        yield "data: [DONE]\n\n"
        return
    except Exception:
        logger.exception("Unexpected failure while streaming a completion")
        yield (
            'event: error\ndata: {"error":{"message":"Upstream completion failed",'
            '"type":"server_error","code":"upstream_error"}}\n\n'
        )
        yield "data: [DONE]\n\n"
        return
    conv_uuid = conversation.uuid

    if conv_uuid:
        async with _conversation_cache.lock:
            _conversation_cache.set(token, conv_uuid, conversation, model_id)

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
