"""Translate shared-core streaming chunks into Responses SSE events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from orjson import dumps, loads


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Iterator


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
    for sequence, event_type, fields in _initial_events(response_id, item_id, model):
        yield sse_data_event(event_type, sequence, **fields)
    async for event in _response_events(stream, response_id, item_id, model, previous_response_id, on_thread):
        yield event


async def _response_events(
    stream: Any,
    response_id: str,
    item_id: str,
    model: str,
    previous_response_id: str | None,
    on_thread: Callable[[str, str], None] | None,
) -> AsyncGenerator[str, None]:
    """Process upstream frames and emit exactly one terminal response state."""
    event_sequence = 4
    text_parts: list[str] = []
    async for frame in stream:
        chunk, error = _decode_frame(frame)
        if error is not None:
            yield _response_failed(response_id, event_sequence, error)
            return
        if chunk is None:
            continue
        _update_thread_mapping(chunk, response_id, on_thread)
        deltas, finished = _collect_text_deltas(chunk, text_parts)
        for delta in deltas:
            event = _response_text_delta(item_id, event_sequence, delta)
            yield event
            event_sequence += 1
        if finished:
            completed = _response_completed(
                response_id, item_id, model, "".join(text_parts), event_sequence, previous_response_id
            )
            for event in completed:
                yield event
            yield "data: [DONE]\n\n"
            return
    yield _response_failed(response_id, event_sequence, _incomplete_error())


def _initial_events(response_id: str, item_id: str, model: str) -> Iterator[tuple[int, str, dict[str, Any]]]:
    """Build payloads for the initial Responses lifecycle events."""
    response = {"id": response_id, "object": "response", "status": "in_progress", "model": model}
    item = {"id": item_id, "type": "message", "role": "assistant", "status": "in_progress", "content": []}
    content_part = {"type": "output_text", "text": "", "annotations": []}
    yield 0, "response.created", {"response": response}
    yield 1, "response.in_progress", {"response": response}
    yield 2, "response.output_item.added", {"output_index": 0, "item": item}
    yield (
        3,
        "response.content_part.added",
        {
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "part": content_part,
        },
    )


def _decode_frame(frame: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Decode a data frame or return a structured terminal error."""
    if not isinstance(frame, str):
        return None, None
    event_type, data = _parse_frame(frame)
    if event_type == "error":
        return None, _decode_error(data)
    if event_type == "done":
        return None, _incomplete_error()
    if event_type != "data" or not data:
        return None, None
    try:
        chunk = loads(data)
    except ValueError:
        return None, None
    return (chunk, None) if isinstance(chunk, dict) else (None, None)


def _parse_frame(frame: str) -> tuple[str, str]:
    """Parse the event type and data payload from an SSE frame."""
    event_type = "data"
    data = ""
    for line in frame.splitlines():
        if line.startswith("event: "):
            event_type = line[7:].strip()
        elif line.startswith("data: "):
            data = line[6:].strip()
    if data == "[DONE]":
        return "done", data
    return event_type, data


def _update_thread_mapping(
    chunk: dict[str, Any],
    response_id: str,
    on_thread: Callable[[str, str], None] | None,
) -> None:
    """Store the response-to-thread mapping when an upstream chunk includes it."""
    thread_uuid = _extract_thread_uuid(chunk)
    if thread_uuid and on_thread is not None:
        on_thread(response_id, thread_uuid)


def _extract_thread_uuid(chunk: dict[str, Any]) -> str | None:
    """Read the optional thread identifier from an upstream chunk."""
    perplexity = chunk.get("perplexity")
    if isinstance(perplexity, dict):
        value = perplexity.get("thread_uuid")
        return value if isinstance(value, str) else None
    return None


def _decode_error(data: str) -> dict[str, Any]:
    """Decode the upstream error payload, falling back to a safe message."""
    try:
        error = loads(data) if data else {"message": "Upstream response failed"}
    except ValueError:
        return {"message": "Upstream response failed"}
    return error if isinstance(error, dict) else {"message": "Upstream response failed"}


def _incomplete_error() -> dict[str, str]:
    """Return the error payload used when the upstream stream ends early."""
    return {"message": "Upstream stream ended before a completion event", "code": "upstream_incomplete"}


def _collect_text_deltas(chunk: dict[str, Any], text_parts: list[str]) -> tuple[list[str], bool]:
    """Append content deltas and report whether a choice completed."""
    deltas: list[str] = []
    for choice in chunk.get("choices", []):
        delta = choice.get("delta", {}).get("content")
        if isinstance(delta, str) and delta:
            text_parts.append(delta)
            deltas.append(delta)
        if choice.get("finish_reason") == "stop":
            return deltas, True
    return deltas, False


def _response_failed(response_id: str, sequence: int, error: dict[str, Any]) -> str:
    """Serialize a failed Responses lifecycle event."""
    response = {"id": response_id, "object": "response", "status": "failed", "error": error}
    return sse_data_event("response.failed", sequence, response=response)


def _response_text_delta(item_id: str, sequence: int, delta: str) -> str:
    """Serialize one output-text delta event."""
    return sse_data_event(
        "response.output_text.delta",
        sequence,
        item_id=item_id,
        output_index=0,
        content_index=0,
        delta=delta,
    )


def _response_completed(
    response_id: str,
    item_id: str,
    model: str,
    text: str,
    sequence: int,
    previous_response_id: str | None,
) -> Iterator[str]:
    """Build terminal events for a completed Responses text output."""
    content_part = {"type": "output_text", "text": text, "annotations": []}
    item = {"id": item_id, "type": "message", "role": "assistant", "status": "completed", "content": [content_part]}
    yield sse_data_event(
        "response.output_text.done",
        sequence,
        item_id=item_id,
        output_index=0,
        content_index=0,
        text=text,
    )
    sequence += 1
    yield sse_data_event(
        "response.content_part.done",
        sequence,
        item_id=item_id,
        output_index=0,
        content_index=0,
        part=content_part,
    )
    sequence += 1
    yield sse_data_event("response.output_item.done", sequence, output_index=0, item=item)
    sequence += 1
    response = {
        "id": response_id,
        "object": "response",
        "status": "completed",
        "model": model,
        "output": [item],
        "output_text": text,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    if previous_response_id:
        response["previous_response_id"] = previous_response_id
    yield sse_data_event("response.completed", sequence, response=response)
