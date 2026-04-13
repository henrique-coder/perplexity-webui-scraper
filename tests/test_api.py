from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pytest import fixture

from perplexity_webui_scraper.api.server import app
from perplexity_webui_scraper.core import Conversation


# Constants
TOKEN = "test-session-token"
AUTH_HEADER = f"Bearer {TOKEN}"
MODEL_ID = "gpt-5.4"


class _MockModelRegistry:
    def __contains__(self, item: object) -> bool:
        return True

    def __iter__(self):
        yield MODEL_ID


_mock_models = _MockModelRegistry()


def _make_mock_conversation() -> MagicMock:
    conv = MagicMock(spec=Conversation)
    conv.uuid = "fake-uuid-1234"
    conv.answer = "Mock answer"

    def ask_side_effect(query: str, files: list | None = None, stream: bool = False) -> None:
        conv.answer = f"Response to: {query}"

    conv.ask = MagicMock(side_effect=ask_side_effect)
    return conv


@fixture(autouse=True)
def _patch_models():
    """Bypass model validation so we can focus on API logic."""

    with patch("perplexity_webui_scraper.api.server.MODELS", _mock_models):
        yield


@fixture
def client() -> TestClient:
    return TestClient(app)


def test_missing_auth_header(client: TestClient) -> None:
    """Request without Authorization header should return 401."""

    response = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json()["error"]["message"]


def test_malformed_auth_header(client: TestClient) -> None:
    """Request with malformed Authorization header (not Bearer) should return 401."""

    response = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": "Basic token123"},
    )
    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json()["error"]["message"]


def test_invalid_model(client: TestClient) -> None:
    """Request with an unregistered model should return 400 Bad Request."""

    # We temporarily disable our mock registry to let the real one fail
    with patch("perplexity_webui_scraper.api.server.MODELS", {}):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "non-existent-model", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": AUTH_HEADER},
        )
        assert response.status_code == 400
        assert "Unknown model" in response.json()["error"]["message"]


@patch("perplexity_webui_scraper.api.server._get_client")
def test_perplexity_extensions_are_parsed(mock_get_client: MagicMock, client: TestClient) -> None:
    """Verify that Perplexity extensions are parsed into the config."""

    mock_client_instance = MagicMock()
    mock_conv = _make_mock_conversation()
    mock_client_instance.create_conversation.return_value = mock_conv
    mock_get_client.return_value = mock_client_instance

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "Tell me about quantum physics"}],
            "perplexity": {
                "search_focus": "writing",
                "citation_mode": "markdown",
                "time_range": "week",
            },
        },
        headers={"Authorization": AUTH_HEADER},
    )

    assert response.status_code == 200

    # Ensure create_conversation was called
    mock_client_instance.create_conversation.assert_called_once()

    # Check that the ConversationConfig was built with the parsed extensions
    config_arg = mock_client_instance.create_conversation.call_args[0][0]

    assert config_arg.search_focus == "writing"
    assert config_arg.citation_mode == "markdown"
    assert config_arg.time_range == "week"


@patch("perplexity_webui_scraper.api.server._get_client")
def test_system_prompt_concatenation(mock_get_client: MagicMock, client: TestClient) -> None:
    """Verify that a 'system' message is prepended to the final query string sent to Perplexity."""

    mock_client_instance = MagicMock()
    mock_conv = _make_mock_conversation()
    mock_client_instance.create_conversation.return_value = mock_conv
    mock_get_client.return_value = mock_client_instance

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": "You are a helpful physics teacher."},
                {"role": "user", "content": "Explain gravity."},
            ],
        },
        headers={"Authorization": AUTH_HEADER},
    )

    assert response.status_code == 200

    # Check what was passed to ask()
    mock_conv.ask.assert_called_once()
    actual_query = mock_conv.ask.call_args[0][0]

    # The system prompt should be embedded in the query string
    assert "You are a helpful physics teacher." in actual_query
    assert "Explain gravity." in actual_query
    assert "[System]:" in actual_query
