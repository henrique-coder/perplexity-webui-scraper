"""Minimal text-mode Responses API request and response schemas."""

from __future__ import annotations

from time import time
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResponsesRequest(BaseModel):
    """Request fields implemented by the local Responses API adapter."""

    model_config = ConfigDict(extra="forbid")

    model: str
    input: str | list[dict[str, Any]]
    instructions: str | None = None
    stream: bool = False
    previous_response_id: str | None = None
    perplexity: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_unimplemented_fields(cls, value: Any) -> Any:
        """Reject unsupported protocol options rather than silently ignoring them."""
        if isinstance(value, dict):
            unsupported = {"tools", "tool_choice", "background", "store", "truncation"} & value.keys()
            if unsupported:
                fields = ", ".join(sorted(unsupported))
                raise ValueError(f"Unsupported Responses API fields: {fields}")

        return value


class ResponsesAPIResponse(BaseModel):
    """Completed Responses API object with text output only."""

    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed"] = "completed"
    error: None = None
    incomplete_details: None = None
    model: str
    output: list[dict[str, Any]]
    output_text: str
    previous_response_id: str | None = None
    usage: dict[str, int] = Field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

    @classmethod
    def build(
        cls,
        model: str,
        content: str,
        response_id: str,
        previous_response_id: str | None,
    ) -> ResponsesAPIResponse:
        """Build completed response and a single assistant text item."""
        item_id = f"msg_{uuid4().hex}"
        output = [
            {
                "id": item_id,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": content, "annotations": []}],
            }
        ]
        return cls(
            id=response_id,
            created_at=int(time()),
            model=model,
            output=output,
            output_text=content,
            previous_response_id=previous_response_id,
        )
