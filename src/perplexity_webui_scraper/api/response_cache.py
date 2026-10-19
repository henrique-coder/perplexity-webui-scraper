"""Short-lived mapping between public Responses IDs and Perplexity threads."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from time import monotonic


class ResponseThreadCache:
    """Bounded TTL map used to implement ``previous_response_id`` locally."""

    def __init__(self, max_entries: int = 4096, ttl_seconds: float = 30 * 60) -> None:
        if max_entries < 1 or ttl_seconds <= 0:
            raise ValueError("Response cache limits must be positive")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[tuple[str, str], tuple[str, float]] = OrderedDict()
        self._lock = Lock()

    def get(self, token: str, response_id: str) -> str | None:
        """Resolve a response ID to its originating Perplexity thread UUID."""
        with self._lock:
            now = monotonic()
            self._evict_expired(now)
            key = (token, response_id)
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries[key] = (entry[0], now)
            self._entries.move_to_end(key)
            return entry[0]

    def set(self, token: str, response_id: str, thread_uuid: str) -> None:
        """Cache a response/thread association without persisting credentials."""
        with self._lock:
            now = monotonic()
            self._evict_expired(now)
            key = (token, response_id)
            self._entries[key] = (thread_uuid, now)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def _evict_expired(self, now: float) -> None:
        stale = [
            key for key, (_thread_uuid, last_access) in self._entries.items() if now - last_access > self._ttl_seconds
        ]
        for key in stale:
            self._entries.pop(key, None)
