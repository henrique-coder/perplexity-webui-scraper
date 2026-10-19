"""Integration tests for the Responses API route and shared conversation core."""

from __future__ import annotations

from asyncio import run
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from orjson import loads
from pytest import fixture
from starlette.testclient import TestClient

from perplexity_webui_scraper.api.app import app
from perplexity_webui_scraper.api.conversation_cache import _CachedConversation
from perplexity_webui_scraper.api.responses_stream import chat_stream_to_responses
from perplexity_webui_scraper.api.routes.completions import _client_pool, _conversation_cache, _response_thread_cache
from perplexity_webui_scraper.core import Conversation


if TYPE_CHECKING:
    from collections.abc import Generator


MODEL = "perplexity/best"
TOKEN = "test-upstream-token"


@fixture(autouse=True)
def _clean_state():
    _conversation_cache._store.clear()
    _client_pool._clients.clear()
    _response_thread_cache._entries.clear()
    yield
    _conversation_cache._store.clear()
    _client_pool._clients.clear()
    _response_thread_cache._entries.clear()


@fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def _conversation() -> MagicMock:
    conversation = MagicMock(spec=Conversation)
    conversation.uuid = "thread-id"
    conversation.answer = "Perplexity answer"
    conversation.ask = MagicMock()
    return conversation


def test_responses_non_stream_uses_shared_conversation_core(client: TestClient) -> None:
    conversation = _conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Hello"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["output_text"] == "Perplexity answer"
    assert body["output"][0]["content"][0]["text"] == "Perplexity answer"
    assert body["id"].startswith("resp_")
    assert _response_thread_cache.get(TOKEN, body["id"]) == "thread-id"
    conversation.ask.assert_called_once_with("Hello", files=None)
    assert "test-upstream-token" not in str(response.text)


