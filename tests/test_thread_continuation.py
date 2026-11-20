"""Offline tests for Chat Completions thread continuation and streaming."""

from __future__ import annotations

from asyncio import CancelledError, create_task, run, sleep
from contextlib import suppress
from typing import Any
from unittest.mock import MagicMock, patch

from orjson import loads
from pytest import fixture
from starlette.testclient import TestClient

from perplexity_webui_scraper._internal.constants import SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper.api.app import app
from perplexity_webui_scraper.api.conversation_cache import _CachedConversation
from perplexity_webui_scraper.api.routes.completions import (
    _client_pool,
    _conversation_cache,
    _LockReleasingStreamingResponse,
    _start_chat_stream,
    _stream_response,
)
from perplexity_webui_scraper.api.schemas.request import ChatCompletionRequest
from perplexity_webui_scraper.core import Conversation


_JWE = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
TOKEN = f"{SESSION_COOKIE_PREFIX}123e4567-e89b-42d3-a456-426614174000={_JWE}"
AUTH_HEADER = f"Bearer {TOKEN}"
THREAD_UUID = "synthetic-thread-uuid"
MODEL_ID = "test/custom-model"


class _Models:
    def resolve_for_use(self, item: str, **_kwargs: object) -> MagicMock:
        return MagicMock(id=item)

    def list_all(self) -> list[MagicMock]:
        return [MagicMock(id=MODEL_ID)]


def _conversation(uuid: str = THREAD_UUID) -> MagicMock:
    conversation = MagicMock(spec=Conversation)
    conversation.uuid = uuid
    conversation.answer = "Mock answer"
    conversation.ask = MagicMock()
    return conversation


@fixture(autouse=True)
def _clean_caches():
    _conversation_cache.clear()
    _client_pool.clear()
    with patch("perplexity_webui_scraper.api.routes.completions.MODELS", _Models()):
        yield
    _conversation_cache.clear()
    _client_pool.clear()


@fixture
def http_client():
    with TestClient(app) as test_client:
        yield test_client


def test_new_conversation_returns_thread_uuid(http_client: TestClient) -> None:
    conversation = _conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = http_client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": AUTH_HEADER},
        )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Mock answer"
    assert response.json()["perplexity"]["thread_uuid"] == THREAD_UUID


def test_followup_uses_only_latest_user_message(http_client: TestClient) -> None:
    conversation = _conversation()
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(conversation, model_id=MODEL_ID)
    response = http_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "user", "content": "First"},
                {"role": "assistant", "content": "Reply"},
                {"role": "user", "content": "Follow-up"},
            ],
            "perplexity": {"thread_uuid": THREAD_UUID},
        },
        headers={"Authorization": AUTH_HEADER},
    )
    assert response.status_code == 200
    conversation.ask.assert_called_once_with("Follow-up", files=None)
    assert response.json()["perplexity"]["thread_uuid"] == THREAD_UUID


def test_followup_rejects_model_change(http_client: TestClient) -> None:
    conversation = _conversation()
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(conversation, model_id="old-model")
    response = http_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "Continue"}],
            "perplexity": {"thread_uuid": THREAD_UUID},
        },
        headers={"Authorization": AUTH_HEADER},
    )
    assert response.status_code == 400
    conversation.ask.assert_not_called()


def test_followup_reuses_only_the_callers_cached_thread(http_client: TestClient) -> None:
    other_token = f"{SESSION_COOKIE_PREFIX}223e4567-e89b-42d3-a456-426614174000={_JWE}"
    conversation = _conversation()
    _conversation_cache._store[(other_token, THREAD_UUID)] = _CachedConversation(conversation, model_id=MODEL_ID)

    response = http_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "Continue"}],
            "perplexity": {"thread_uuid": THREAD_UUID},
        },
        headers={"Authorization": AUTH_HEADER},
    )

    assert response.status_code == 404
    conversation.ask.assert_not_called()


def test_followup_sends_base64_image_to_cached_conversation(http_client: TestClient) -> None:
    conversation = _conversation()
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(conversation, model_id=MODEL_ID)

    response = http_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,aW1hZ2U="}}],
                }
            ],
            "perplexity": {"thread_uuid": THREAD_UUID},
        },
        headers={"Authorization": AUTH_HEADER},
    )

    assert response.status_code == 200
    conversation.ask.assert_called_once_with("", files=[(b"image", "image.png", "image/png")])


def test_followup_rejects_remote_image_without_fetching(http_client: TestClient) -> None:
    conversation = _conversation()
    _conversation_cache._store[(TOKEN, THREAD_UUID)] = _CachedConversation(conversation, model_id=MODEL_ID)

    response = http_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "https://attacker.example/image.png"}}],
                }
            ],
            "perplexity": {"thread_uuid": THREAD_UUID},
        },
        headers={"Authorization": AUTH_HEADER},
    )

    assert response.status_code == 400
    conversation.ask.assert_not_called()


