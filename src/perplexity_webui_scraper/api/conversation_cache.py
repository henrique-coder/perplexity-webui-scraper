"""TTL-based conversation cache for the API server."""

from __future__ import annotations

from asyncio import Lock
from dataclasses import dataclass, field
from time import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from perplexity_webui_scraper.core.conversation import Conversation

_CONVERSATION_TTL_SECONDS: float = 30 * 60


@dataclass
class _CachedConversation:
    """A cached Conversation with TTL tracking."""

    conversation: Conversation
    model_id: str | None = None
    operation_lock: Lock = field(default_factory=Lock)
    last_access: float = field(default_factory=time)


class ConversationCache:
    """Async-safe TTL cache for Conversation objects.

    Conversations are keyed by ``(session_token, thread_uuid)`` tuples.
    Stale entries are evicted before each lookup or store.

    Args:
        ttl_seconds: Inactivity timeout in seconds (default: 30 min).
    """

    def __init__(self, ttl_seconds: float = _CONVERSATION_TTL_SECONDS) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], _CachedConversation] = {}
        self.lock: Lock = Lock()

    def get(self, token: str, thread_uuid: str) -> Conversation | None:
        """Look up a conversation.  Must be called while ``self.lock`` is held."""
        self._evict_stale()
        cached = self._store.get((token, thread_uuid))

        if cached is None:
            return None

        cached.last_access = time()

        return cached.conversation

    def get_entry(self, token: str, thread_uuid: str) -> _CachedConversation | None:
        """Look up a cached entry and refresh its TTL. Must hold ``self.lock``."""
        self._evict_stale()
        cached = self._store.get((token, thread_uuid))

        if cached is not None:
            cached.last_access = time()

        return cached

    def set(self, token: str, thread_uuid: str, conversation: Conversation, model_id: str | None = None) -> None:
        """Store or update a conversation.  Must be called while ``self.lock`` is held."""
        key = (token, thread_uuid)
        existing = self._store.get(key)

        if existing is not None:
            existing.conversation = conversation

            if model_id is not None:
                existing.model_id = model_id

            existing.last_access = time()
        else:
            self._store[key] = _CachedConversation(conversation=conversation, model_id=model_id)

        self._evict_stale()

    def remove(self, token: str, thread_uuid: str) -> None:
        """Remove one conversation entry. Must be called while ``self.lock`` is held."""
        self._store.pop((token, thread_uuid), None)

    def _evict_stale(self) -> None:
        """Remove all entries exceeding the TTL."""
        now = time()
        stale = [k for k, v in self._store.items() if now - v.last_access > self._ttl]

        for key in stale:
            del self._store[key]
