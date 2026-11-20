"""TTL-based conversation cache for the API server."""

from __future__ import annotations

from asyncio import Lock
from dataclasses import dataclass, field
from time import time
from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper.auth.cookies import parse_session_credential, serialize_session_credential


if TYPE_CHECKING:
    from collections.abc import Callable

    from perplexity_webui_scraper.core.conversation import Conversation


_CONVERSATION_TTL_SECONDS: float = 30 * 60


@dataclass
class _CachedConversation:
    """A cached Conversation with TTL tracking."""

    conversation: Conversation
    model_id: str | None = None
    client: Any = None
    operation_lock: Lock = field(default_factory=Lock)
    last_access: float = field(default_factory=time)


class ConversationCache:
    """Async-safe TTL cache for Conversation objects.

    Conversations are keyed by ``(session_token, thread_uuid)`` tuples.
    Stale entries are evicted before each lookup or store.

    Args:
        ttl_seconds: Inactivity timeout in seconds (default: 30 min).
        on_acquire: Optional callback invoked when caching a conversation with an owner client.
        on_release: Optional callback invoked when a cached conversation is evicted or replaced.
    """

    def __init__(
        self,
        ttl_seconds: float = _CONVERSATION_TTL_SECONDS,
        *,
        on_acquire: Callable[[Any], None] | None = None,
        on_release: Callable[[Any], None] | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], _CachedConversation] = {}
        self._on_acquire = on_acquire
        self._on_release = on_release
        self.lock: Lock = Lock()

    def _acquire_client(self, client: Any) -> None:
        if client is not None and self._on_acquire is not None:
            self._on_acquire(client)

    def _release_client(self, client: Any) -> None:
        if client is not None and self._on_release is not None:
            self._on_release(client)

    def get(self, token: str, thread_uuid: str) -> Conversation | None:
        """Look up a conversation.  Must be called while ``self.lock`` is held."""
        canonical_token = serialize_session_credential(parse_session_credential(token))
        self._evict_stale()
        cached = self._store.get((canonical_token, thread_uuid))

        if cached is None:
            return None

        cached.last_access = time()

        return cached.conversation

    def get_entry(self, token: str, thread_uuid: str) -> _CachedConversation | None:
        """Look up a cached entry and refresh its TTL. Must hold ``self.lock``."""
        canonical_token = serialize_session_credential(parse_session_credential(token))
        self._evict_stale()
        cached = self._store.get((canonical_token, thread_uuid))

        if cached is not None:
            cached.last_access = time()

        return cached

    def set(
        self,
        token: str,
        thread_uuid: str,
        conversation: Conversation,
        model_id: str | None = None,
        client: Any = None,
    ) -> None:
        """Store or update a conversation.  Must be called while ``self.lock`` is held."""
        canonical_token = serialize_session_credential(parse_session_credential(token))
        key = (canonical_token, thread_uuid)
        existing = self._store.get(key)

        if existing is not None:
            existing.conversation = conversation

            if model_id is not None:
                existing.model_id = model_id

            if client is not None and existing.client is not client:
                self._acquire_client(client)
                previous_client = existing.client
                existing.client = client
                self._release_client(previous_client)

            existing.last_access = time()
        else:
            self._acquire_client(client)
            self._store[key] = _CachedConversation(conversation=conversation, model_id=model_id, client=client)

        self._evict_stale()

    def remove(self, token: str, thread_uuid: str) -> None:
        """Remove one conversation entry. Must be called while ``self.lock`` is held."""
        canonical_token = serialize_session_credential(parse_session_credential(token))
        removed = self._store.pop((canonical_token, thread_uuid), None)

        if removed is not None:
            self._release_client(removed.client)

    def clear(self) -> None:
        """Remove all cached conversations and release their client references."""
        for entry in list(self._store.values()):
            self._release_client(entry.client)

        self._store.clear()

    def _evict_stale(self) -> None:
        """Remove all entries exceeding the TTL."""
        now = time()
        stale = [k for k, v in self._store.items() if now - v.last_access > self._ttl]

        for key in stale:
            evicted = self._store.pop(key)
            self._release_client(evicted.client)