def test_responses_previous_response_id_continues_thread(client: TestClient) -> None:
    conversation = _conversation()
    _conversation_cache._store[(TOKEN, "thread-id")] = _CachedConversation(conversation=conversation, model_id=MODEL)
    _response_thread_cache.set(TOKEN, "resp_previous", "thread-id")
    response = client.post(
        "/v1/responses",
        json={"model": MODEL, "input": "Follow up", "previous_response_id": "resp_previous"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.json()["previous_response_id"] == "resp_previous"
    conversation.ask.assert_called_once_with("Follow up", files=None)


def test_responses_rejects_unsupported_input_item(client: TestClient) -> None:
    response = client.post(
        "/v1/responses",
        json={"model": MODEL, "input": [{"type": "function_call", "name": "tool"}]},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 422


def test_responses_rejects_unimplemented_tools(client: TestClient) -> None:
    upstream = MagicMock()
    upstream.create_conversation.return_value = _conversation()
    with patch(
        "perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream
    ) as get_client:
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Use the tool", "tools": [{"type": "function", "name": "lookup"}]},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 422
    get_client.assert_not_called()


def test_responses_requires_auth_when_no_server_default(client: TestClient) -> None:
    response = client.post("/v1/responses", json={"model": MODEL, "input": "Hello"})
    assert response.status_code == 401


def test_responses_stream_emits_responses_protocol_events(client: TestClient) -> None:
    conversation = _conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    snapshots = [
        MagicMock(answer=None, last_chunk="The ", chunks=["The "]),
        MagicMock(answer=None, last_chunk="answer", chunks=["The ", "answer"]),
        MagicMock(answer="The answer", last_chunk="answer", chunks=["The ", "answer"]),
    ]
    conversation.__iter__.return_value = iter(snapshots)
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Hello", "stream": True},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 200
    assert "event: response.created" in str(response.text)
    assert "event: response.output_text.delta" in str(response.text)
    assert "event: response.content_part.added" in str(response.text)
    assert "event: response.content_part.done" in str(response.text)
    assert "event: response.completed" in str(response.text)
    text_deltas = [
        loads(line[6:])["delta"]
        for line in str(response.text).splitlines()
        if line.startswith("data: ") and '"type":"response.output_text.delta"' in line
    ]
    assert "".join(text_deltas) == "The answer"


def test_responses_stream_does_not_delay_until_final_snapshot(client: TestClient) -> None:
    conversation = _conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    snapshots = [
        MagicMock(answer=None, last_chunk="The ", chunks=["The "]),
        MagicMock(answer=None, last_chunk="answer", chunks=["The ", "answer"]),
        MagicMock(answer="The answer", last_chunk="answer", chunks=["The ", "answer"]),
    ]
    conversation.__iter__.return_value = iter(snapshots)
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Hello", "stream": True},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 200
    assert "response.output_text.delta" in str(response.text)


def test_responses_stream_translates_upstream_errors() -> None:
    async def frames():
        yield 'event: error\ndata: {"error":{"message":"Upstream completion failed","code":"upstream_error"}}\n\n'

    events = list(run(_collect(chat_stream_to_responses(frames(), MODEL))))
    assert any("response.failed" in event for event in events)
    assert all("response.completed" not in event for event in events)


def test_responses_stream_reports_failure_after_silent_upstream_disconnect() -> None:
    async def frames():
        yield 'data: {"choices":[{"delta":{"content":"partial answer"}}]}\n\n'

    events = run(_collect(chat_stream_to_responses(frames(), MODEL)))

    assert any("response.output_text.delta" in event for event in events)
    assert any("response.failed" in event for event in events)
    assert all("response.completed" not in event for event in events)


def test_responses_stream_ignores_malformed_event_payloads() -> None:
    async def frames():
        yield "data: not-json\n\n"
        yield 'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'

    events = run(_collect(chat_stream_to_responses(frames(), MODEL)))

    assert any('"delta":"ok"' in event for event in events)
    assert any("response.completed" in event for event in events)


def test_chat_completion_stream_reports_upstream_disconnect_as_error(client: TestClient) -> None:
    conversation = _conversation()
    conversation.__iter__.side_effect = ConnectionError("upstream disconnected")
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": [{"role": "user", "content": "Hello"}], "stream": True},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    assert '"code":"upstream_incomplete"' in str(response.text)
    assert 'finish_reason":"stop' not in str(response.text)


def test_responses_stream_reports_upstream_disconnect_as_failure(client: TestClient) -> None:
    conversation = _conversation()
    conversation.__iter__.side_effect = ConnectionError("upstream disconnected")
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Hello", "stream": True},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    assert "event: response.failed" in str(response.text)
    assert "event: response.completed" not in str(response.text)


async def _collect(events: Any) -> list[str]:
    return [event async for event in events]


def test_responses_stream_reports_failure_if_chat_stream_ends_without_finish_chunk() -> None:
    async def frames():
        yield 'data: {"choices":[{"delta":{"content":"partial answer"}}]}\n\n'
        yield "data: [DONE]\n\n"

    events = run(_collect(chat_stream_to_responses(frames(), MODEL)))

    assert any("response.output_text.delta" in event for event in events)
    assert any("response.failed" in event for event in events)
    assert all("response.completed" not in event for event in events)


def test_responses_rejects_remote_image_url_without_fetching(client: TestClient) -> None:
    response = client.post(
        "/v1/responses",
        json={
            "model": MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_image", "image_url": "https://example.invalid/image.png"}],
                }
            ],
        },
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 422


def test_responses_server_default_uses_gateway_key_without_leaking_upstream(client: TestClient) -> None:
    conversation = _conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    with (
        patch.dict(
            "os.environ",
            {"PERPLEXITY_SESSION_TOKEN": "upstream-secret", "PERPLEXITY_API_KEY": "gateway-secret"},
            clear=True,
        ),
        patch(
            "perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream
        ) as get_client,
    ):
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Hello"},
            headers={"X-API-Key": "gateway-secret"},
        )
    assert response.status_code == 200
    get_client.assert_called_once_with("upstream-secret")
    assert "upstream-secret" not in str(response.text)


def test_responses_rejects_incorrect_gateway_key(client: TestClient) -> None:
    with patch.dict(
        "os.environ",
        {"PERPLEXITY_SESSION_TOKEN": "upstream-secret", "PERPLEXITY_API_KEY": "gateway-secret"},
        clear=True,
    ):
        response = client.post(
            "/v1/responses",
            json={"model": MODEL, "input": "Hello"},
            headers={"X-API-Key": "incorrect"},
        )
    assert response.status_code == 401
