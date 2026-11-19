"""Public data models for Perplexity responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


__all__ = ["ActivityEvent", "Response", "SearchResultItem"]


class SearchResultItem(BaseModel):
    """A web source cited in a Perplexity response."""

    model_config = ConfigDict(frozen=True)

    url: str | None = None
    title: str | None = None
    snippet: str | None = None


class ActivityEvent(BaseModel):
    """Public, allowlisted user-visible activity from a Perplexity response."""

    kind: Literal["search"]
    status: Literal["in_progress", "completed"]
    label: str
    queries: list[str] = Field(default_factory=list)
    results: list[SearchResultItem] = Field(default_factory=list)


class Response(BaseModel):
    """One streaming response snapshot yielded by ``Conversation.ask(stream=True)``."""

    answer: str | None = None
    chunks: list[str] = Field(default_factory=list)
    last_chunk: str | None = None
    search_results: list[SearchResultItem] = Field(default_factory=list)
    activity: list[ActivityEvent] = Field(default_factory=list)
    conversation_uuid: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
