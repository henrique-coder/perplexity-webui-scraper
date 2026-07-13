"""Tests for the thread continuation feature in the OpenAI-compatible REST API.

These tests mock the Perplexity core library so they run without a real
session token or network access.
"""

from __future__ import annotations

from time import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from orjson import loads
from pytest import fixture

from perplexity_webui_scraper.api.app import app
from perplexity_webui_scraper.api.conversation_cache import _CachedConversation
from perplexity_webui_scraper.api.routes.completions import _client_pool, _conversation_cache
from perplexity_webui_scraper.core import Conversation


# Constants

TOKEN = "test-session-token"
AUTH_HEADER = f"Bearer {TOKEN}"
THREAD_UUID = "test-thread-uuid-1234"
MODEL_ID = "openai/gpt-5.6-terra"


# Model validation mock
# The existing MODELS registry uses Pydantic iteration which yields
# (field_name, Model) tuples, making model ID membership checks always False.
# We mock the ``resolve`` method and bypass the ``in`` check so tests can
# focus on the thread continuation logic.


class _MockModelRegistry:
    """Minimal stand-in for ModelRegistry that accepts any model ID."""

    def resolve(self, item: str) -> MagicMock:
        return MagicMock(id=MODEL_ID)

    def list_all(self) -> list[MagicMock]:
        return [MagicMock(id=MODEL_ID)]

    def resolve_for_use(self, item: str, **_kwargs: object) -> MagicMock:
        return self.resolve(item)


_mock_models = _MockModelRegistry()


# Helpers


def _make_mock_conversation(uuid: str = THREAD_UUID, answer: str = "Mock answer") -> MagicMock:
    """Create a mock ``Conversation`` that behaves enough for the API layer.

    Uses ``spec=Conversation`` so ``isinstance()`` checks pass in the
    streaming code path.
    """
    conv = MagicMock(spec=Conversation)
    conv.uuid = uuid
    conv.answer = answer

    def ask_side_effect(query: str, files: list | None = None, stream: bool = False) -> None:
        conv.answer = f"Response to: {query}"

    conv.ask = MagicMock(side_effect=ask_side_effect)

    return conv


def _make_mock_client(conv: MagicMock | None = None) -> MagicMock:
    """Create a mock ``Perplexity`` client."""
    client = MagicMock()

    if conv is None:
        conv = _make_mock_conversation()

    client.create_conversation = MagicMock(return_value=conv)
    return client


# Fixtures


@fixture(autouse=True)
def _clean_caches():
    """Clear all caches and patch MODELS before each test."""
    _conversation_cache._store.clear()
    _client_pool._clients.clear()

    with patch("perplexity_webui_scraper.api.routes.completions.MODELS", _mock_models):
        yield

    _conversation_cache._store.clear()
    _client_pool._clients.clear()


@fixture
def http_client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)


# Test 1: New conversation — no thread_uuid


def test_new_conversation_returns_thread_uuid(http_client: TestClient) -> None:
    """A request without thread_uuid should create a new conversation and return perplexity.thread_uuid."""
    mock_conv = _make_mock_conversation()
    mock_client = _make_mock_client(mock_conv)

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "perplexity" in data
    assert "thread_uuid" in data["perplexity"]
    assert data["perplexity"]["thread_uuid"] == THREAD_UUID


# Test 2: Follow-up with thread_uuid


def test_followup_with_thread_uuid(http_client: TestClient) -> None:
    """A request with a valid cached thread_uuid should continue using only the last message."""
    mock_conv = _make_mock_conversation()
    mock_client = _make_mock_client(mock_conv)

    # Pre-populate the cache
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(conversation=mock_conv)

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "First reply"},
                    {"role": "user", "content": "Follow-up question"},
                ],
                "perplexity": {"thread_uuid": THREAD_UUID},
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 200

    data = resp.json()

    # Should have called .ask() with only the last user message
    mock_conv.ask.assert_called_once()
    call_args = mock_conv.ask.call_args

    assert call_args[0][0] == "Follow-up question"

    # Response should include the thread_uuid
    assert data["perplexity"]["thread_uuid"] == THREAD_UUID

    # Should NOT have created a new conversation
    mock_client.create_conversation.assert_not_called()


