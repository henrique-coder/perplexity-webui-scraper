"""Translate shared-core streaming chunks into Responses SSE events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from orjson import dumps, loads


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable


def sse_data_event(event_type: str, sequence_number: int, **fields: Any) -> str:
    """Serialize one Responses event frame."""
    payload = {"type": event_type, "sequence_number": sequence_number, **fields}
    return f"event: {event_type}\ndata: {dumps(payload).decode()}\n\n"


async def chat_stream_to_responses(
    stream: Any,
    model: str,
    previous_response_id: str | None = None,
    on_thread: Callable[[str, str], None] | None = None,
) -> AsyncGenerator[str, None]:
    """Adapt internal completion frames into text Responses events."""
    response_id = f"resp_{uuid4().hex}"
    item_id = f"msg_{uuid4().hex}"
    sequence = 0
    yield sse_data_event(
        "response.created",
        sequence,
        response={"id": response_id, "object": "response", "status": "in_progress", "model": model},
    )
    sequence += 1
    yield sse_data_event(
        "response.in_progress",
        sequence,
        response={"id": response_id, "object": "response", "status": "in_progress", "model": model},
    )
    sequence += 1
    yield sse_data_event(
        "response.output_item.added",
        sequence,
        output_index=0,
        item={"id": item_id, "type": "message", "role": "assistant", "status": "in_progress", "content": []},
    )
    sequence += 1
    content_part = {"type": "output_text", "text": "", "annotations": []}
    yield sse_data_event(
        "response.content_part.added",
        sequence,
        item_id=item_id,
        output_index=0,
        content_index=0,
        part=content_part,
    )
    sequence += 1
    text_parts: list[str] = []
    stream_finished = False
    async for frame in stream:
        if isinstance(frame, str) and frame.startswith("event: error\n"):
            error_data = next((line[6:] for line in frame.splitlines() if line.startswith("data: ")), "{}")
            try:
                error = loads(error_data)
            except Exception:
                error = {"message": "Upstream response failed"}
            yield sse_data_event(
                "response.failed",
                sequence,
                response={"id": response_id, "object": "response", "status": "failed", "error": error},
            )
            return
        if isinstance(frame, str) and frame.startswith("data: [DONE]"):
            yield sse_data_event(
                "response.failed",
                sequence,
                response={
                    "id": response_id,
                    "object": "response",
                    "status": "failed",
                    "error": {
                        "message": "Upstream stream ended before a completion event",
                        "code": "upstream_incomplete",
                    },
                },
            )
            return
        if not isinstance(frame, str) or not frame.startswith("data: "):
            continue
        data = frame[6:].strip()
        if data == "[DONE]":
            continue
        try:
            chunk = loads(data)
        except Exception:
            continue
        thread_uuid = chunk.get("perplexity", {}).get("thread_uuid")
        if thread_uuid and on_thread is not None:
            on_thread(response_id, thread_uuid)
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {}).get("content")
            if isinstance(delta, str) and delta:
                text_parts.append(delta)
                yield sse_data_event(
                    "response.output_text.delta",
                    sequence,
                    item_id=item_id,
                    output_index=0,
                    content_index=0,
                    delta=delta,
                )
                sequence += 1
            if choice.get("finish_reason") == "stop":
                stream_finished = True
                response_uuid = chunk.get("perplexity", {}).get("thread_uuid")
                if response_uuid and on_thread is not None:
                    on_thread(response_id, response_uuid)
                full_text = "".join(text_parts)
                yield sse_data_event(
                    "response.output_text.done",
                    sequence,
                    item_id=item_id,
                    output_index=0,
                    content_index=0,
                    text=full_text,
                )
                sequence += 1
                yield sse_data_event(
                    "response.content_part.done",
                    sequence,
                    item_id=item_id,
                    output_index=0,
                    content_index=0,
                    part={"type": "output_text", "text": full_text, "annotations": []},
                )
                sequence += 1
                item = {
                    "id": item_id,
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": full_text, "annotations": []}],
                }
                yield sse_data_event("response.output_item.done", sequence, output_index=0, item=item)
                sequence += 1
                response = {
                    "id": response_id,
                    "object": "response",
                    "status": "completed",
                    "model": model,
                    "output": [item],
                    "output_text": full_text,
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                }
                if previous_response_id:
                    response["previous_response_id"] = previous_response_id
                yield sse_data_event("response.completed", sequence, response=response)
                yield "data: [DONE]\n\n"
                return
    if not stream_finished:
        yield sse_data_event(
            "response.failed",
            sequence,
            response={
                "id": response_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "message": "Upstream stream ended before a completion event",
                    "code": "upstream_incomplete",
                },
            },
        )
        return

    full_text = "".join(text_parts)
    yield sse_data_event(
        "response.output_text.done", sequence, item_id=item_id, output_index=0, content_index=0, text=full_text
    )
    sequence += 1
    yield sse_data_event(
        "response.content_part.done",
        sequence,
        item_id=item_id,
        output_index=0,
        content_index=0,
        part={"type": "output_text", "text": full_text, "annotations": []},
    )
    sequence += 1
    item = {
        "id": item_id,
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": full_text, "annotations": []}],
    }
    yield sse_data_event("response.output_item.done", sequence, output_index=0, item=item)
    sequence += 1
    response = {
        "id": response_id,
        "object": "response",
        "status": "completed",
        "model": model,
        "output": [item],
        "output_text": full_text,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    if previous_response_id:
        response["previous_response_id"] = previous_response_id
    yield sse_data_event("response.completed", sequence, response=response)
    yield "data: [DONE]\n\n"