def test_unknown_thread_is_not_found_and_does_not_leak_identifier(http_client: TestClient) -> None:
    response = http_client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "Continue"}],
            "perplexity": {"thread_uuid": "private-thread-id"},
        },
        headers={"Authorization": AUTH_HEADER},
    )
    assert response.status_code == 404
    assert "not found or expired" in response.text
    assert "private-thread-id" not in response.text


def test_unstarted_stream_releases_cached_thread_lock() -> None:
    async def check_release() -> bool:
        entry = _CachedConversation(conversation=_conversation(), model_id=MODEL_ID)
        await entry.operation_lock.acquire()
        response = _LockReleasingStreamingResponse(_empty_stream(), operation_lock=entry.operation_lock)

        async def send(_message: Any) -> None:
            raise RuntimeError("disconnect")

        with suppress(RuntimeError):
            await response(scope={"type": "http", "asgi": {"spec_version": "2.4"}}, receive=MagicMock(), send=send)
        return not entry.operation_lock.locked()

    assert run(check_release())


def test_stream_failure_emits_safe_error_without_successful_stop() -> None:
    conversation = _conversation()
    conversation.__iter__.side_effect = RuntimeError("private upstream detail")
    events = run(_collect_events(_stream_response(conversation, MODEL_ID, TOKEN)))
    assert any(event.startswith("event: error") for event in events)
    assert "upstream_error" in "".join(events)
    assert all("private upstream detail" not in event for event in events)
    assert not any('"finish_reason":"stop"' in event for event in events)


def test_streaming_returns_thread_uuid_in_terminal_chunk(http_client: TestClient) -> None:
    conversation = _conversation()
    snapshot = MagicMock(last_chunk="Streamed answer", answer="Streamed answer", chunks=["Streamed answer"])
    conversation.__iter__ = MagicMock(return_value=iter([snapshot]))
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = http_client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}], "stream": True},
            headers={"Authorization": AUTH_HEADER},
        )
    chunks = [loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: {")]
    terminal = next(chunk for chunk in chunks if chunk["choices"][0].get("finish_reason") == "stop")
    assert terminal["perplexity"]["thread_uuid"] == THREAD_UUID


def test_client_pool_defers_closing_until_cached_conversation_evicts(http_client: TestClient) -> None:
    second_token = f"{SESSION_COOKIE_PREFIX}123e4567-e89b-42d3-a456-426614174001={_JWE}"
    first_conversation = _conversation()
    second_conversation = _conversation()
    first_client = MagicMock()
    first_client.create_conversation.return_value = first_conversation
    second_client = MagicMock()
    second_client.create_conversation.return_value = second_conversation

    with (
        patch("perplexity_webui_scraper.api.auth.Perplexity", side_effect=[first_client, second_client]),
        patch.object(_client_pool, "_max_clients", 1),
    ):
        first_response = http_client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Start"}]},
            headers={"Authorization": AUTH_HEADER},
        )
        assert first_response.status_code == 200

        second_response = http_client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Other"}]},
            headers={"Authorization": f"Bearer {second_token}"},
        )
        assert second_response.status_code == 200
        first_client.close.assert_not_called()

        continued = http_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "Continue"}],
                "perplexity": {"thread_uuid": THREAD_UUID},
            },
            headers={"Authorization": AUTH_HEADER},
        )
        assert continued.status_code == 200
        first_client.close.assert_not_called()

        _conversation_cache.remove(TOKEN, THREAD_UUID)
        first_client.close.assert_called_once()


def test_cancelled_stream_wait_releases_client_lease_without_unlocking_lock() -> None:
    second_token = f"{SESSION_COOKIE_PREFIX}123e4567-e89b-42d3-a456-426614174001={_JWE}"
    conversation = _conversation()
    first_client = MagicMock()
    second_client = MagicMock()

    async def exercise_cancellation() -> None:
        with (
            patch("perplexity_webui_scraper.api.auth.Perplexity", side_effect=[first_client, second_client]),
            patch.object(_client_pool, "_max_clients", 1),
        ):
            pooled_client = _client_pool.get_or_create(TOKEN)
            _conversation_cache.set(TOKEN, THREAD_UUID, conversation, MODEL_ID, client=pooled_client)
            entry = _conversation_cache.get_entry(TOKEN, THREAD_UUID)
            assert entry is not None
            _client_pool.get_or_create(second_token)
            first_client.close.assert_not_called()

            await entry.operation_lock.acquire()
            _client_pool.acquire(pooled_client)
            request = ChatCompletionRequest(
                model=MODEL_ID,
                messages=[{"role": "user", "content": "Continue"}],
                stream=True,
            )
            task = create_task(_start_chat_stream(conversation, entry, pooled_client, request, TOKEN, "Continue", []))
            await sleep(0)

            task.cancel()
            with suppress(CancelledError):
                await task

            assert entry.operation_lock.locked()
            entry.operation_lock.release()
            first_client.close.assert_not_called()

            _conversation_cache.remove(TOKEN, THREAD_UUID)
            first_client.close.assert_called_once()

    run(exercise_cancellation())


async def _empty_stream() -> Any:
    if False:
        yield ""


async def _collect_events(stream: Any) -> list[str]:
    return [event async for event in stream]
