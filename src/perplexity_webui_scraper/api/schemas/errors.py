"""OpenAI-compatible error response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Inner error payload matching the OpenAI error schema.

    Attributes:
        message: Human-readable error description.
        type: Error category string (e.g. ``"invalid_request_error"``).
        code: Optional machine-readable error code (e.g. HTTP status as a string).
    """

    message: str
    type: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI-compatible error envelope.

    Attributes:
        error: The wrapped :class:`ErrorDetail` payload.
    """

    error: ErrorDetail
