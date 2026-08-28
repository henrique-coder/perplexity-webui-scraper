from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from niquests import Session
from pytest import fixture, warns

from perplexity_webui_scraper._internal.exceptions import FileAccessError, ModelAccessError, ModelRiskWarning
from perplexity_webui_scraper.api.app import app
from perplexity_webui_scraper.core import Conversation
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from collections.abc import Generator


# Constants
TOKEN = "test-session-token"
AUTH_HEADER = f"Bearer {TOKEN}"
MODEL_ID = "openai/gpt-5.6-terra"


class _MockModelRegistry:
    def resolve(self, item: str) -> MagicMock:
        if item == "non-existent-model":
            raise ValueError

        return MagicMock(id=MODEL_ID)

    def list_all(self) -> list[MagicMock]:
        return [MagicMock(id=MODEL_ID)]

    def resolve_for_use(self, item: str, **_kwargs: object) -> MagicMock:
        return self.resolve(item)


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
    with patch("perplexity_webui_scraper.api.routes.completions.MODELS", _mock_models):
        yield


@fixture
def client() -> Generator[Session, None, None]:
    with Session(app=app) as session:
        yield session


def test_missing_auth_header(client: Session) -> None:
    """Request without Authorization header should return 401."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json()["error"]["message"]


def test_api_does_not_allow_cross_origin_requests(client: Session) -> None:
    """Requests from arbitrary browser origins must not receive CORS permission."""
    response = client.get("/v1/models", headers={"Origin": "https://attacker.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_malformed_auth_header(client: Session) -> None:
    """Request with malformed Authorization header (not Bearer) should return 401."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": "Basic token123"},
    )
    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json()["error"]["message"]


def test_invalid_model(client: Session) -> None:
    """Request with an unregistered model should return 400 Bad Request."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "non-existent-model", "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": AUTH_HEADER},
    )
    assert response.status_code == 400
    assert "Unknown model" in response.json()["error"]["message"]


def test_invalid_custom_model_exposes_validation_error(client: Session) -> None:
    """Invalid custom identifiers should not be reported as unknown catalog models."""
    with patch("perplexity_webui_scraper.api.routes.completions.MODELS", MODELS):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "custom:",
                "messages": [{"role": "user", "content": "Hello"}],
                "perplexity": {"allow_risky_model": True},
            },
            headers={"Authorization": AUTH_HEADER},
        )

    message = response.json()["error"]["message"]
    assert response.status_code == 400
    assert "Custom model identifiers must contain" in message
    assert "Available:" not in message


def test_model_catalog_exposes_risk_metadata(client: Session) -> None:
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()["data"]
    expected = {model.id: model for model in MODELS.list_all()}
    assert {item["id"] for item in data} == set(expected)

    for item in data:
        model = expected[item["id"]]
        metadata = item["perplexity"]
        assert item["owned_by"] == model.provider
        assert metadata["min_tier"] == model.min_tier
        assert metadata["is_official"] == model.is_official
        assert metadata["status"] == model.status
        expected_tested_at = model.last_tested_at.isoformat().replace("+00:00", "Z") if model.last_tested_at else None
        assert metadata["last_tested_at"] == expected_tested_at


def test_risky_model_api_requires_and_accepts_acknowledgement(client: Session) -> None:
    risky_model_id = next(model.id for model in MODELS.list_all() if model.status != "available")

    with patch("perplexity_webui_scraper.api.routes.completions.MODELS", MODELS):
        denied = client.post(
            "/v1/chat/completions",
            json={"model": risky_model_id, "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": AUTH_HEADER},
        )

    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "model_status_confirmation_required"

    mock_client_instance = MagicMock()
    mock_client_instance.create_conversation.return_value = _make_mock_conversation()
    with (
        patch("perplexity_webui_scraper.api.routes.completions.MODELS", MODELS),
        patch(
            "perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create",
            return_value=mock_client_instance,
        ),
        warns(ModelRiskWarning),
    ):
        allowed = client.post(
            "/v1/chat/completions",
            json={
                "model": risky_model_id,
                "messages": [{"role": "user", "content": "Hello"}],
                "perplexity": {"allow_risky_model": True},
            },
            headers={"Authorization": AUTH_HEADER},
        )

    assert allowed.status_code == 200


@patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create")
def test_model_access_error_returns_403(mock_get_or_create: MagicMock, client: Session) -> None:
    """Model tier failures should return an OpenAI-compatible 403 error."""
    mock_client_instance = MagicMock()
    mock_conv = _make_mock_conversation()
    mock_conv.ask.side_effect = ModelAccessError("anthropic/claude-opus-4.8", "max", "pro")
    mock_client_instance.create_conversation.return_value = mock_conv
    mock_get_or_create.return_value = mock_client_instance

    response = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": AUTH_HEADER},
    )

    body = response.json()

    assert response.status_code == 403
    assert body["error"]["code"] == "model_access_denied"
    assert "requires a max account" in body["error"]["message"]


@patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create")
def test_file_access_error_returns_403(mock_get_or_create: MagicMock, client: Session) -> None:
    """Free-tier file failures should return an OpenAI-compatible 403 error."""
    mock_client_instance = MagicMock()
    mock_conv = _make_mock_conversation()
    mock_conv.ask.side_effect = FileAccessError("free")
    mock_client_instance.create_conversation.return_value = mock_conv
    mock_get_or_create.return_value = mock_client_instance

    response = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": AUTH_HEADER},
    )

    body = response.json()

    assert response.status_code == 403
    assert body["error"]["code"] == "file_access_denied"
    assert "File attachments require a paid Perplexity account" in body["error"]["message"]


@patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create")
def test_perplexity_extensions_are_parsed(mock_get_or_create: MagicMock, client: Session) -> None:
    """Verify that Perplexity extensions are parsed into the config."""
    mock_client_instance = MagicMock()
    mock_conv = _make_mock_conversation()
    mock_client_instance.create_conversation.return_value = mock_conv
    mock_get_or_create.return_value = mock_client_instance

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


@patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create")
def test_system_prompt_concatenation(mock_get_or_create: MagicMock, client: Session) -> None:
    """Verify that a 'system' message is prepended to the final query string sent to Perplexity."""
    mock_client_instance = MagicMock()
    mock_conv = _make_mock_conversation()
    mock_client_instance.create_conversation.return_value = mock_conv
    mock_get_or_create.return_value = mock_client_instance

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