# Test 3: Non-existent thread_uuid returns 404


def test_invalid_thread_uuid_returns_404(http_client: TestClient) -> None:
    """A request with an uncached thread_uuid should return a 404 error with a clear message."""
    mock_client = _make_mock_client()

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Hello"}],
                "perplexity": {"thread_uuid": "nonexistent-uuid"},
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 404
    assert "not found or expired" in resp.json()["error"]["message"]


# Test 4: Streaming with thread_uuid


def test_streaming_new_conversation_includes_thread_uuid(http_client: TestClient) -> None:
    """A streaming request without thread_uuid should include it in the final chunk."""
    mock_conv = _make_mock_conversation()
    mock_client = _make_mock_client(mock_conv)

    # Make the conversation iterable for streaming (yields one response)
    mock_response = MagicMock()
    mock_response.last_chunk = "Streamed answer"
    mock_response.answer = "Streamed answer"
    mock_conv.__iter__ = MagicMock(return_value=iter([mock_response]))

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 200

    # Parse SSE lines to find the final chunk with finish_reason
    lines = resp.text.strip().split("\n")
    final_chunk = None

    for raw_line in lines:
        line = raw_line.strip()

        if line.startswith("data: ") and line != "data: [DONE]":
            chunk = loads(line[6:])

            if chunk.get("choices", [{}])[0].get("finish_reason") == "stop":
                final_chunk = chunk

    # The final chunk should have perplexity.thread_uuid
    assert final_chunk is not None, "No final chunk with finish_reason='stop' found"
    assert "perplexity" in final_chunk
    assert final_chunk["perplexity"]["thread_uuid"] == THREAD_UUID


# Test 5: space_uuid and thread_uuid together


def test_space_uuid_and_thread_uuid_together(http_client: TestClient) -> None:
    """Passing both space_uuid and thread_uuid should not conflict."""
    mock_conv = _make_mock_conversation()
    mock_client = _make_mock_client(mock_conv)

    # Pre-populate the cache
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(conversation=mock_conv)

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Question in space"}],
                "perplexity": {
                    "thread_uuid": THREAD_UUID,
                    "space_uuid": "some-space-uuid",
                },
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 200

    data = resp.json()

    assert data["perplexity"]["thread_uuid"] == THREAD_UUID

    # Should have used the cached conversation, not created a new one
    mock_client.create_conversation.assert_not_called()


# Test 6: TTL eviction


def test_expired_conversation_is_evicted(http_client: TestClient) -> None:
    """A conversation that has exceeded the TTL should be evicted and return a 404."""
    mock_conv = _make_mock_conversation()
    mock_client = _make_mock_client(mock_conv)

    # Pre-populate with an expired entry (last_access 31 minutes ago)
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(
        conversation=mock_conv,
        last_access=time() - (31 * 60),
    )

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Hello"}],
                "perplexity": {"thread_uuid": THREAD_UUID},
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 404
    assert "not found or expired" in resp.json()["error"]["message"]


# Test 7: Backward compatibility — no perplexity block at all


def test_no_perplexity_block_works_as_before(http_client: TestClient) -> None:
    """A request with no perplexity block should work identically to the original behavior."""
    mock_conv = _make_mock_conversation()
    mock_client = _make_mock_client(mock_conv)

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=mock_client):
        resp = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert resp.status_code == 200

    data = resp.json()

    # Should still include thread_uuid in response for future continuation
    assert "perplexity" in data
    assert "thread_uuid" in data["perplexity"]

    # Should have created a new conversation
    mock_client.create_conversation.assert_called_once()
